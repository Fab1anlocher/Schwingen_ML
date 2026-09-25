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


# Marker in Schwinger.quellen für ein schlussgang.ch-Porträt. Stubs (nur aus
# der Statistik-PDF bekannt) tragen ihn nicht.
PORTRAET_MARKER = "portraet"


def hat_portraet(quellen) -> bool:
    """True, wenn der Schwinger ein Porträt hat.

    Bewusst über die Quelle und NICHT über den Kranzstatus: schlussgang.ch
    führt Porträts nur für Kranzer und besser (706 von 706 Porträts sind
    mindestens Kranzer), Stubs haben immer kranzstatus "kein". Ein
    Kranzstatus-Test wäre damit zirkulär. Die Quelle ist die eigentliche
    Information -- ob überhaupt Profildaten existieren.

    Gespiegelt in web/lib/inference.ts (hatPortraet).
    """
    return any(PORTRAET_MARKER in q for q in (quellen or []))


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
    # Gleichnamiger Porträt-Schwinger, von dem dieser Eintrag getrennt wurde
    # (s. namensvettern.py); sonst None.
    namensvetter_von: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


_ZAEHLER = re.compile(r"^\(?\d{1,2}\)?$")


def anzeigename(s: "Schwinger") -> str:
    """Name für die App, einheitlich "Vorname Nachname".

    Porträts liefern "Vorname Nachname", die Statistik-PDF (alle Schwinger
    ohne Porträt) "Nachname Vorname" -- in einer Liste stand dann "Samuel
    Giger" neben "Giger Ramon". Umgedreht wird nur, was eindeutig ist: genau
    zwei Namensteile (2160 von 2204 Namen ohne Porträt). Bei drei und mehr
    ist offen, was Vor- und was Nachname ist ("Di Pietro Loris" gegen "Botta
    Gian Joel") -- die bleiben, wie die Quelle sie schreibt. Ein
    Unterscheidungs-Zähler ("(2)") wandert ans Ende. Nur Anzeige: IDs und
    Namensauflösung arbeiten mit dem Originalnamen.
    """
    if hat_portraet(s.quellen) or s.namensvetter_von:
        return s.name  # schon "Vorname Nachname"
    teile = s.name.split()
    zaehler = [t for t in teile if _ZAEHLER.match(t)]
    namen = [t for t in teile if not _ZAEHLER.match(t)]
    if len(namen) != 2:
        return s.name
    return " ".join([namen[1], namen[0], *zaehler])


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
