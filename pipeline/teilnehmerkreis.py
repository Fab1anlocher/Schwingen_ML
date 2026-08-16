"""Teilnehmerkreis eines kommenden Fests (FR-2).

An fast allen Schwingfesten startet nur, wer dem veranstaltenden Verband
angehört. Eine Favoritenliste, die das ignoriert, zeigt an jedem Fest
dieselben national stärksten Schwinger -- real passiert: am Nordwestschweizer
Schwingfest standen sechs Schwinger aus Bern und der Nordostschweiz.

Gemessen an den erfassten Festen 2023-2026 (Median-Anteil des grössten
Teilverbands unter den Teilnehmern):

    Kantonalfeste     93 %      Teilverbandsfeste  91 %
    Regionalfeste     85 %      Bergfeste          43 %
    Eidgenössische    28 %

Regionalfeste sind also genauso regional wie Kantonalfeste -- ihr Name nennt
aber nur einen Ort ("Herbstschwinget Unteriberg"), keinen Verband. Deshalb
wird der Kreis primär aus der **Vorausgabe desselben Fests** bestimmt: wer
letztes Jahr dort antrat, sagt den Kreis besser voraus als jede Namensregel.

Validiert über alle 165 aufeinanderfolgenden Fest-Paare der Datenbasis: bei
Schwelle 60 % ergeben sich 139 Einschränkungen, **keine einzige davon falsch**.
Bergfeste fallen dabei von selbst auf "offen" (43 % < 60 %), ohne Sonderregel.
"""
from __future__ import annotations

import collections
import re

# Anteil, ab dem ein Fest als auf einen Teilverband beschränkt gilt.
DOMINANZ_SCHWELLE = 0.60
# Weniger Teilnehmer mit bekanntem Teilverband -> Stichprobe zu klein.
MIN_TEILNEHMER_MIT_VERBAND = 10

# Fest-Name -> Teilverband, nach der ESV-Gliederung (5 Teilverbände,
# 29 Kantonal-/Gauverbände; dieselbe Quelle wie ``pipeline.kantone``).
# Nur Notnagel, wenn keine Vorausgabe vorliegt.
#
# Wortgrenzen sind zwingend: ohne sie steckt "urner" in "Solothurner" und
# vier Nordwestschweizer Feste galten als Innerschweizer.
TEILVERBAND_MUSTER: list[tuple[str, re.Pattern]] = [
    ("Bern", re.compile(
        r"\b(bern-jurassisch\w*|berner|emmentalisch\w*|mittelländisch\w*"
        r"|oberaargauisch\w*|seeländisch\w*|oberländisch\w*)\b")),
    ("Innerschweiz", re.compile(
        r"\b(innerschweizer|luzerner|ob-\s*und\s*nidwaldner|obwaldner|nidwaldner"
        r"|schwyzer|urner|zuger|tessiner)\b")),
    ("Nordostschweiz", re.compile(
        r"\b(nordostschweizer|appenzeller|glarner|bündner|schaffhauser"
        r"|st\.\s*galler|thurgauer|toggenburger|zürcher)\b")),
    ("Nordwestschweiz", re.compile(
        r"\b(nordwestschweizer|aargauer|baselbieter|baselstädtisch\w*"
        r"|baselland\w*|solothurner)\b")),
    ("Suedwestschweiz", re.compile(
        r"\b(südwestschweizer|freiburger|fribourgeois\w*|genfer|jurassisch\w*"
        r"|neuenburger|waadtländer|walliser|vaudois\w*|valaisan\w*)\b")),
]

# Fest-Typen mit gesamtschweizerischem Feld -- nie über den Namen einschränken.
OFFENE_TYPEN = {"berg", "eidgenoessisch"}


def basisname(name: str) -> str:
    """Fest-Name ohne Jahreszahl, als Schlüssel für wiederkehrende Feste."""
    return re.sub(r"\s*(19|20)\d{2}\s*$", "", name).strip().lower()


def teilverband_aus_name(name: str, typ: str) -> str | None:
    """Notnagel ohne Vorausgabe: Verband aus dem Fest-Namen."""
    if typ in OFFENE_TYPEN:
        return None
    n = name.lower()
    for teilverband, muster in TEILVERBAND_MUSTER:
        if muster.search(n):
            return teilverband
    return None


def _dominanter_verband(schwinger_ids, schwinger: dict) -> tuple[str | None, float, int]:
    verbaende = [
        schwinger[sid].teilverband
        for sid in schwinger_ids
        if sid in schwinger and getattr(schwinger[sid], "teilverband", None)
    ]
    if len(verbaende) < MIN_TEILNEHMER_MIT_VERBAND:
        return None, 0.0, len(verbaende)
    verband, anzahl = collections.Counter(verbaende).most_common(1)[0]
    return verband, anzahl / len(verbaende), len(verbaende)


def teilnehmer_je_fest(gaenge) -> dict[str, set]:
    teilnehmer: dict[str, set] = collections.defaultdict(set)
    for gang in gaenge:
        teilnehmer[gang.event_id].add(gang.schwinger_a_id)
        teilnehmer[gang.event_id].add(gang.schwinger_b_id)
    return teilnehmer


def bestimme_teilnehmerkreis(kommende: list[dict], events, gaenge, schwinger: dict) -> list[dict]:
    """Ergänzt jedes kommende Fest um ``teilverband`` + ``teilverband_quelle``.

    ``teilverband = None`` heisst offenes Feld, nicht "unbekannt": in beiden
    Fällen wird nicht gefiltert, aber die Quelle macht den Unterschied sichtbar.
    """
    teilnehmer = teilnehmer_je_fest(gaenge)
    nach_basis: dict[str, list] = collections.defaultdict(list)
    for event in events:
        nach_basis[basisname(event.name)].append((event.datum, event.id))

    for fest in kommende:
        verband = None
        quelle = "offen"
        vorausgaben = sorted(nach_basis.get(basisname(fest["name"]), []))
        if vorausgaben:
            letzte_id = vorausgaben[-1][1]
            kandidat, anteil, n = _dominanter_verband(teilnehmer.get(letzte_id, ()), schwinger)
            if kandidat and anteil >= DOMINANZ_SCHWELLE:
                verband, quelle = kandidat, "vorausgabe"
            elif kandidat:
                quelle = "vorausgabe_offen"
        if verband is None and quelle != "vorausgabe_offen":
            aus_name = teilverband_aus_name(fest["name"], fest.get("typ", ""))
            if aus_name:
                verband, quelle = aus_name, "namensmuster"
        fest["teilverband"] = verband
        fest["teilverband_quelle"] = quelle
    return kommende
