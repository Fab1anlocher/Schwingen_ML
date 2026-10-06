"""Stil-Typen (stiltypen.py): Abweichung gegen die Erwartung, Typ aus der Lage."""
from __future__ import annotations

import random

import numpy as np

from pipeline.labels import GangResultat
from pipeline.schema import Schwinger
from pipeline.stiltypen import TYPEN, berechne_stiltypen, typ_von


class _Elo:
    gaenge_gezaehlt: dict = {}

    def get(self, sid):
        return 1500.0


def _gang(eid, datum, a, b, ergebnis, note_a, note_b):
    symbole = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}[ergebnis]
    return GangResultat(event_id=eid, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
                        symbol_a=symbole[0], note_a=note_a, symbol_b=symbole[1], note_b=note_b,
                        ergebnis=ergebnis, fest_typ="kantonal")


def _liga(regionen: dict[str, float], n_je_region=60, n_feste=60, spezial=None, seed=1):
    """Feste je Region; Plattwurf-Quote der Region = Benotung ihrer Kampfrichter.

    ``spezial``: {sid: (region, p_platt, p_gestellt)} für einzelne Schwinger.
    """
    rng = random.Random(seed)
    spezial = spezial or {}
    personen = {r: [f"{r}{i:02d}" for i in range(n_je_region)] for r in regionen}
    for sid, (region, _, _) in spezial.items():
        personen[region].append(sid)
    gaenge, snapshots = [], []
    for f in range(n_feste):
        for region, p_platt_region in regionen.items():
            eid = f"{region}-{f}"
            datum = f"2025-{1 + f % 12:02d}-{1 + f // 12:02d}"
            feld = personen[region][:]
            rng.shuffle(feld)
            for a, b in zip(feld[0::2], feld[1::2]):
                p_g = max(spezial.get(a, (0, 0, 0.2))[2], spezial.get(b, (0, 0, 0.2))[2])
                if rng.random() < p_g:
                    erg, na, nb = "gestellt", 8.75, 8.75
                else:
                    a_siegt = rng.random() < 0.5
                    sieger = a if a_siegt else b
                    p_platt = spezial.get(sieger, (0, p_platt_region, 0))[1]
                    note = 10.0 if rng.random() < p_platt else 9.75
                    erg = "sieg_a" if a_siegt else "sieg_b"
                    na, nb = (note, 8.5) if a_siegt else (8.5, note)
                gaenge.append(_gang(eid, datum, a, b, erg, na, nb))
                snapshots.append({"event_id": eid, "schwinger_a_id": a, "schwinger_b_id": b,
                                  "elo_a_pre": 1500.0, "elo_b_pre": 1500.0,
                                  "n_a_pre": 50, "n_b_pre": 50})
    alle = [sid for liste in personen.values() for sid in liste]
    schwinger = {sid: Schwinger(id=sid, name=sid, quellen=["test"]) for sid in alle}
    return gaenge, snapshots, schwinger, set(alle)


def test_typ_von_deckt_alle_lagen_ab():
    assert typ_von(1.0, -1.0) == "werfer"
    assert typ_von(1.0, 0.0) == "werfer"
    assert typ_von(1.0, 1.0) == "lauerer"
    assert typ_von(0.0, 1.0) == "bollwerk"
    assert typ_von(-1.0, 1.0) == "bollwerk"
    assert typ_von(-1.0, 0.0) == "bodenarbeiter"
    assert typ_von(-1.0, -1.0) == "bodenarbeiter"
    assert typ_von(0.0, -1.0) == "entscheider"
    assert typ_von(0.2, 0.2) == "allrounder"


def test_werfer_und_bollwerk_werden_erkannt():
    spezial = {"werfer": ("r", 0.95, 0.2), "bollwerk": ("r", 0.5, 0.6)}
    gaenge, snaps, schwinger, aktive = _liga({"r": 0.5}, n_feste=100, spezial=spezial)

    res = berechne_stiltypen(gaenge, snaps, schwinger, _Elo(), aktive)

    punkte = {p["schwinger_id"]: p for p in res["punkte"]}
    assert max(punkte, key=lambda s: punkte[s]["plattwurf"]) == "werfer"
    assert max(punkte, key=lambda s: punkte[s]["gestellt"]) == "bollwerk"
    assert punkte["werfer"]["typ"] in ("werfer", "lauerer")
    assert punkte["bollwerk"]["typ"] in ("bollwerk", "lauerer")
    assert punkte["werfer"]["plattwurf_quote"] > 0.85
    assert sum(t["n"] for t in res["typen"]) == res["n_schwinger"] == len(punkte)
    assert {t["typ"] for t in res["typen"]} <= set(TYPEN)


def test_grosszuegige_benotung_eines_fests_ist_kein_stil():
    # Region "g" benotet fast jeden Sieg mit 10.00, Region "s" selten. Ohne die
    # Quote des Fests wären alle aus "g" Werfer.
    gaenge, snaps, schwinger, aktive = _liga({"g": 0.85, "s": 0.35})

    res = berechne_stiltypen(gaenge, snaps, schwinger, _Elo(), aktive)

    g = [p["plattwurf"] for p in res["punkte"] if p["schwinger_id"].startswith("g")]
    s = [p["plattwurf"] for p in res["punkte"] if p["schwinger_id"].startswith("s")]
    roh = [np.mean([p["plattwurf_quote"] for p in res["punkte"] if p["schwinger_id"].startswith(r)])
           for r in "gs"]
    roh_abstand = 100 * (roh[0] - roh[1])
    assert roh_abstand > 40                      # roh liegen die Regionen weit auseinander
    # gegen die Erwartung bleibt davon fast nichts (Rest: Rauschen der
    # Fest-Quote bei nur rund 24 Siegen je Fest dämpft die Korrektur)
    assert abs(np.mean(g) - np.mean(s)) < 0.15 * roh_abstand


def test_zu_wenig_gaenge_gibt_keinen_typ():
    gaenge, snaps, schwinger, aktive = _liga({"r": 0.5}, n_feste=10)
    assert berechne_stiltypen(gaenge, snaps, schwinger, _Elo(), aktive) is None


def test_schlussgang_zaehlt_nicht_als_plattwurf():
    # Der Punktbeste eines Fests gewinnt 10.00 gegen 8.75 (Schlussgang-Muster):
    # dieser Sieg darf nicht in seine Plattwurf-Quote.
    gaenge, snaps, schwinger, aktive = _liga({"r": 0.5})
    vorher = berechne_stiltypen(gaenge, snaps, schwinger, _Elo(), aktive)
    n_vorher = {p["schwinger_id"]: p["n_siege"] for p in vorher["punkte"]}
    eid = gaenge[0].event_id
    gaenge.append(_gang(eid, gaenge[0].datum, "r00", "r01", "sieg_a", 10.0, 8.75))
    snaps.append({"event_id": eid, "schwinger_a_id": "r00", "schwinger_b_id": "r01",
                  "elo_a_pre": 1500.0, "elo_b_pre": 1500.0, "n_a_pre": 50, "n_b_pre": 50})
    # r00 zum Punktbesten dieses Fests machen: weitere Siege mit hoher Note
    for gegner in ("r02", "r03", "r04", "r05"):
        gaenge.append(_gang(eid, gaenge[0].datum, "r00", gegner, "sieg_a", 10.0, 8.5))
        snaps.append({"event_id": eid, "schwinger_a_id": "r00", "schwinger_b_id": gegner,
                      "elo_a_pre": 1500.0, "elo_b_pre": 1500.0, "n_a_pre": 50, "n_b_pre": 50})
    nachher = berechne_stiltypen(gaenge, snaps, schwinger, _Elo(), aktive)
    n_nachher = {p["schwinger_id"]: p["n_siege"] for p in nachher["punkte"]}
    assert n_nachher["r00"] == n_vorher["r00"] + 4   # die vier normalen Siege, nicht der Schlussgang
