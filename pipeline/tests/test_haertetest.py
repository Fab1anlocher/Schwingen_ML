"""Härtetest (haertetest.py): Einfrieren, Wache, Auswertung -- und die
vektorisierte Inferenz rechnet wie die App-Nachbildung."""
from __future__ import annotations

import json
import random

import numpy as np
import pytest

from pipeline import config, haertetest
from pipeline import modell as modell_modul
from pipeline.export import modell_json
from pipeline.features import FEATURE_NAMES
from pipeline.modell import spiegel_vektor, spiegle, trainiere_modell
from pipeline.paritaet import json_inferenz_wie_app, lr_gestalt


@pytest.fixture(autouse=True)
def _schnell(monkeypatch):
    monkeypatch.setattr(modell_modul, "GBM_MAX_BAEUME", 60)
    monkeypatch.setattr(modell_modul, "zeitgewicht", lambda datum_tr: None)


def _daten(n_je_jahr=400, jahre=(2025, 2026), seed=0):
    """Gänge über mehrere Jahre, je 20 Gänge pro Fest, mit Spiegelzeilen."""
    rng = np.random.default_rng(seed)
    X, y, meta = [], [], []
    for jahr in jahre:
        for i in range(n_je_jahr):
            x = rng.normal(size=len(FEATURE_NAMES))
            x[spiegel_vektor() > 0] = np.abs(x[spiegel_vektor() > 0])
            p_a = 1 / (1 + np.exp(-2 * x[0]))
            k = 1 if rng.random() < 0.2 else (0 if rng.random() < p_a else 2)
            m = {"event_id": f"f{jahr}-{i // 20}", "datum": f"{jahr}-{5 + i // 100:02d}-{1 + (i // 20) % 28:02d}",
                 "schwinger_a_id": f"a{i}", "schwinger_b_id": f"b{i}", "elo_diff": 100 * x[0]}
            X += [x, spiegle(x[None, :])[0]]
            y += [k, {0: 2, 1: 1, 2: 0}[k]]
            meta += [m, {**m, "augmented": True, "elo_diff": -m["elo_diff"]}]
    return np.array(X), np.array(y), meta


def _modell(X, y, meta, typ="gbm") -> dict:
    m = trainiere_modell(X, y, [mm["datum"] for mm in meta], typ)
    return {"features": FEATURE_NAMES, "config": {"merkmal_version": 3}, **modell_json(m)}


def test_vektorisiert_wie_die_app():
    X, y, meta = _daten(n_je_jahr=150, jahre=(2025,))
    modell = _modell(X, y, meta)
    p = haertetest.baeume_wahrscheinlichkeiten(modell, X[:60])
    for k in random.Random(0).sample(range(60), 20):
        assert np.allclose(p[k], json_inferenz_wie_app(modell, list(X[k])), atol=1e-12, rtol=0)
    lr = lr_gestalt(modell)
    p2 = haertetest.baeume_wahrscheinlichkeiten(lr, X[:20])
    assert np.allclose(p2, [json_inferenz_wie_app(lr, list(x)) for x in X[:20]], atol=1e-12, rtol=0)


def test_einfrieren_und_warten():
    X, y, meta = _daten()
    modell = _modell(X, y, meta)
    obj = haertetest.einfrieren(modell, X, meta, saison=2027, code_commit="abc")
    assert obj["pruefsumme"] == haertetest.pruefsumme(modell)
    assert len(obj["referenz"]) == min(haertetest.REFERENZ_GAENGE, len(X) // 2)
    # Fingerabdruck = die jüngsten Gänge
    assert obj["referenz"][-1]["gang"].startswith("f2026")
    res = haertetest.auswerten(obj, X, y, meta)
    assert res["status"] == "wartet" and res["n"] == 0
    assert res["wache"]["modell_unveraendert"] and res["wache"]["eingaben_unveraendert"]
    assert res["wache"]["warnung"] is None


def test_ersetzen_vor_der_pruefsaison_fuehrt_den_vorgaenger_mit():
    """Nach einer Datenkorrektur darf neu eingefroren werden, solange die
    Prüfsaison keinen Gang hat -- der Vorgänger bleibt sichtbar."""
    X, y, meta = _daten()
    erst = haertetest.einfrieren(_modell(X, y, meta), X, meta, saison=2027, code_commit="aaa")
    assert erst["vorgaenger"] == []
    zweit = haertetest.einfrieren(_modell(X[::-1], y[::-1], meta[::-1]), X, meta, saison=2027,
                                  code_commit="bbb", vorgaenger=erst)
    dritt = haertetest.einfrieren(_modell(X, y, meta), X, meta, saison=2027, vorgaenger=zweit)
    assert [v["code_commit"] for v in dritt["vorgaenger"]] == ["aaa", "bbb"]
    assert dritt["vorgaenger"][0]["pruefsumme"] == erst["pruefsumme"]
    assert haertetest.auswerten(dritt, X, y, meta)["vorgaenger"] == dritt["vorgaenger"]


def test_einfrieren_zu_spaet_bricht_ab():
    X, y, meta = _daten(jahre=(2026, 2027))
    with pytest.raises(RuntimeError, match="zu spät"):
        haertetest.einfrieren(_modell(X, y, meta), X, meta, saison=2027)


def test_auswertung_der_pruefsaison():
    X, y, meta = _daten(jahre=(2025, 2026, 2027))
    vor = np.array([int(m["datum"][:4]) < 2027 for m in meta])
    modell = _modell(X[vor], y[vor], [m for m, v in zip(meta, vor) if v])
    obj = haertetest.einfrieren(modell, X[vor], [m for m, v in zip(meta, vor) if v], saison=2027)
    res = haertetest.auswerten(obj, X, y, meta)
    assert res["status"] == "laeuft" and res["n"] == 400 and res["n_feste"] == 20
    p = haertetest.baeume_wahrscheinlichkeiten(modell, X[[i for i, m in enumerate(meta)
                                                          if m["datum"] >= "2027" and not m.get("augmented")]])
    yt = y[[i for i, m in enumerate(meta) if m["datum"] >= "2027" and not m.get("augmented")]]
    assert res["modell"]["treffer"] == round(float((p.argmax(1) == yt).mean()), 6)
    assert res["konfidenz"]["accuracy"][0] <= res["modell"]["treffer"] <= res["konfidenz"]["accuracy"][1]
    assert {"treffer", "log_loss", "brier"} <= set(res["elo_angepasst"])
    assert res["wache"]["eingaben_unveraendert"]


def test_wache_meldet_veraenderung():
    X, y, meta = _daten()
    modell = _modell(X, y, meta)
    obj = haertetest.einfrieren(modell, X, meta, saison=2027)
    # Andere Eingaben (z.B. geänderter Rating-Code): fast alle Merkmale anders.
    X2 = X.copy()
    X2[:, 0] += 0.5
    res = haertetest.auswerten(obj, X2, y, meta)
    assert not res["wache"]["eingaben_unveraendert"] and "andere Prognosen" in res["wache"]["warnung"]
    # Verändertes Modell: Prüfsumme stimmt nicht mehr.
    obj2 = json.loads(json.dumps(obj))
    obj2["modell"]["stufen"]["sieg"]["basis"] += 0.1
    res2 = haertetest.auswerten(obj2, X, y, meta)
    assert not res2["wache"]["modell_unveraendert"] and "Prüfsumme" in res2["wache"]["warnung"]


def test_ohne_einfrieren():
    X, y, meta = _daten(n_je_jahr=40, jahre=(2025,))
    assert haertetest.auswerten(None, X, y, meta)["status"] == "nicht_eingefroren"


def test_eingefrorene_datei_im_repo_ist_unveraendert():
    """Liegt ein eingefrorenes Modell im Repo, muss seine Prüfsumme stimmen --
    niemand darf es nachträglich anpassen (auch nicht der Bot)."""
    pfad = config.ARTIFACTS_DIR / haertetest.DATEINAME
    if not pfad.exists():
        pytest.skip("noch kein Modell eingefroren")
    obj = json.loads(pfad.read_text(encoding="utf-8"))
    assert haertetest.pruefsumme(obj["modell"]) == obj["pruefsumme"]
