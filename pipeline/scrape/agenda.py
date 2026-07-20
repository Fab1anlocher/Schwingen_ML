"""Agenda-Scraper: kommende Feste + veröffentlichte Paarungen (FR-2, §4.1).

    URL: schlussgang.ch/agenda

Liefert kommende Feste; falls Spitzenpaarungen veröffentlicht sind (AK-2.1),
werden diese mitgegeben, sonst greift AK-2.2 (Favoriten-/Kranz-Prognose) in
der Web-App.

STATUS: Gerüst. Selektoren gegen die reale HTML-Struktur zu fixieren (R-6).
"""
from __future__ import annotations


def scrape_agenda() -> list[dict]:
    """Kommende Feste im Artefakt-Schema.

    Schema je Fest:
        {
          "id": str, "name": str, "datum": "YYYY-MM-DD", "typ": str,
          "ort": str, "quelle": "schlussgang.ch/agenda",
          "paarungen": [ {"a_id": str, "b_id": str}, ... ]  # optional
        }
    """
    # TODO(R-6): HTML von schlussgang.ch/agenda laden (scrape.http.hole) und
    # Feste + ggf. Spitzenpaarungen extrahieren. Schwinger über Name+Jahrgang
    # auf stabile IDs mappen (schema.schwinger_key).
    return []
