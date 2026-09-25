"""Messungen auf Rohdaten (messung.py): Noten-Merkmale leak-frei und gespiegelt."""
from __future__ import annotations

import numpy as np

from pipeline.labels import GangResultat
from pipeline.messung import noten_merkmale, verteilung


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
