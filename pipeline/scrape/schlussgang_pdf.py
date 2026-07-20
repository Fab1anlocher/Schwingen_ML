"""Parser für die Ranglisten-PDFs von schlussgang.ch (§4.1, primäre Quelle).

    URL-Muster: backend-api.schlussgang.ch/.../<eventId>-statistic-final.pdf

Das PDF enthält je Schwinger die Gang-Resultate als Symbol (+/-/o) + Note
sowie das Punktetotal. Dieser Parser extrahiert Roh-Einträge (eine
Perspektive je Zeile) im Schema von labels.RohGangEintrag; die
Deduplizierung/Validierung passiert danach in labels.py (§4.3).

STATUS: Gerüst. Die konkrete Text-Extraktion muss gegen echte PDFs
kalibriert werden (Spaltenlayout variiert je Jahrgang, R-6). Für die
Text-Extraktion eignet sich `pdfplumber` (in requirements optional).
"""
from __future__ import annotations

import re
from typing import Iterable

from ..labels import RohGangEintrag

# Erwartete Symbole in der Gang-Spalte.
_SYMBOL_RE = re.compile(r"[+\-o]")
_NOTE_RE = re.compile(r"\d{1,2}\.\d{2}")
_LINE_RE = re.compile(
    r"^(?P<a>.+?)\s+(?:vs\.?|gegen|-)\s+(?P<b>.+?)\s+"
    r"(?P<sa>[+\-o])(?:/(?P<sb>[+\-o]))?"
    r"(?:\s+(?P<na>\d{1,2}\.\d{2})(?:/(?P<nb>\d{1,2}\.\d{2}))?)?$"
)


def pdf_url(event_id: str) -> str:
    """Event-ID -> PDF-URL (R-6: Mapping gegen Event-Seite verifizieren)."""
    return (
        "https://backend-api.schlussgang.ch/api/v1/documents/"
        f"{event_id}-statistic-final.pdf"
    )


def extrahiere_text(pdf_bytes: bytes) -> str:
    """PDF -> Text. Nutzt pdfplumber, wenn verfügbar."""
    try:
        import io
        import pdfplumber  # type: ignore
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "pdfplumber nicht installiert. `pip install pdfplumber` "
            "oder in requirements-pipeline.txt aktivieren."
        ) from e
    import io
    text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for seite in pdf.pages:
            text.append(seite.extract_text() or "")
    return "\n".join(text)


def parse_pdf_text(
    text: str, event_id: str, datum: str, fest_typ: str
) -> list[RohGangEintrag]:
    """Extrahiert Roh-Gang-Einträge aus dem PDF-Text.

    ACHTUNG: Diese Implementierung ist ein KALIBRIERUNGS-Gerüst. Das reale
    PDF-Layout (Schwinger-Block mit Gegner-Namen, Symbol, Note je Gang)
    muss anhand echter Dateien fixiert werden. Bis dahin gibt die Funktion
    eine leere Liste zurück, statt falsche Daten zu erzeugen (§4.3: lieber
    kein Label als ein falsches).
    """
    return parse_text_zeilen(text.splitlines(), event_id=event_id, datum=datum, fest_typ=fest_typ)


def parse_text_zeilen(
    lines: Iterable[str], *, event_id: str, datum: str, fest_typ: str
) -> list[RohGangEintrag]:
    """Pragmatischer Zeilenparser für kalibrierte Textauszüge.

    Erwartete Zeilen (Beispiel):
      "Max Muster vs Peter Beispiel +/o 10.00/8.75"
    """
    eintraege: list[RohGangEintrag] = []
    from ..schema import schwinger_key

    for raw in lines:
        line = raw.strip()
        if not line or not _SYMBOL_RE.search(line):
            continue
        m = _LINE_RE.match(re.sub(r"\s+", " ", line))
        if not m:
            continue
        a_name = m.group("a").strip()
        b_name = m.group("b").strip()
        a_id = schwinger_key(a_name, None)
        b_id = schwinger_key(b_name, None)
        sa = m.group("sa")
        sb = m.group("sb") or {"+": "o", "o": "+", "-": "-"}[sa]
        na = float(m.group("na")) if m.group("na") else None
        nb = float(m.group("nb")) if m.group("nb") else None
        eintraege.append(RohGangEintrag(event_id, datum, a_id, b_id, sa, na, fest_typ))
        eintraege.append(RohGangEintrag(event_id, datum, b_id, a_id, sb, nb, fest_typ))
    return eintraege
