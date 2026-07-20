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

from ..labels import RohGangEintrag

# Erwartete Symbole in der Gang-Spalte.
_SYMBOL_RE = re.compile(r"[+\-o]")
_NOTE_RE = re.compile(r"\d{1,2}\.\d{2}")


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
    eintraege: list[RohGangEintrag] = []
    # TODO(R-6): Blockstruktur je Schwinger parsen:
    #   - Schwinger-Name + Jahrgang/Verein (-> stabiler Key, schema.schwinger_key)
    #   - je Gang: Gegner-Name, Symbol (+/-/o), Note
    #   - Punktetotal je Schwinger -> labels.validiere_punktetotal(...)
    # Danach RohGangEintrag(event_id, datum, schwinger_id, gegner_id, symbol, note, fest_typ).
    return eintraege
