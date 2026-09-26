"""Tests für den 4-Wege-Benchmark (Kranz-Heuristik/Elo/ML ohne Elo/ML komplett)."""
from __future__ import annotations

import numpy as np

from pipeline.features import FEATURE_NAMES
from pipeline.benchmark import (
    _accuracy,
    _brier_score,
    elo_baseline_wahrscheinlichkeiten,
    fuehre_benchmark_durch,
    kranz_heuristik_wahrscheinlichkeiten,
)


def test_brier_score_perfekte_vorhersage_ist_null():
    p = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    y = np.array([0, 2])
    assert _brier_score(p, y) == 0.0


def test_brier_score_komplett_falsch_ist_maximal():
    p = np.array([[0.0, 0.0, 1.0]])
    y = np.array([0])
    # Abweichung (0-1)^2 + (0-0)^2 + (1-0)^2 = 2.0 -> schlechtestmöglicher Wert.
    assert _brier_score(p, y) == 2.0


def test_accuracy_zaehlt_argmax_treffer():
    p = np.array([[0.6, 0.3, 0.1], [0.1, 0.2, 0.7], [0.5, 0.4, 0.1]])
    y = np.array([0, 2, 1])  # letzte Zeile falsch (argmax=0, tatsächlich 1)
    assert _accuracy(p, y) == 2 / 3


def test_kranz_heuristik_bevorzugt_mehr_kraenze():
    kranz_diff = np.array([2.0, -1.0, 0.0])
    p = kranz_heuristik_wahrscheinlichkeiten(kranz_diff)
    assert list(p[0]) == [1.0, 0.0, 0.0]  # A hat mehr Kränze -> sieg_a
    assert list(p[1]) == [0.0, 0.0, 1.0]  # B hat mehr Kränze -> sieg_b
    assert list(p[2]) == [0.0, 1.0, 0.0]  # Gleichstand -> gestellt


def test_elo_baseline_grosser_vorsprung_favorisiert_klar():
    p = elo_baseline_wahrscheinlichkeiten(np.array([400.0]))
    assert p[0][0] > 0.8  # P(sieg_a) bei +400 Elo klar favorisiert


def test_elo_baseline_gleichstand_ist_symmetrisch():
    p = elo_baseline_wahrscheinlichkeiten(np.array([0.0]))
    pa, pd, pb = p[0]
    assert pa == pb
    assert pd > 0.0  # Gestellt-Wahrscheinlichkeit maximal bei Ratinggleichheit


def _zeile(rating_diff: float = 0.0, kranz_diff: float = 0.0) -> list[float]:
    # Reihenfolge = FEATURE_NAMES; nur Rating und Kranz sind besetzt.
    x = [0.0] * len(FEATURE_NAMES)
    x[FEATURE_NAMES.index("rating_diff")] = rating_diff
    x[FEATURE_NAMES.index("rating_abstand")] = abs(rating_diff)
    x[FEATURE_NAMES.index("kranz_diff")] = kranz_diff
    return x


def _meta(datum: str, augmented: bool = False, elo_diff: float = 0.0) -> dict:
    m = {"event_id": "e", "datum": datum, "schwinger_a_id": "a", "schwinger_b_id": "b", "n_a": 0, "n_b": 0,
         "elo_diff": elo_diff}
    if augmented:
        m["augmented"] = True
    return m


def test_fuehre_benchmark_durch_ignoriert_augmentierte_testzeilen():
    # Trainingsjahr 2023: 6 Zeilen, alle 3 Klassen vertreten.
    X = [
        _zeile(rating_diff=150, kranz_diff=1),
        _zeile(rating_diff=-150, kranz_diff=-1),
        _zeile(rating_diff=0, kranz_diff=0),
        _zeile(rating_diff=200, kranz_diff=2),
        _zeile(rating_diff=-200, kranz_diff=-2),
        _zeile(rating_diff=0, kranz_diff=0),
    ]
    y = [0, 2, 1, 0, 2, 1]
    meta = [_meta("2023-01-01") for _ in range(6)]

    # Holdout-Jahr 2024: 4 echte Gänge + 4 gespiegelte Augmentations-Zeilen.
    X_test_original = [
        _zeile(rating_diff=100, kranz_diff=1),
        _zeile(rating_diff=-100, kranz_diff=-1),
        _zeile(rating_diff=0, kranz_diff=0),
        _zeile(rating_diff=50, kranz_diff=2),
    ]
    y_test_original = [0, 2, 1, 0]
    X_test_augmented = [
        _zeile(rating_diff=-100, kranz_diff=-1),
        _zeile(rating_diff=100, kranz_diff=1),
        _zeile(rating_diff=0, kranz_diff=0),
        _zeile(rating_diff=-50, kranz_diff=-2),
    ]
    y_test_augmented = [2, 0, 1, 2]

    X += X_test_original + X_test_augmented
    y += y_test_original + y_test_augmented
    meta += [_meta("2024-01-01") for _ in X_test_original]
    meta += [_meta("2024-01-01", augmented=True) for _ in X_test_augmented]

    ergebnis = fuehre_benchmark_durch(X, y, meta)

    assert ergebnis["holdout_jahr"] == 2024
    # Nur die 4 ECHTEN Testgänge zählen, nicht die 4 gespiegelten.
    assert ergebnis["n_test"] == 4
    assert set(ergebnis["kandidaten"].keys()) == {
        "kranz_heuristik", "elo_baseline", "elo_angepasst", "ml_ohne_elo", "lr_komplett", "ml_komplett",
    }
    for key, werte in ergebnis["kandidaten"].items():
        assert 0.0 <= werte["accuracy"] <= 1.0
        assert 0.0 <= werte["brier_score"] <= 2.0
        # Log-Loss für alle mit Wahrscheinlichkeiten, nicht für die 0/1-Heuristik.
        assert (werte["log_loss"] is None) == (key == "kranz_heuristik")

    # Die Heuristik weist aus, wie oft sie keinen Favoriten hat.
    kranz = ergebnis["kandidaten"]["kranz_heuristik"]
    assert kranz["anteil_gleichstand"] == 0.25 and kranz["accuracy_ohne_gleichstand"] == 1.0

    # Kranz-Heuristik ist auf diesen Daten deterministisch perfekt (Label
    # folgt exakt dem Vorzeichen von kranz_diff, s. Testdaten oben).
    assert ergebnis["kandidaten"]["kranz_heuristik"]["accuracy"] == 1.0


def test_fuehre_benchmark_durch_gibt_none_bei_einzelner_saison():
    # Deckt nur EINE Saison ab (z.B. taeglicher Update-Lauf mit kurzem
    # Zeitfenster, s. fetch_raw --seit-datum) -> Holdout == einzige Saison,
    # also 0 Trainingszeilen. Ein sinnvoller Vergleich ist dann nicht moeglich.
    X = [_zeile(rating_diff=100, kranz_diff=1), _zeile(rating_diff=-100, kranz_diff=-1)]
    y = [0, 2]
    meta = [_meta("2026-01-01"), _meta("2026-01-02")]

    assert fuehre_benchmark_durch(X, y, meta) is None


def test_elo_baseline_nimmt_den_rohen_elo_abstand_aus_meta():
    """Seit Merkmalsversion 2 ist rating_diff durch die Streuung skaliert --
    die Baseline darf es nicht mehr mal 100 zurückrechnen. Hier steht im
    Merkmal absichtlich ein anderer Wert als in meta: massgebend ist meta."""
    X = [_zeile(rating_diff=d) for d in (1.0, -1.0, 0.0, 1.0, -1.0, 0.0)]
    y = [0, 2, 1, 0, 2, 1]
    meta = [_meta("2023-01-01", elo_diff=d) for d in (100, -100, 0, 100, -100, 0)]
    # Merkmal: B minimal vorne (x100 zurückgerechnet -> Favorit B) ...
    X.append(_zeile(rating_diff=-0.01))
    y.append(0)
    meta.append(_meta("2024-01-01", elo_diff=400.0))   # ... echter Abstand: A +400
    res = fuehre_benchmark_durch(X, y, meta)
    assert res["kandidaten"]["elo_baseline"]["accuracy"] == 1.0
    assert res["kandidaten"]["elo_baseline"]["brier_score"] < 0.1
