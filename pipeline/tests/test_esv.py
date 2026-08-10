"""Tests für den ESV-Ranglisten-Parser (esv.py).

Mechanische Absicherung gegen eine nachgebildete Ranglisten-Tabelle: prüft,
dass Event-Metadaten, Schwinger und Roh-Gang-Einträge korrekt extrahiert und
über die Label-Pipeline zu konsistenten Gängen dedupliziert werden.
Die Anpassung an das reale HTML-Layout erfolgt via recon_esv.py (R-6).
"""
from __future__ import annotations

import pytest

pytest.importorskip("bs4")

from pipeline.scrape import esv
from pipeline.labels import dedupliziere


HTML = """
<html><head><title>Solothurner Kantonal Schwingfest vom 04.05.2025</title></head>
<body><h1>Solothurner Kantonal Schwingfest vom 04.05.2025</h1>
<table>
<tr><th>Nr</th><th>Name</th><th>Jg</th><th>Verband</th><th>Gang1</th><th>Gang2</th><th>Total</th><th>Kranz</th></tr>
<tr><td>1</td><td>Muster Hans</td><td>1998</td><td>ISV</td><td>2 + 10.00</td><td>3 - 9.00</td><td>19.00</td><td>Kranz</td></tr>
<tr><td>2</td><td>Beispiel Fritz</td><td>1999</td><td>NOSV</td><td>1 o 8.75</td><td>3 + 9.75</td><td>18.50</td><td></td></tr>
<tr><td>3</td><td>Test Ueli</td><td>2000</td><td>BKSV</td><td>2 o 8.50</td><td>1 - 9.00</td><td>17.50</td><td></td></tr>
</table></body></html>
"""


def test_event_meta():
    schwinger, event, roh = esv.parse_rangliste(HTML, "6628")
    assert event.id == "esv-6628"
    assert event.datum == "2025-05-04"
    assert event.typ == "kantonal"
    assert event.quelle == "esv.ch"


def test_schwinger_extraktion():
    schwinger, event, roh = esv.parse_rangliste(HTML, "6628")
    assert len(schwinger) == 3
    namen = {s.name for s in schwinger.values()}
    assert {"Muster Hans", "Beispiel Fritz", "Test Ueli"} == namen
    hans = next(s for s in schwinger.values() if s.name == "Muster Hans")
    assert hans.jahrgang == 1998
    assert hans.kranzstatus == "kranzer"


def test_dedup_und_labels():
    schwinger, event, roh = esv.parse_rangliste(HTML, "6628")
    # 3 Paarungen x 2 Perspektiven = 6 Roh-Einträge.
    assert len(roh) == 6
    gaenge, warnungen = dedupliziere(roh)
    assert len(gaenge) == 3
    assert warnungen == []
    ergebnisse = sorted(g.ergebnis for g in gaenge)
    # Muster schlägt Test (gestellt? nein: Muster - Test -> gestellt),
    # Beispiel vs Muster -> Muster siegt, Beispiel vs Test -> Beispiel siegt.
    assert ergebnisse == ["gestellt", "sieg_a", "sieg_b"]


def test_zelle_parsing():
    assert esv._parse_zelle("2 + 10.00") == ("2", "+", 10.0)
    assert esv._parse_zelle("1 o 8.75") == ("1", "o", 8.75)
    assert esv._parse_zelle("3 - 9.00") == ("3", "-", 9.0)
    assert esv._parse_zelle("") is None


def test_finde_anlass_ids():
    html = '<a href="/ranglisten/?anlass=3694">ESAF</a> <a href="?anlass=6628">Solo</a>'
    assert esv.finde_anlass_ids(html) == ["3694", "6628"]
