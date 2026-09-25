"""Das Prognosemodell: zweistufiges Gradient Boosting (Standard) oder LR.

Beide Typen hinter EINER Schnittstelle, damit Training (train.py), Benchmark
(benchmark.py), Harness (harness.py) und Export (export.py) dasselbe Modell
meinen:

    modell = trainiere_modell(Xtr, ytr, datum_tr)   # typ aus config.MODELL_TYP
    p = modell.predict_proba(X)                     # (n, 3): sieg_a, gestellt, sieg_b

**Warum Gradient Boosting** (Merkmalsversion 3, Roadmap M1): mit denselben
16 Merkmalen Log-Loss Validierung 2025 0.7627 -> 0.7400, Test 2026
0.7400 -> 0.7207. Die LR überschätzte Aussenseiter (19.4 % vorhergesagt,
15.7 % eingetreten) und unterschätzte Favoriten; nichtlineare Zusatzmerkmale
holten davon nur 0.001 zurück. Der Gewinn liegt in Wechselwirkungen, die nur
ein nichtlineares Modell sieht.

**Warum zweistufig.** Ein Drei-Klassen-Boosting (Sieg A / Gestellt / Sieg B)
war minimal besser (0.7388 / 0.7206), lernte aber in dünn besetzten Ecken
Unsinn: bei 7-8 % der Paare mit Vorgeschichte SENKTE eine hohe Gestellt-
Bilanz die Gestellt-Chance (Orlik-Staudenmann, 5 von 6 Duellen gestellt:
-8.7 Punkte). Monotonie-Vorgaben kann sklearn nur für zwei Klassen, darum:

    Stufe 1  g = P(Gestellt)                    -- monoton laut MONOTON_GESTELLT
    Stufe 2  s = P(Sieg A | nicht gestellt)     -- monoton laut MONOTON_SIEG
    P = [(1 - g) * s,  g,  (1 - g) * (1 - s)]

Gemessen: 0 % solcher Fehlrichtungen, Log-Loss 0.7400 / 0.7207. Mehr
Vorgaben (Form, Kranz, Erfahrung) kosteten 0.005-0.007 -- Erfahrung wirkt
tatsächlich nicht monoton.

**Symmetrie.** "A gegen B" muss dasselbe ergeben wie "B gegen A", nur
gespiegelt. Die LR ist das durch die Spiegelzeilen im Training exakt, Bäume
nur ungefähr -- darum mittelt ``predict_proba`` über beide Richtungen: die
Gestellt-Stufe als (g(x) + g(x')) / 2, die Sieg-Stufe als
(s(x) + 1 - s(x')) / 2, mit x' = gespiegeltes x. Die App rechnet genauso
(web/lib/inference.ts). Gespiegelt wird je Merkmal: Differenzen wechseln das
Vorzeichen, symmetrische Merkmale bleiben (``SYMMETRISCH``).

**Baumzahl zeitlich gewählt.** Das eingebaute Early Stopping von sklearn
nimmt eine zufällige Stichprobe -- mit Spiegelzeilen und Gängen desselben
Fests auf beiden Seiten wäre das zu optimistisch. Hier: die jüngsten
``VALIDIERUNGSANTEIL`` der Trainingsdaten (nach Datum) bestimmen die Baumzahl
je Stufe, danach wird auf dem ganzen Training neu gefittet.
"""
from __future__ import annotations

import numpy as np

from .config import (
    GBM_LERNRATE,
    GBM_MAX_BAEUME,
    GBM_MAX_BLAETTER,
    GBM_MIN_BLATT_GESTELLT,
    GBM_MIN_BLATT_SIEG,
    MODELL_TYP,
    MONOTON_GESTELLT,
    MONOTON_SIEG,
    SEED,
    VALIDIERUNGSANTEIL,
)
from .features import FEATURE_NAMES

# Kennung in model.json -- App (inference.ts), paritaet.py und
# verify_inference verzweigen danach.
TYP_LR = "logistic_regression_multinomial"
TYP_GBM = "gradient_boosting_zweistufig"

# Merkmale, die beim Tausch von A und B GLEICH bleiben. Alle anderen sind
# Differenzen A - B und wechseln das Vorzeichen. Spiegelt SYMMETRISCH in
# web/lib/inference.ts (dort für die Erklärbalken).
SYMMETRISCH = frozenset({
    "rating_abstand", "same_teilverband", "schwung_overlap",
    "gestellt_neigung", "paar_gestellt", "spitzen_niveau",
})


def spiegel_vektor(n: int | None = None) -> np.ndarray:
    """+1 für symmetrische, -1 für Differenz-Merkmale (die ersten n Merkmale)."""
    namen = FEATURE_NAMES if n is None else FEATURE_NAMES[:n]
    return np.array([1.0 if name in SYMMETRISCH else -1.0 for name in namen])


def spiegle(X: np.ndarray) -> np.ndarray:
    """Merkmalsvektor(en) von "A gegen B" -> "B gegen A"."""
    X = np.asarray(X, dtype=float)
    return X * spiegel_vektor(X.shape[-1])


def _p1(sk, X: np.ndarray) -> np.ndarray:
    """P(Klasse 1) eines binären sklearn-Modells."""
    return sk.predict_proba(X)[:, 1]


def _gestellt(p_x: np.ndarray, p_gespiegelt: np.ndarray) -> np.ndarray:
    """Gestellt ist symmetrisch: Mittel beider Richtungen."""
    return (p_x + p_gespiegelt) / 2.0


def _sieg_a(p_x: np.ndarray, p_gespiegelt: np.ndarray) -> np.ndarray:
    """Sieg A gespiegelt ist Sieg B: Mittel aus s(x) und 1 - s(x')."""
    return (p_x + (1.0 - p_gespiegelt)) / 2.0


def kombiniere(g: np.ndarray, s: np.ndarray) -> np.ndarray:
    """(P(Gestellt), P(Sieg A | entschieden)) -> (n, 3) sieg_a, gestellt, sieg_b."""
    return np.column_stack([(1.0 - g) * s, g, (1.0 - g) * (1.0 - s)])


class Prognosemodell:
    """Trainiertes Modell samt allem, was Export und Inferenz brauchen.

    ``mu``/``sigma``: Mittel und Streuung der Trainingsmerkmale. Die LR
    rechnet standardisiert; beide Typen nutzen ``mu`` als "neutralen" Wert
    je Merkmal für die Erklärbalken (Gegenprobe, s. inference.ts).
    ``sk``: bei der LR das sklearn-Modell, beim Boosting ein dict
    {"gestellt": ..., "sieg": ...} mit den zwei binären Stufen.
    """

    def __init__(self, typ: str, sk, mu: np.ndarray, sigma: np.ndarray):
        self.typ = typ
        self.sk = sk
        self.mu = mu
        self.sigma = sigma

    def predict_proba(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if len(X) == 0:
            return np.empty((0, 3))
        if self.typ == "lr":
            return self.sk.predict_proba((X - self.mu) / self.sigma)
        Xs = spiegle(X)
        g = _gestellt(_p1(self.sk["gestellt"], X), _p1(self.sk["gestellt"], Xs))
        s = _sieg_a(_p1(self.sk["sieg"], X), _p1(self.sk["sieg"], Xs))
        return kombiniere(g, s)

    @property
    def n_baeume(self) -> dict | None:
        """Bäume je Stufe (nur Boosting)."""
        if self.typ != "gbm":
            return None
        return {stufe: int(sk.n_iter_) for stufe, sk in self.sk.items()}


def _monotonie(vorgaben: dict) -> list[int]:
    """{Merkmal: +1/-1} -> Vorgabe je Spalte, wie sklearn sie erwartet (0 = frei)."""
    return [vorgaben.get(f, 0) for f in FEATURE_NAMES]


def _gbm(n_baeume: int, min_blatt: int, monoton):
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(
        max_iter=n_baeume, learning_rate=GBM_LERNRATE, max_leaf_nodes=GBM_MAX_BLAETTER,
        min_samples_leaf=min_blatt, monotonic_cst=_monotonie(monoton),
        early_stopping=False, random_state=SEED,
    )


def beste_baumzahl(Xtr, ytr_binaer, datum_tr, *, symmetrie, min_blatt: int, monoton) -> int:
    """Baumzahl mit dem kleinsten Log-Loss auf den jüngsten Trainingsdaten.

    ``symmetrie``: _gestellt oder _sieg_a -- gemessen wird, was predict_proba
    später rechnet (gemittelt mit der gespiegelten Paarung)."""
    from sklearn.metrics import log_loss

    tage = np.asarray(datum_tr, dtype="datetime64[D]").astype(np.int64)
    grenze = np.quantile(tage, 1.0 - VALIDIERUNGSANTEIL)
    fit, val = tage < grenze, tage >= grenze
    if fit.sum() < 50 or val.sum() < 20 or len(np.unique(ytr_binaer[fit])) < 2:
        return max(10, GBM_MAX_BAEUME // 4)  # zu wenig Daten zum Messen (z.B. Tests)
    sk = _gbm(GBM_MAX_BAEUME, min_blatt, monoton).fit(Xtr[fit], ytr_binaer[fit])
    Xv, yv = Xtr[val], ytr_binaer[val]
    verluste = [
        log_loss(yv, symmetrie(p[:, 1], q[:, 1]), labels=[0, 1])
        for p, q in zip(sk.staged_predict_proba(Xv), sk.staged_predict_proba(spiegle(Xv)))
    ]
    return int(np.argmin(verluste)) + 1


def _stufe(Xtr, ytr_binaer, datum_tr, *, symmetrie, min_blatt: int, monoton):
    n = beste_baumzahl(Xtr, ytr_binaer, datum_tr, symmetrie=symmetrie, min_blatt=min_blatt, monoton=monoton)
    return _gbm(n, min_blatt, monoton).fit(Xtr, ytr_binaer)


def trainiere_modell(Xtr, ytr, datum_tr, typ: str = MODELL_TYP) -> Prognosemodell:
    """Modell auf den Trainingszeilen fitten (inkl. Spiegelzeilen).

    ``datum_tr``: ISO-Datum je Trainingszeile, für die zeitliche Wahl der
    Baumzahl (nur Boosting).
    """
    Xtr = np.asarray(Xtr, dtype=float)
    ytr = np.asarray(ytr)
    mu = Xtr.mean(axis=0)
    sigma = Xtr.std(axis=0)
    sigma[sigma == 0] = 1.0
    if typ == "lr":
        from sklearn.linear_model import LogisticRegression

        sk = LogisticRegression(max_iter=2000, C=1.0, random_state=SEED).fit((Xtr - mu) / sigma, ytr)
        return Prognosemodell("lr", sk, mu, sigma)
    if typ != "gbm":
        raise ValueError(f"Unbekannter Modelltyp: {typ}")
    datum_tr = np.asarray(datum_tr)
    gestellt = _stufe(Xtr, (ytr == 1).astype(int), datum_tr, symmetrie=_gestellt,
                      min_blatt=GBM_MIN_BLATT_GESTELLT, monoton=MONOTON_GESTELLT)
    entschieden = ytr != 1
    sieg = _stufe(Xtr[entschieden], (ytr[entschieden] == 0).astype(int), datum_tr[entschieden],
                  symmetrie=_sieg_a, min_blatt=GBM_MIN_BLATT_SIEG, monoton=MONOTON_SIEG)
    return Prognosemodell("gbm", {"gestellt": gestellt, "sieg": sieg}, mu, sigma)
