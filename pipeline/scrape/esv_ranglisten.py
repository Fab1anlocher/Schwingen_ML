"""Parser für die Ranglisten von esv.ch (neue Primärquelle, §4.1).

Beispiel-URL: https://esv.ch/ranglisten/?anlass=7141
Enumeration je Jahr:  https://esv.ch/ranglisten/?jahr=2010  (listet alle anlass-IDs)

Warum esv.ch statt schlussgang.ch:
  - Stabile Schwinger-ID (``data-uid`` je Zeile) + Porträt-Slug -> eindeutige
    Identität ohne fragiles Namens-Matching.
  - Verband/Kanton steht bei JEDER Zeile (nicht nur bei Porträt-Schwingern).
  - Gang-für-Gang-Paarungen mit explizitem win/draw/loss + Punkten (kein
    Symbol-Raten wie beim PDF).
  - Ranglisten zurück bis 2006 -> deutlich mehr Historie als schlussgang.

Struktur einer Rangliste-Seite (an echten Seiten kalibriert):
  - Tab ``#anlass-tab-rangliste`` enthält je Kategorie mehrere
    ``div.rangliste-gang-panel[data-rl-gang=N]`` -- kumulierte Ranglisten nach
    Gang 1..N. NUR das Panel mit dem höchsten ``data-rl-gang`` ist die
    vollständige Schlussrangliste (enthält alle Gänge je Schwinger); die
    Zwischen-Panels sind Teilmengen und würden Gänge mehrfach zählen.
  - Je Schwinger eine ``tr.rang-row.rang-expandable[data-uid]`` mit Rang, Name
    (+ Porträt-Link), Kranzkennung (Karriere-Sterne), Verband, Punktetotal;
    darauf folgen ``tr.rang-detail-row[data-detail-uid]`` je Gang mit
    ``td.gang-score-cell.(win|draw|loss)``, ``span.gang-sym``, ``span.gang-pt``
    und dem Gegner (``td.gang-gegner`` + ``td.gang-verband``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_TITEL_RE = re.compile(r"^(?P<name>.*?)\s+vom\s+(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4})")
_ERGEBNIS_VON_SYMBOL = {"+": "win", "-": "draw", "o": "loss"}

# --- Fest-Stufen (Hierarchie, für Elo-Gewichtung; s. Projekt-Memory) --------
# Reihenfolge der Prüfung ist wichtig: eidgenössisch vor berg vor teilverband
# vor kantonal, sonst greifen allgemeinere Regeln zu früh.
_BERGFESTE = ("brünig", "bruenig", "rigi", "schwägalp", "schwaegalp",
              "schwarzsee", "stoos", "weissenstein")
_TEILVERBAND = ("innerschweizer", "nordostschweiz", "nordwestschweiz",
                "südwestschweiz", "suedwestschweiz", "bernisch-kantonal",
                "bernisch kantonal")
# Berner Gauverbandsfeste gelten als kantonal-gleichwertig (s. Hierarchie).
_KANTONAL_GAU = ("emmentalisch", "mittelländisch", "mittellaendisch",
                 "oberländisch", "oberlaendisch", "oberaargauisch",
                 "seeländisch", "seelaendisch", "berner-jura")


def fest_stufe(name: str) -> str:
    """Fest-Name -> Stufe: eidgenoessisch|berg|teilverband|kantonal|regional.

    Heuristik über Namens-Schlüsselwörter (+ fixe Berg-/Eidg.-Listen); bewusst
    konservativ, damit z.B. "Eidg. Schwinger-Fussballturnier" NICHT als
    eidgenössisches Schwingfest zählt. Gewichte/Feinschliff s. Elo-Integration.
    """
    n = (name or "").lower()
    eidg_kern = "schwingfest" in n or "älpler" in n or "aelpler" in n or "schwing- und" in n
    if (("eidgenöss" in n or "eidgenoess" in n or "eidg." in n) and eidg_kern) \
            or "kilchberg" in n or "unspunnen" in n:
        return "eidgenoessisch"
    if any(b in n for b in _BERGFESTE):
        return "berg"
    if any(t in n for t in _TEILVERBAND):
        return "teilverband"
    if "kantonal" in n or any(g in n for g in _KANTONAL_GAU):
        return "kantonal"
    return "regional"


@dataclass
class AnlassRef:
    """Ein Fest aus dem Jahres-Index (?jahr=YYYY)."""
    anlass_id: str
    name: str
    datum: Optional[str]          # ISO YYYY-MM-DD
    kategorie: str                # "aktiv" | "jung" | ...
    ort: Optional[str]
    stufe: str                    # aus fest_stufe(name)


def parse_jahr_index(html: str) -> list[AnlassRef]:
    """?jahr=YYYY-Index -> Liste aller Feste (mit Kategorie/Datum/Ort/Stufe).

    Die Kategorie kommt aus der tr-Klasse ("aktiv"/"jung"); für das Modell
    interessieren i.d.R. nur die aktiv-Feste (Aktivschwinger)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    refs: list[AnlassRef] = []
    for tr in soup.find_all("tr", id=re.compile(r"^anlass\d+")):
        anlass_id = tr.get("id", "")[len("anlass"):]
        klassen = tr.get("class") or []
        kategorie = klassen[0] if klassen else "?"
        name_td = tr.find("td", class_="name")
        name = name_td.get_text(" ", strip=True) if name_td else ""
        datum = None
        time_el = tr.find("time")
        if time_el and time_el.get("datetime"):
            datum = time_el["datetime"][:10]
        ort_td = tr.find("td", class_="ort")
        refs.append(
            AnlassRef(
                anlass_id=anlass_id,
                name=name,
                datum=datum,
                kategorie=kategorie,
                ort=ort_td.get_text(" ", strip=True) if ort_td else None,
                stufe=fest_stufe(name),
            )
        )
    return refs


def _slug_aus_href(href: Optional[str]) -> Optional[str]:
    """.../schwingerportraets/<slug>/ -> <slug> (stabiler Personen-Schlüssel)."""
    if not href:
        return None
    m = re.search(r"/schwingerportraets/([^/?#]+)", href)
    return m.group(1) if m else None


def _name_ohne_kennung(a_tag) -> str:
    """Reiner Name aus dem <a> (ohne die <span class=kranzkennung>-Sterne)."""
    for span in a_tag.find_all("span"):
        span.extract()
    return re.sub(r"\s+", " ", a_tag.get_text(" ", strip=True)).strip()


def _sterne(el) -> int:
    kk = el.find("span", class_="kranzkennung") if el else None
    return len(kk.get_text(strip=True)) if kk and set(kk.get_text(strip=True)) <= {"*"} else 0


@dataclass
class EsvSchwinger:
    uid: str
    slug: Optional[str]
    name: str
    verband: Optional[str]
    karriere_sterne: int          # lebenslange Kranzkennung (*/**/***), NICHT pro Fest
    rang: str                     # "1a", "3c", ...
    punkte_total: Optional[float]
    kranz_hier: bool              # Kranz an DIESEM Fest gewonnen


@dataclass
class EsvGang:
    schwinger_uid: str
    gegner_slug: Optional[str]
    gegner_name: str
    gegner_verband: Optional[str]
    symbol: str                   # +/-/o (aus win/draw/loss abgeleitet)
    ergebnis: str                 # "win" | "draw" | "loss" (aus schwinger_uid-Sicht)
    punkte: Optional[float]


@dataclass
class EsvRangliste:
    anlass_id: Optional[str]
    name: str
    datum: Optional[str]          # ISO YYYY-MM-DD
    schwinger: list[EsvSchwinger] = field(default_factory=list)
    gaenge: list[EsvGang] = field(default_factory=list)


def _float(text: str) -> Optional[float]:
    text = (text or "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_rangliste(html: str, anlass_id: Optional[str] = None) -> EsvRangliste:
    """esv.ch-Rangliste-HTML -> strukturierte Schlussrangliste (nur höchstes
    Gang-Panel je Kategorie, alle Gänge, dedupliziert später über labels)."""
    from bs4 import BeautifulSoup  # lokal, damit Import der Pipeline ohne bs4 nicht bricht

    soup = BeautifulSoup(html, "html.parser")

    name, datum = "", None
    title = soup.find("title")
    if title:
        m = _TITEL_RE.match(title.get_text(" ", strip=True))
        if m:
            name = m.group("name").strip()
            datum = f"{m.group('y')}-{m.group('m')}-{m.group('d')}"

    rl = EsvRangliste(anlass_id=anlass_id, name=name, datum=datum)

    tab = soup.find("div", id="anlass-tab-rangliste") or soup
    panels = tab.find_all("div", class_="rangliste-gang-panel")
    if not panels:
        return rl

    # Panels je Kategorie gruppieren wäre ideal; in der Praxis liegt hier eine
    # Kategorie (Aktive) mit Gang 1..N. Wir nehmen je vorkommender data-uid nur
    # das Panel mit dem höchsten Gang -> vollständigste Gang-Liste, keine
    # Doppelzählung der Zwischenränge.
    bestes_panel = max(panels, key=lambda p: int(p.get("data-rl-gang") or 0))

    for row in bestes_panel.find_all("tr", class_="rang-row"):
        uid = row.get("data-uid")
        if not uid:
            continue
        name_td = row.find("td", class_="col-name")
        a = name_td.find("a") if name_td else None
        sterne = _sterne(name_td)
        sname = _name_ohne_kennung(a) if a else (name_td.get_text(" ", strip=True) if name_td else "")
        slug = _slug_aus_href(a.get("href")) if a else None
        verband_td = row.find("td", class_="col-verband")
        rang_td = row.find("td", class_="col-rang")
        punkte_td = row.find("td", class_="col-punkte")
        kranz_td = row.find("td", class_="col-kranz")
        rl.schwinger.append(
            EsvSchwinger(
                uid=uid,
                slug=slug,
                name=sname,
                verband=verband_td.get_text(strip=True) if verband_td else None,
                karriere_sterne=sterne,
                rang=rang_td.get_text(strip=True) if rang_td else "",
                punkte_total=_float(punkte_td.get_text()) if punkte_td else None,
                kranz_hier=bool(kranz_td and kranz_td.find(["img", "i", "span"])),
            )
        )

    for det in bestes_panel.find_all("tr", class_="rang-detail-row"):
        uid = det.get("data-detail-uid")
        if not uid:
            continue
        # Massgeblich ist das gang-sym (+/-/o) aus Sicht des Zeilen-Schwingers,
        # NICHT die CSS-Klasse gang-score-cell win/draw/loss -- die ist bei esv
        # unzuverlässig (gestellt/verloren vertauscht; das Symbol stimmt dagegen
        # mit der Note überein und ergibt spiegelbildliche Perspektiven).
        sym_el = det.find("span", class_="gang-sym")
        symbol = sym_el.get_text(strip=True) if sym_el else ""
        ergebnis = _ERGEBNIS_VON_SYMBOL.get(symbol)
        if ergebnis is None:
            continue
        pt_el = det.find("span", class_="gang-pt")
        gegner_td = det.find("td", class_="gang-gegner")
        ga = gegner_td.find("a") if gegner_td else None
        gverband_td = det.find("td", class_="gang-verband")
        rl.gaenge.append(
            EsvGang(
                schwinger_uid=uid,
                gegner_slug=_slug_aus_href(ga.get("href")) if ga else None,
                gegner_name=_name_ohne_kennung(ga) if ga else (gegner_td.get_text(" ", strip=True) if gegner_td else ""),
                gegner_verband=gverband_td.get_text(strip=True) if gverband_td else None,
                symbol=symbol,
                ergebnis=ergebnis,
                punkte=_float(pt_el.get_text()) if pt_el else None,
            )
        )

    return rl
