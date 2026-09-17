"""Tests für MAE/MSE (pipeline.metriken)."""
import math

import numpy as np
import pytest

from pipeline.config import KLASSEN
from pipeline.metriken import (
    erwarteter_punktwert,
    mae,
    mse,
    punktwert_aus_klasse,
    punktwert_fehlermasse,
)


def test_mae_und_mse_von_hand_nachgerechnet():
    y = [3.0, 5.0, 2.0]
    yhat = [2.0, 5.0, 4.0]
    # Fehler: 1, 0, -2  ->  |.|: 1, 0, 2 ; quadriert: 1, 0, 4
    assert mae(y, yhat) == pytest.approx(3 / 3)
    assert mse(y, yhat) == pytest.approx(5 / 3)


def test_perfekte_vorhersage_ist_null():
    y = [1.0, 0.5, 0.0]
    assert mae(y, y) == 0.0
    assert mse(y, y) == 0.0


def test_mse_gewichtet_grosse_fehler_staerker_als_mae():
    """Kernaussage der beiden Masse: gleiche Fehlersumme, andere Verteilung.

    A macht vier kleine Fehler, B einen grossen. Die Summe der Absolutfehler
    ist identisch, MAE bewertet beide also gleich -- MSE bestraft B deutlich.
    """
    y = [0.0, 0.0, 0.0, 0.0]
    a = [1.0, 1.0, 1.0, 1.0]   # 4x Fehler 1
    b = [4.0, 0.0, 0.0, 0.0]   # 1x Fehler 4

    assert mae(y, a) == pytest.approx(mae(y, b))
    assert mse(y, b) > mse(y, a)
    assert mse(y, a) == pytest.approx(1.0)   # (1+1+1+1)/4
    assert mse(y, b) == pytest.approx(4.0)   # (16+0+0+0)/4


def test_punktwert_aus_klasse_folgt_elo_konvention():
    """Sieg=1, Gestellt=0.5, Niederlage=0 (wie ratings.EloModell.update)."""
    idx = [KLASSEN.index("sieg_a"), KLASSEN.index("gestellt"), KLASSEN.index("sieg_b")]
    assert punktwert_aus_klasse(idx).tolist() == [1.0, 0.5, 0.0]


def test_erwarteter_punktwert_mittelt_die_verteilung():
    p = np.zeros((3, len(KLASSEN)))
    p[0, KLASSEN.index("sieg_a")] = 1.0        # sicherer Sieg A -> 1.0
    p[1, KLASSEN.index("gestellt")] = 1.0      # sicher gestellt -> 0.5
    p[2, KLASSEN.index("sieg_a")] = 0.5        # 50/50 Sieg A / Sieg B -> 0.5
    p[2, KLASSEN.index("sieg_b")] = 0.5
    assert erwarteter_punktwert(p).tolist() == [1.0, 0.5, 0.5]


def test_punktwert_fehlermasse_bei_perfekter_prognose():
    y = [KLASSEN.index("sieg_a"), KLASSEN.index("sieg_b")]
    p = np.zeros((2, len(KLASSEN)))
    p[0, KLASSEN.index("sieg_a")] = 1.0
    p[1, KLASSEN.index("sieg_b")] = 1.0
    res = punktwert_fehlermasse(p, y)
    assert res["mae"] == 0.0
    assert res["mse"] == 0.0


def test_punktwert_fehlermasse_bei_maximal_falscher_prognose():
    """Sieg A vorhergesagt, Sieg B eingetreten -> Fehler 1.0 je Gang."""
    y = [KLASSEN.index("sieg_b")]
    p = np.zeros((1, len(KLASSEN)))
    p[0, KLASSEN.index("sieg_a")] = 1.0
    res = punktwert_fehlermasse(p, y)
    assert res["mae"] == pytest.approx(1.0)
    assert res["mse"] == pytest.approx(1.0)


def test_leere_eingabe_ergibt_nan_statt_zu_werfen():
    """Der Holdout kann leer sein (s. train.trainiere) -- kein Absturz."""
    assert math.isnan(mae([], []))
    assert math.isnan(mse([], []))


def test_formfehler_wird_gemeldet():
    with pytest.raises(ValueError):
        mae([1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        mse([1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        erwarteter_punktwert(np.zeros((2, len(KLASSEN) + 1)))
