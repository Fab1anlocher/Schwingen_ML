"""Kader-Aufbau (zustandslos) und Rohdaten-Einlesen (mit Buchhaltung).

Deckt die zwei Fehler ab, an denen der produktive Lauf tatsächlich gescheitert
ist: der Kader hing am Stand des CI-Caches, und verworfene Roh-Einträge wurden
nirgends gezählt.
"""
from __future__ import annotations

import json

import pytest

from pipeline import scrape
from pipeline.roster import baue_roster, namen_aus_gaengen, pruefe_kader
from pipeline.scrape import lade_echte_daten
from pipeline.scrape.schlussgang_resultate import merge_events_raw_json, merge_gaenge_raw_json


def _gang(event_id, a, b, symbol="+", note=10.0):
    return {
        "event_id": event_id, "datum": "2026-05-01", "fest_typ": "kantonal",
        "schwinger_name": a, "gegner_name": b, "symbol": symbol, "note": note, "kranz": False,
    }


PORTRAIT = {
    "id": "dominik gasser|2000", "name": "Dominik Gasser", "jahrgang": 2000,
    "gewicht_kg": 100.0, "groesse_cm": 185.0, "kranzstatus": "kranzer",
    "portrait_image": "https://…/bild.jpg",  # interne Felder dürfen nicht in den Kader
}


class TestBaueRoster:
    def test_pdf_name_wird_dem_portraet_zugeordnet(self):
        """Der Kernfehler: "Gasser Dominik" (381 Gänge) und "Dominik Gasser"
        (0 Gänge, mit Physis) waren zwei Einträge für dieselbe Person."""
        eintraege, stat = baue_roster([PORTRAIT], [_gang("e1", "Gasser Dominik", "Muster Hans")])
        ids = {e["id"] for e in eintraege}
        assert "dominik gasser|2000" in ids
        assert stat["n_pdf_namen_auf_portraet_gemappt"] == 1
        assert stat["n_stubs"] == 1  # nur "Muster Hans"
        assert not pruefe_kader(eintraege)

    def test_interne_portraet_felder_landen_nicht_im_kader(self):
        eintraege, _ = baue_roster([PORTRAIT], [])
        assert not any(k.startswith("portrait_") for k in eintraege[0])

    def test_ist_zustandslos_und_deterministisch(self):
        """Zweimal derselbe Input -> byte-identischer Kader, unabhängig von
        vorherigen Läufen. Genau das war vorher nicht gegeben."""
        gaenge = [_gang("e1", "Gasser Dominik", "Muster Hans"), _gang("e1", "Muster Hans", "Zemp Silvan")]
        a, _ = baue_roster([PORTRAIT], gaenge)
        b, _ = baue_roster([PORTRAIT], list(reversed(gaenge)))
        assert a == b

    def test_gleiche_person_verschieden_geschrieben_ergibt_einen_eintrag(self):
        eintraege, stat = baue_roster(
            [], [_gang("e1", "Muster Hans", "X Y"), _gang("e1", "Hans Muster", "X Y")]
        )
        namen = sorted(e["name"] for e in eintraege)
        assert stat["n_stubs"] == 2, namen  # "Hans Muster" == "Muster Hans", plus "X Y"
        assert not pruefe_kader(eintraege)

    def test_mehrdeutiger_name_wird_gemeldet_nicht_geraten(self):
        """Zwei echte Namensvettern -- das PDF nennt nur den Namen, eine
        Zuordnung wäre geraten. Real im Kader: Roman Bucher (2002/2003),
        Christian Zemp (2000/2004), Jonas Wüthrich (2001/2003)."""
        portraits = [
            {"id": "lukas gisler|1998", "name": "Lukas 1 Gisler", "jahrgang": 1998},
            {"id": "lukas gisler|2003", "name": "Lukas 2 Gisler", "jahrgang": 2003},
        ]
        eintraege, stat = baue_roster(portraits, [_gang("e1", "Gisler Lukas", "Muster Hans")])
        assert stat["n_mehrdeutige_namen"] == 1
        assert stat["n_pdf_namen_auf_portraet_gemappt"] == 0  # nicht geraten
        # Auch KEIN Stub: den könnte lade_echte_daten nie auflösen (derselbe
        # mehrdeutige Schlüssel), er bliebe ein toter Kadereintrag.
        assert stat["n_pdf_namen_unaufloesbar"] == 1
        assert "Gisler Lukas" in stat["pdf_namen_unaufloesbar"]
        assert not any(e["id"].startswith("gisler lukas") for e in eintraege)
        assert {e["id"] for e in eintraege} == {
            "lukas gisler|1998", "lukas gisler|2003", "hans muster|?"}

    def test_name_mit_zaehler_bekommt_trotz_mehrdeutigkeit_einen_eintrag(self):
        """Der Zähler macht ihn unterscheidbar -- der Stub ist auflösbar."""
        portraits = [
            {"id": "jonas (1) wuthrich|2001", "name": "Jonas (1) Wüthrich", "jahrgang": 2001},
            {"id": "jonas wuthrich|2003", "name": "Jonas Wüthrich", "jahrgang": 2003},
        ]
        eintraege, stat = baue_roster(
            portraits, [_gang("e1", "Wüthrich Jonas (2)", "Muster Hans")]
        )
        assert stat["n_pdf_namen_unaufloesbar"] == 0
        assert any(e["name"] == "Wüthrich Jonas (2)" for e in eintraege)

    def test_namen_aus_gaengen_sammelt_beide_seiten(self):
        assert namen_aus_gaengen([_gang("e1", "A B", "C D")]) == {"A B", "C D"}


class TestLadeEchteDaten:
    @pytest.fixture
    def raw(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape, "RAW_DIR", tmp_path)
        def schreibe(name, obj):
            (tmp_path / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return schreibe

    def test_zaehlt_verworfene_eintraege_statt_still_zu_schlucken(self, raw):
        raw("schwinger.json", {"schwinger": [
            {"id": "a|1", "name": "Anna Muster"}, {"id": "b|2", "name": "Beat Kunz"}]})
        raw("events.json", {"events": [
            {"id": "schlussgang-1", "name": "Fest", "datum": "2026-05-01", "typ": "kantonal"}]})
        raw("gaenge.json", {"gaenge": [
            _gang("schlussgang-1", "Muster Anna", "Kunz Beat"),           # ok (gespiegelt)
            _gang("schlussgang-1", "Muster Anna", "Unbekannt Person"),    # Name nicht auflösbar
            _gang("schlussgang-1", "Muster Anna", "Anna Muster"),         # gegen sich selbst
            _gang("schlussgang-99", "Muster Anna", "Kunz Beat"),          # Fest unbekannt
        ]})
        _, events, roh, bericht = lade_echte_daten(mit_bericht=True)
        assert len(roh) == 1
        assert bericht.n_roh_gesamt == 4
        assert bericht.verworfen["name_nicht_aufloesbar"] == 1
        assert bericht.verworfen["schwinger_gegen_sich_selbst"] == 1
        assert bericht.verworfen["fest_unbekannt_oder_verworfen"] == 1
        assert bericht.verlustquote == 0.75
        assert "Unbekannt Person" in bericht.beispiele_unaufloesbar

    def test_testfeste_werden_aussortiert(self, raw):
        """"Testschwinget" (ev-2026-test) lag real in den ausgelieferten Daten
        und bestimmte dort sogar das jüngste Fest-Datum."""
        raw("schwinger.json", {"schwinger": [
            {"id": "a|1", "name": "Anna Muster"}, {"id": "b|2", "name": "Beat Kunz"}]})
        raw("events.json", {"events": [
            {"id": "schlussgang-1", "name": "Fest", "datum": "2026-05-01", "typ": "kantonal"},
            {"id": "ev-2026-test", "name": "Testschwinget", "datum": "2026-07-20", "typ": "kantonal"},
        ]})
        raw("gaenge.json", {"gaenge": [_gang("schlussgang-1", "Muster Anna", "Kunz Beat")]})
        _, events, _, bericht = lade_echte_daten(mit_bericht=True)
        assert [e.id for e in events] == ["schlussgang-1"]
        assert bericht.events_verworfen["fremde_id"] == 1

    def test_fehlende_rohdaten_geben_klaren_fehler(self, raw):
        raw("schwinger.json", {"schwinger": []})
        with pytest.raises(RuntimeError, match="fetch_raw"):
            lade_echte_daten()


class TestRawMerge:
    def test_merge_events_entfernt_fremde_ids(self, tmp_path):
        pfad = tmp_path / "events.json"
        pfad.write_text(json.dumps({"events": [
            {"id": "ev-2026-test", "name": "Testschwinget", "datum": "2026-07-20"},
            {"id": "schlussgang-1", "name": "Fest", "datum": "2026-05-01"},
        ]}), encoding="utf-8")
        zusammen = merge_events_raw_json(pfad, [])
        assert [e["id"] for e in zusammen] == ["schlussgang-1"]

    def test_merge_gaenge_ersetzt_neu_geladenes_fest_ohne_duplikate(self, tmp_path):
        pfad = tmp_path / "gaenge.json"
        pfad.write_text(json.dumps({"gaenge": [_gang("schlussgang-1", "A B", "C D")]}), encoding="utf-8")
        zusammen = merge_gaenge_raw_json(
            pfad, [_gang("schlussgang-1", "A B", "C D")], {"schlussgang-1"},
            bekannte_events={"schlussgang-1"},
        )
        assert len(zusammen) == 1

    def test_merge_gaenge_entfernt_verwaiste(self, tmp_path):
        pfad = tmp_path / "gaenge.json"
        pfad.write_text(json.dumps({"gaenge": [
            _gang("schlussgang-1", "A B", "C D"), _gang("ev-2026-test", "A B", "C D"),
        ]}), encoding="utf-8")
        zusammen = merge_gaenge_raw_json(pfad, [], set(), bekannte_events={"schlussgang-1"})
        assert [g["event_id"] for g in zusammen] == ["schlussgang-1"]


class TestBlaetternAbbruch:
    """Die Blätterschleife über die JSON:API darf nicht endlos laufen.

    Ohne `--event-limit` (Standard beim vollen Refetch) war sie nur durch das
    Verhalten der Gegenseite begrenzt: liefert die API bei wachsendem
    `page[offset]` immer dieselbe Seite, würden dieselben Feste endlos erneut
    geladen -- bei 2 s Rate-Limit je Statistik-PDF sind das Stunden.
    """

    @staticmethod
    def _antwort(nids):
        return json.dumps({"data": [
            {"attributes": {"drupal_internal__nid": n, "field_event_date": "2026-05-01",
                            "title": f"Fest {n}"}} for n in nids]})

    def test_stoppt_wenn_api_dieselbe_seite_wiederholt(self, monkeypatch):
        from pipeline.scrape import schlussgang_resultate as sr
        aufrufe = []

        def immer_gleich(url, **kw):
            aufrufe.append(url)
            return self._antwort(range(1, 51))  # ignoriert page[offset]

        monkeypatch.setattr(sr, "hole", immer_gleich)
        events = sr.scrape_events(seit_datum="2023-01-01", page_size=50)
        assert len(events) == 50            # nicht 50 * MAX_SEITEN
        assert len(aufrufe) == 2            # zweite Seite bringt nichts Neues -> Stopp

    def test_blaettert_normal_bis_zur_letzten_seite(self, monkeypatch):
        from pipeline.scrape import schlussgang_resultate as sr
        seiten = [self._antwort(range(1, 51)), self._antwort(range(51, 101)),
                  self._antwort(range(101, 131))]
        monkeypatch.setattr(sr, "hole", lambda url, **kw: seiten.pop(0))
        events = sr.scrape_events(seit_datum="2023-01-01", page_size=50)
        assert len(events) == 130
        assert len({e["id"] for e in events}) == 130   # keine Duplikate

    def test_seitenlimit_greift(self, monkeypatch):
        from pipeline.scrape import schlussgang_resultate as sr
        zaehler = iter(range(1, 10**6))
        monkeypatch.setattr(
            sr, "hole",
            lambda url, **kw: self._antwort([next(zaehler) for _ in range(50)]),
        )
        events = sr.scrape_events(seit_datum="2023-01-01", page_size=50)
        assert len(events) == 50 * sr.MAX_SEITEN   # hart begrenzt, kein Endlosloop
