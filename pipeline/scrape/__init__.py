"""Echte Datenquelle: ESV-Ranglisten (esv.ch/ranglisten) (§4.1).

Höflich und rate-limitiert (NFR-4): fester User-Agent, Delay zwischen
Requests, robots.txt respektieren (siehe http.py). Die Parser in esv.py sind
gegen eine echte Seite zu kalibrieren (recon_esv.py, R-6); bis dahin läuft die
Pipeline mit `--source synth`.
"""
from __future__ import annotations

# Anzahl der zu ladenden Anlässe im Standard-Lauf (None = alle von der Indexseite).
STANDARD_MAX_ANLAESSE = 30


def lade_echte_daten(anlass_ids: list[str] | None = None, max_anzahl: int | None = STANDARD_MAX_ANLAESSE):
    """Lädt & parst ESV-Ranglisten zu (schwinger, events, roh).

    Rückgabe-Schema identisch zu synth.erzeuge_datensatz(), damit
    run_pipeline die Quelle transparent tauschen kann.
    """
    from .esv import scrape_anlaesse
    return scrape_anlaesse(anlass_ids=anlass_ids, max_anzahl=max_anzahl)


def lade_kommende_feste():
    """Kommende Feste (FR-2). Die ESV-Ranglisten sind resultatorientiert;
    eine Agenda-Quelle wird separat angebunden. Bis dahin leer."""
    return []
