"""Messungen auf Rohdaten (messung.py): Noten-Merkmale leak-frei und gespiegelt."""
from __future__ import annotations

import numpy as np

from pipeline.labels import GangResultat
from pipeline.messung import (logit, noten_merkmale, schlussgang_verdacht, siegart_bericht,
                              siege_mit_elo, verteilung)


def _gang(eid, datum, a, b, ergebnis, note_a, note_b):
    symbole = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}[ergebnis]
    return GangResultat(event_id=eid, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
                        symbol_a=symbole[0], note_a=note_a, symbol_b=symbole[1], note_b=note_b,
                        ergebnis=ergebnis, fest_typ="kantonal")


def test_noten_merkmale_sehen_nur_fruehere_feste():
    gaenge = [
        # Fest 1: A gewinnt mit Plattwurf gegen B, C ohne gegen D.
        _gang("f1", "2025-05-01", "a", "b", "sieg_a", 10.0, 8.5),
        _gang("f1", "2025-05-01", "c", "d", "sieg_a", 9.75, 8.5),
        # Fest 2: wieder A gegen B -- hier darf nur Fest 1 zählen.
        _gang("f2", "2025-06-01", "a", "b", "sieg_a", 9.75, 8.75),
    ]
    meta = [{"event_id": "f1", "schwinger_a_id": "a", "schwinger_b_id": "b"},
            {"event_id": "f2", "schwinger_a_id": "a", "schwinger_b_id": "b"},
            {"event_id": "f2", "schwinger_a_id": "a", "schwinger_b_id": "b", "augmented": True}]
    N = noten_merkmale(gaenge, meta)
    assert np.allclose(N[0], 0.0)          # vor dem ersten Fest weiss niemand etwas
    assert N[1, 0] > 0                     # A hat schon einmal plattgeworfen, B nicht
    assert N[2, 0] == -N[1, 0]             # Spiegelzeile: B gegen A
    assert N[2, 2] == N[1, 2]              # symmetrisches Merkmal bleibt


def test_verteilung_zaehlt_noten_je_ausgang():
    z = "\n".join(verteilung([_gang("f", "2025-05-01", "a", "b", "gestellt", 8.75, None)]))
    assert "1 ohne Note" in z and "| gestellt | 1 | 8.75 (100.0%) |" in z


def test_schlussgang_verdacht_trifft_nur_den_punktbesten():
    gaenge = [
        _gang("f", "2025-05-01", "a", "b", "sieg_a", 10.0, 8.75),   # a: Punktbester, 10/8.75
        _gang("f", "2025-05-01", "a", "c", "sieg_a", 10.0, 8.5),    # a, aber normaler Verlierer
        _gang("f", "2025-05-01", "c", "d", "sieg_a", 10.0, 8.75),   # 10/8.75, nicht Punktbester
    ]
    assert schlussgang_verdacht(gaenge) == {0}


def test_siege_mit_elo_filtert_neulinge_und_schlussgang():
    gaenge = [
        _gang("f", "2025-05-01", "a", "b", "sieg_b", 8.5, 10.0),
        _gang("f", "2025-05-01", "c", "d", "sieg_a", 9.75, 8.5),
    ]
    snap = [{"event_id": "f", "schwinger_a_id": "a", "schwinger_b_id": "b",
             "elo_a_pre": 1500, "elo_b_pre": 1600, "n_a_pre": 30, "n_b_pre": 30},
            {"event_id": "f", "schwinger_a_id": "c", "schwinger_b_id": "d",
             "elo_a_pre": 1500, "elo_b_pre": 1500, "n_a_pre": 30, "n_b_pre": 3}]
    # Gang 0 wäre Schlussgang-Verdacht nur mit 8.75; hier 8.50 -> bleibt.
    zeilen = siege_mit_elo(gaenge, snap)
    assert len(zeilen) == 1                       # c-d: d hat erst 3 Gänge
    assert zeilen[0]["sieger"] == "b" and zeilen[0]["elo_s"] == 1600 and zeilen[0]["platt"]


def test_logit_findet_bekannten_effekt():
    rng = np.random.default_rng(0)
    x = rng.normal(size=20000)
    y = (rng.random(20000) < 1 / (1 + np.exp(-(0.2 + 0.5 * x)))).astype(float)
    b, se = logit(np.column_stack([np.ones_like(x), x]), y)
    assert abs(b[1] - 0.5) < 3 * se[1] and se[1] < 0.03


def test_siegart_bericht_trennt_staerke_und_abstand():
    # Plattwurf hängt nur am Abstand, nicht an der Stärke selbst.
    rng = np.random.default_rng(1)
    zeilen = []
    for i in range(6000):
        elo_s, elo_v = rng.normal(1550, 80), rng.normal(1500, 80)
        p = 1 / (1 + np.exp(-(0.1 + 0.6 * (elo_s - elo_v) / 100)))
        zeilen.append({"sieger": f"s{i % 60}", "verlierer": "v", "elo_s": elo_s, "elo_v": elo_v,
                       "platt": bool(rng.random() < p), "offensiv": False,
                       "fest_typ": "kantonal", "datum": f"202{3 + i % 3}-06-01",
                       "event_id": f"f{i % 30}"})
    z = "\n".join(siegart_bericht(zeilen))
    for teil in ("Nach Stärke des Siegers", "Stärke und Abstand getrennt", "Eigenschaft",
                 "Benoten die Feste", "ohne die Benotung des Fests"):
        assert teil in z
    zeile = next(l for l in z.splitlines() if l.startswith("| Elo des Siegers"))
    koeff_staerke = float(zeile.split("|")[2])
    zeile = next(l for l in z.splitlines() if l.startswith("| Abstand zum Verlierer"))
    koeff_abstand = float(zeile.split("|")[2])
    assert abs(koeff_staerke) < 0.1 and koeff_abstand > 0.4


def test_festtag_gangnummer_und_vorherige_punkte():
    from pipeline.labels import RohGangEintrag
    from pipeline.messung import festtag_merkmale

    def roh(sid, gid, sym, note):
        return RohGangEintrag(event_id="f", datum="2025-05-01", schwinger_id=sid, gegner_id=gid,
                              symbol=sym, note=note, fest_typ="kantonal")
    # a: Gang 1 gegen c (Sieg 10.00), Gang 2 gegen b (Sieg 9.75).
    # b: Gang 1 gegen d (gestellt 8.75), Gang 2 gegen a (Niederlage 8.50).
    r = [roh("a", "c", "+", 10.0), roh("a", "b", "+", 9.75),
         roh("b", "d", "-", 8.75), roh("b", "a", "o", 8.5),
         roh("c", "a", "o", 8.5), roh("d", "b", "-", 8.75)]
    gaenge = [_gang("f", "2025-05-01", "a", "b", "sieg_a", 9.75, 8.5),
              _gang("f", "2025-05-01", "a", "c", "sieg_a", 10.0, 8.5),
              _gang("f", "2025-05-01", "b", "d", "gestellt", 8.75, 8.75)]
    meta = [{"event_id": "f", "schwinger_a_id": "a", "schwinger_b_id": "b"},
            {"event_id": "f", "schwinger_a_id": "b", "schwinger_b_id": "a"}]   # Sicht B gegen A
    F, info = festtag_merkmale(gaenge, r, meta)
    assert info["anteil_gleiche_position"] == 1.0
    assert F[0].tolist() == [10.0 - 8.75, 1.0, 2.0]      # vor Gang 2: a 10.00/1 Sieg, b 8.75/0
    assert F[1].tolist() == [8.75 - 10.0, -1.0, 2.0]


def test_paarung_kennzahlen_einseitig_und_zu_viele_gaenge():
    from pipeline.labels import RohGangEintrag
    from pipeline.messung import paarung_kennzahlen

    def e(eid, datum, s, g, sym):
        return RohGangEintrag(event_id=eid, datum=datum, schwinger_id=s, gegner_id=g,
                              symbol=sym, note=None, fest_typ="regional")
    roh = [e("f1", "2023-05-01", "a", "b", "+"), e("f1", "2023-05-01", "b", "a", "o"),   # beidseitig
           e("f1", "2023-05-01", "a", "c", "-")]                                          # nur eine Seite
    roh += [e("f1", "2023-05-01", "a", f"x{i}", "+") for i in range(7)]                   # a: 9 Gänge
    c = paarung_kennzahlen(roh)["2023"]
    assert c["ueber8"] == 1 and c["paare"] == 9 and c["einseitig"] == 8
    assert c["gestellt_einseitig"] == 1 and c["gestellt_zweiseitig"] == 0


def test_vettern_verdacht_doppeltage_und_zu_viele_gaenge():
    from pipeline.labels import RohGangEintrag
    from pipeline.messung import vettern_verdacht

    def e(eid, datum, s, g):
        return RohGangEintrag(event_id=eid, datum=datum, schwinger_id=s, gegner_id=g,
                              symbol="+", note=None, fest_typ="regional")
    roh = [e("f1", "2026-04-12", "a", "b"), e("f2", "2026-04-12", "a", "c")]   # zwei Feste, ein Tag
    roh += [e("f3", "2026-05-01", "d", f"x{i}") for i in range(9)]              # 9 Gänge
    v = vettern_verdacht(roh)
    assert v["a"]["doppeltage"] == 1 and v["d"]["ueber8"] == 1 and "b" not in v
