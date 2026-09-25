"""Teilverband der Schwinger ohne Porträt, geschätzt aus ihren Festen (P6).

76 % des Kaders haben kein schlussgang.ch-Porträt und damit keinen
Teilverband. An Kantonal-, Teilverbands- und Regionalfesten startet aber fast
nur, wer dem veranstaltenden Verband angehört (Median-Anteil des grössten
Teilverbands 85-93 %, s. teilnehmerkreis.py). Wer immer wieder an Festen
desselben Verbands antritt, gehört mit hoher Sicherheit dazu.

Regel: ein Fest zählt als Fest eines Verbands, wenn dieser unter den
Teilnehmern mit bekanntem Verband dominiert (wie in teilnehmerkreis.py).
Geschätzt wird nur bei mindestens MIN_ZUGEORDNETE_FESTE solchen Festen und
wenn mindestens MIN_REINHEIT davon auf denselben Verband fallen. Offene Feste
(Berg-, Eidgenössische) fallen dabei von selbst heraus.

Gemessen an den 640 Porträt-Schwingern mit bekanntem Verband, jeweils ohne
den eigenen Verband in der Festzählung (Leave-one-out): 99.8 % richtig bei
91 % Abdeckung. Mit nur einem Fest wären es 89.5 %, mit drei 97.7% -- daher
die Mindestzahl. Diese Prüfung läuft bei JEDEM Lauf erneut
(``pruefe_schaetzung``); fällt sie unter MIN_TREFFERQUOTE, wird nichts
geschätzt, statt still schlechte Werte auszuliefern.

Bewusst NICHT im Modell: mit geschätzten Verbänden gälte „gleicher Verband“
für 73 % aller Gänge statt 17 %, das Merkmal verlöre seine Aussage (Test-Log-
Loss 0.7503 -> 0.7512). Die Schätzung dient der Anzeige und der Suche --
darum ein eigenes Feld ``teilverband_geschaetzt``; ``teilverband`` bleibt
der gemessene Wert aus dem Porträt.
"""
from __future__ import annotations

import collections

from .teilnehmerkreis import DOMINANZ_SCHWELLE, MIN_TEILNEHMER_MIT_VERBAND, teilnehmer_je_fest

MIN_ZUGEORDNETE_FESTE = 3
MIN_REINHEIT = 0.75
# Selbstprüfung: darunter wird nichts geschätzt. Und ohne genug Prüffälle ist
# die Trefferquote selbst nicht belastbar.
MIN_TREFFERQUOTE = 0.97
MIN_PRUEFFAELLE = 50


def _verband_des_fests(zaehler: collections.Counter) -> str | None:
    n = sum(zaehler.values())
    if n < MIN_TEILNEHMER_MIT_VERBAND:
        return None
    verband, anzahl = zaehler.most_common(1)[0]
    return verband if anzahl / n >= DOMINANZ_SCHWELLE else None


def _schaetze(feste, fest_zaehler: dict, eigener_verband: str | None = None) -> str | None:
    """Verband aus den besuchten Festen. ``eigener_verband`` wird aus der
    Festzählung herausgerechnet (Leave-one-out für die Selbstprüfung)."""
    stimmen: collections.Counter = collections.Counter()
    for eid in feste:
        zaehler = fest_zaehler[eid]
        if eigener_verband:
            zaehler = zaehler.copy()
            zaehler[eigener_verband] -= 1
        verband = _verband_des_fests(zaehler)
        if verband:
            stimmen[verband] += 1
    n = sum(stimmen.values())
    if n < MIN_ZUGEORDNETE_FESTE:
        return None
    verband, anzahl = stimmen.most_common(1)[0]
    return verband if anzahl / n >= MIN_REINHEIT else None


def schaetze_teilverbaende(gaenge, schwinger: dict) -> tuple[dict[str, str], dict]:
    """(Schätzung je Schwinger ohne Verband, Prüfbericht für report.json)."""
    teilnehmer = teilnehmer_je_fest(gaenge)
    bekannt = {
        sid: s.teilverband for sid, s in schwinger.items() if getattr(s, "teilverband", None)
    }
    fest_zaehler = {
        eid: collections.Counter(bekannt[sid] for sid in ts if sid in bekannt)
        for eid, ts in teilnehmer.items()
    }
    feste_von: dict[str, list] = collections.defaultdict(list)
    for eid, ts in teilnehmer.items():
        for sid in ts:
            feste_von[sid].append(eid)

    richtig = falsch = 0
    for sid, verband in bekannt.items():
        if sid not in feste_von:
            continue
        geschaetzt = _schaetze(feste_von[sid], fest_zaehler, eigener_verband=verband)
        if geschaetzt is None:
            continue
        if geschaetzt == verband:
            richtig += 1
        else:
            falsch += 1
    n_pruef = richtig + falsch
    trefferquote = richtig / n_pruef if n_pruef else None
    ohne = [sid for sid in schwinger if sid not in bekannt]
    bericht = {
        "pruef_faelle": n_pruef,
        "trefferquote": round(trefferquote, 4) if trefferquote is not None else None,
        "n_ohne_verband": len(ohne),
    }
    if trefferquote is None or n_pruef < MIN_PRUEFFAELLE or trefferquote < MIN_TREFFERQUOTE:
        return {}, {**bericht, "angewandt": False, "n_geschaetzt": 0}

    schaetzung = {}
    for sid in ohne:
        verband = _schaetze(feste_von.get(sid, ()), fest_zaehler)
        if verband:
            schaetzung[sid] = verband
    return schaetzung, {**bericht, "angewandt": True, "n_geschaetzt": len(schaetzung)}
