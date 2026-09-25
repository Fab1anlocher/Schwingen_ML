"""Prognose-Check je Fest (Roadmap F1): richtige Zuordnung und ehrliche Kennzahlen."""
from __future__ import annotations

import numpy as np

from pipeline import prognose_check as pc


def _meta(event_id, datum, a="a", b="b", augmented=False):
    return {"event_id": event_id, "datum": datum, "schwinger_a_id": a,
            "schwinger_b_id": b, "augmented": augmented}


def test_holdout_vorhersagen_werden_je_fest_und_saison_verdichtet(monkeypatch):
    # Keine frühere Saison auswertbar: nur die Holdout-Vorhersagen zählen.
    monkeypatch.setattr(pc, "auswertbare_saisons", lambda meta, holdout: [])
    meta = [
        _meta("alt", "2025-06-01"),
        _meta("f1", "2026-05-01"), _meta("f1", "2026-05-01", augmented=True),
        _meta("f1", "2026-05-01", "c", "d"),
        _meta("f2", "2026-06-01"),
    ]
    y = np.array([0, 0, 2, 1, 2])
    # Vorhersagen nur für die Holdout-Zeilen OHNE Spiegelzeile (f1, f1, f2).
    p = np.array([[0.6, 0.3, 0.1], [0.5, 0.2, 0.3], [0.2, 0.2, 0.6]])
    snapshots = [{"event_id": "f1", "schwinger_a_id": "a", "schwinger_b_id": "b",
                  "elo_a_pre": 1600.0, "elo_b_pre": 1400.0}]
    X = np.zeros((len(meta), 3))
    out = pc.prognose_check(X, y, meta, snapshots, 2026, p)

    f1 = out["feste"]["f1"]
    assert f1["n"] == 2
    assert f1["treffer"] == 0.5                      # 1. Gang richtig (sieg_a), 2. nicht (gestellt)
    assert f1["p_eingetreten"] == round((0.6 + 0.2) / 2, 4)
    assert f1["gestellt_eingetreten"] == 0.5
    assert f1["treffer_elo"] == 1.0                  # nur ein Gang mit Elo-Stand, A klar vorne
    assert out["feste"]["f2"]["treffer"] == 1.0
    assert "alt" not in out["feste"]                 # Saison 2025 wurde nicht ausgewertet
    s = out["saisons"]["2026"]
    assert s["n"] == 3 and s["n_feste"] == 2
    assert s["treffer"] == round(2 / 3, 4)


def test_nur_saisons_mit_eingeschwungenem_training_davor():
    # Datenbasis ab 2023: die Einschwingphase endet 2024; vor 2025 liegt eine
    # eingeschwungene Saison, vor 2024 keine.
    meta = [_meta("e", f"{j}-06-01") for j in (2023, 2024, 2025, 2026) for _ in range(25_000)]
    assert pc.auswertbare_saisons(meta, 2026) == [2025]
