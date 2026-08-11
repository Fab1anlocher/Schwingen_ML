"""Identitätsauflösung zwischen den beiden Namensformen der Quelle (§4.4, R-5).

schlussgang.ch liefert denselben Schwinger in zwei Schreibweisen:

  * **Porträt** (JSON:API ``node/portrait``) -> ``"Vorname Nachname"``
    (aus ``field_portrait_first_name`` + ``field_portrait_last_name``)
  * **Statistik-PDF** (Ranglisten) -> ``"Nachname Vorname"``

Ein reiner Stringvergleich findet also NIE einen Treffer. Der frühere
Fuzzy-Matcher (Teilstring-Suche über alle Namen) hat das verdeckt, dabei aber
zwei Fehlerklassen erzeugt:

  1. **Gespaltene Identitäten** — dieselbe Person zweimal im Kader, einmal mit
     Physis aber ohne Gänge (Porträt), einmal mit allen Gängen aber ohne
     Physis (PDF-Stub). Real beobachtet: "Dominik Gasser" (0 Gänge) vs.
     "Gasser Dominik" (381 Gänge).
  2. **Falsche Verschmelzungen** — Teilstring-Treffer über Namenspräfixe
     ("Alex" in "Alexander") führten dazu, dass zwei verschiedene Gegner auf
     dieselbe ID zeigten; im Extremfall stand ein Schwinger gegen sich selbst.

Deshalb hier: ein **reihenfolgeunabhängiger, deterministischer** Schlüssel aus
der sortierten Token-Menge des Namens. Gleiche Tokens = gleiche Person,
unabhängig von der Reihenfolge. Kein Teilstring-Matching, kein Raten: ist ein
Schlüssel mehrdeutig (zwei verschiedene Personen gleichen Namens), wird er als
mehrdeutig gemeldet statt willkürlich aufgelöst.
"""
from __future__ import annotations

import re

from .schema import normalize_name, schwinger_key

# schlussgang.ch hängt bei Namensgleichheit einen Zähler an ("Lukas 1 Gisler",
# "Marcel (1) Stucki", "Thomas (2) Wüthrich"). Der Zähler steht nur im Porträt,
# nie im PDF -- als Token würde er den Abgleich verhindern.
_ZAEHLER_TOKEN = re.compile(r"^\(?\d{1,2}\)?$")


def namens_tokens(name: str) -> tuple[str, ...]:
    """Reihenfolgeunabhängiger Identitätsschlüssel eines Namens.

    >>> namens_tokens("Dominik Gasser") == namens_tokens("Gasser Dominik")
    True
    >>> namens_tokens("Lukas 1 Gisler") == namens_tokens("Gisler Lukas")
    True
    """
    tokens = [t for t in normalize_name(name).split() if not _ZAEHLER_TOKEN.match(t)]
    return tuple(sorted(tokens))


class Namensindex:
    """Namen -> Schwinger-ID, deterministisch und reihenfolgeunabhängig.

    ``mehrdeutig`` sammelt Token-Schlüssel, hinter denen mehr als eine Person
    steckt (echte Namensvettern). Für die wird bewusst NICHT aufgelöst --
    ``finde()`` gibt dort ``None`` zurück, damit die Gänge sichtbar als
    unauflösbar gezählt werden, statt still der falschen Person zuzufallen.
    """

    def __init__(self) -> None:
        self._nach_tokens: dict[tuple[str, ...], str] = {}
        self.mehrdeutig: set[tuple[str, ...]] = set()

    def __len__(self) -> int:
        return len(self._nach_tokens)

    def registriere(self, name: str, sid: str) -> None:
        key = namens_tokens(name)
        if not key:
            return
        vorhanden = self._nach_tokens.get(key)
        if vorhanden is None:
            self._nach_tokens[key] = sid
        elif vorhanden != sid:
            self.mehrdeutig.add(key)

    def finde(self, name: str) -> str | None:
        key = namens_tokens(name)
        if not key or key in self.mehrdeutig:
            return None
        return self._nach_tokens.get(key)


def baue_namensindex(eintraege: list[dict]) -> Namensindex:
    """Index aus Roh-Schwinger-Einträgen (``{"id": ..., "name": ...}``)."""
    idx = Namensindex()
    for e in eintraege:
        name = str(e.get("name") or "").strip()
        sid = str(e.get("id") or "").strip()
        if name and sid:
            idx.registriere(name, sid)
    return idx


def stub_id(name: str) -> str:
    """Deterministische ID für einen Schwinger ohne Porträt (nur PDF-Name).

    Basiert auf der sortierten Token-Menge, damit derselbe Schwinger unabhängig
    von der Schreibreihenfolge im PDF immer dieselbe ID bekommt.
    """
    return schwinger_key(" ".join(namens_tokens(name)), None)
