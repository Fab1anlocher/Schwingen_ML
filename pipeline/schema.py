"""Kanonisches Datenschema (§4.2).

Alle Quellen werden auf diese Entitäten gemappt. Schwinger-Identität ist
stabil über (normalisierter Name + Jahrgang), da IDs quellenübergreifend
differieren (§4.1, R-5).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional


# Kranzstatus als Ordinalskala (für Differenz-Merkmal, ML-4).
KRANZSTATUS_ORDINAL = {
    "kein": 0,
    "kranzer": 1,       # hat mindestens einen Kranz
    "eidgenosse": 2,    # Kranz am Eidgenössischen
    "koenig": 3,        # Schwingerkönig
}


def normalize_name(name: str) -> str:
    """Namensnormalisierung für Identitätsauflösung (R-5).

    Entfernt Akzente, Mehrfach-Leerzeichen, vereinheitlicht Gross/Klein.
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def schwinger_key(name: str, jahrgang: Optional[int]) -> str:
    """Stabiler Identitätsschlüssel: normalisierter Name + Jahrgang.

    Trennt Namensdubletten unterschiedlicher Personen (§4.4, R-5).
    """
    jg = str(jahrgang) if jahrgang else "?"
    return f"{normalize_name(name)}|{jg}"


@dataclass
class Schwinger:
    id: str                                  # = schwinger_key(...)
    name: str
    jahrgang: Optional[int] = None
    groesse_cm: Optional[float] = None
    gewicht_kg: Optional[float] = None
    kranzstatus: str = "kein"                # key aus KRANZSTATUS_ORDINAL
    teilverband: Optional[str] = None
    kanton: Optional[str] = None
    schwingklub: Optional[str] = None
    senne_turner: Optional[str] = None       # "senne" | "turner" | None
    schwinger_seit: Optional[int] = None
    bevorzugte_schwuenge: list[str] = field(default_factory=list)
    quellen: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    id: str
    name: str
    datum: str                               # ISO-8601 (YYYY-MM-DD)
    typ: str                                 # key aus config.FEST_TYPEN
    quelle: str
    ort: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Gang:
    """Ein Gang (Bout), dedupliziert auf genau einen Eintrag (§4.3 Regel 2)."""
    event_id: str
    datum: str                               # ISO-8601, aus Event (für zeitl. Sortierung)
    schwinger_a_id: str
    schwinger_b_id: str
    symbol_a: str                            # "+" | "-" | "o"
    note_a: Optional[float]
    symbol_b: str
    note_b: Optional[float]
    ergebnis: str                            # key aus config.KLASSEN
    fest_typ: str

    def to_dict(self) -> dict:
        return asdict(self)
