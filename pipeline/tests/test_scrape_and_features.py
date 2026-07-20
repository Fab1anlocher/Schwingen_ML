from __future__ import annotations

from datetime import date

from pipeline.features import FEATURE_NAMES
from pipeline.scrape.agenda import parse_agenda_html
from pipeline.scrape.schlussgang_pdf import parse_text_zeilen


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


def test_pdf_text_line_parser_generates_two_perspectives():
    lines = ["Max Muster vs Peter Beispiel +/o 10.00/8.75"]
    eintraege = parse_text_zeilen(
        lines, event_id="ev-1", datum="2026-07-20", fest_typ="kantonal"
    )
    assert len(eintraege) == 2
    assert eintraege[0].symbol == "+"
    assert eintraege[1].symbol == "o"


def test_feature_list_contains_preferred_swing_features():
    assert "schwung_overlap" in FEATURE_NAMES
    assert "schwung_count_diff" in FEATURE_NAMES
