"""Cross-Check: JSON-Artefakt-Inferenz == sklearn-Modelle (NFR-3).

Stellt sicher, dass die clientseitige Inferenz (die exakt diese JSON-Logik in
TypeScript spiegelt) für BEIDE Modelle (Logistic Regression und Gradient
Boosting) dieselben Wahrscheinlichkeiten liefert wie die trainierten
sklearn-Modelle. Verhindert Drift zwischen Training und Web-App.
"""
from __future__ import annotations

import math

import numpy as np

from .synth import erzeuge_datensatz
from .labels import dedupliziere
from .ratings import fahre_elo_durch
from .features import baue_features
from .train import trainiere
from .export import serialisiere_gbm


def _softmax(logits):
    m = max(logits)
    exp = [math.exp(l - m) for l in logits]
    s = sum(exp)
    return [e / s for e in exp]


def _lr_json_inferenz(model, x):
    mu, sigma = model["mu"], model["sigma"]
    z = [(x[i] - mu[i]) / (sigma[i] or 1) for i in range(len(x))]
    logits = [sum(model["coef"][k][i] * z[i] for i in range(len(z))) + model["intercept"][k]
              for k in range(len(model["coef"]))]
    return _softmax(logits)


def _tree_value(tree, x):
    node = 0
    while tree["children_left"][node] != -1:      # -1 == Blatt
        f = tree["feature"][node]
        node = (tree["children_left"][node] if x[f] <= tree["threshold"][node]
                else tree["children_right"][node])
    return tree["value"][node]


def _gbm_json_inferenz(gbm_json, x):
    raw = list(gbm_json["init_raw"])
    lr = gbm_json["learning_rate"]
    for stage in gbm_json["stages"]:
        for k, tree in enumerate(stage):
            raw[k] += lr * _tree_value(tree, x)
    return _softmax(raw)


def main():
    schwinger, events, roh = erzeuge_datensatz()
    gaenge, _ = dedupliziere(roh)
    _, snapshots = fahre_elo_durch(gaenge)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    train_res = trainiere(X, y, meta)

    lr = train_res["lr"]["modell"]
    gbm = train_res["gbm"]["modell"]
    lr_json = {
        "mu": [float(v) for v in train_res["mu"]],
        "sigma": [float(v) for v in train_res["sigma"]],
        "coef": [[float(v) for v in row] for row in lr.coef_],
        "intercept": [float(v) for v in lr.intercept_],
    }
    gbm_json = serialisiere_gbm(gbm)

    Xarr = np.array(X)
    mu = np.array(train_res["mu"]); sigma = np.array(train_res["sigma"])
    p_lr_ref = lr.predict_proba((Xarr - mu) / np.where(sigma == 0, 1, sigma))
    p_gbm_ref = gbm.predict_proba(Xarr)

    max_lr = max_gbm = 0.0
    idxs = range(0, len(X), max(1, len(X) // 50))  # ~50 Stichproben
    for i in idxs:
        x = X[i]
        p_lr = _lr_json_inferenz(lr_json, x)
        p_gbm = _gbm_json_inferenz(gbm_json, x)
        max_lr = max(max_lr, max(abs(a - b) for a, b in zip(p_lr, p_lr_ref[i])))
        max_gbm = max(max_gbm, max(abs(a - b) for a, b in zip(p_gbm, p_gbm_ref[i])))

    print(f"LR : max. Abweichung JSON vs sklearn = {max_lr:.2e}")
    print(f"GBM: max. Abweichung JSON vs sklearn = {max_gbm:.2e}")
    assert max_lr < 1e-9, "LR-Inferenz-Drift!"
    assert max_gbm < 1e-9, "GBM-Inferenz-Drift!"
    print("✓ Beide Modelle konsistent (clientseitige TS-Logik = sklearn).")


if __name__ == "__main__":
    main()
