"""Echte Datenquellen-Scraper (§4.1).

Diese Module sind mit den REALEN URL-Mustern angelegt, aber bewusst höflich
und rate-limitiert (NFR-4): fester User-Agent, Delay zwischen Requests,
robots.txt respektieren. Für den MVP läuft die Pipeline mit --source synth;
sobald diese Scraper gegen echte Feste verifiziert sind (R-6), liefert
`lade_echte_daten()` denselben Schematyp wie synth.erzeuge_datensatz().
"""
from __future__ import annotations


def lade_echte_daten():
    """Bündelt Portrait-, Event- und PDF-Scraper zu (schwinger, events, roh).

    Noch nicht gegen Live-Feste verifiziert (R-6). Struktur steht; die
    Parser in schlussgang_pdf.py / agenda.py sind zu vervollständigen und
    gegen echte PDFs zu testen, bevor produktiv geschaltet wird.
    """
    raise NotImplementedError(
        "Echte Scraper noch nicht aktiviert. MVP nutzt --source synth. "
        "Siehe pipeline/scrape/schlussgang_pdf.py und agenda.py."
    )


def lade_kommende_feste():
    """Kommende Feste + veröffentlichte Paarungen (FR-2, agenda.py)."""
    from .agenda import scrape_agenda
    return scrape_agenda()
