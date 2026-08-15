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
# "Marcel (1) Stucki"). Er steht MEIST nur im Porträt, gelegentlich aber auch
# im PDF ("Wüthrich Jonas (1)", "Wüthrich Jonas (2)" -- real beobachtet).
# Darum wird er beim Abgleich zweistufig behandelt, s. Namensindex.finde().
_ZAEHLER_TOKEN = re.compile(r"^\(?\d{1,2}\)?$")


def namens_tokens(name: str, *, mit_zaehler: bool = False) -> tuple[str, ...]:
    """Reihenfolgeunabhängiger Identitätsschlüssel eines Namens.

    ``mit_zaehler=False`` (Standard) ignoriert den Unterscheidungs-Zähler --
    damit findet "Gisler Lukas" das Porträt "Lukas 1 Gisler".
    ``mit_zaehler=True`` behält ihn und trennt damit echte Namensvettern.

    >>> namens_tokens("Dominik Gasser") == namens_tokens("Gasser Dominik")
    True
    >>> namens_tokens("Lukas 1 Gisler") == namens_tokens("Gisler Lukas")
    True
    >>> namens_tokens("Wüthrich Jonas (1)", mit_zaehler=True) != \
        namens_tokens("Wüthrich Jonas (2)", mit_zaehler=True)
    True
    """
    tokens = normalize_name(name).split()
    if not mit_zaehler:
        tokens = [t for t in tokens if not _ZAEHLER_TOKEN.match(t)]
    return tuple(sorted(tokens))


def hat_zaehler(name: str) -> bool:
    """Trägt der Name einen Unterscheidungs-Zähler ("(1)", "1")?

    Ein vorhandener Zähler ist ein positiver Hinweis der Quelle, WELCHER von
    mehreren Gleichnamigen gemeint ist. Sein Fehlen ist dagegen KEIN Hinweis --
    darum wird nur auf vorhandene Zähler hin aufgelöst, nie auf ihr Fehlen.
    """
    return any(_ZAEHLER_TOKEN.match(t) for t in normalize_name(name).split())


class Namensindex:
    """Namen -> Schwinger-ID, deterministisch und reihenfolgeunabhängig.

    ``mehrdeutig`` sammelt Token-Schlüssel, hinter denen mehr als eine Person
    steckt (echte Namensvettern). Für die wird bewusst NICHT aufgelöst --
    ``finde()`` gibt dort ``None`` zurück, damit die Gänge sichtbar als
    unauflösbar gezählt werden, statt still der falschen Person zuzufallen.
    """

    def __init__(self) -> None:
        self._nach_tokens: dict[tuple[str, ...], str] = {}
        self._mit_zaehler: dict[tuple[str, ...], str] = {}
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
        if hat_zaehler(name):
            self._mit_zaehler.setdefault(namens_tokens(name, mit_zaehler=True), sid)

    def finde(self, name: str) -> str | None:
        """Name -> Schwinger-ID, oder None wenn nicht eindeutig auflösbar.

        Zuerst über den Zähler, falls der Name einen trägt: die Quelle sagt
        damit selbst, welcher von mehreren Gleichnamigen gemeint ist
        (PDF "Wüthrich Jonas (1)" == Porträt "Jonas (1) Wüthrich"). Erst danach
        über die zählerfreie Form -- und die nur, wenn sie eindeutig ist.
        """
        if hat_zaehler(name):
            treffer = self._mit_zaehler.get(namens_tokens(name, mit_zaehler=True))
            if treffer is not None:
                return treffer
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
    von der Schreibreihenfolge im PDF immer dieselbe ID bekommt. Ein
    Unterscheidungs-Zähler bleibt erhalten -- sonst fielen "Wüthrich Jonas (1)"
    und "Wüthrich Jonas (2)" auf dieselbe ID zusammen.
    """
    return schwinger_key(" ".join(namens_tokens(name, mit_zaehler=True)), None)
