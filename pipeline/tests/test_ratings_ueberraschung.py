"""Tests für den Überraschungs-Index (erwartete vs. tatsächliche Elo-Punkte)."""
from __future__ import annotations

from pipeline.labels import GangResultat
from pipeline.ratings import berechne_ueberraschung


def _snap(event_id, a, b, elo_a, elo_b):
    return {
        "event_id": event_id,
        "schwinger_a_id": a,
        "schwinger_b_id": b,
        "elo_a_pre": elo_a,
        "elo_b_pre": elo_b,
        "n_a_pre": 0,
        "n_b_pre": 0,
    }


def test_underdog_sieg_ergibt_grosse_positive_ueberraschung():
    # B (1900) haushoch favorisiert gegenüber A (1500), gewinnt aber A.
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
    ]
    snapshots = [_snap("ev1", "a", "b", 1500.0, 1900.0)]
    ergebnis = berechne_ueberraschung(gaenge, snapshots)

    assert ergebnis["a"]["index"] > 0.8  # klarer Aussenseitersieg
    assert ergebnis["b"]["index"] < -0.8  # Favorit enttäuscht entsprechend stark
    assert ergebnis["a"]["n"] == 1
    assert ergebnis["a"]["groesster_erfolg"]["gegner_id"] == "b"
    assert "groesster_erfolg" not in ergebnis["b"] or ergebnis["b"]["groesster_erfolg"] is None


def test_erwarteter_sieg_ergibt_kleine_ueberraschung():
    # A klar favorisiert und gewinnt auch -> Überraschung nahe 0.
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
    ]
    snapshots = [_snap("ev1", "a", "b", 1900.0, 1500.0)]
    ergebnis = berechne_ueberraschung(gaenge, snapshots)

    assert abs(ergebnis["a"]["index"]) < 0.2
    assert abs(ergebnis["b"]["index"]) < 0.2


def test_gestellt_bei_gleichstand_keine_ueberraschung():
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "-", 9.0, "-", 9.0, "gestellt", "kantonal"),
    ]
    snapshots = [_snap("ev1", "a", "b", 1500.0, 1500.0)]
    ergebnis = berechne_ueberraschung(gaenge, snapshots)

    assert ergebnis["a"]["index"] == 0.0
    assert ergebnis["b"]["index"] == 0.0


def test_fehlender_snapshot_wird_uebersprungen():
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
    ]
    ergebnis = berechne_ueberraschung(gaenge, [])
    assert ergebnis == {}


def test_gaenge_vor_ab_datum_zaehlen_nicht():
    """Die Pipeline übergibt das Ende der Einschwingphase: davor liegen alle
    Ratings beim Startwert, jeder Sieg eines späteren Spitzenschwingers sähe
    wie eine Überraschung aus."""
    gaenge = [
        GangResultat("ev1", "2023-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
        GangResultat("ev2", "2024-06-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
    ]
    snapshots = [_snap("ev1", "a", "b", 1500.0, 1900.0), _snap("ev2", "a", "b", 1900.0, 1500.0)]
    ergebnis = berechne_ueberraschung(gaenge, snapshots, ab_datum="2024-01-01")

    assert ergebnis["a"]["n"] == 1
    assert ergebnis["a"]["groesster_erfolg"]["event_id"] == "ev2"
