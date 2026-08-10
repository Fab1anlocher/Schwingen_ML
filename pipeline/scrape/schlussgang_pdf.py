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


def _spalten_grenzen(woerter, seitenbreite: float) -> list[float]:
    """Linke Spaltenkanten der 3 Schwinger-Spalten.

    Bevorzugt die x-Positionen der Rang-Kopf-Tokens (1a, 2b, …); fällt sonst
    auf Drittel der Seitenbreite zurück (robust gegen ragged Randblöcke).
    """
    xs = sorted(round(w["x0"]) for w in woerter if _RANG_RE.match(w["text"]))
    kanten: list[float] = []
    for x in xs:
        if not kanten or x - kanten[-1] > 40:
            kanten.append(float(x))
    if len(kanten) >= 2:
        return kanten[:3]
    # Fallback: Drittel der Seite.
    return [0.0, seitenbreite / 3.0, 2.0 * seitenbreite / 3.0]


def _zeilen_je_spalte(woerter, kanten: list[float]) -> dict[int, list[list[dict]]]:
    """Ordnet Wörter Spalten (per x) und Zeilen (per y) zu."""
    if not kanten:
        return {}
    # Grenzen = linke Kanten der Folgespalten (Spalten sind breit: „Symbol Name Note").
    grenzen = kanten[1:]

    def spalte(x: float) -> int:
        for i, g in enumerate(grenzen):
            if x < g - 2:  # kleine Toleranz
                return i
        return len(kanten) - 1

    # Wörter je Spalte sammeln, dann in Zeilen clustern (Toleranz gegen leicht
    # unterschiedliche top-Werte innerhalb einer visuellen Zeile).
    proSpalte: dict[int, list[dict]] = {i: [] for i in range(len(kanten))}
    for w in woerter:
        proSpalte[spalte(w["x0"])].append(w)

    zeilen: dict[int, list[list[dict]]] = {}
    for c, ws in proSpalte.items():
        ws.sort(key=lambda w: (w["top"], w["x0"]))
        lines: list[list[dict]] = []
        ref = None
        for w in ws:
            if ref is None or w["top"] - ref > 3.5:
                lines.append([w])
                ref = w["top"]
            else:
                lines[-1].append(w)
        for ln in lines:
            ln.sort(key=lambda w: w["x0"])
        zeilen[c] = lines
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

    import os
    debug = os.environ.get("SCHWINGEN_PDF_DEBUG") == "1"

    with _open(pdf_bytes) as pdf:
        for pi, page in enumerate(pdf.pages):
            woerter = page.extract_words(x_tolerance=1.5, y_tolerance=2)
            kanten = _spalten_grenzen(woerter, float(page.width))
            if debug and pi == 0:
                print(f"[dbg] Seite1 breite={page.width} woerter={len(woerter)} kanten={kanten}")
                print("[dbg] erste Wörter:",
                      [(w["text"], round(w["x0"]), round(w["top"])) for w in woerter[:8]])
            zeilen = _zeilen_je_spalte(woerter, kanten)
            if debug and pi == 0:
                for zl in zeilen.get(0, [])[:6]:
                    tk = _text(zl)
                    print(f"[dbg] col0 line={tk} kopf={_parse_kopf(tk)} gang={_parse_gang(tk)}")
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
