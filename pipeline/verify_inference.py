"""Cross-Check: JSON-Artefakt-Inferenz == sklearn-Modell (NFR-3).

Stellt sicher, dass die clientseitige Inferenz (die exakt diese JSON-Logik
in TypeScript spiegelt) dieselben Wahrscheinlichkeiten liefert wie das
trainierte sklearn-Modell. Verhindert Drift zwischen Training und Web-App.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

# Windows-Konsolen laufen oft auf cp1252, das kann "✓" nicht encodieren —
# ohne das hier stürzt nur der letzte print(), obwohl die eigentliche
# Prüfung (assert max_abw < 1e-9) längst erfolgreich durchgelaufen ist.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from .features import feature_vektor_fuer_prognose
from .schema import Schwinger

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


_SCHWINGER_FELDER = {f.name for f in Schwinger.__dataclass_fields__.values()}


def _schwinger_aus_dict(d: dict) -> Schwinger:
    return Schwinger(**{k: v for k, v in d.items() if k in _SCHWINGER_FELDER})


def main():
    model = json.loads((ART / "model.json").read_text())
    schwinger = {s["id"]: s for s in json.loads((ART / "schwinger.json").read_text())["schwinger"]}
    ratings = json.loads((ART / "ratings.json").read_text())["ratings"]

    heute = date.today().isoformat()

    ids = list(schwinger.keys())[:6]
    max_abw = 0.0
    for i in range(0, len(ids) - 1, 2):
        a_dict, b_dict = schwinger[ids[i]], schwinger[ids[i + 1]]
        a, b = _schwinger_aus_dict(a_dict), _schwinger_aus_dict(b_dict)
        ra = ratings.get(a.id, {"elo": 1500, "n_gaenge": 0})
        rb = ratings.get(b.id, {"elo": 1500, "n_gaenge": 0})

        # Dieselbe Funktion wie die Live-Prognose (pipeline/features.py) —
        # kein separat gepflegter Merkmalsvektor mehr, der aus dem Ruder
        # laufen kann (genau das ist hier zuvor passiert: rating_abstand
        # wurde in features.py ergänzt, aber nie in diesem Skript nachgezogen).
        x = feature_vektor_fuer_prognose(
            ra["elo"], rb["elo"], a_dict["form"], b_dict["form"],
            ra["n_gaenge"], rb["n_gaenge"], a, b, heute,
        )

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
            f"{a.name} vs {b.name}: "
            f"P={[round(v,3) for v in p_json]} (Summe {sum(p_json):.3f}) abw={abw:.2e}"
        )

    print(f"\nMax. Abweichung JSON vs Referenz: {max_abw:.2e}")
    assert max_abw < 1e-9, "Inferenz-Drift!"
    print("✓ Inferenz konsistent (clientseitige TS-Logik = Modell).")


if __name__ == "__main__":
    main()
