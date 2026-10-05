"""Saisonrückblick (saison_rueckblick.py): Elo je Saison, Kränze, Aufsteiger."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import saison_rueckblick as sr
from pipeline.labels import GangResultat
from pipeline.ratings import EloModell, fahre_elo_durch


def _gang(eid, datum, a, b, ergebnis, typ="kantonal"):
    sym = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}[ergebnis]
    return GangResultat(event_id=eid, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
                        symbol_a=sym[0], note_a=None, symbol_b=sym[1], note_b=None,
                        ergebnis=ergebnis, fest_typ=typ)


def _saisons():
    gaenge = []
    for jahr in (2024, 2025, 2026):
        for f in range(sr.MIN_FESTE_SAISON):
            datum = f"{jahr}-05-{1 + f:02d}"
            # "a" gewinnt immer, "c" kommt 2026 neu dazu und gewinnt auch.
            gaenge.append(_gang(f"{jahr}-{f}", datum, "a", "b", "sieg_a"))
            if jahr == 2026:
                gaenge.append(_gang(f"{jahr}-{f}", datum, "b", "c", "sieg_b"))
    return gaenge


def test_elo_je_saison_endet_wie_fahre_elo_durch():
    gaenge = _saisons()
    je = sr.elo_je_saison(gaenge)
    modell, _ = fahre_elo_durch(gaenge)
    assert je[2026]["nachher"] == modell.ratings
    assert je[2024]["vorher"]["a"] == EloModell().get("a")      # vor dem ersten Gang: Startwert
    assert je[2026]["vorher"]["a"] == je[2025]["nachher"]["a"]  # Saisonübergang ohne Lücke
    assert je[2026]["neu"] == {"c"} and je[2024]["neu"] == {"a", "b"} and je[2025]["neu"] == set()


def test_rueckblick_aufsteiger_und_kraenze():
    gaenge = _saisons()
    schwinger = {s: SimpleNamespace(name=s.upper()) for s in "abc"}
    kraenze = sr.kraenze_je_saison([
        SimpleNamespace(datum="2026-05-01", schwinger_id="a", kranz=True),
        SimpleNamespace(datum="2026-06-01", schwinger_id="a", kranz=True),
        SimpleNamespace(datum="2026-06-01", schwinger_id="c", kranz=True),
        SimpleNamespace(datum="2026-06-01", schwinger_id="b", kranz=False),
    ])
    r = sr.rueckblick(gaenge, schwinger, kraenze=kraenze, ueberraschungen={"2026": [
        {"event_id": "2026-3", "datum": "2026-05-04", "sieger": "c", "verlierer": "b",
         "p_sieger": 0.1, "p_gestellt": 0.2}]})
    assert list(r["saisons"]) == ["2025", "2026"]    # die erste Saison (Einschwingen) fehlt
    s = r["saisons"]["2026"]
    assert s["n_feste"] == sr.MIN_FESTE_SAISON and s["n_gaenge"] == 2 * sr.MIN_FESTE_SAISON
    # Aufsteiger nur, wer schon vorher in den Daten war; der Neuling c steht bei den Neuen.
    assert [a["id"] for a in s["aufsteiger"]] == ["a", "b"] and [a["id"] for a in s["neue"]] == ["c"]
    assert s["aufsteiger"][0]["gewinn"] > 0 > s["aufsteiger"][1]["gewinn"]
    # Gewinn aus den ungerundeten Werten, darum bis 0.1 Abweichung zur Differenz der gerundeten.
    assert all(abs(a["gewinn"] - (a["elo_nachher"] - a["elo_vorher"])) <= 0.11
               for a in s["aufsteiger"] + s["neue"])
    assert s["kraenze"][0] == {"id": "a", "name": "A", "kraenze": 2}
    assert s["ueberraschungen"][0]["sieger_name"] == "C"


def test_kurze_jahre_zaehlen_nicht_als_saison():
    gaenge = _saisons() + [_gang("x", "2027-09-01", "a", "b", "sieg_a")]
    assert list(sr.rueckblick(gaenge, {})["saisons"]) == ["2025", "2026"]
