"""Vertrauensintervalle über Feste (train.konfidenzintervalle)."""
from __future__ import annotations

import numpy as np

from pipeline.train import konfidenzintervalle


def _daten(n_feste: int, je_fest: int, treffer_je_fest):
    """Je Fest je_fest Gänge; im Fest i ist der Anteil treffer_je_fest[i] richtig."""
    p, y, meta = [], [], []
    for i in range(n_feste):
        for k in range(je_fest):
            richtig = k < treffer_je_fest[i] * je_fest
            p.append([0.7, 0.2, 0.1])
            y.append(0 if richtig else 2)
            meta.append({"event_id": f"f{i}"})
    return np.array(p), np.array(y), meta


def test_intervall_umschliesst_den_wert_und_ist_geordnet():
    rng = np.random.default_rng(0)
    p, y, meta = _daten(60, 20, rng.uniform(0.5, 0.8, 60))
    k = konfidenzintervalle(p, y, meta, wiederholungen=300)
    acc = float((p.argmax(1) == y).mean())
    assert k["n_feste"] == 60 and k["methode"] == "bootstrap_feste"
    assert k["accuracy"][0] < acc < k["accuracy"][1]
    assert k["log_loss"][0] < k["log_loss"][1]


def test_feste_gleich_heisst_kein_spielraum():
    # Alle Feste identisch: jeder Bootstrap-Zug ergibt denselben Wert.
    p, y, meta = _daten(10, 10, [0.6] * 10)
    k = konfidenzintervalle(p, y, meta, wiederholungen=50)
    assert k["accuracy"][0] == k["accuracy"][1] == 0.6


def test_ohne_testgaenge_kein_intervall():
    assert konfidenzintervalle(np.empty((0, 3)), np.empty(0, dtype=int), []) is None
