"""Vorschau "kommende Feste" (FR-2).

Der Fixture-Datensatz bildet die zwei Feste vom 16.08.2026 nach, die in der
App fehlten (Schwägalp = Bergkranzfest, Mümliswil = Teilverbandsfest).
"""
from __future__ import annotations

from datetime import date

import pytest

from pipeline.scrape import agenda as A


def _api_antwort() -> dict:
    return {
        "data": [
            {
                "attributes": {
                    "drupal_internal__nid": 56001,
                    "title": "Schwägalp-Schwinget 2026",
                    "field_event_date": "2026-08-16T08:00:00+02:00",
                    "field_event_location": "Schwägalp",
                    "field_event_state": "published",
                },
                "relationships": {"field_category": {"data": {"id": "t-berg"}}},
            },
            {
                "attributes": {
                    "drupal_internal__nid": 56002,
                    "field_title_custom": "Nordwestschweizer Schwingfest Mümliswil 2026",
                    "title": "NWS Mümliswil",
                    "field_event_date": "2026-08-16",
                    "field_event_location": "Mümliswil",
                },
                "relationships": {"field_category": {"data": {"id": "t-tv"}}},
            },
            {   # Vergangenes Fest -> muss rausfallen.
                "attributes": {
                    "drupal_internal__nid": 55000,
                    "title": "Lüderen-Schwinget ob Langnau 2026",
                    "field_event_date": "2026-08-09",
                },
            },
            {   # Heute, aber bereits abgeschlossen -> muss rausfallen.
                "attributes": {
                    "drupal_internal__nid": 55001,
                    "title": "Testfest heute",
                    "field_event_date": "2026-08-15",
                    "field_event_state": "finished",
                },
            },
        ],
        "included": [
            {"id": "t-berg", "attributes": {"name": "Bergkranzfest"}},
            {"id": "t-tv", "attributes": {"name": "Teilverbandsfest"}},
        ],
    }


def test_jsonapi_liefert_die_beiden_feste_vom_16_august():
    feste = A.parse_jsonapi_kommende(_api_antwort(), heute=date(2026, 8, 15))
    assert [f["name"] for f in feste] == [
        "Nordwestschweizer Schwingfest Mümliswil 2026",
        "Schwägalp-Schwinget 2026",
    ]
    nach_name = {f["name"]: f for f in feste}
    # Der Typ kommt aus der Kategorie-Taxonomie, nicht aus der Namensheuristik:
    # "Schwägalp-Schwinget" enthält das Wort "Berg" gar nicht.
    assert nach_name["Schwägalp-Schwinget 2026"]["typ"] == "berg"
    assert nach_name["Nordwestschweizer Schwingfest Mümliswil 2026"]["typ"] == "teilverband"
    assert nach_name["Schwägalp-Schwinget 2026"]["id"] == "schlussgang-56001"
    assert nach_name["Schwägalp-Schwinget 2026"]["ort"] == "Schwägalp"


def test_vergangene_und_abgeschlossene_feste_fallen_raus():
    feste = A.parse_jsonapi_kommende(_api_antwort(), heute=date(2026, 8, 15))
    namen = {f["name"] for f in feste}
    assert "Lüderen-Schwinget ob Langnau 2026" not in namen
    assert "Testfest heute" not in namen


def test_kommende_url_filtert_zeitfenster_und_kategorie():
    url = A.kommende_url(0, 50, ab_datum="2026-08-15", bis_datum="2026-10-14",
                         typ="Aktivschwinger")
    assert "field_event_date" in url
    assert "2026-08-15" in url and "2026-10-14" in url
    assert "field_event_type" in url and "Aktivschwinger" in url
    assert "include=field_category" in url
    # Kein finished-Filter: kommende Feste sind gerade NICHT finished.
    assert "finished" not in url


@pytest.mark.parametrize(
    "name,erwartet",
    [
        ("Bergkranzfest Rigi", "berg"),
        ("Bergschwinget Sörenberg 2026", "berg"),
        ("Eidgenössisches Schwing- und Älplerfest", "eidgenoessisch"),
        ("Schwyzer Kantonalschwingfest Küssnacht", "kantonal"),
        # Regression: "berg" steckt mitten in "Werdtberg" -- ohne Wortgrenze
        # wurde dieses Kantonalfest als Bergkranzfest ausgewiesen. Der Name
        # selbst nennt keinen Typ, die Heuristik darf also nur "regional"
        # liefern; den echten Typ kennt allein die Kategorie-Taxonomie.
        ("Bern-Jurassisches Schwingfest Werdtberg 2026", "regional"),
        ("Sörenberg-Schwinget 2026", "regional"),
        ("Oberaargauisches Schwingfest Burgdorf 2026", "regional"),
        ("Schwägalp-Schwinget 2026", "regional"),
    ],
)
def test_typ_heuristik_respektiert_wortgrenzen(name, erwartet):
    assert A.typ_von_name(name) == erwartet


def test_ortsnamen_auf_berg_sind_keine_bergfeste():
    for name in ("Bern-Jurassisches Schwingfest Werdtberg 2026",
                 "Sörenberg-Schwinget 2026", "Schwarzenberg-Schwinget"):
        assert A.typ_von_name(name) != "berg"


def test_paarungen_nur_bei_echten_trennern():
    # Bindestriche in Fest-/Doppelnamen dürfen keine Paarung erzeugen.
    assert A._extract_paarungen("Bern-Jurassisches Schwingfest Werdtberg") == []
    assert A._extract_paarungen("Max Muster vs Peter Beispiel") == [
        ("Max Muster", "Peter Beispiel")
    ]
    assert A._extract_paarungen("Hans Held gegen Ueli Stark") == [("Hans Held", "Ueli Stark")]


def test_lade_kommende_faellt_auf_agenda_html_zurueck(monkeypatch):
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"Bergschwinget Test",
     "startDate":"2026-08-20T10:00:00+02:00","location":{"name":"Sörenberg"}}
    </script>
    """

    def fake_hole(url, **kw):
        if url.startswith(A.EVENT_LIST_URL):
            raise PermissionError("robots.txt verbietet Abruf")
        return html

    monkeypatch.setattr(A, "hole", fake_hole)
    feste, diagnose = A.lade_kommende(heute=date(2026, 8, 15))
    assert len(feste) == 1
    assert diagnose["pfad"] == "agenda_html"
    # Der Fehlschlag des Primärpfads bleibt dokumentiert, statt still zu sein.
    assert any("PermissionError" in (v.get("fehler") or "") for v in diagnose["versuche"])


def test_lade_kommende_meldet_beide_fehlschlaege(monkeypatch):
    def fake_hole(url, **kw):
        raise PermissionError("robots.txt verbietet Abruf")

    monkeypatch.setattr(A, "hole", fake_hole)
    feste, diagnose = A.lade_kommende(heute=date(2026, 8, 15))
    assert feste == []
    assert diagnose["pfad"] is None
    assert len(diagnose["versuche"]) == 2


def test_leeres_markup_wird_als_leer_nicht_als_fehler_gemeldet(monkeypatch):
    monkeypatch.setattr(
        A, "hole",
        lambda url, **kw: '{"data": []}' if url.startswith(A.EVENT_LIST_URL) else "<html></html>",
    )
    feste, diagnose = A.lade_kommende(heute=date(2026, 8, 15))
    assert feste == []
    assert [v["n"] for v in diagnose["versuche"]] == [0, 0]


def test_qualitaetsbericht_weist_leere_vorschau_als_warnung_aus():
    from pipeline.datenqualitaet import _zeilen

    leer = _zeilen({"datenqualitaet": {"kommende_feste": {
        "n": 0, "n_mit_paarungen": 0, "quelle": None,
        "versuche": [{"pfad": "jsonapi", "fehler": "PermissionError: robots.txt verbietet Abruf"}],
        "naechstes": None}}})
    text = "\n".join(leer)
    assert "Kommende Feste" in text
    assert "⚠️" in text
    # Der Grund muss im Bericht stehen, nicht nur im Log.
    assert "robots.txt verbietet Abruf" in text

    voll = "\n".join(_zeilen({"datenqualitaet": {"kommende_feste": {
        "n": 2, "n_mit_paarungen": 1, "quelle": "jsonapi",
        "versuche": [{"pfad": "jsonapi", "n": 2}], "naechstes": "2026-08-16"}}}))
    assert "✅ 2 Fest(e) geladen" in voll
    assert "jsonapi" in voll and "2026-08-16" in voll


def test_bericht_ueberlebt_report_ohne_datenbasis():
    """Regression: ``f"{'?':,}"`` warf ValueError und riss den Bericht mit."""
    from pipeline.datenqualitaet import _tausender, _zeilen

    assert _tausender(129990) == "129'990"
    assert _tausender(None) == "?"
    text = "\n".join(_zeilen({"datenqualitaet": {"anteil_unvollstaendiger_gaenge": 0.16}}))
    assert "Gänge (dedupliziert) | ?" in text
