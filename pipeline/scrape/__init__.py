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
    """Fest-PDFs von schlussgang.ch laden (Cloud-tauglich, automatischer Finder).

    Entdeckt Feste automatisch über die JSON:API (discover.liste_feste). Fällt
    auf die manuelle ID-Liste in config zurück, falls die API nichts liefert.
    """
    from ..config import SCHLUSSGANG_EVENT_IDS, SCHLUSSGANG_MAX_FESTE, SCHLUSSGANG_NUR_AKTIV
    from .schlussgang_pdf import lade_von_url, lade_event

    schwinger: dict = {}
    events: list = []
    roh: list = []

    quellen = []  # (loader, kennung, name, datum, typ)
    try:
        from .discover import liste_feste
        feste = liste_feste(max_feste=SCHLUSSGANG_MAX_FESTE)
        if SCHLUSSGANG_NUR_AKTIV:
            feste = [f for f in feste if (f.get("typ") or "").lower().startswith("aktiv")]
        print(f"      Finder: {len(feste)} Feste mit Statistik-PDF entdeckt")
        for f in feste:
            quellen.append(("url", f["pdf_url"], f.get("name", ""), f.get("datum"), None))
    except Exception as e:  # noqa: BLE001
        print(f"      (Finder nicht verfügbar: {type(e).__name__}: {e})")

    if not quellen:  # Fallback: manuelle IDs
        for eid in SCHLUSSGANG_EVENT_IDS:
            quellen.append(("id", eid, "", None, None))

    for art, kennung, name, datum, typ in quellen:
        try:
            if art == "url":
                ev_id = "sg-" + kennung.rstrip("/").split("/")[-1].split("-statistic")[0].split(".")[0]
                s, ev, r = lade_von_url(kennung, ev_id, name, datum, typ)
            else:
                s, ev, r = lade_event(kennung)
        except Exception as e:  # noqa: BLE001 - fehlende/kaputte PDFs überspringen
            print(f"      (übersprungen {kennung}: {type(e).__name__}: {e})")
            continue
        if not r:
            continue
        events.append(ev)
        roh.extend(r)
        for sid, sw in s.items():
            schwinger.setdefault(sid, sw)
    print(f"      Total: {len(events)} Feste geparst, {len(roh)} Roh-Einträge, "
          f"{len(schwinger)} Schwinger")
    return schwinger, events, roh


def lade_kommende_feste():
    """Kommende Feste (FR-2) — Agenda-Anbindung folgt; bis dahin leer."""
    return []
