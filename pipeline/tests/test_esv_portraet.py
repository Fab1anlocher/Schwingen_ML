"""Tests für den esv.ch-Porträt-Parser (Stammdaten + Karriere-Historie)."""
from __future__ import annotations

import pytest

pytest.importorskip("bs4")

from pipeline.scrape.esv_portraet import parse_portraet

FIXTURE = """
<html><body>
<h1>Muster Hans (Bern)</h1>
<table>
  <tr><td>Name</td><td>Muster</td></tr>
  <tr><td>Vorname</td><td>Hans</td></tr>
  <tr><td>Wohnort</td><td>Bern</td></tr>
  <tr><td>Geburtsdatum</td><td>15.04.2000</td></tr>
  <tr><td>Beruf</td><td>Landwirt</td></tr>
  <tr><td>Senne / Turner</td><td>Senne</td></tr>
  <tr><td>Gewicht</td><td>115 kg</td></tr>
  <tr><td>Grösse</td><td>192 cm</td></tr>
  <tr><td>Schwingklub</td><td>Schwarzenburg</td></tr>
  <tr><td>Bevorzugte Schwünge</td><td>Kurz, Übersprung</td></tr>
  <tr><td>Kränze</td><td>71</td></tr>
</table>
<h2>Eidgenössische Teilnahmen</h2>
<table class="potraitTable">
  <tr><th>Rang</th><th>Punkte</th><th>Jahr</th><th>Fest</th></tr>
  <tr><td class="rang">2</td><td class="unter_rang">a</td><td class="punkte">76.75</td><td>2022</td><td>Eidgenössisches Schwingfest</td></tr>
</table>
<h2>Kränze</h2>
<table class="potraitTable">
  <tr><th>Rang</th><th>Punkte</th><th>Jahr</th><th>Fest</th></tr>
  <tr><td class="rang">1</td><td class="unter_rang"></td><td class="punkte">58.75</td><td>2026</td><td>Bergschwinget Rigi</td></tr>
  <tr><td class="rang">4</td><td class="unter_rang">b</td><td class="punkte">57.25</td><td>2026</td><td>Zürcher Kantonalschwingfest</td></tr>
</table>
</body></html>
"""


def test_stammdaten():
    p = parse_portraet(FIXTURE, "Muster_Hans_Bern")
    assert p.slug == "Muster_Hans_Bern"
    assert p.name == "Muster" and p.vorname == "Hans"
    assert p.wohnort == "Bern"
    assert p.geburtsdatum == "2000-04-15" and p.jahrgang == 2000
    assert p.beruf == "Landwirt"
    assert p.senne_turner == "senne"
    assert p.gewicht_kg == 115.0 and p.groesse_cm == 192.0
    assert p.schwingklub == "Schwarzenburg"
    assert p.bevorzugte_schwuenge == ["Kurz", "Übersprung"]
    assert p.kraenze_total == 71


def test_eidgenoessische_historie():
    p = parse_portraet(FIXTURE, "x")
    assert len(p.eidgenoessische) == 1
    e = p.eidgenoessische[0]
    assert e.rang == "2a" and e.punkte == 76.75 and e.jahr == 2022
    assert e.stufe == "eidgenoessisch"


def test_kraenze_historie_und_stufen():
    p = parse_portraet(FIXTURE, "x")
    assert len(p.kraenze) == 2
    assert p.kraenze[0].rang == "1" and p.kraenze[0].stufe == "berg"
    assert p.kraenze[1].rang == "4b" and p.kraenze[1].stufe == "kantonal"


def test_unplausible_koerpermasse_werden_verworfen():
    html = FIXTURE.replace("115 kg", "9 kg").replace("192 cm", "300 cm")
    p = parse_portraet(html, "x")
    assert p.gewicht_kg is None and p.groesse_cm is None


def test_leeres_portraet():
    p = parse_portraet("<html><body>nix</body></html>", "leer")
    assert p.name == "" and p.eidgenoessische == [] and p.kraenze == []
