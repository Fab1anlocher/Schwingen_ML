"""Scraper für die offiziellen ESV-Ranglisten (esv.ch/ranglisten).

Neue primäre Datenquelle (§4.1). Struktur:
    Index:            https://esv.ch/ranglisten/
    Einzelfest:       https://esv.ch/ranglisten/?anlass=<ANLASS_ID>

Die Ranglisten nutzen die offizielle Schwingen-Notation (Symbol +/-/o + Note),
identisch zur Label-Logik in labels.py (§4.3) — die bleibt unverändert gültig.

WICHTIG — Kalibrierung (R-6): Das exakte HTML-Layout (Tabellen-Klassen, wie
Gegner/Symbol/Note je Gang-Zelle kodiert sind) ist von dieser Umgebung aus
nicht abrufbar (Egress-Sperre). Die Parser hier sind an der üblichen ESV-
Ranglisten-Struktur orientiert und über `pipeline/scrape/recon_esv.py` gegen
eine echte Seite zu verifizieren. Bis dahin bleibt `--source synth` der
lauffähige Default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

from .http import hole
from ..config import ESV_BASE, FEST_TYPEN

QUELLE = "esv.ch"
from ..schema import Schwinger, Event, schwinger_key
from ..labels import RohGangEintrag


# --- URL-Hilfen ----------------------------------------------------------

def anlass_url(anlass_id: int | str, base: str = ESV_BASE) -> str:
    return f"{base}?anlass={anlass_id}"


# --- Index: Anlass-IDs entdecken ----------------------------------------

def finde_anlass_ids(index_html: str) -> list[str]:
    """Extrahiert alle `?anlass=<id>`-Verweise aus einer Index-/Listenseite.

    Höflich (NFR-4): wir folgen nur vom Verband publizierten Links, statt
    IDs blind durchzuiterieren.
    """
    ids: list[str] = []
    for m in re.finditer(r"[?&]anlass=(\d+)", index_html):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def lade_anlass_ids(base: str = ESV_BASE) -> list[str]:
    html = hole(base)
    return finde_anlass_ids(html)


# --- Rangliste eines Anlasses parsen ------------------------------------

@dataclass
class RanglistenZeile:
    startnummer: Optional[str]
    name: str
    jahrgang: Optional[int]
    verband: Optional[str]
    klub: Optional[str]
    kranz: bool
    gaenge: list[tuple[Optional[str], str, Optional[float]]]  # (gegner_startnr, symbol, note)
    total: Optional[float]


def _bs(html: str):
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "beautifulsoup4 nicht installiert. `pip install beautifulsoup4` "
            "oder requirements-pipeline.txt verwenden."
        ) from e
    return BeautifulSoup(html, "html.parser")


_SYMBOL_MAP = {
    "+": "+", "-": "-", "o": "o", "0": "o", "O": "o", "•": "o",
}
# Eine Gang-Zelle enthält typischerweise Gegner-Startnummer, Symbol und Note,
# z. B. "12 + 10.00" oder "12+10.0". Diese Regex ist gegen eine echte Seite
# zu verifizieren (recon_esv.py).
_ZELLE_RE = re.compile(
    r"(?P<gegner>\d{1,3})?\s*(?P<symbol>[+\-oO0•])\s*(?P<note>\d{1,2}[.,]\d{2})?"
)


def _parse_zelle(text: str) -> Optional[tuple[Optional[str], str, Optional[float]]]:
    text = text.strip()
    if not text:
        return None
    m = _ZELLE_RE.search(text)
    if not m or not m.group("symbol"):
        return None
    symbol = _SYMBOL_MAP.get(m.group("symbol"), "o")
    note = None
    if m.group("note"):
        note = float(m.group("note").replace(",", "."))
    return (m.group("gegner"), symbol, note)


def _jahr_aus_text(text: str) -> Optional[int]:
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def _fest_typ(name: str) -> str:
    n = name.lower()
    if "eidg" in n or "esaf" in n:
        return "eidgenoessisch"
    if "berg" in n or "brünig" in n or "bruenig" in n or "rigi" in n or "stoos" in n:
        return "berg"
    if "kantonal" in n:
        return "kantonal"
    if "teilverband" in n or "nordost" in n or "innerschw" in n or "berner" in n \
            or "nordwest" in n or "südwest" in n or "suedwest" in n:
        return "teilverband"
    return "regional"


def parse_event_meta(soup, anlass_id: str) -> Event:
    """Liest Fest-Name, Datum, Ort aus der Rangliste (Kopfbereich).

    KALIBRIERUNG (R-6): Selektor für den Titel ggf. anpassen. Fällt auf den
    Seitentitel / erste Überschrift zurück.
    """
    titel = ""
    for sel in ("h1", "h2", "title"):
        el = soup.find(sel)
        if el and el.get_text(strip=True):
            titel = el.get_text(strip=True)
            break
    jahr = _jahr_aus_text(titel) or _jahr_aus_text(soup.get_text()[:2000])
    datum = f"{jahr}-01-01" if jahr else "1900-01-01"
    # Datum präziser aus einem "dd.mm.yyyy" im Kopf.
    md = re.search(r"(\d{2})\.(\d{2})\.((?:19|20)\d{2})", soup.get_text()[:2000])
    if md:
        datum = f"{md.group(3)}-{md.group(2)}-{md.group(1)}"
    return Event(
        id=f"esv-{anlass_id}",
        name=titel or f"Anlass {anlass_id}",
        datum=datum,
        typ=_fest_typ(titel),
        quelle=QUELLE,
    )


def parse_rangliste(html: str, anlass_id: str) -> tuple[dict[str, Schwinger], Event, list[RohGangEintrag]]:
    """Parst eine ESV-Rangliste zu (Schwinger, Event, Roh-Gang-Einträgen).

    KALIBRIERUNG (R-6): Die Tabellenerkennung und Spaltenzuordnung ist gegen
    eine echte Seite zu verifizieren (recon_esv.py). Struktur unten spiegelt
    die übliche ESV-Rangliste: eine Ergebnistabelle mit einer Zeile je
    Schwinger und je Gang eine Zelle (Gegner-Startnr, Symbol, Note).
    """
    soup = _bs(html)
    event = parse_event_meta(soup, anlass_id)

    zeilen = _extrahiere_zeilen(soup)

    # Startnummer -> stabile Schwinger-ID (innerhalb des Anlasses eindeutig).
    schwinger: dict[str, Schwinger] = {}
    startnr_zu_id: dict[str, str] = {}
    for z in zeilen:
        sid = schwinger_key(z.name, z.jahrgang)
        startnr_zu_id[z.startnummer or z.name] = sid
        if sid not in schwinger:
            schwinger[sid] = Schwinger(
                id=sid,
                name=z.name,
                jahrgang=z.jahrgang,
                kranzstatus="kranzer" if z.kranz else "kein",
                teilverband=z.verband,
                schwingklub=z.klub,
                quellen=[QUELLE],
            )

    roh: list[RohGangEintrag] = []
    for z in zeilen:
        sid = schwinger_key(z.name, z.jahrgang)
        for (gegner_nr, symbol, note) in z.gaenge:
            gegner_id = startnr_zu_id.get(gegner_nr) if gegner_nr else None
            if not gegner_id:
                # Ohne identifizierbaren Gegner kann der Gang nicht dedupliziert
                # werden -> überspringen (lieber kein Label als ein falsches, §4.3).
                continue
            roh.append(RohGangEintrag(
                event_id=event.id,
                datum=event.datum,
                schwinger_id=sid,
                gegner_id=gegner_id,
                symbol=symbol,
                note=note,
                fest_typ=event.typ,
            ))

    return schwinger, event, roh


def _extrahiere_zeilen(soup) -> list[RanglistenZeile]:
    """Findet die Ergebnistabelle und extrahiert je Schwinger eine Zeile.

    KALIBRIERUNG (R-6): Heuristik — nimmt die Tabelle mit den meisten Zeilen.
    Spaltenzuordnung (Name/Jahrgang/Verband/Gänge/Total) an echtem Layout fixieren.
    """
    tabellen = soup.find_all("table")
    if not tabellen:
        return []
    tabelle = max(tabellen, key=lambda t: len(t.find_all("tr")))

    zeilen: list[RanglistenZeile] = []
    for tr in tabelle.find_all("tr"):
        zellen = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(zellen) < 4:
            continue
        # Namen-Spalte finden: erste Zelle mit Buchstaben und Leerzeichen.
        name_idx = next(
            (i for i, c in enumerate(zellen) if re.search(r"[A-Za-zäöüÄÖÜ]{2,}\s+[A-Za-zäöüÄÖÜ]", c)),
            None,
        )
        if name_idx is None:
            continue
        name = zellen[name_idx]
        startnr = zellen[0] if re.fullmatch(r"\d{1,3}", zellen[0]) else None
        jahrgang = None
        verband = None
        for c in zellen[name_idx + 1:name_idx + 4]:
            if jahrgang is None and re.fullmatch(r"(19|20)\d{2}", c):
                jahrgang = int(c)
            elif verband is None and re.search(r"[A-Za-zäöüÄÖÜ]", c):
                verband = c
        gaenge = [g for g in (_parse_zelle(c) for c in zellen) if g]
        total = None
        for c in reversed(zellen):
            mt = re.fullmatch(r"\d{2,3}[.,]\d{2}", c)
            if mt:
                total = float(c.replace(",", "."))
                break
        kranz = "kranz" in " ".join(zellen).lower()
        zeilen.append(RanglistenZeile(
            startnummer=startnr, name=name, jahrgang=jahrgang, verband=verband,
            klub=None, kranz=kranz, gaenge=gaenge, total=total,
        ))
    return zeilen


# --- Öffentliche Sammel-Funktion ----------------------------------------

def scrape_anlaesse(anlass_ids: list[str] | None = None, max_anzahl: int | None = None):
    """Lädt & parst mehrere Anlässe zu (schwinger, events, roh).

    anlass_ids=None -> IDs von der Index-Seite entdecken.
    """
    if anlass_ids is None:
        anlass_ids = lade_anlass_ids()
    if max_anzahl:
        anlass_ids = anlass_ids[:max_anzahl]

    alle_schwinger: dict[str, Schwinger] = {}
    events: list[Event] = []
    roh_gesamt: list[RohGangEintrag] = []

    for aid in anlass_ids:
        html = hole(anlass_url(aid))
        schwinger, event, roh = parse_rangliste(html, aid)
        events.append(event)
        roh_gesamt.extend(roh)
        for sid, s in schwinger.items():
            if sid not in alle_schwinger:
                alle_schwinger[sid] = s

    return alle_schwinger, events, roh_gesamt
