from __future__ import annotations

from datetime import date

from pipeline.features import FEATURE_NAMES
from pipeline.scrape.agenda import parse_agenda_html
from pipeline.scrape.schlussgang_pdf import pdf_url, tabellen_bloecke


def test_agenda_jsonld_parse_event_and_pairings():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"Event",
        "name":"Bergschwinget Test",
        "startDate":"2099-08-01T10:00:00+02:00",
        "location":{"name":"Sörenberg"},
        "description":"Max Muster vs Peter Beispiel; Hans Held gegen Ueli Stark"
      }
      </script>
    </body></html>
    """
    events = parse_agenda_html(html, heute=date(2026, 1, 1))
    assert len(events) == 1
    ev = events[0]
    assert ev["typ"] == "berg"
    assert ev["datum"] == "2099-08-01"
    assert len(ev["paarungen_namen"]) == 2


def _wort(text: str, x0: float, top: float) -> dict:
    return {"text": text, "x0": x0, "top": top}


def test_statistic_pdf_table_parser_generates_two_perspectives():
    # Nachbildung des echten Statistik-Tabellen-Layouts: zwei Spalten,
    # je Schwinger eine Kopfzeile (Rang, Name, Total) + eine Gang-Zeile.
    woerter = [
        _wort("1", 10, 10), _wort("Muster", 20, 10), _wort("Max", 60, 10), _wort("9.75", 180, 10),
        _wort("+", 10, 25), _wort("Beispiel", 20, 25), _wort("Peter", 80, 25), _wort("9.75", 180, 25),
        _wort("2", 210, 10), _wort("Beispiel", 220, 10), _wort("Peter", 280, 10), _wort("8.75", 360, 10),
        _wort("o", 210, 25), _wort("Muster", 220, 25), _wort("Max", 280, 25), _wort("8.75", 360, 25),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert len(bloecke) == 2
    a = next(b for b in bloecke if b["name"] == "Muster Max")
    b = next(b for b in bloecke if b["name"] == "Beispiel Peter")
    assert a["total"] == 9.75 and b["total"] == 8.75
    assert a["gaenge"] == [{"symbol": "+", "gegner_name": "Beispiel Peter", "note": 9.75}]
    assert b["gaenge"] == [{"symbol": "o", "gegner_name": "Muster Max", "note": 8.75}]


def test_pdf_url_uses_node_id():
    assert pdf_url(52044) == (
        "https://www.schlussgang.ch/sites/default/files/event-ranking-list/52044-statistic-final.pdf"
    )


def test_feature_list_contains_preferred_swing_features():
    assert "schwung_overlap" in FEATURE_NAMES
    assert "schwung_count_diff" in FEATURE_NAMES
