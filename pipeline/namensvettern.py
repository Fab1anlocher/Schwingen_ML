"""Namensvettern trennen, die der Namensindex zu EINER Person macht.

Der Namensindex (identity.py) löst einen Namen nur auf, wenn er eindeutig
ist. "Eindeutig" heisst dort aber nur: EIN Porträt dieses Namens. Hat ein
gleichnamiger zweiter Schwinger kein Porträt, landen seine Gänge und Kränze
still beim Porträt-Schwinger. Real gefunden: Samuel Giger (Thurgau,
Eidgenosse) bekam die Gänge eines Luzerners gleichen Namens dazu --
Escholzmatt, Wolhusen, Engelberg, Luzerner Kantonal --, an fünf Tagen stand
er sogar an zwei Festen gleichzeitig im Sägemehl. Ebenso Dominik Gasser,
Marco Ulrich, Marco Fankhauser, Jonas Müller u. a. Das verfälscht Elo,
Kopf-an-Kopf, Kränze und Feste beider Personen.

Die Schlussrangliste führt zu jedem Teilnehmer den Schwingklub. Jeder Klub
gehört genau einem Teilverband an (aus den Porträts gelernt, s.
ranglisten.verband_ueber_klub). Zwei Belege trennen:

1. **Jahrgang-Zusatz**: die Rangliste schreibt Namensvettern mit Jahrgang
   ("Giger Samuel (2004)"). Weicht er vom Jahrgang des Porträts ab, ist es
   sicher eine andere Person.
2. **Klub eines anderen Teilverbands, durchmischt**: startet "derselbe"
   Schwinger an Festen für Klubs zweier Teilverbände, und wechseln sich die
   beiden in der zeitlichen Abfolge ständig ab -- oder stehen sie am selben
   Tag an zwei Festen --, sind es zwei Personen. Ein Klubwechsel ist dagegen
   ein Block: vorher der eine, nachher der andere Verband, höchstens noch
   einmal zurück. Gemessen an den echten Daten trennt das scharf: echte
   Namensvettern 20-38 Wechsel und immer auch Feste am selben Tag, Klub-
   wechsler (Théo Rogivue, Flurin Eymann u. a.) 2-5 Wechsel und nie am selben
   Tag. Die Gruppe im Verband des Porträts bleibt beim Porträt, die andere
   bekommt einen eigenen Eintrag.

Umgekehrt löst die Rangliste auch **mehrdeutige** Namen auf, die der Index
bewusst offen lässt (zwei Porträts gleichen Namens, z. B. Roman Bucher 2002
und 2003): steht am Fest nur einer der beiden, sagt der Jahrgang-Zusatz oder
der Verband seines Klubs, welcher. Vorher gingen alle ihre Gänge verloren.

Zurück kommt eine Zuordnung (Fest, Namens-Tokens) -> ID. Sie gilt für
die Gänge (Statistik-PDF) UND die Ranglisten-Einträge desselben Fests. Wo
beide Gleichnamigen am selben Fest antraten, lässt sich über den Namen
allein nicht sagen, wem welcher Gang gehört -- dort bleibt es beim Alten
(gezählt im Bericht).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .identity import namens_tokens
from .schema import hat_portraet

_JAHRGANG_RE = re.compile(r"^(.*?)\s*\((\d{4})\)$")

# Klub -> Teilverband nur, wenn die Porträt-Mitglieder des Klubs eindeutig
# einem Verband angehören (Namensvettern-Einträge selbst sind in der Minderheit
# und stimmen nicht mit).
MIN_KLUB_STIMMEN = 3
MIN_KLUB_ANTEIL = 0.8
# Ab so vielen Festen gilt eine Verbandsgruppe als eigene Person -- ein
# einzelnes Gastspiel-Fest mit falsch erkanntem Klub reicht nicht.
MIN_FESTE_JE_GRUPPE = 2
# Ohne Fest am selben Tag: so viele Wechsel zwischen den beiden Gruppen in der
# zeitlichen Abfolge braucht es mindestens -- absolut und als Anteil dessen,
# was zufälliges Durchmischen erwarten liesse (2mn/(m+n) bei m und n Festen).
MIN_WECHSEL = 6
MIN_WECHSEL_ANTEIL = 0.5

_VERBAND_KURZ = {
    "Bern": "be", "Innerschweiz": "is", "Nordostschweiz": "nos",
    "Nordwestschweiz": "nws", "Suedwestschweiz": "sws",
}


def _basisname(name: str) -> tuple[str, int | None]:
    m = _JAHRGANG_RE.match(name.strip())
    if m:
        return m.group(1), int(m.group(2))
    return name.strip(), None


def _vetter_id(tokens: tuple[str, ...], zusatz: str) -> str:
    return f"{' '.join(tokens)}|{zusatz}"


def sind_zwei_personen(heim: list[tuple[str, str]], fremd: list[tuple[str, str]]) -> bool:
    """Zwei Gruppen von Auftritten (Datum, Fest) -- durchmischt oder nacheinander?

    Zwei Personen, wenn eine am selben Tag an einem ANDEREN Fest stand als die
    andere, oder wenn die zeitliche Abfolge oft zwischen den Gruppen wechselt.
    """
    heim_je_tag: dict[str, set] = defaultdict(set)
    for datum, eid in heim:
        heim_je_tag[datum].add(eid)
    if any(heim_je_tag.get(datum, set()) - {eid} for datum, eid in fremd):
        return True
    folge = sorted([(d, 0) for d, _ in heim] + [(d, 1) for d, _ in fremd])
    wechsel = sum(1 for (_, a), (_, b) in zip(folge, folge[1:]) if a != b)
    m, n = len(heim), len(fremd)
    erwartet = 2 * m * n / (m + n)
    return wechsel >= MIN_WECHSEL and wechsel >= MIN_WECHSEL_ANTEIL * erwartet


def klub_verbaende(ranglisten: dict, finde, schwinger: dict) -> dict[str, str]:
    """Klub (Schreibweise der Rangliste) -> Teilverband, aus den Porträts."""
    stimmen: dict[str, Counter] = defaultdict(Counter)
    for eintrag in ranglisten.values():
        for e in eintrag.get("eintraege", []) if isinstance(eintrag, dict) else []:
            klub = e.get("schwingklub")
            basis, jahr = _basisname(str(e.get("name", "")))
            sid = finde(basis) if klub else None
            s = schwinger.get(sid) if sid else None
            if s is None or not s.teilverband or not hat_portraet(s.quellen):
                continue
            if jahr and s.jahrgang and jahr != s.jahrgang:
                continue
            stimmen[klub][s.teilverband] += 1
    out = {}
    for klub, z in stimmen.items():
        verband, n = z.most_common(1)[0]
        if sum(z.values()) >= MIN_KLUB_STIMMEN and n / sum(z.values()) >= MIN_KLUB_ANTEIL:
            out[klub] = verband
    return out


def trenne_namensvettern(ranglisten: dict, events: dict, finde, schwinger: dict):
    """(Zuordnung, neue Schwinger-Einträge, Bericht).

    ``ranglisten``: event_id -> {"eintraege": [...]} (roh, s. fetch_raw).
    ``events``: event_id -> Event mit ``datum``. ``finde``: Namensindex.finde.
    ``schwinger``: id -> Schwinger (Porträts + Stubs).
    Zuordnung: (event_id, namens_tokens) -> ID des Namensvetters.
    """
    verband_von_klub = klub_verbaende(ranglisten, finde, schwinger)
    # Namens-Tokens -> Porträt-IDs, für die mehrdeutigen Namen.
    portraets_je_name: dict[tuple, list[str]] = defaultdict(list)
    for sid, sw in schwinger.items():
        if hat_portraet(sw.quellen):
            portraets_je_name[namens_tokens(sw.name)].append(sid)
    mehrdeutig_eintraege: list[tuple[str, tuple, int | None, str | None]] = []
    je_fest_name: Counter = Counter()
    # Porträt-ID -> Liste (event_id, datum, verband des Klubs | None, tokens)
    auftritte: dict[str, list] = defaultdict(list)
    jahrgang_vettern: list[tuple[str, tuple, str, int, str]] = []

    for eid, eintrag in ranglisten.items():
        event = events.get(eid)
        if event is None or not isinstance(eintrag, dict) or "fehler" in eintrag:
            continue
        for e in eintrag.get("eintraege", []):
            basis, jahr = _basisname(str(e.get("name", "")))
            tokens = namens_tokens(basis)
            if not tokens:
                continue
            je_fest_name[(eid, tokens)] += 1
            sid = finde(basis)
            if sid is None and len(portraets_je_name.get(tokens, [])) > 1:
                mehrdeutig_eintraege.append((eid, tokens, jahr, verband_von_klub.get(e.get("schwingklub"))))
                continue
            s = schwinger.get(sid) if sid else None
            if s is None or not hat_portraet(s.quellen):
                continue
            if jahr and s.jahrgang and jahr != s.jahrgang:
                jahrgang_vettern.append((eid, tokens, basis, jahr, sid))
                continue
            auftritte[sid].append((eid, event.datum, verband_von_klub.get(e.get("schwingklub")), tokens))

    zuordnung: dict[tuple[str, tuple], str] = {}
    neue: dict[str, dict] = {}
    selbes_fest = 0
    beispiele: list[str] = []

    def haenge_um(eid: str, tokens: tuple, neue_id: str) -> bool:
        nonlocal selbes_fest
        if je_fest_name[(eid, tokens)] > 1:
            selbes_fest += 1  # beide am selben Fest: Gänge nicht zuordenbar
            return False
        zuordnung[(eid, tokens)] = neue_id
        return True

    aufgeloest = 0
    for eid, tokens, jahr, verband in mehrdeutig_eintraege:
        kandidaten = portraets_je_name[tokens]
        if jahr:
            passend = [k for k in kandidaten if schwinger[k].jahrgang == jahr]
        else:
            passend = [k for k in kandidaten if verband and schwinger[k].teilverband == verband]
        if len(passend) == 1 and haenge_um(eid, tokens, passend[0]):
            aufgeloest += 1

    for eid, tokens, basis, jahr, sid in jahrgang_vettern:
        neue_id = _vetter_id(tokens, str(jahr))
        if haenge_um(eid, tokens, neue_id):
            neue.setdefault(neue_id, {"id": neue_id, "name": schwinger[sid].name, "jahrgang": jahr,
                                      "kranzstatus": "kein", "namensvetter_von": sid,
                                      "quellen": ["schlussgang.ch/rangliste"]})

    for sid, liste in auftritte.items():
        eigen = schwinger[sid].teilverband
        gruppen: dict[str, list] = defaultdict(list)
        for eid, datum, verband, tokens in liste:
            if verband:
                gruppen[verband].append((eid, datum, tokens))
        heim = gruppen.get(eigen, [])
        if len(heim) < MIN_FESTE_JE_GRUPPE:
            continue  # Porträt-Verband nicht belegt (veraltet?) -- nichts raten
        for verband, fremd in gruppen.items():
            if verband == eigen or len(fremd) < MIN_FESTE_JE_GRUPPE:
                continue
            if not sind_zwei_personen([(d, e) for e, d, _ in heim], [(d, e) for e, d, _ in fremd]):
                continue  # Klubwechsel derselben Person
            tokens = fremd[0][2]
            neue_id = _vetter_id(tokens, _VERBAND_KURZ.get(verband, verband.lower()))
            umgehaengt = sum(haenge_um(eid, t, neue_id) for eid, _, t in fremd)
            if umgehaengt:
                neue.setdefault(neue_id, {"id": neue_id, "name": schwinger[sid].name, "jahrgang": None,
                                          "kranzstatus": "kein", "namensvetter_von": sid,
                                          "quellen": ["schlussgang.ch/rangliste"]})
                if len(beispiele) < 10:
                    beispiele.append(f"{schwinger[sid].name}: {umgehaengt} Feste ({verband}) "
                                     f"getrennt von {eigen}")

    bericht = {
        "klubs_mit_verband": len(verband_von_klub),
        "personen_getrennt": len(neue),
        "feste_umgehaengt": len(zuordnung),
        "nicht_trennbar_selbes_fest": selbes_fest,
        "mehrdeutige_feste_aufgeloest": aufgeloest,
        "beispiele": beispiele,
    }
    return zuordnung, neue, bericht
