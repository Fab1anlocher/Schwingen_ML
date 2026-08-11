"""Parser für die Ranglisten-PDFs von schlussgang.ch (§4.1, primäre Quelle).

    URL-Muster: www.schlussgang.ch/sites/default/files/event-ranking-list/<nid>-statistic-final.pdf
    (<nid> = drupal_internal__nid des Event-Knotens, s. schlussgang_resultate.py)

Das PDF ist eine "Statistische Tabelle": drei Spalten nebeneinander, pro
Schwinger ein Block aus Kopfzeile (Rang, Name, Kranz-Sterne, Punktetotal)
gefolgt von je einer Zeile pro Gang (Symbol, Gegnername, Note). Jeder reale
Gang erscheint darum zweimal im Dokument (einmal je Schwinger-Perspektive) -
das passt direkt auf labels.dedupliziere().

Kalibriert anhand echter PDFs (Moos-Schwinget Schönenberg 2026, 51 Schwinger;
Bergschwinget Klöntal 2026, 70 Schwinger): Spaltenpositionen sind fix, die
Summe der Gang-Noten je Schwinger stimmt exakt mit dem ausgewiesenen
Punktetotal überein (§4.3 Regel 4 lässt sich damit prüfen).
"""
from __future__ import annotations

import io
import re
from typing import Iterable

# Feste Spalten-x-Positionen des Tabellen-Templates (Punkte, aus PDF-Wortkoordinaten).
_SPALTEN = [(0.0, 200.0), (200.0, 380.0), (380.0, 600.0)]

_RANG_RE = re.compile(r"^\d+[a-z]?$")
_SYMBOL_RE = re.compile(r"^[+\-o]$")
_NOTE_RE = re.compile(r"^\d{1,2}\.\d{2}$")
_STERN_RE = re.compile(r"^\*{1,3}$")


def pdf_url(nid: int | str) -> str:
    """Node-ID -> URL der finalen Statistik-PDF."""
    return f"https://www.schlussgang.ch/sites/default/files/event-ranking-list/{nid}-statistic-final.pdf"


def extrahiere_woerter(pdf_bytes: bytes) -> list[list[dict]]:
    """PDF-Bytes -> Liste von Wortlisten je Seite (pdfplumber `extract_words()`)."""
    try:
        import pdfplumber  # type: ignore
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "pdfplumber nicht installiert. `pip install pdfplumber` "
            "oder requirements-pipeline.txt verwenden."
        ) from e
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [page.extract_words() for page in pdf.pages]


def _spalte(x0: float) -> int | None:
    for i, (lo, hi) in enumerate(_SPALTEN):
        if lo <= x0 < hi:
            return i
    return None


def _gruppiere_zeilen(woerter: list[dict], toleranz: float = 3.0) -> list[list[str]]:
    """Wörter (mit x0/top) zu Zeilen gruppieren (Token-Liste, x-sortiert)."""
    zeilen: list[list[dict]] = []
    aktuelle: list[dict] = []
    aktuelles_top: float | None = None
    for w in sorted(woerter, key=lambda w: (w["top"], w["x0"])):
        if aktuelles_top is None or abs(w["top"] - aktuelles_top) <= toleranz:
            aktuelle.append(w)
            aktuelles_top = w["top"] if aktuelles_top is None else aktuelles_top
        else:
            zeilen.append(aktuelle)
            aktuelle = [w]
            aktuelles_top = w["top"]
    if aktuelle:
        zeilen.append(aktuelle)
    return [[w["text"] for w in sorted(z, key=lambda w: w["x0"])] for z in zeilen]


def tabellen_bloecke(pages_words: Iterable[list[dict]]) -> list[dict]:
    """Statistik-PDF-Wörter -> Schwinger-Blöcke.

    Jeder Block: {"name": str, "total": float|None, "gaenge": [
        {"symbol": "+"|"-"|"o", "gegner_name": str, "note": float|None}, ...
    ]}
    """
    spalten_zeilen: list[list[list[str]]] = [[], [], []]
    for woerter in pages_words:
        eimer: list[list[dict]] = [[], [], []]
        for w in woerter:
            i = _spalte(w["x0"])
            if i is not None:
                eimer[i].append(w)
        for i in range(3):
            spalten_zeilen[i].extend(_gruppiere_zeilen(eimer[i]))

    bloecke: list[dict] = []
    for zeilen in spalten_zeilen:
        aktuell: dict | None = None
        for tokens in zeilen:
            if not tokens:
                continue
            erstes = tokens[0]
            if _RANG_RE.match(erstes) and len(tokens) >= 2:
                rest = tokens[1:]
                total = None
                if rest and _NOTE_RE.match(rest[-1]):
                    total = float(rest[-1])
                    rest = rest[:-1]
                # Sterne in der Kopfzeile = Kranz an DIESEM Fest (offizielle
                # PDF-Spalte "Kranz-Sterne", s. Moduldocstring) -- vorher
                # geparst und sofort verworfen; jetzt für die Kranz-Zählung
                # (Schwinger-Seite) festgehalten statt weggeworfen.
                kranz = bool(rest and _STERN_RE.match(rest[-1]))
                if kranz:
                    rest = rest[:-1]
                name = " ".join(rest)
                if not name:
                    # Ungültige/fremde Kopfzeile (z.B. Jahreszahl im Seitenkopf) verwerfen.
                    aktuell = None
                    continue
                if aktuell is not None:
                    bloecke.append(aktuell)
                aktuell = {"name": name, "total": total, "kranz": kranz, "gaenge": []}
            elif _SYMBOL_RE.match(erstes):
                if aktuell is None:
                    continue
                rest = tokens[1:]
                note = None
                if rest and _NOTE_RE.match(rest[-1]):
                    note = float(rest[-1])
                    rest = rest[:-1]
                if rest and _STERN_RE.match(rest[-1]):
                    rest = rest[:-1]
                gegner_name = " ".join(rest)
                if not gegner_name:
                    continue
                aktuell["gaenge"].append(
                    {"symbol": erstes, "gegner_name": gegner_name, "note": note}
                )
        if aktuell is not None:
            bloecke.append(aktuell)
    return bloecke


def parse_pdf_bytes(
    pdf_bytes: bytes, *, event_id: str, datum: str, fest_typ: str
) -> list[dict]:
    """Statistik-PDF -> Roh-Gang-Einträge im Schema von artifacts/raw/gaenge.json.

    Jeder Gang liegt zweimal vor (eine Zeile je Perspektive); die
    Zusammenführung/Validierung übernimmt weiterhin labels.dedupliziere()
    beim Laden über pipeline.scrape.lade_echte_daten().
    """
    bloecke = tabellen_bloecke(extrahiere_woerter(pdf_bytes))
    eintraege: list[dict] = []
    for block in bloecke:
        for gang in block["gaenge"]:
            eintraege.append(
                {
                    "event_id": event_id,
                    "datum": datum,
                    "fest_typ": fest_typ,
                    "schwinger_name": block["name"],
                    "gegner_name": gang["gegner_name"],
                    "symbol": gang["symbol"],
                    "note": gang["note"],
                    "kranz": block["kranz"],
                }
            )
    return eintraege


def schwinger_namen(pdf_bytes: bytes) -> list[str]:
    """Alle im PDF vorkommenden Schwinger-Namen (für Schwinger-Stub-Ergänzung)."""
    bloecke = tabellen_bloecke(extrahiere_woerter(pdf_bytes))
    return [b["name"] for b in bloecke if b["name"]]
