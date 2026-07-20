"""Label-Ableitung, Deduplizierung und Validierung (§4.3, KRITISCH).

Das Symbol im PDF ist die massgebliche Ergebnisquelle aus Sicht des
jeweiligen Schwingers:
    +  -> Sieg
    -  -> Gestellt (unentschieden)
    o  -> Niederlage
Die Note ist ein separates Qualitätsmerkmal, KEIN Ersatz fürs Symbol.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Symbol aus Sicht eines Schwingers -> Ergebnis für ihn.
SYMBOL_ERGEBNIS = {
    "+": "sieg",
    "-": "gestellt",
    "o": "niederlage",
}

# Konsistenzregel: Symbol A vs. Symbol B muss spiegelbildlich passen (§4.3 Regel 4).
SPIEGEL = {
    "+": "o",   # Sieg gegenüber Niederlage
    "o": "+",
    "-": "-",   # Gestellt gegenüber Gestellt
}


class LabelError(ValueError):
    """Parsing-/Konsistenzfehler bei der Label-Ableitung."""


@dataclass
class RohGangEintrag:
    """Ein Gang-Eintrag wie im PDF: EINE Perspektive (ein Schwinger, ein Symbol).

    Jeder Gang erscheint im PDF zweimal (beide Perspektiven), daher werden
    diese Einträge über (event, {a,b}) zusammengeführt (dedupliziert).
    """
    event_id: str
    datum: str
    schwinger_id: str          # Perspektiven-Inhaber
    gegner_id: str
    symbol: str                # aus Sicht von schwinger_id
    note: Optional[float]
    fest_typ: str


def ergebnis_aus_symbolen(symbol_a: str, symbol_b: str) -> str:
    """Leitet das kanonische 3-Klassen-Label (sieg_a/gestellt/sieg_b) ab.

    A ist massgeblich; B wird nur zur Konsistenzprüfung genutzt.
    """
    if symbol_a not in SYMBOL_ERGEBNIS:
        raise LabelError(f"Unbekanntes Symbol A: {symbol_a!r}")
    if symbol_b not in SYMBOL_ERGEBNIS:
        raise LabelError(f"Unbekanntes Symbol B: {symbol_b!r}")
    if SPIEGEL[symbol_a] != symbol_b:
        raise LabelError(
            f"Inkonsistente Symbole: A={symbol_a!r} erwartet B={SPIEGEL[symbol_a]!r}, "
            f"gefunden B={symbol_b!r}"
        )
    erg_a = SYMBOL_ERGEBNIS[symbol_a]
    if erg_a == "sieg":
        return "sieg_a"
    if erg_a == "niederlage":
        return "sieg_b"
    return "gestellt"


def _paar_schluessel(event_id: str, a: str, b: str) -> tuple[str, tuple[str, str]]:
    """Ungerichteter Schlüssel je Gang: Reihenfolge der IDs egal."""
    return (event_id, tuple(sorted((a, b))))


def dedupliziere(eintraege: list[RohGangEintrag]) -> tuple[list["GangResultat"], list[str]]:
    """Führt beide PDF-Perspektiven pro Gang zusammen (§4.3 Regel 2).

    Rückgabe: (deduplizierte Gänge, Liste von Warnungen/Fehlern).
    Jeder Gang wird genau einmal gespeichert; die kanonische A-Seite ist die
    lexikographisch kleinere Schwinger-ID (deterministisch, reproduzierbar).
    """
    gruppen: dict = {}
    for e in eintraege:
        k = _paar_schluessel(e.event_id, e.schwinger_id, e.gegner_id)
        gruppen.setdefault(k, []).append(e)

    resultate: list[GangResultat] = []
    warnungen: list[str] = []

    for (event_id, (id_low, id_high)), grp in gruppen.items():
        # Perspektiven nach Inhaber indexieren.
        von = {e.schwinger_id: e for e in grp}

        e_low = von.get(id_low)
        e_high = von.get(id_high)

        if e_low is None or e_high is None:
            # Nur eine Perspektive vorhanden -> aus vorhandenem Symbol ableiten,
            # aber als unvollständig markieren (keine Kreuzvalidierung möglich).
            vorhanden = e_low or e_high
            gespiegelt_symbol = SPIEGEL.get(vorhanden.symbol)
            if gespiegelt_symbol is None:
                warnungen.append(
                    f"{event_id} {id_low}/{id_high}: unbekanntes Symbol, verworfen"
                )
                continue
            if vorhanden is e_low:
                symbol_a, note_a = e_low.symbol, e_low.note
                symbol_b, note_b = gespiegelt_symbol, None
            else:
                symbol_a, note_a = gespiegelt_symbol, None
                symbol_b, note_b = e_high.symbol, e_high.note
            warnungen.append(
                f"{event_id} {id_low}/{id_high}: nur eine Perspektive vorhanden"
            )
        else:
            symbol_a, note_a = e_low.symbol, e_low.note
            symbol_b, note_b = e_high.symbol, e_high.note

        try:
            ergebnis = ergebnis_aus_symbolen(symbol_a, symbol_b)
        except LabelError as err:
            warnungen.append(f"{event_id} {id_low}/{id_high}: {err} -> verworfen")
            continue

        resultate.append(
            GangResultat(
                event_id=event_id,
                datum=grp[0].datum,
                schwinger_a_id=id_low,
                schwinger_b_id=id_high,
                symbol_a=symbol_a,
                note_a=note_a,
                symbol_b=symbol_b,
                note_b=note_b,
                ergebnis=ergebnis,
                fest_typ=grp[0].fest_typ,
            )
        )

    return resultate, warnungen


def validiere_punktetotal(
    schwinger_id: str,
    einzelnoten: list[float],
    ausgewiesenes_total: float,
    toleranz: float = 0.01,
) -> Optional[str]:
    """Validierung §4.3 Regel 4: Summe der Noten = ausgewiesenes Total.

    Rückgabe: Fehlermeldung bei Abweichung, sonst None.
    """
    summe = round(sum(einzelnoten), 2)
    if abs(summe - ausgewiesenes_total) > toleranz:
        return (
            f"Punktetotal-Abweichung für {schwinger_id}: "
            f"Summe {summe} != ausgewiesen {ausgewiesenes_total} (Parsing-Fehler)"
        )
    return None


@dataclass
class GangResultat:
    """Deduplizierter Gang, kanonische Form (id_low = A)."""
    event_id: str
    datum: str
    schwinger_a_id: str
    schwinger_b_id: str
    symbol_a: str
    note_a: Optional[float]
    symbol_b: str
    note_b: Optional[float]
    ergebnis: str
    fest_typ: str
