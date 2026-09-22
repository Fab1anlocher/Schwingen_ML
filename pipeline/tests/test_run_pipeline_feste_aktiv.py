"""Tests für die Schwinger-Aggregationen in run_pipeline.py: Fest-Zählung
(anzahl_feste), Abzeichen-Selbsttest und Aktiv-Erkennung."""
from __future__ import annotations

from pipeline.labels import GangResultat
from pipeline.schema import Schwinger
from pipeline.run_pipeline import (
    _abzeichen_plausibilitaet,
    _aktive_schwinger,
    _anzahl_feste,
)


def _gang(event_id, datum, a, b, abz_a=False, abz_b=False) -> GangResultat:
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
        status_abzeichen_a=abz_a,
        status_abzeichen_b=abz_b,
    )


def _schwinger(sid, kranzstatus="kein") -> Schwinger:
    return Schwinger(id=sid, name=sid, kranzstatus=kranzstatus)


def test_anzahl_feste_zaehlt_distinkte_feste_nicht_gaenge():
    gaenge = [
        _gang("ev1", "2025-08-01", "anna|1995", "beat|1996"),
        _gang("ev1", "2025-08-01", "anna|1995", "carl|1997"),
        _gang("ev2", "2025-09-01", "anna|1995", "beat|1996"),
    ]
    result = _anzahl_feste(gaenge)
    assert result["anna|1995"] == 2      # ev1 + ev2, nicht 3 Gänge
    assert result["carl|1997"] == 1


def test_anzahl_feste_zaehlt_beide_seiten():
    gaenge = [_gang("ev1", "2025-08-01", "anna|1995", "beat|1996")]
    result = _anzahl_feste(gaenge)
    assert result["anna|1995"] == 1
    assert result["beat|1996"] == 1


def test_anzahl_feste_ist_unabhaengig_vom_abzeichen():
    """Die Zahl haengt am Antreten, nicht an der Stern-Markierung."""
    ohne = _anzahl_feste([_gang("ev1", "2025-08-01", "a|1", "b|2")])
    mit = _anzahl_feste([_gang("ev1", "2025-08-01", "a|1", "b|2", abz_a=True, abz_b=True)])
    assert ohne == mit


def test_abzeichen_plausibilitaet_erkennt_vollstaendigen_treffer():
    """Beide Kranzer sind markiert -> Trefferquote 1.0, keine Refetch-Warnung."""
    gaenge = [_gang("ev1", "2025-08-01", "a|1", "b|2", abz_a=True, abz_b=True)]
    schwinger = {"a|1": _schwinger("a|1", "eidgenosse"), "b|2": _schwinger("b|2", "kranzer")}
    res = _abzeichen_plausibilitaet(gaenge, schwinger)
    assert res["trefferquote_median"] == 1.0
    assert res["feste_ohne_abzeichen"] == 0
    assert res["plausibel"] is True
    assert res["hinweis_refetch"] is False


def test_abzeichen_plausibilitaet_meldet_fest_ohne_jeden_treffer():
    """Der Fall, der monatelang unbemerkt blieb: Kranzer im Feld, kein Stern
    erkannt -- Altbestand in artifacts/raw, der einen Refetch braucht."""
    gaenge = [_gang("ev1", "2025-08-01", "a|1", "b|2")]
    schwinger = {"a|1": _schwinger("a|1", "eidgenosse"), "b|2": _schwinger("b|2", "kranzer")}
    res = _abzeichen_plausibilitaet(gaenge, schwinger)
    assert res["trefferquote_median"] == 0.0
    assert res["feste_ohne_abzeichen"] == 1
    assert res["plausibel"] is False
    assert res["hinweis_refetch"] is True


def test_abzeichen_plausibilitaet_ignoriert_feste_ohne_kranzer():
    """Ohne Kranzer im Feld gibt es nichts zu finden -- kein Fehlalarm."""
    gaenge = [_gang("ev1", "2025-08-01", "a|1", "b|2")]
    schwinger = {"a|1": _schwinger("a|1"), "b|2": _schwinger("b|2")}
    res = _abzeichen_plausibilitaet(gaenge, schwinger)
    assert res == {"n_feste_mit_kranzern": 0}


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
