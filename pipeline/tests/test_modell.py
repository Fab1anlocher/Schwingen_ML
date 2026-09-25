"""Prognosemodell (modell.py): Symmetrie, zeitliche Baumzahl, Export == Modell."""
from __future__ import annotations

import numpy as np
import pytest

from pipeline import modell as modell_modul
from pipeline.export import modell_json, pruefe_modell_export
from pipeline.features import FEATURE_NAMES
from pipeline.modell import SYMMETRISCH, spiegel_vektor, spiegle, trainiere_modell
from pipeline.paritaet import json_inferenz_wie_app


@pytest.fixture(autouse=True)
def _schnell(monkeypatch, request):
    """Höchstens 150 Bäume, und ohne Zeitgewicht ausser in Tests mit
    "gewicht" im Namen: mit Stichprobengewicht rechnet sklearn die
    Bin-Grenzen als gewichtete Perzentile, ~5 s je Fit schon auf diesen
    kleinen Daten. Symmetrie, Export und Monotonie hängen nicht davon ab."""
    monkeypatch.setattr(modell_modul, "GBM_MAX_BAEUME", 150)
    if "gewicht" not in request.node.name:
        monkeypatch.setattr(modell_modul, "zeitgewicht", lambda datum_tr: None)


def _daten(n=900, seed=0):
    """Synthetische Gänge mit Spiegelzeilen: Sieg hängt am ersten Merkmal."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, len(FEATURE_NAMES)))
    sym = spiegel_vektor() > 0
    X[:, sym] = np.abs(X[:, sym])
    p_a = 1 / (1 + np.exp(-2 * X[:, 0]))
    y = np.where(rng.random(n) < 0.2, 1, np.where(rng.random(n) < p_a, 0, 2))
    Xs = spiegle(X)
    ys = np.array([{0: 2, 1: 1, 2: 0}[v] for v in y])
    datum = [f"2025-{1 + i % 12:02d}-01" for i in range(n)]
    return np.vstack([X, Xs]), np.concatenate([y, ys]), datum + datum


def test_spiegel_vektor_kennt_die_symmetrischen_merkmale():
    s = spiegel_vektor()
    assert len(s) == len(FEATURE_NAMES)
    assert {n for n, v in zip(FEATURE_NAMES, s) if v > 0} == SYMMETRISCH


def test_boosting_ist_exakt_paar_symmetrisch():
    X, y, datum = _daten()
    m = trainiere_modell(X, y, datum, "gbm")
    p, q = m.predict_proba(X[:50]), m.predict_proba(spiegle(X[:50]))
    assert np.allclose(p, q[:, ::-1], atol=1e-12)
    assert np.allclose(p.sum(axis=1), 1.0)


def test_export_rechnet_wie_das_trainierte_modell_boosting_und_lr():
    X, y, datum = _daten()
    for typ in ("gbm", "lr"):
        m = trainiere_modell(X, y, datum, typ)
        artefakt = {"features": FEATURE_NAMES, **modell_json(m)}
        assert pruefe_modell_export(m, artefakt, X[:100]) < 1e-5
        x = list(X[3])
        assert np.allclose(json_inferenz_wie_app(artefakt, x), m.predict_proba(X[3:4])[0], atol=1e-5)


def test_baumzahl_wird_je_stufe_zeitlich_gewaehlt_auch_mit_gewicht():
    X, y, datum = _daten()
    m = trainiere_modell(X, y, datum, "gbm")
    assert set(m.n_baeume) == {"gestellt", "sieg"}
    assert all(1 <= n <= 150 for n in m.n_baeume.values())


def test_zeitgewicht_halbiert_sich_je_halbwertszeit():
    from pipeline.modell import zeitgewicht

    w = zeitgewicht(["2024-09-25", "2025-09-25", "2026-09-25"], 365.0)
    assert np.allclose(w, [0.25, 0.5, 1.0], atol=0.01)
    assert zeitgewicht(["2026-09-25"], None) is None


def test_monotonie_vorgaben_gelten_fuer_die_gestellt_chance():
    """Orlik-Staudenmann-Fall: mehr gestellte Duelle dürfen P(Gestellt) nicht
    senken, ein grösserer Rating-Abstand darf sie nicht erhöhen."""
    X, y, datum = _daten()
    m = trainiere_modell(X, y, datum, "gbm")
    for merkmal, richtung in (("paar_gestellt", 1), ("gestellt_neigung", 1), ("rating_abstand", -1)):
        i = FEATURE_NAMES.index(merkmal)
        Z = np.repeat(X[:40], 9, axis=0)
        Z[:, i] = np.tile(np.linspace(-0.2, 2.0, 9), 40)
        g = m.predict_proba(Z)[:, 1].reshape(40, 9)
        assert (richtung * np.diff(g, axis=1) >= -1e-12).all(), merkmal
