"""Fest-Simulation (fest_simulation.py): Zählungen, Regeln, Zufall."""
from __future__ import annotations

import math

from pipeline.fest_simulation import REGELN_JE_TYP, Regeln, mulberry32, simuliere


def _feld(n: int, spreizung: float = 4.0):
    """Paar-konsistente Wahrscheinlichkeiten: Teilnehmer 0 am stärksten."""
    staerke = [1 - i / n for i in range(n)]
    sieg = [[0.0] * n for _ in range(n)]
    gestellt = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                d = (staerke[i] - staerke[j]) * spreizung
                g = 0.22 * math.exp(-abs(d))
                sieg[i][j] = (1 - g) / (1 + math.exp(-d))
                gestellt[i][j] = g
    return sieg, gestellt


def test_mulberry32_ist_bitgleich_zu_javascript():
    # Werte aus Node: mulberry32(42) -> 0.6011037519201636, 0.44829055899754167
    r = mulberry32(42)
    assert abs(r() - 0.6011037519201636) < 1e-15
    assert abs(r() - 0.44829055899754167) < 1e-15


def test_zaehlungen_sind_vollstaendig_und_plausibel():
    sieg, gestellt = _feld(41)                    # ungerade: ein Freilos je Gang
    e = simuliere(sieg, gestellt, REGELN_JE_TYP["kantonal"], n_sim=300, seed=3)
    assert sum(e.festsieg) == 300                 # genau ein Sieger je Fest
    assert sum(e.schlussgang) == 600              # zwei im Schlussgang
    kraenze_je_fest = sum(e.kranz) / 300
    assert round(0.16 * 41) <= kraenze_je_fest <= round(0.16 * 41) + 4   # Punktgleichheit an der Grenze
    a = e.anteile()
    assert a[0]["festsieg"] > a[-1]["festsieg"] and a[0]["kranz"] > a[-1]["kranz"]


def test_gleicher_startwert_gleiches_ergebnis():
    sieg, gestellt = _feld(20)
    e1 = simuliere(sieg, gestellt, Regeln(), n_sim=50, seed=9)
    e2 = simuliere(sieg, gestellt, Regeln(), n_sim=50, seed=9)
    assert e1.festsieg == e2.festsieg and e1.punkte_summe == e2.punkte_summe


def test_ohne_kranzquote_keine_kraenze_und_acht_gaenge_am_eidgenoessischen():
    sieg, gestellt = _feld(30)
    e = simuliere(sieg, gestellt, Regeln(kranzquote=0.0), n_sim=40, seed=1)
    assert sum(e.kranz) == 0 and e.kranzgrenze_summe == 0
    eidg = simuliere(sieg, gestellt, REGELN_JE_TYP["eidgenoessisch"], n_sim=40, seed=1)
    # 8 Gänge: der Beste sammelt deutlich mehr Punkte als bei 6.
    assert eidg.punkte_summe[0] / 40 > 70
