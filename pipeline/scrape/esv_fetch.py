"""Fetch-Schicht für esv.ch mit Disk-Cache (Phase 2 der esv-Migration).

Der Backfill ab 2010 lädt einige Tausend Ranglisten-Seiten (~156 Aktiv-Feste
je Jahr). Damit das einmalig lokal, etappenweise und unterbrechbar läuft,
werden alle Seiten roh unter artifacts/raw/esv/ zwischengespeichert -- ein
erneuter Lauf holt nur noch neue/fehlende Feste. artifacts/raw/ ist nicht im
Repo (wird nicht committet), der Cache bleibt lokal.

Baut auf pipeline.scrape.http.hole (Rate-Limit + robots.txt, NFR-4) auf.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from .esv_ranglisten import AnlassRef, parse_jahr_index
from .http import hole

ESV_CACHE = config.ARTIFACTS_DIR / "raw" / "esv"
_JAHR_URL = "https://esv.ch/ranglisten/?jahr={jahr}"
_ANLASS_URL = "https://esv.ch/ranglisten/?anlass={anlass_id}"
_PORTRAET_URL = "https://esv.ch/schwingerportraets/{slug}/"


def _cache_hole(url: str, cache_datei: str, *, erzwinge_neu: bool = False) -> str:
    """GET mit Disk-Cache. Vorhandene Datei wird gelesen statt neu geladen."""
    pfad = ESV_CACHE / cache_datei
    if pfad.exists() and not erzwinge_neu:
        return pfad.read_text(encoding="utf-8")
    html = hole(url)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(html, encoding="utf-8")
    return html


def hole_jahr_index(jahr: int, *, erzwinge_neu: bool = False) -> str:
    # Laufendes Jahr immer neu holen (kommen laufend Feste dazu); Vergangenheit
    # ist statisch und darf aus dem Cache kommen.
    return _cache_hole(_JAHR_URL.format(jahr=jahr), f"jahr_{jahr}.html", erzwinge_neu=erzwinge_neu)


def hole_rangliste(anlass_id: str, *, erzwinge_neu: bool = False) -> str:
    return _cache_hole(
        _ANLASS_URL.format(anlass_id=anlass_id), f"anlass_{anlass_id}.html", erzwinge_neu=erzwinge_neu
    )


def hole_portraet(slug: str, *, erzwinge_neu: bool = False) -> str:
    return _cache_hole(_PORTRAET_URL.format(slug=slug), f"portraet_{slug}.html", erzwinge_neu=erzwinge_neu)


def feste_im_zeitraum(
    von_jahr: int, bis_jahr: int, *, nur_aktiv: bool = True, aktuelles_jahr: int | None = None
) -> list[AnlassRef]:
    """Alle Feste von von_jahr..bis_jahr (inkl.) aus den Jahres-Indizes.

    nur_aktiv filtert auf Aktivschwinger-Feste (Kategorie 'aktiv'); Jung-/
    Nachwuchsfeste interessieren das Modell nicht.
    """
    refs: list[AnlassRef] = []
    for jahr in range(von_jahr, bis_jahr + 1):
        html = hole_jahr_index(jahr, erzwinge_neu=(jahr == aktuelles_jahr))
        for r in parse_jahr_index(html):
            if not nur_aktiv or r.kategorie == "aktiv":
                refs.append(r)
    return refs
