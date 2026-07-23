"""Tests für die Schwinger-Aggregationen in run_pipeline.py: Kranz-Zählung
(anzahl_kraenze) und Aktiv-Erkennung (letzte Saison in der Datenbasis)."""
from __future__ import annotations

from pipeline.labels import GangResultat
from pipeline.run_pipeline import _aktive_schwinger, _anzahl_kraenze


def _gang(event_id, datum, a, b, kranz_a=False, kranz_b=False) -> GangResultat:
    return GangResultat(
        event_id=event_id,
        datum=datum,
        schwinger_a_id=a,
        schwinger_b_id=b,
        symbol_a="+",
        note_a=10.0,
        symbol_b="o",
        note_b=None,
        ergebnis="sieg_a",
        fest_typ="kantonal",
        kranz_a=kranz_a,
        kranz_b=kranz_b,
    )


def test_anzahl_kraenze_zaehlt_distinkte_feste_nicht_gaenge():
    # Zwei Gänge am selben Fest mit Kranz -> trotzdem nur 1 Kranz (pro Fest, nicht pro Gang).
    gaenge = [
        _gang("ev1", "2025-08-01", "anna|1995", "beat|1996", kranz_a=True),
        _gang("ev1", "2025-08-01", "anna|1995", "carl|1997", kranz_a=True),
        _gang("ev2", "2025-09-01", "anna|1995", "beat|1996", kranz_a=False),
    ]
    result = _anzahl_kraenze(gaenge)
    assert result["anna|1995"] == 1
    assert "beat|1996" not in result or result.get("beat|1996", 0) == 0


def test_anzahl_kraenze_beide_seiten():
    gaenge = [_gang("ev1", "2025-08-01", "anna|1995", "beat|1996", kranz_a=True, kranz_b=True)]
    result = _anzahl_kraenze(gaenge)
    assert result["anna|1995"] == 1
    assert result["beat|1996"] == 1


def test_anzahl_kraenze_ueber_mehrere_feste_summiert():
    gaenge = [
        _gang("ev1", "2024-08-01", "anna|1995", "beat|1996", kranz_a=True),
        _gang("ev2", "2025-08-01", "anna|1995", "beat|1996", kranz_a=True),
    ]
    result = _anzahl_kraenze(gaenge)
    assert result["anna|1995"] == 2


def test_aktive_schwinger_nur_referenzjahr():
    gaenge = [
        _gang("ev1", "2026-05-01", "anna|1995", "beat|1996"),
        _gang("ev2", "2024-05-01", "carl|1997", "dora|1998"),
    ]
    aktive = _aktive_schwinger(gaenge, referenz_jahr=2026)
    assert aktive == {"anna|1995", "beat|1996"}
    assert "carl|1997" not in aktive


def test_aktive_schwinger_mehrfach_beteiligt_bleibt_einmal():
    gaenge = [
        _gang("ev1", "2026-05-01", "anna|1995", "beat|1996"),
        _gang("ev2", "2026-06-01", "anna|1995", "carl|1997"),
    ]
    aktive = _aktive_schwinger(gaenge, referenz_jahr=2026)
    assert aktive == {"anna|1995", "beat|1996", "carl|1997"}
