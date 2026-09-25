"""Merkmalsversion 3: Gestellt-Bilanz des Paars und Spitzen-Niveau."""
from __future__ import annotations

import math

from pipeline.config import ELO_START, GESTELLT_NEIGUNG_K, PAAR_GESTELLT_K
from pipeline.features import (
    FEATURE_NAMES,
    MERKMALE_JE_VERSION,
    baue_features,
    feature_vektor_fuer_prognose,
    paar_gestellt,
    spitzen_niveau,
)
from pipeline.labels import GangResultat
from pipeline.ratings import fahre_elo_durch
from pipeline.schema import Schwinger

_I = {n: i for i, n in enumerate(FEATURE_NAMES)}
_SYMBOLE = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}


def _gang(event, datum, a, b, ergebnis="sieg_a"):
    sa, sb = _SYMBOLE[ergebnis]
    return GangResultat(event_id=event, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
                        symbol_a=sa, note_a=None, symbol_b=sb, note_b=None,
                        ergebnis=ergebnis, fest_typ="kantonal")


def _zeilen(gaenge, ids):
    _, snaps = fahre_elo_durch(gaenge)
    X, _, meta = baue_features(gaenge, snaps, {i: Schwinger(id=i, name=i) for i in ids}, augment=True)
    return X, meta


def test_versionen_haengen_nur_hinten_an():
    assert MERKMALE_JE_VERSION == {1: 13, 2: 14, 3: 16} and len(FEATURE_NAMES) == 16


# --- Gestellt-Bilanz des Paars ------------------------------------------------------

def test_paar_bilanz_ohne_duelle_ist_null_und_schrumpft_gegen_die_erwartung():
    assert paar_gestellt(0, 0, 0.3, 0.1) == 0.0
    # 5 von 6 gestellt, Erwartung 0.2: (5 + 4 * 0.2) / 10 - 0.2
    assert math.isclose(paar_gestellt(6, 5, 0.25, 0.15), (5 + PAAR_GESTELLT_K * 0.2) / (6 + PAAR_GESTELLT_K) - 0.2)
    assert paar_gestellt(6, 0, 0.25, 0.15) < 0 < paar_gestellt(1, 1, 0.25, 0.15)


def test_paar_bilanz_ist_leakfrei_symmetrisch_und_zaehlt_nur_dieses_paar():
    gaenge = [_gang("f1", "2024-05-01", "a", "b", "gestellt"), _gang("f1", "2024-05-01", "c", "d"),
              _gang("f2", "2024-06-01", "a", "b"), _gang("f2", "2024-06-01", "a", "d")]
    X, meta = _zeilen(gaenge, "abcd")
    f1 = [x for x, m in zip(X, meta) if m["event_id"] == "f1"]
    assert all(x[_I["paar_gestellt"]] == 0.0 for x in f1)  # erst NACH dem Fest gezählt
    ab = [x for x, m in zip(X, meta) if m["event_id"] == "f2" and m["schwinger_b_id"] == "b"]
    ad = [x for x, m in zip(X, meta) if m["event_id"] == "f2" and m["schwinger_b_id"] == "d"]
    assert ab[0][_I["paar_gestellt"]] == ab[1][_I["paar_gestellt"]] > 0  # Spiegelzeile gleich
    assert ad[0][_I["paar_gestellt"]] == 0.0  # a und d sind sich nie begegnet
    # Vor f2: Basis 1 von 2; a und b je 1 von 1 gestellt -> geschrumpfte
    # Einzelneigung, und das Paar hat 1 von 1 gestellt.
    basis = 0.5
    n = (1 + GESTELLT_NEIGUNG_K * basis) / (1 + GESTELLT_NEIGUNG_K)
    assert math.isclose(ab[0][_I["paar_gestellt"]], paar_gestellt(1, 1, n, n))


# --- Spitzen-Niveau ---------------------------------------------------------------

def test_spitzen_niveau_misst_den_schwaecheren_und_ist_unten_null():
    assert spitzen_niveau(2100, 1800, 100.0) == spitzen_niveau(1800, 2100, 100.0) == 3.0
    assert spitzen_niveau(2100, ELO_START - 50, 100.0) == 0.0


def test_spitzen_niveau_ist_in_beiden_zeilen_gleich_und_nur_hoch_wenn_beide_stark():
    # a und c gewinnen in f1 und liegen danach über dem Startwert, b und d darunter.
    gaenge = [_gang("f1", "2024-05-01", "a", "b"), _gang("f1", "2024-05-01", "c", "d"),
              _gang("f2", "2024-06-01", "a", "c"), _gang("f2", "2024-06-01", "a", "d")]
    X, meta = _zeilen(gaenge, "abcd")
    ac = [x for x, m in zip(X, meta) if m["event_id"] == "f2" and m["schwinger_b_id"] == "c"]
    ad = [x for x, m in zip(X, meta) if m["event_id"] == "f2" and m["schwinger_b_id"] == "d"]
    assert ac[0][_I["spitzen_niveau"]] == ac[1][_I["spitzen_niveau"]] > 0
    assert ad[0][_I["spitzen_niveau"]] == ad[1][_I["spitzen_niveau"]] == 0.0


# --- Live-Prognose ------------------------------------------------------------------

def _live(version, **kw):
    cfg = {"merkmal_version": version, "elo_streuung": 125.0, "gestellt_basis": 0.2}
    sa, sb = Schwinger(id="a", name="a"), Schwinger(id="b", name="b")
    return feature_vektor_fuer_prognose(1750, 1625, 0.6, 0.4, 100, 9, sa, sb, "2026-06-01", 0.0,
                                        modell_config=cfg, **kw)


def test_live_v3_rechnet_bilanz_aus_den_duellen_und_niveau_aus_elo():
    x = _live(3, neigung_a=0.3, neigung_b=0.1, duelle=6, duelle_gestellt=5)
    assert len(x) == 16
    assert math.isclose(x[_I["paar_gestellt"]], paar_gestellt(6, 5, 0.3, 0.1))
    assert math.isclose(x[_I["spitzen_niveau"]], (1625 - 1500) / 125.0)
    # Fehlende Neigung: Basis, wie bei gestellt_neigung.
    assert math.isclose(_live(3, duelle=2, duelle_gestellt=2)[_I["paar_gestellt"]], paar_gestellt(2, 2, 0.2, 0.2))


def test_live_v2_modell_kennt_die_neuen_merkmale_nicht():
    assert len(_live(2, duelle=6, duelle_gestellt=5)) == 14
