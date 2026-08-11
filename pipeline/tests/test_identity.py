"""Tests der Identitätsauflösung (§4.4, R-5).

Die Beispiele sind KEINE erfundenen Fixtures, sondern real in
``artifacts/schwinger.json`` gefundene gespaltene Identitäten: dieselbe
Person stand einmal als Porträt (mit Physis, 0 Gänge) und einmal als
PDF-Stub (mit allen Gängen, ohne Physis) im ausgelieferten Kader.
"""
from __future__ import annotations

from pipeline.identity import Namensindex, baue_namensindex, namens_tokens, stub_id


class TestNamensTokens:
    def test_reihenfolge_egal(self):
        # schlussgang.ch: Porträt "Vorname Nachname", Statistik-PDF "Nachname Vorname"
        assert namens_tokens("Dominik Gasser") == namens_tokens("Gasser Dominik")
        assert namens_tokens("Jonas Wüthrich") == namens_tokens("Wüthrich Jonas")

    def test_akzente_und_gross_klein_egal(self):
        assert namens_tokens("Jonas Wüthrich") == namens_tokens("wuthrich jonas")

    def test_zaehler_suffix_wird_ignoriert(self):
        # Porträt-Namen bei Namensgleichheit: "Lukas 1 Gisler", "Marcel (1) Stucki"
        assert namens_tokens("Lukas 1 Gisler") == namens_tokens("Gisler Lukas")
        assert namens_tokens("Marcel (1) Stucki") == namens_tokens("Stucki Marcel")

    def test_mehrteilige_vornamen(self):
        assert namens_tokens("Gian Maria Odermatt") == namens_tokens("Odermatt Gian Maria")

    def test_verschiedene_personen_bleiben_verschieden(self):
        assert namens_tokens("Arnold Robin") != namens_tokens("Arnold Livio")

    def test_kein_teilstring_matching(self):
        """Der alte Fuzzy-Matcher hielt "Alex" für "Alexander"."""
        assert namens_tokens("Huber Alex") != namens_tokens("Alexander Huber")


class TestNamensindex:
    def test_findet_gespiegelten_namen(self):
        idx = baue_namensindex([{"id": "dominik gasser|2000", "name": "Dominik Gasser"}])
        assert idx.finde("Gasser Dominik") == "dominik gasser|2000"

    def test_unbekannter_name_gibt_none(self):
        idx = baue_namensindex([{"id": "a|1", "name": "Dominik Gasser"}])
        assert idx.finde("Robin Arnold") is None

    def test_mehrdeutigkeit_wird_nicht_geraten(self):
        """Zwei echte Namensvettern -> lieber unaufgelöst als falsch zugeordnet."""
        idx = baue_namensindex([
            {"id": "lukas gisler|1998", "name": "Lukas 1 Gisler"},
            {"id": "lukas gisler|2003", "name": "Lukas 2 Gisler"},
        ])
        assert idx.finde("Gisler Lukas") is None
        assert namens_tokens("Lukas 1 Gisler") in idx.mehrdeutig

    def test_gleiche_person_mehrfach_registriert_ist_keine_mehrdeutigkeit(self):
        idx = Namensindex()
        idx.registriere("Dominik Gasser", "dominik gasser|2000")
        idx.registriere("Gasser Dominik", "dominik gasser|2000")
        assert not idx.mehrdeutig
        assert idx.finde("Gasser Dominik") == "dominik gasser|2000"

    def test_leerer_name_stoert_nicht(self):
        idx = baue_namensindex([{"id": "a|1", "name": "  "}, {"id": "b|2", "name": "Beat Muster"}])
        assert idx.finde("Muster Beat") == "b|2"


class TestStubId:
    def test_ist_reihenfolgeunabhaengig(self):
        # Derselbe Schwinger darf nie zwei IDs bekommen, egal wie das PDF ihn schreibt.
        assert stub_id("Gasser Dominik") == stub_id("Dominik Gasser")

    def test_verschiedene_personen_verschiedene_ids(self):
        assert stub_id("Arnold Robin") != stub_id("Arnold Livio")
