"""4-Wege-Benchmark: Heuristik vs. Elo vs. ML ohne Historie vs. ML komplett.

Beantwortet die Nutzerfrage "bringt Elo wirklich einen Mehrwert, oder reichen
physische/Stil-/Verbandsmerkmale, und ist unser Modell insgesamt besser als
ein reines Elo-Ranking?" mit vier klar abgegrenzten, FAIR verglichenen
Kandidaten:

  1. Kranz-Heuristik   – "wer mehr Kränze hat, gewinnt immer" (keine Statistik).
  2. Elo-Baseline       – klassisches Elo, feste Formel, kein Fitting (ML-2).
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
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from .config import SEED, KLASSEN
from .features import FEATURE_NAMES
from .ratings import EloModell
from .train import _split_zeitlich, bestimme_holdout_jahr

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
_RATING_DIFF_IDX = FEATURE_NAMES.index("rating_diff")


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


def fuehre_benchmark_durch(X: list[list[float]], y: list[int], meta: list[dict]) -> dict:
    """Vergleicht alle 4 Kandidaten auf demselben zeitlichen Holdout (echte Gänge)."""
    X_arr = np.asarray(X)
    y_arr = np.asarray(y)
    holdout = bestimme_holdout_jahr(meta)

    ist_test = np.array([int(m["datum"][:4]) >= holdout for m in meta])
    ist_original = np.array([not m.get("augmented", False) for m in meta])
    test_maske = ist_test & ist_original
    train_maske = ~ist_test  # Training nutzt Augmentation bewusst (Paar-Symmetrie).

    Xte, yte = X_arr[test_maske], y_arr[test_maske]
    Xtr, ytr = X_arr[train_maske], y_arr[train_maske]

    ergebnis: dict[str, dict] = {}

    # 1) Kranz-Heuristik.
    p_kranz = kranz_heuristik_wahrscheinlichkeiten(Xte[:, _KRANZ_DIFF_IDX])
    ergebnis["kranz_heuristik"] = _bewerte(p_kranz, yte)

    # 2) Elo-Baseline (rating_diff-Merkmal ist bereits (elo_a - elo_b) / 100).
    p_elo = elo_baseline_wahrscheinlichkeiten(Xte[:, _RATING_DIFF_IDX] * 100.0)
    ergebnis["elo_baseline"] = _bewerte(p_elo, yte)

    # 3) ML ohne Historie (nur Physis/Stil/Verband), gleicher Train/Test-Split.
    spalten_a = [FEATURE_NAMES.index(n) for n in PHYSIS_STIL_VERBAND]
    p_a = _fit_predict(Xtr[:, spalten_a], ytr, Xte[:, spalten_a])
    ergebnis["ml_ohne_elo"] = _bewerte(p_a, yte)

    # 4) ML komplett (Champion, alle Merkmale).
    p_b = _fit_predict(Xtr, ytr, Xte)
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


def _bewerte(p: np.ndarray, y: np.ndarray) -> dict:
    return {
        "accuracy": round(_accuracy(p, y), 4),
        "brier_score": round(_brier_score(p, y), 4),
    }
