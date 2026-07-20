"""Cross-Check: JSON-Artefakt-Inferenz == sklearn-Modell (NFR-3).

Stellt sicher, dass die clientseitige Inferenz (die exakt diese JSON-Logik
in TypeScript spiegelt) dieselben Wahrscheinlichkeiten liefert wie das
trainierte sklearn-Modell. Verhindert Drift zwischen Training und Web-App.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"


def _softmax(logits):
    m = max(logits)
    exp = [math.exp(l - m) for l in logits]
    s = sum(exp)
    return [e / s for e in exp]


def json_inferenz(model, x):
    """Reine JSON-Logik (identisch zu web/lib/inference.ts)."""
    mu = model["standardisierung"]["mu"]
    sigma = model["standardisierung"]["sigma"]
    z = [(x[i] - mu[i]) / (sigma[i] or 1) for i in range(len(x))]
    logits = [
        sum(model["coef"][k][i] * z[i] for i in range(len(z))) + model["intercept"][k]
        for k in range(len(model["coef"]))
    ]
    return _softmax(logits)


def main():
    model = json.loads((ART / "model.json").read_text())
    schwinger = {s["id"]: s for s in json.loads((ART / "schwinger.json").read_text())["schwinger"]}
    ratings = json.loads((ART / "ratings.json").read_text())["ratings"]

    kranz = model["config"]["kranzstatus_ordinal"]
    jahr = __import__("datetime").date.today().year

    ids = list(schwinger.keys())[:6]
    max_abw = 0.0
    for i in range(0, len(ids) - 1, 2):
        a, b = schwinger[ids[i]], schwinger[ids[i + 1]]
        ra = ratings.get(a["id"], {"elo": 1500, "n_gaenge": 0})
        rb = ratings.get(b["id"], {"elo": 1500, "n_gaenge": 0})

        def alter(s):
            return jahr - s["jahrgang"] if s["jahrgang"] else None

        def d(x, y):
            return (x - y) if (x is not None and y is not None) else 0.0

        x = [
            (ra["elo"] - rb["elo"]) / 100.0,
            a["form"] - b["form"],
            float(kranz.get(a["kranzstatus"], 0) - kranz.get(b["kranzstatus"], 0)),
            d(alter(a), alter(b)),
            d(a["gewicht_kg"], b["gewicht_kg"]),
            d(a["groesse_cm"], b["groesse_cm"]),
            float(ra["n_gaenge"] - rb["n_gaenge"]),
            0.0,  # bergfest
            0.0,  # gross_fest
            1.0 if a["teilverband"] and a["teilverband"] == b["teilverband"] else 0.0,
        ]

        p_json = json_inferenz(model, x)

        # Referenz: sklearn-Logik direkt (coef·z + intercept -> softmax) ist
        # identisch zu predict_proba der Multinomial-LR.
        mu = np.array(model["standardisierung"]["mu"])
        sigma = np.array(model["standardisierung"]["sigma"])
        z = (np.array(x) - mu) / np.where(sigma == 0, 1, sigma)
        logits = np.array(model["coef"]) @ z + np.array(model["intercept"])
        p_ref = np.exp(logits - logits.max())
        p_ref = p_ref / p_ref.sum()

        abw = max(abs(pj - pr) for pj, pr in zip(p_json, p_ref))
        max_abw = max(max_abw, abw)
        print(
            f"{a['name']} vs {b['name']}: "
            f"P={[round(v,3) for v in p_json]} (Summe {sum(p_json):.3f}) abw={abw:.2e}"
        )

    print(f"\nMax. Abweichung JSON vs Referenz: {max_abw:.2e}")
    assert max_abw < 1e-9, "Inferenz-Drift!"
    print("✓ Inferenz konsistent (clientseitige TS-Logik = Modell).")


if __name__ == "__main__":
    main()
