"""Echte Datenquellen (§4.1).

Primär und VOLLAUTOMATISCH (Cloud/GitHub Actions): schlussgang.ch
statistic-final.pdf (kein WAF gegen Cloud-IPs; PDFs stammen laut Fusszeile
vom ESV). Sekundär (nur vom Heimrechner, WAF): esv.ch/ranglisten.

Höflich und rate-limitiert (NFR-4): fester User-Agent, Delay, robots.txt.
"""
from __future__ import annotations


def lade_echte_daten(source: str = "schlussgang"):
    """Lädt & parst echte Daten zu (schwinger, events, roh).

    Rückgabe-Schema identisch zu synth.erzeuge_datensatz(), damit run_pipeline
    die Quelle transparent tauschen kann.
    """
    if source in ("schlussgang", "scrape"):
        return _lade_schlussgang()
    if source == "esv":
        from .esv import scrape_anlaesse
        return scrape_anlaesse(max_anzahl=30)
    raise ValueError(f"Unbekannte echte Quelle: {source}")


def _lade_schlussgang():
    """Fest-PDFs von schlussgang.ch laden (Cloud-tauglich)."""
    from ..config import SCHLUSSGANG_EVENT_IDS
    from .schlussgang_pdf import lade_event

    schwinger: dict = {}
    events: list = []
    roh: list = []
    for eid in SCHLUSSGANG_EVENT_IDS:
        try:
            s, ev, r = lade_event(eid)
        except Exception as e:  # noqa: BLE001 - fehlende/kaputte PDFs überspringen
            print(f"      (Fest {eid} übersprungen: {type(e).__name__}: {e})")
            continue
        events.append(ev)
        roh.extend(r)
        for sid, sw in s.items():
            schwinger.setdefault(sid, sw)
        print(f"      Fest {eid}: {ev.name} — {len(r)} Roh-Einträge")
    return schwinger, events, roh


def lade_kommende_feste():
    """Kommende Feste (FR-2) — Agenda-Anbindung folgt; bis dahin leer."""
    return []
