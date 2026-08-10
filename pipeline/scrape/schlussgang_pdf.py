"""Parser für schlussgang.ch statistic-final.pdf (§4.1, primäre Quelle).

    URL: backend-api.schlussgang.ch/sites/default/files/event-ranking-list/<ID>-statistic-final.pdf

Diese PDFs stammen laut Fusszeile direkt vom ESV und sind vom Cloud-Runner
erreichbar (kein WAF) -> vollautomatisches Scraping möglich.

Layout (positionsbasiert, 3 Schwinger-Spalten nebeneinander):
    Kopfzeile je Schwinger:  "<Rang> <Name Vorname> <Total>"   z. B. "5a Schnellmann Alexander 56.25"
    darunter je Gang:        "<Symbol> <Gegner> [*/**/***] <Note>"  z. B. "+ Rusterholz Kevin 9.75"
Symbol: + = Sieg, - = Gestellt, o = Niederlage (§4.3). Sterne = Kranzstatus.

Der Parser clustert die Wörter über ihre x-Position in Spalten (robuster als
Text-Splitting), rekonstruiert je Spalte die Zeilen und leitet Roh-Gang-
Einträge ab, die danach von labels.py dedupliziert/validiert werden.
"""
from __future__ import annotations

import io
import re

from ..schema import Schwinger, schwinger_key
from ..labels import RohGangEintrag

_SYMBOLE = {"+", "-", "o", "O", "0"}
_RANG_RE = re.compile(r"^\d+[a-z]?$")           # 5a, 10c, 1 …
_NOTE_RE = re.compile(r"^\d{1,2}\.\d{2}$")      # 9.75, 10.00, 0.00
_STERN_RE = re.compile(r"^\*{1,3}$")
_KRANZ_STERNE = {"": "kein", "*": "kranzer", "**": "eidgenosse", "***": "koenig"}


def _open(pdf_bytes: bytes):
    import pdfplumber  # type: ignore
    return pdfplumber.open(io.BytesIO(pdf_bytes))


def _spalten_grenzen(woerter) -> list[float]:
    """Ermittelt die linken Spaltenkanten aus den Rang-Kopf-Tokens (3 Spalten)."""
    xs = sorted({round(w["x0"]) for w in woerter if _RANG_RE.match(w["text"])})
    if not xs:
        return []
    # Kanten zu ~3 Clustern zusammenfassen (Toleranz 25px).
    kanten: list[float] = []
    for x in xs:
        if not kanten or x - kanten[-1] > 25:
            kanten.append(x)
    return kanten


def _zeilen_je_spalte(woerter, kanten: list[float]) -> dict[int, list[list[dict]]]:
    """Ordnet Wörter Spalten (per x) und Zeilen (per y) zu."""
    if not kanten:
        return {}
    grenzen = [(kanten[i] + kanten[i + 1]) / 2 for i in range(len(kanten) - 1)]

    def spalte(x: float) -> int:
        for i, g in enumerate(grenzen):
            if x < g:
                return i
        return len(kanten) - 1

    aus: dict[int, dict[int, list[dict]]] = {i: {} for i in range(len(kanten))}
    for w in woerter:
        c = spalte(w["x0"])
        y = round(w["top"])
        aus[c].setdefault(y, []).append(w)
    zeilen: dict[int, list[list[dict]]] = {}
    for c, ys in aus.items():
        zeilen[c] = [sorted(ys[y], key=lambda w: w["x0"]) for y in sorted(ys)]
    return zeilen


def _text(zeile: list[dict]) -> list[str]:
    return [w["text"] for w in zeile]


def _parse_gang(tokens: list[str]):
    """'+ Rusterholz Kevin 9.75' -> (symbol, gegner, kranz, note)."""
    if not tokens or tokens[0] not in _SYMBOLE:
        return None
    symbol = "o" if tokens[0] in ("O", "0") else tokens[0]
    rest = tokens[1:]
    if not rest or not _NOTE_RE.match(rest[-1]):
        return None
    note = float(rest[-1]); rest = rest[:-1]
    kranz = ""
    if rest and _STERN_RE.match(rest[-1]):
        kranz = rest[-1]; rest = rest[:-1]
    gegner = " ".join(rest).strip()
    if not gegner or note == 0.0:
        return None
    return symbol, gegner, _KRANZ_STERNE.get(kranz, "kein"), note


def _parse_kopf(tokens: list[str]):
    """'5a Schnellmann Alexander 56.25' -> (name, kranz, total)."""
    if len(tokens) < 3 or not _RANG_RE.match(tokens[0]):
        return None
    if not _NOTE_RE.match(tokens[-1]) and not re.match(r"^\d+\.\d{2}$", tokens[-1]):
        return None
    total = float(tokens[-1]); rest = tokens[1:-1]
    kranz = ""
    if rest and _STERN_RE.match(rest[-1]):
        kranz = rest[-1]; rest = rest[:-1]
    name = " ".join(rest).strip()
    if not name:
        return None
    return name, _KRANZ_STERNE.get(kranz, "kein"), total


def parse_statistic_pdf(pdf_bytes: bytes, event_id: str, datum: str, fest_typ: str):
    """PDF -> (schwinger: dict[id,Schwinger], roh: list[RohGangEintrag])."""
    schwinger: dict[str, Schwinger] = {}
    roh: list[RohGangEintrag] = []

    def hole_id(name: str, kranz: str = "kein") -> str:
        sid = schwinger_key(name, None)
        if sid not in schwinger:
            schwinger[sid] = Schwinger(id=sid, name=name, kranzstatus=kranz,
                                       quellen=["schlussgang.ch"])
        elif kranz != "kein" and schwinger[sid].kranzstatus == "kein":
            schwinger[sid].kranzstatus = kranz
        return sid

    with _open(pdf_bytes) as pdf:
        for page in pdf.pages:
            woerter = page.extract_words(x_tolerance=1.5, y_tolerance=2)
            kanten = _spalten_grenzen(woerter)
            zeilen = _zeilen_je_spalte(woerter, kanten)
            for c in sorted(zeilen):
                aktiv: str | None = None
                for zeile in zeilen[c]:
                    toks = _text(zeile)
                    kopf = _parse_kopf(toks)
                    if kopf:
                        name, kranz, _total = kopf
                        aktiv = hole_id(name, kranz)
                        continue
                    if aktiv is None:
                        continue
                    g = _parse_gang(toks)
                    if not g:
                        continue
                    symbol, gegner, gk, note = g
                    gid = hole_id(gegner, gk)
                    if gid == aktiv:
                        continue
                    roh.append(RohGangEintrag(
                        event_id=event_id, datum=datum, schwinger_id=aktiv,
                        gegner_id=gid, symbol=symbol, note=note, fest_typ=fest_typ))
    return schwinger, roh
