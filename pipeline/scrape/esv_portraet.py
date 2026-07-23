"""Parser für die Schwinger-Porträts von esv.ch (Stammdaten + Karriere-Historie).

Beispiel: https://esv.ch/schwingerportraets/Staudenmann_Fabian_Guggisberg/

Liefert die vom System gewünschten Stammdaten (Geburtsdatum/Jahrgang, Gewicht,
Grösse, Senne/Turner, bevorzugte Schwünge, Karriere-Kranzzahl) sowie die zwei
Ergebnis-Tabellen (Eidgenössische Teilnahmen, Kränze) mit Rang/Punkte/Jahr/Fest.

Struktur (an echten Porträts kalibriert):
  - 1. Tabelle: Schlüssel-Wert-Stammdaten ("Name"|"Staudenmann", ...).
  - Tabellen ``table.potraitTable`` unter den Überschriften "Eidgenössische
    Teilnahmen" bzw. "Kränze": Spalten ``td.rang`` + ``td.unter_rang`` (a/b/c)
    + ``td.punkte`` + Jahr + Fest.

Hinweis NFR-5: esv.ch zeigt das volle Geburtsdatum; wir behalten intern nur den
Jahrgang für die Alters-Berechnung, exportiert wird kein Tagesdatum.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .esv_ranglisten import fest_stufe


@dataclass
class FestErgebnis:
    rang: str                     # "1a", "3", ...
    punkte: Optional[float]
    jahr: Optional[int]
    fest: str
    stufe: str                    # fest_stufe(fest)


@dataclass
class EsvPortraet:
    slug: str
    name: str = ""                # Nachname
    vorname: str = ""
    wohnort: Optional[str] = None
    geburtsdatum: Optional[str] = None   # ISO YYYY-MM-DD (intern)
    jahrgang: Optional[int] = None
    beruf: Optional[str] = None
    senne_turner: Optional[str] = None   # "senne" | "turner"
    gewicht_kg: Optional[float] = None
    groesse_cm: Optional[float] = None
    schwingklub: Optional[str] = None
    bevorzugte_schwuenge: list[str] = field(default_factory=list)
    kraenze_total: Optional[int] = None
    website: Optional[str] = None
    eidgenoessische: list[FestErgebnis] = field(default_factory=list)
    kraenze: list[FestErgebnis] = field(default_factory=list)


def _zahl(text: str, min_wert: float, max_wert: float) -> Optional[float]:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    if not m:
        return None
    w = float(m.group(0))
    return w if min_wert <= w <= max_wert else None


def _datum_iso(text: str) -> tuple[Optional[str], Optional[int]]:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text or "")
    if not m:
        return None, None
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}", int(y)


def _tabelle_ergebnisse(tabelle) -> list[FestErgebnis]:
    ergebnisse: list[FestErgebnis] = []
    for tr in tabelle.find_all("tr"):
        rang_td = tr.find("td", class_="rang")
        if rang_td is None:
            continue  # Kopfzeile
        unter = tr.find("td", class_="unter_rang")
        rang = rang_td.get_text(strip=True) + (unter.get_text(strip=True) if unter else "")
        punkte_td = tr.find("td", class_="punkte")
        # Jahr/Fest sind die zwei letzten schlichten Zellen ohne Sonderklasse.
        schlichte = [td for td in tr.find_all("td") if not td.get("class")]
        jahr = None
        fest = ""
        if len(schlichte) >= 2:
            jm = re.search(r"\d{4}", schlichte[-2].get_text())
            jahr = int(jm.group(0)) if jm else None
            fest = schlichte[-1].get_text(" ", strip=True)
        ergebnisse.append(
            FestErgebnis(
                rang=rang,
                punkte=_zahl(punkte_td.get_text(), 0, 100) if punkte_td else None,
                jahr=jahr,
                fest=fest,
                stufe=fest_stufe(fest),
            )
        )
    return ergebnisse


def parse_portraet(html: str, slug: str) -> EsvPortraet:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    p = EsvPortraet(slug=slug)

    tables = soup.find_all("table")
    if not tables:
        return p

    # 1) Stammdaten: erste Tabelle als Schlüssel-Wert.
    for tr in tables[0].find_all("tr"):
        zellen = tr.find_all(["th", "td"])
        if len(zellen) < 2:
            continue
        label = zellen[0].get_text(" ", strip=True).lower().rstrip(":")
        wert = zellen[1].get_text("\n", strip=True)
        if label == "name":
            p.name = wert
        elif label == "vorname":
            p.vorname = wert
        elif label == "wohnort":
            p.wohnort = wert or None
        elif label == "geburtsdatum":
            p.geburtsdatum, p.jahrgang = _datum_iso(wert)
        elif label == "beruf":
            p.beruf = wert or None
        elif label.startswith("senne"):
            p.senne_turner = "turner" if "turner" in wert.lower() else ("senne" if "senne" in wert.lower() else None)
        elif label == "gewicht":
            p.gewicht_kg = _zahl(wert, 40, 250)
        elif label in ("grösse", "groesse", "grosse"):
            p.groesse_cm = _zahl(wert, 140, 230)
        elif label == "schwingklub":
            p.schwingklub = wert or None
        elif label.startswith("bevorzugte"):
            p.bevorzugte_schwuenge = [s.strip() for s in re.split(r"[,\n/]+", wert) if s.strip()]
        elif label == "kränze" or label == "kraenze":
            m = re.search(r"\d+", wert)
            p.kraenze_total = int(m.group(0)) if m else None
        elif label == "website":
            p.website = wert or None

    # 2) Ergebnis-Tabellen (potraitTable) den Überschriften zuordnen.
    for tabelle in soup.find_all("table", class_="potraitTable"):
        head = tabelle.find_previous(["h2", "h3"])
        titel = head.get_text(" ", strip=True).lower() if head else ""
        eintraege = _tabelle_ergebnisse(tabelle)
        if "eidgen" in titel:
            p.eidgenoessische = eintraege
        elif "kränz" in titel or "kranz" in titel:
            p.kraenze = eintraege

    return p
