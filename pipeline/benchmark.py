"""4-Wege-Benchmark: Heuristik vs. Elo vs. ML ohne Historie vs. ML komplett.

Beantwortet die Nutzerfrage "bringt Elo wirklich einen Mehrwert, oder reichen
physische/Stil-/Verbandsmerkmale, und ist unser Modell insgesamt besser als
ein reines Elo-Ranking?" mit vier klar abgegrenzten, FAIR verglichenen
Kandidaten:

  1. Kranz-Heuristik   – "wer mehr Kränze hat, gewinnt immer" (keine Statistik);
                          bei gleichem Kranzstatus (rund zwei Drittel der
                          Gänge) tippt sie auf Gestellt.
  2. Elo-Baseline       – klassisches Elo, feste Formel, kein Fitting (ML-2).
                          Viel zu zaghaft: wo sie dem Favoriten 64 % gibt,
                          gewinnt er in 85 % (Audit 25.09.2026).
  2b. Elo angepasst     – dieselbe Information (nur der Elo-Abstand), die
                          Wahrscheinlichkeiten aber an den Trainingsgängen
                          angepasst. Der faire Massstab für "was bringt das
                          Modell über Elo hinaus" (2026: Log-Loss 0.857
                          statt 0.910 mit der Formel).
  3. ML ohne Historie   – nur Physis/Stil/Verband (kranz_diff, alter_diff,
                          gewicht_diff, groesse_diff, same_teilverband,
                          schwung_overlap, schwung_count_diff) — bewusst OHNE
                          Elo, Form, Erfahrung und Kopf-an-Kopf, da diese alle
                          aus vergangenen Ergebnissen abgeleitet sind.
  4. ML komplett        – das Produktionsmodell (alle FEATURE_NAMES).

Fairness-Regeln, damit der Vergleich wissenschaftlich sauber ist:
  - ALLE vier werden auf DERSELBEN Holdout-Menge ausgewertet (jüngste Saison).
  - Die Auswertung nutzt NUR echte Gänge, keine augmentierten Spiegel-Zeilen
    (Augmentation ist ein Trainings-Trick für Paar-Symmetrie, keine zweite
    unabhängige Beobachtung — sonst würde jeder Test-Gang doppelt gezählt).
  - Beide ML-Modelle werden auf denselben (nicht-Holdout-)Zeilen trainiert,
    inkl. Augmentation dort (das ist beim Training erwünscht).

Metriken:
  - Accuracy: Anteil korrekt vorhergesagter Sieger (argmax der Verteilung).
  - Brier-Score (multiklassig): mittlere quadratische Abweichung der
    vorhergesagten 3-Klassen-Verteilung vom One-Hot-Ergebnis, gemittelt über
    alle Testgänge. 0 = perfekt, höher = schlechter kalibriert/falscher.
  - Log-Loss wie im Report; für die deterministische Heuristik undefiniert
    (eine sichere Fehlprognose kostet unendlich), darum None.
  - MAE / MSE auf dem Punktwert des Gangs (Sieg=1, Gestellt=0.5, Niederlage=0,
    s. pipeline/metriken.py). Achtung: MAE ist keine "ehrliche" Bewertungs-
    regel -- sie belohnt übertriebene Sicherheit (die Heuristik hat 2026 einen
    besseren MAE als Elo, 0.301 gegen 0.338, bei 42 % gegen 61 % Treffern).
    Die App zeigt darum nur MSE; MAE bleibt im Artefakt.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from .config import SEED
from .modell import trainiere_modell
from .features import FEATURE_NAMES
from .metriken import punktwert_fehlermasse
from .ratings import EloModell
from .train import bestimme_holdout_jahr, trainings_maske

# "Physis, Stil, Verband" — bewusst ohne alles, was aus vergangenen
# Gangergebnissen abgeleitet ist (Elo, Form, Erfahrung, Kopf-an-Kopf).
PHYSIS_STIL_VERBAND = [
    "kranz_diff",
    "alter_diff",
    "gewicht_diff",
    "groesse_diff",
    "same_teilverband",
    "schwung_overlap",
    "schwung_count_diff",
]

_KRANZ_DIFF_IDX = FEATURE_NAMES.index("kranz_diff")


def _brier_score(p: np.ndarray, y: np.ndarray) -> float:
    """Multiklassiger Brier-Score = Mittel über i von sum_c (p_ic - onehot_ic)^2."""
    onehot = np.zeros_like(p)
    onehot[np.arange(len(y)), y] = 1.0
    return float(np.mean(np.sum((p - onehot) ** 2, axis=1)))


def _accuracy(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.argmax(p, axis=1) == y))


def kranz_heuristik_wahrscheinlichkeiten(kranz_diff: np.ndarray) -> np.ndarray:
    """"Wer mehr Kränze hat, gewinnt immer" als deterministische 3-Klassen-Verteilung.

    Gleichstand im Kranzstatus -> die Heuristik hat keinen Favoriten, wird
    als "Gestellt" gewertet (die einzige Klasse ohne Sieger-Aussage).
    """
    p = np.zeros((len(kranz_diff), 3))
    p[kranz_diff > 0, 0] = 1.0
    p[kranz_diff < 0, 2] = 1.0
    p[kranz_diff == 0, 1] = 1.0
    return p


def elo_baseline_wahrscheinlichkeiten(rating_diff_elo: np.ndarray) -> np.ndarray:
    """Klassische Elo-Wahrscheinlichkeiten aus der (unskalierten) Ratingdifferenz.

    `EloModell.wahrscheinlichkeiten(ra, rb)` hängt nur von (ra - rb) ab, daher
    genügt hier die Differenz selbst (ra=diff, rb=0) — keine Notwendigkeit,
    die absoluten Elo-Werte separat mitzuführen.
    """
    modell = EloModell()
    p = np.zeros((len(rating_diff_elo), 3))
    for i, diff in enumerate(rating_diff_elo):
        pa, pd, pb = modell.wahrscheinlichkeiten(float(diff), 0.0)
        p[i] = [pa, pd, pb]
    return p


def fuehre_benchmark_durch(X: list[list[float]], y: list[int], meta: list[dict]) -> dict | None:
    """Vergleicht alle 4 Kandidaten auf demselben zeitlichen Holdout (echte Gänge).

    Gibt None zurück, wenn der zeitliche Split entartet ist (z.B. weil die
    Datenbasis nur eine einzelne Saison umfasst -- dann wäre "Training" auf
    0 Zeilen oder nur 1 Klasse ohnehin bedeutungslos, s. bestimme_holdout_jahr).
    Passiert z.B. beim taeglichen Update-Lauf, der nur ein kleines Zeitfenster
    neu einliest (kein voller Historien-Refetch, s. fetch_raw --seit-datum).
    """
    X_arr = np.asarray(X)
    y_arr = np.asarray(y)
    holdout = bestimme_holdout_jahr(meta)

    ist_test = np.array([int(m["datum"][:4]) >= holdout for m in meta])
    ist_original = np.array([not m.get("augmented", False) for m in meta])
    test_maske = ist_test & ist_original
    # Dieselben Trainingszeilen wie das Produktionsmodell (inkl. Augmentation
    # für Paar-Symmetrie, ohne Einschwingphase) -- sonst misst "ML komplett"
    # hier ein anderes Modell als das ausgelieferte.
    train_maske = trainings_maske(meta, y_arr, holdout)

    Xte, yte = X_arr[test_maske], y_arr[test_maske]
    Xtr, ytr = X_arr[train_maske], y_arr[train_maske]
    datum_tr = [m["datum"] for m, drin in zip(meta, train_maske) if drin]

    if len(Xtr) == 0 or len(Xte) == 0 or len(np.unique(ytr)) < 2:
        return None

    ergebnis: dict[str, dict] = {}

    # 1) Kranz-Heuristik.
    p_kranz = kranz_heuristik_wahrscheinlichkeiten(Xte[:, _KRANZ_DIFF_IDX])
    ergebnis["kranz_heuristik"] = _bewerte(p_kranz, yte, mit_log_loss=False)
    # Wie oft die Regel gar keinen Favoriten hat, und wie gut sie trifft, wo
    # sie einen hat -- sonst liest man 42 % als "Kranzstatus taugt nichts".
    gleich = Xte[:, _KRANZ_DIFF_IDX] == 0
    ergebnis["kranz_heuristik"]["anteil_gleichstand"] = round(float(gleich.mean()), 4)
    ergebnis["kranz_heuristik"]["accuracy_ohne_gleichstand"] = (
        round(_accuracy(p_kranz[~gleich], yte[~gleich]), 4) if (~gleich).any() else None)

    # 2) Elo-Baseline aus dem rohen Elo-Abstand. NICHT aus dem Merkmal
    #    rating_diff zurückrechnen: seit Merkmalsversion 2 ist es in Einheiten
    #    der Rating-Streuung skaliert, nicht mehr fix durch 100.
    elo_diff = np.array([m["elo_diff"] for m in meta], dtype=float)
    p_elo = elo_baseline_wahrscheinlichkeiten(elo_diff[test_maske])
    ergebnis["elo_baseline"] = _bewerte(p_elo, yte)

    # 2b) Elo angepasst: nur Elo-Abstand und seine Grösse (rating_diff,
    #     rating_abstand), Wahrscheinlichkeiten an den Trainingszeilen gelernt.
    spalten_elo = [FEATURE_NAMES.index("rating_diff"), FEATURE_NAMES.index("rating_abstand")]
    p_elo_fit = _fit_predict(Xtr[:, spalten_elo], ytr, Xte[:, spalten_elo])
    ergebnis["elo_angepasst"] = _bewerte(p_elo_fit, yte)

    # 3) ML ohne Historie (nur Physis/Stil/Verband), gleicher Train/Test-Split.
    spalten_a = [FEATURE_NAMES.index(n) for n in PHYSIS_STIL_VERBAND]
    # Bewusst LR: die Spiegel-Symmetrie des Boosting-Modells kennt nur den
    # vollen Merkmalsvektor, und für die Frage "was bringen Elo/Historie?"
    # reicht das lineare Modell.
    p_a = _fit_predict(Xtr[:, spalten_a], ytr, Xte[:, spalten_a])
    ergebnis["ml_ohne_elo"] = _bewerte(p_a, yte)

    # 4) Logistic Regression mit allen Merkmalen -- das Produktionsmodell bis
    #    25.09.2026, als Vergleich zum Boosting (Roadmap M1).
    p_lr = _fit_predict(Xtr, ytr, Xte)
    ergebnis["lr_komplett"] = _bewerte(p_lr, yte)

    # 5) ML komplett: GENAU die Modellklasse des Produktionsmodells.
    p_b = trainiere_modell(Xtr, ytr, datum_tr).predict_proba(Xte)
    ergebnis["ml_komplett"] = _bewerte(p_b, yte)

    return {
        "holdout_jahr": holdout,
        "n_test": int(len(yte)),
        "kandidaten": ergebnis,
    }


def _fit_predict(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray) -> np.ndarray:
    mu = Xtr.mean(axis=0)
    sigma = Xtr.std(axis=0)
    sigma[sigma == 0] = 1.0
    modell = LogisticRegression(max_iter=2000, C=1.0, random_state=SEED)
    modell.fit((Xtr - mu) / sigma, ytr)
    return modell.predict_proba((Xte - mu) / sigma)


def _bewerte(p: np.ndarray, y: np.ndarray, mit_log_loss: bool = True) -> dict:
    fehler = punktwert_fehlermasse(p, y)
    return {
        "accuracy": round(_accuracy(p, y), 4),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1, 2])), 4) if mit_log_loss else None,
        "brier_score": round(_brier_score(p, y), 4),
        "mae": round(fehler["mae"], 4),
        "mse": round(fehler["mse"], 4),
    }
