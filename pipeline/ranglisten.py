"""Schlussranglisten -> je Schwinger: Kränze, Schwingklub, Verband über den Klub.

Quelle: die offiziellen ESV-Schlussranglisten, über schlussgang.ch bezogen
(s. scrape/schlussgang_rangliste.py). Sie führen JEDEN Teilnehmer -- auch die
76 % ohne Porträt -- mit Schwingklub, Senn/Turner und dem Kranz an diesem Fest.

Drei Dinge werden daraus abgeleitet, jedes mit einer Selbstprüfung gegen die
Porträts, die in report.json landet:

* **Kränze seit Datenbeginn** je Schwinger. Prüfung: wer laut Rangliste
  einen Kranz gewann, muss laut Porträt Kranzer oder mehr sein.
* **Schwingklub** (jüngster Eintrag). Prüfung: Übereinstimmung mit dem
  Porträt-Klub, wo es einen gibt.
* **Teilverband und Kantonal-/Gauverband über den Klub.** Jeder Klub gehört
  genau einem Verband an; die Zuordnung wird aus den Porträts gelernt (136
  Klubs, kein einziger mit zwei Teilverbänden). Prüfung: Leave-one-out an den
  Porträt-Schwingern.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .identity import namens_tokens
from .schema import hat_portraet

# Namensvettern trägt die Rangliste mit Jahrgang: "Föhn Franco (2009)".
_JAHRGANG_RE = re.compile(r"^(.*?)\s*\((\d{4})\)$")


@dataclass(frozen=True)
class Teilnahme:
    schwinger_id: str
    event_id: str
    datum: str
    fest_typ: str
    rang: str
    punkte: float
    kranz: bool
    status: str | None
    schwingklub: str | None
    wohnort: str | None
    senne_turner: str | None
    abzeichen: int = 0


def namensaufloesung(finde, schwinger: dict | None = None):
    """Name -> Schwinger-ID; erweitert ``finde`` um den Jahrgang-Zusatz.

    "Föhn Franco (2009)" findet der Namensindex nicht (vierstellige Zahl ist
    kein Unterscheidungs-Zähler). Mit dem Jahrgang ist die Zuordnung sogar
    eindeutiger als ohne: unter gleichnamigen Porträts zählt nur das mit
    genau diesem Jahrgang -- so lösen sich auch echte Namensvettern auf.
    """
    nach_tokens: dict[tuple, list[str]] = defaultdict(list)
    for sid, s in (schwinger or {}).items():
        nach_tokens[namens_tokens(s.name)].append(sid)

    def aufloesen(name: str) -> str | None:
        sid = finde(name)
        if sid is not None:
            return sid
        m = _JAHRGANG_RE.match(name.strip())
        if not m:
            return None
        jahr = int(m.group(2))
        kandidaten = [i for i in nach_tokens.get(namens_tokens(m.group(1)), [])
                      if getattr(schwinger[i], "jahrgang", None) == jahr]
        if len(kandidaten) == 1:
            return kandidaten[0]
        return finde(m.group(1)) if not nach_tokens else None

    return aufloesen


def teilnahmen_aus_ranglisten(ranglisten: dict, events: dict, finde,
                              schwinger: dict | None = None) -> tuple[list[Teilnahme], dict]:
    """Rohe Ranglisten -> Teilnahmen mit aufgelöster Schwinger-ID.

    ``events``: event_id -> Event (nur bekannte Feste zählen).
    ``finde``: Name -> Schwinger-ID oder None (Namensindex.finde).
    ``schwinger``: für die Auflösung über den Jahrgang (s. namensaufloesung).
    """
    finde = namensaufloesung(finde, schwinger)
    teilnahmen: list[Teilnahme] = []
    unaufloesbar: Counter = Counter()
    n_feste = n_fehler = 0
    for eid, eintrag in ranglisten.items():
        event = events.get(eid)
        if event is None:
            continue
        if "fehler" in eintrag:
            n_fehler += 1
            continue
        n_feste += 1
        for e in eintrag.get("eintraege", []):
            sid = finde(e["name"])
            if sid is None:
                unaufloesbar[e["name"]] += 1
                continue
            teilnahmen.append(Teilnahme(
                schwinger_id=sid, event_id=eid, datum=event.datum, fest_typ=event.typ,
                rang=str(e.get("rang")), punkte=float(e.get("punkte") or 0.0),
                kranz=bool(e.get("kranz")), status=e.get("status"),
                schwingklub=e.get("schwingklub"), wohnort=e.get("wohnort"),
                senne_turner=e.get("senne_turner"),
                abzeichen=int(e.get("abzeichen") or 0),
            ))
    n_eintraege = len(teilnahmen) + sum(unaufloesbar.values())
    return teilnahmen, {
        "n_feste": n_feste,
        "n_nicht_lesbar": n_fehler,
        "n_teilnahmen": len(teilnahmen),
        "anteil_namen_aufgeloest": round(len(teilnahmen) / n_eintraege, 4) if n_eintraege else None,
        "beispiele_unaufloesbar": [n for n, _ in unaufloesbar.most_common(5)],
    }


def kraenze_je_schwinger(teilnahmen: list[Teilnahme]) -> dict[str, dict]:
    """Gewonnene Kränze je Schwinger, gesamt und je Festtyp."""
    out: dict[str, dict] = defaultdict(lambda: {"gesamt": 0, "nach_typ": Counter()})
    for t in teilnahmen:
        eintrag = out[t.schwinger_id]
        if t.kranz:
            eintrag["gesamt"] += 1
            eintrag["nach_typ"][t.fest_typ] += 1
    return {sid: {"gesamt": v["gesamt"], "nach_typ": dict(v["nach_typ"])} for sid, v in out.items()}


def _juengster_wert(teilnahmen: list[Teilnahme], feld: str) -> dict[str, str]:
    werte: dict[str, tuple[str, str]] = {}
    for t in teilnahmen:
        wert = getattr(t, feld)
        if wert and (t.schwinger_id not in werte or t.datum >= werte[t.schwinger_id][0]):
            werte[t.schwinger_id] = (t.datum, wert)
    return {sid: w for sid, (_, w) in werte.items()}


def kranzstatus_je_schwinger(teilnahmen: list[Teilnahme]) -> dict[str, str]:
    """Kranzstatus laut Rangliste: kranzer oder eidgenosse (höchster erreichter).

    Zwei Quellen je Teilnahme, beide nötig:
    * die Sterne = Stand VOR dem Fest (Legende: * Kantonal-/Gauverbandskranz,
      ** Teilverbandskranz, *** Eidgenössischer Kranz);
    * der Ausgang dieses Fests: wer hier einen Kranz gewinnt, ist danach
      mindestens Kranzer, ein eidgenössischer Kranz macht zum Eidgenossen.
    Fritz Ramseier trat am ESAF 2025 mit zwei Sternen an und wurde dort
    Neueidgenosse -- nur mit den Sternen stünde er als Kranzer da.

    Für die Anzeige bei Schwingern ohne Porträt, die bisher als "kein"
    erschienen, obwohl sie Kranzer sind.
    """
    stufe: dict[str, int] = defaultdict(int)
    for t in teilnahmen:
        s = 2 if t.abzeichen >= 3 else (1 if t.abzeichen else 0)
        if t.kranz:
            s = max(s, 2 if (t.fest_typ == "eidgenoessisch" or t.status == "Neueidgenosse") else 1)
        stufe[t.schwinger_id] = max(stufe[t.schwinger_id], s)
    return {sid: ("eidgenosse" if n >= 2 else "kranzer") for sid, n in stufe.items() if n}


def klub_je_schwinger(teilnahmen: list[Teilnahme]) -> dict[str, str]:
    """Jüngster Schwingklub laut Rangliste (Klubwechsel: der aktuelle zählt)."""
    return _juengster_wert(teilnahmen, "schwingklub")


def senne_turner_je_schwinger(teilnahmen: list[Teilnahme]) -> dict[str, str]:
    return _juengster_wert(teilnahmen, "senne_turner")


# Ein Klub gilt als zugeordnet, wenn so viele seiner Porträt-Mitglieder
# denselben Verband tragen. Gemessen: kein Klub mit zwei Teilverbänden.
MIN_KLUB_EINDEUTIGKEIT = 0.9


def verband_ueber_klub(klubs: dict[str, str], schwinger: dict) -> tuple[dict[str, tuple[str | None, str | None]], dict]:
    """Klub -> (Teilverband, Kantonal-/Gauverband), gelernt aus den Porträts.

    Rückgabe: (Zuordnung je Schwinger OHNE Porträt-Verband, Prüfbericht).
    Die Prüfung sagt jedem Porträt-Schwinger seinen Verband aus den ANDEREN
    Mitgliedern seines Klubs voraus (Leave-one-out) und vergleicht.
    """
    mitglieder: dict[str, list[str]] = defaultdict(list)
    for sid, klub in klubs.items():
        s = schwinger.get(sid)
        if s is not None and getattr(s, "teilverband", None):
            mitglieder[klub].append(sid)

    def mehrheit(ids: list[str], feld: str) -> str | None:
        werte = Counter(getattr(schwinger[i], feld) for i in ids if getattr(schwinger[i], feld, None))
        if not werte:
            return None
        wert, n = werte.most_common(1)[0]
        return wert if n / sum(werte.values()) >= MIN_KLUB_EINDEUTIGKEIT else None

    richtig = falsch = 0
    for klub, ids in mitglieder.items():
        for sid in ids:
            andere = [i for i in ids if i != sid]
            if not andere:
                continue
            vorhersage = mehrheit(andere, "teilverband")
            if vorhersage is None:
                continue
            richtig += vorhersage == schwinger[sid].teilverband
            falsch += vorhersage != schwinger[sid].teilverband

    zuordnung_klub = {klub: (mehrheit(ids, "teilverband"), mehrheit(ids, "kanton"))
                      for klub, ids in mitglieder.items()}
    ergebnis: dict[str, tuple[str | None, str | None]] = {}
    ohne_verband = [sid for sid in klubs if not getattr(schwinger.get(sid), "teilverband", None)]
    for sid in ohne_verband:
        tv, kanton = zuordnung_klub.get(klubs[sid], (None, None))
        if tv:
            ergebnis[sid] = (tv, kanton)
    n_pruef = richtig + falsch
    return ergebnis, {
        "klubs_bekannt": sum(1 for tv, _ in zuordnung_klub.values() if tv),
        "pruef_faelle": n_pruef,
        "trefferquote": round(richtig / n_pruef, 4) if n_pruef else None,
        "n_ohne_porträt_mit_klub": len(ohne_verband),
        "n_zugeordnet": len(ergebnis),
    }


def konsistenz(kraenze: dict[str, dict], klubs: dict[str, str], schwinger: dict) -> dict:
    """Selbstprüfung der Rangliste gegen die Porträts.

    * Porträt-Klub == Ranglisten-Klub (wo beide vorliegen).
    * Kranzgewinner ohne Porträt: schlussgang.ch porträtiert nur Kranzer und
      besser -- ein Kranzgewinner ohne Porträt ist entweder ein frischer
      Neukranzer, dessen Porträt noch fehlt, oder ein Zuordnungsfehler.
    """
    gleich = verschieden = 0
    for sid, klub in klubs.items():
        s = schwinger.get(sid)
        if s is not None and getattr(s, "schwingklub", None):
            gleich += s.schwingklub == klub
            verschieden += s.schwingklub != klub
    kranz_ohne_portraet = [
        sid for sid, k in kraenze.items()
        if k["gesamt"] and sid in schwinger and not hat_portraet(schwinger[sid].quellen)
    ]
    n = gleich + verschieden
    return {
        "klub_wie_porträt": round(gleich / n, 4) if n else None,
        "klub_vergleiche": n,
        "kranzgewinner_ohne_porträt": len(kranz_ohne_portraet),
        "beispiele_kranzgewinner_ohne_porträt": sorted(kranz_ohne_portraet)[:5],
    }


def kranzquoten(teilnahmen: list[Teilnahme]) -> dict[str, float]:
    """Median-Kranzquote je Festtyp (Plausibilität: Kranzfeste ~14-18 %)."""
    je_fest: dict[str, list[bool]] = defaultdict(list)
    typ: dict[str, str] = {}
    for t in teilnahmen:
        je_fest[t.event_id].append(t.kranz)
        typ[t.event_id] = t.fest_typ
    quoten: dict[str, list[float]] = defaultdict(list)
    for eid, werte in je_fest.items():
        quoten[typ[eid]].append(sum(werte) / len(werte))
    return {t: round(sorted(q)[len(q) // 2], 4) for t, q in sorted(quoten.items())}


KRANZFEST_TYPEN = ("kantonal", "teilverband", "berg")


def kranzfeste_ohne_kranz(teilnahmen: list[Teilnahme]) -> list[str]:
    """Kranzfeste, an denen die Rangliste keinen einzigen Kranz zeigt.

    Ein Kantonal-, Teilverbands- oder Bergfest vergibt immer Kränze. Ohne
    einen einzigen hat der Parser die Status-Spalte dieses PDFs nicht erkannt.
    """
    kranz: dict[str, bool] = defaultdict(bool)
    for t in teilnahmen:
        if t.fest_typ in KRANZFEST_TYPEN:
            kranz[t.event_id] |= t.kranz
    return sorted(eid for eid, hat in kranz.items() if not hat)
