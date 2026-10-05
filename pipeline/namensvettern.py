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


# --- Stufe 2: Herkunft (Klub, Wohnort) der Rangliste (Roadmap D5) -----------
#
# Stufe 1 trennt nur über verschiedene Teilverbände und nur Porträt-
# Schwinger. Real übrig blieben (Messung "vettern", 05.10.2026) u. a. zwei
# Alex Schuler aus Rothenthurm (Klub am Mythen, Eidgenosse, und Klub
# Einsiedeln), oft am selben Fest; zwei Marcel Stucki (Siehen, Zäziwil),
# drei Simon Röthlisberger, zwei Ramon Betschart (Muotathal, Mittel-
# Rheintal), zwei Adrian Meier ohne Porträt. Die Rangliste nennt zu jedem
# Auftritt Wohnort und Klub -- das unterscheidet sie.
#
# Zwei Klubs eines Namens sind zwei Personen, wenn es einen Beleg gibt: am
# selben Fest oder am selben Tag an zwei Festen (hart), oder ständig
# abwechselnd UND aus verschiedenen Wohnorten -- ein Klub, der mal so, mal
# anders geschrieben wird, wechselt auch ständig ab, aber der Wohnort bleibt.
# Ohne Beleg bleibt es eine Person (Klubwechsel, Schreibweisen); gleicher
# Wohnort ohne Beleg ebenso. Stehen beide am selben
# Fest, ordnet das Punktetotal den PDF-Block der Ranglisten-Zeile zu
# (Rangliste-Punkte == Block-Total), s. scrape.lade_echte_daten.

_KLUB_FUELLWOERTER = re.compile(r"\b(schwingklub|schwingerklub|schwingsektion|sk)\b")


def klub_schluessel(text: str | None) -> str | None:
    """Klubname vergleichbar machen: klein, ohne Satzzeichen, Füllwörter und
    Leerzeichen ("Mittel-Rheintal" == "Mittelrheintal")."""
    if not text:
        return None
    t = re.sub(r"[^\w ]", " ", str(text).lower())
    t = "".join(_KLUB_FUELLWOERTER.sub(" ", t).split())
    return t or None


def herkunft(eintrag: dict, bekannte_klubs: set[str]) -> str | None:
    """Klub-Schlüssel eines Ranglisten-Eintrags.

    Fehlt der Klub, ist er oft in die Wohnort-Spalte gerutscht ("Süderen
    Siehen", "Lungern ONSVLungern"): dann zählt ein bekannter Klub desselben
    Namens, mit dem die Wohnort-Spalte endet.
    """
    k = klub_schluessel(eintrag.get("schwingklub"))
    if k:
        return k
    w = klub_schluessel(eintrag.get("wohnort"))
    if not w:
        return None
    treffer = [b for b in bekannte_klubs if w.endswith(b)]
    return max(treffer, key=len) if treffer else None


def _punkte(wert) -> float | None:
    try:
        return round(float(wert), 2)
    except (TypeError, ValueError):
        return None


def _zwei_personen(a: list[tuple[str, str]], b: list[tuple[str, str]],
                   wo_a: set[str], wo_b: set[str]) -> bool:
    """(Datum, Fest)-Listen zweier Herkünfte: belegt verschieden?"""
    if {e for _, e in a} & {e for _, e in b}:
        return True  # beide am selben Fest
    tage_a = defaultdict(set)
    for datum, eid in a:
        tage_a[datum].add(eid)
    if any(tage_a.get(datum, set()) - {eid} for datum, eid in b):
        return True  # am selben Tag an zwei Festen
    # Ständiges Abwechseln zählt nur bei verschiedenen Wohnorten.
    return bool(wo_a and wo_b and not (wo_a & wo_b)) and sind_zwei_personen(a, b)


def herkunft_gruppen(auftritte: dict[str, list[tuple[str, str]]], wohnorte: dict[str, set[str]],
                     fest_id: dict[str, str] | None = None) -> list[set[str]]:
    """Klubs eines Namens zu Personen gruppieren.

    ``auftritte``: Klub -> [(Datum, Fest)]. ``wohnorte``: Klub -> Wohnorte.
    ``fest_id``: Klub -> ID, die Stufe 1 schon vergeben hat (Namensvetter);
    gleiche ID = gleiche Person, verschiedene IDs = verschiedene Personen.
    """
    fest_id = fest_id or {}
    klubs = sorted(auftritte, key=lambda k: (-len(auftritte[k]), k))
    konflikt = set()
    for i, a in enumerate(klubs):
        for b in klubs[i + 1:]:
            ia, ib = fest_id.get(a), fest_id.get(b)
            if (ia and ib and ia != ib) or _zwei_personen(
                    auftritte[a], auftritte[b], wohnorte.get(a, set()), wohnorte.get(b, set())):
                konflikt.add(frozenset((a, b)))
    gruppen = [{k} for k in klubs]

    def vertraeglich(x: set, y: set) -> bool:
        return not any(frozenset((a, b)) in konflikt for a in x for b in y)

    def vereine(bedingung) -> None:
        geaendert = True
        while geaendert:
            geaendert = False
            for i in range(len(gruppen)):
                for j in range(i + 1, len(gruppen)):
                    x, y = gruppen[i], gruppen[j]
                    if vertraeglich(x, y) and bedingung(x, y):
                        gruppen[i] = x | y
                        del gruppen[j]
                        geaendert = True
                        break
                if geaendert:
                    break

    # 1. Gleiche Stufe-1-ID und gleicher Wohnort binden, sofern kein Beleg dagegen.
    vereine(lambda x, y: bool({fest_id.get(k) for k in x if fest_id.get(k)}
                              & {fest_id.get(k) for k in y if fest_id.get(k)}))
    vereine(lambda x, y: bool(set().union(*(wohnorte.get(k, set()) for k in x))
                              & set().union(*(wohnorte.get(k, set()) for k in y))))
    # 2. Wer mit niemandem im Konflikt steht, ist dieselbe Person wie die
    #    grösste verträgliche Gruppe (Klubwechsel, andere Schreibweise).
    def ohne_konflikt(x: set) -> bool:
        return all(vertraeglich(x, y) for y in gruppen if y is not x)
    for x in sorted(gruppen, key=lambda g: sum(len(auftritte[k]) for k in g)):
        if x in gruppen and len(gruppen) > 1 and ohne_konflikt(x):
            ziel = max((y for y in gruppen if y is not x),
                       key=lambda g: sum(len(auftritte[k]) for k in g))
            gruppen.remove(x)
            gruppen[gruppen.index(ziel)] = ziel | x
    return sorted(gruppen, key=lambda g: -sum(len(auftritte[k]) for k in g))


def trenne_nach_herkunft(ranglisten: dict, events: dict, finde, schwinger: dict,
                         zuordnung: dict, neue: dict):
    """Stufe 2: (Zuordnung, neue Einträge, Block-Zuordnung, Bericht).

    Ergänzt die Zuordnung (Fest, Namens-Tokens) -> ID von Stufe 1. Stehen
    zwei Gleichnamige am selben Fest, gibt es dort keine Zuordnung über den
    Namen, sondern die Block-Zuordnung (Fest, Namens-Tokens, Punkte) -> ID:
    die Punkte der Rangliste sind das Punktetotal des PDF-Blocks.
    """
    verband_von_klub = {klub_schluessel(k): v for k, v in klub_verbaende(ranglisten, finde, schwinger).items()}
    je_name: dict[tuple, list] = defaultdict(list)   # tokens -> [(eid, datum, eintrag)]
    for eid, eintrag in ranglisten.items():
        event = events.get(eid)
        if event is None or not isinstance(eintrag, dict) or "fehler" in eintrag:
            continue
        for e in eintrag.get("eintraege", []):
            basis, jahr = _basisname(str(e.get("name", "")))
            tokens = namens_tokens(basis)
            if tokens and not jahr:          # Jahrgang-Zusatz: schon Stufe 1
                je_name[tokens].append((eid, event.datum, e))

    zuordnung = dict(zuordnung)
    neue = dict(neue)
    block: dict[tuple, str] = {}
    getrennt, beispiele = 0, []
    for tokens, liste in je_name.items():
        basis_id = finde(" ".join(tokens))
        if basis_id is None:
            continue
        bekannte = {k for k in (klub_schluessel(e.get("schwingklub")) for _, _, e in liste) if k}
        auftritte: dict[str, list] = defaultdict(list)
        wohnorte: dict[str, set] = defaultdict(set)
        fest_id: dict[str, Counter] = defaultdict(Counter)
        klub_je_eintrag = []
        for eid, datum, e in liste:
            k = herkunft(e, bekannte)
            klub_je_eintrag.append(k)
            if k is None:
                continue
            auftritte[k].append((datum, eid))
            if klub_schluessel(e.get("wohnort")):
                wohnorte[k].add(klub_schluessel(e.get("wohnort")))
            vorher = zuordnung.get((eid, tokens))
            if vorher and vorher != basis_id:
                fest_id[k][vorher] += 1
        if len(auftritte) < 2:
            continue
        gruppen = herkunft_gruppen(auftritte, wohnorte,
                                   {k: c.most_common(1)[0][0] for k, c in fest_id.items()})
        if len(gruppen) < 2:
            continue
        # Welche Gruppe ist der Porträt-/Basis-Schwinger?
        s = schwinger.get(basis_id)
        eigen_klub = klub_schluessel(s.schwingklub) if s else None
        def passt(g: set) -> int:
            if any(fest_id.get(k) for k in g):
                return -1                      # gehört einem Namensvetter aus Stufe 1
            if eigen_klub and eigen_klub in g:
                return 3
            if s and s.teilverband and any(verband_von_klub.get(k) == s.teilverband for k in g):
                return 2
            return 1
        basis = max(gruppen, key=lambda g: (passt(g), sum(len(auftritte[k]) for k in g)))
        ids: dict[str, str] = {}
        for g in gruppen:
            stufe1 = Counter()
            for k in g:
                stufe1.update(fest_id.get(k, Counter()))
            if g is basis:
                gid = basis_id
            elif stufe1:
                gid = stufe1.most_common(1)[0][0]
            else:
                kurz = sorted(g, key=lambda k: -len(auftritte[k]))[0].replace(" ", "-")
                gid = _vetter_id(tokens, kurz)
                if gid not in neue and gid not in schwinger:
                    ref = schwinger.get(basis_id)
                    neue[gid] = {"id": gid, "name": ref.name if ref else " ".join(tokens),
                                 "jahrgang": None, "kranzstatus": "kein", "namensvetter_von": basis_id,
                                 "quellen": ["schlussgang.ch/rangliste"]}
                    getrennt += 1
                    if len(beispiele) < 10:
                        beispiele.append(f"{ref.name if ref else ' '.join(tokens)}: "
                                         f"{', '.join(sorted(g))} getrennt von {', '.join(sorted(basis))}")
            for k in g:
                ids[k] = gid
        je_fest: dict[str, list] = defaultdict(list)
        for (eid, _, e), k in zip(liste, klub_je_eintrag):
            je_fest[eid].append((e, ids.get(k) if k else None))
        for eid, eintraege in je_fest.items():
            if len(eintraege) == 1:
                gid = eintraege[0][1]
                if gid and gid != basis_id:
                    zuordnung[(eid, tokens)] = gid
                elif gid == basis_id:
                    zuordnung.pop((eid, tokens), None)
                continue
            zuordnung.pop((eid, tokens), None)
            punkte = Counter(_punkte(e.get("punkte")) for e, _ in eintraege)
            for e, gid in eintraege:
                p = _punkte(e.get("punkte"))
                if gid and p is not None and punkte[p] == 1:
                    block[(eid, tokens, p)] = gid
    bericht = {"personen_getrennt": getrennt, "feste_selber_name_mehrfach": len({k[:2] for k in block}),
               "beispiele": beispiele}
    return zuordnung, neue, block, bericht
