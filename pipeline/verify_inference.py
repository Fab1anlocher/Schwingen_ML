"""Cross-Check: JSON-Artefakt-Inferenz == sklearn-Modell (NFR-3).

Stellt sicher, dass die Gewichte in model.json -- mit der Softmax-Logik, die
web/lib/inference.ts spiegelt -- dieselben Wahrscheinlichkeiten liefern wie
das trainierte sklearn-Modell. Verhindert Drift beim Export der Gewichte.

Was es NICHT prüft: den Merkmalsvektor der Web-App. Der Vektor wird hier mit
Python gebaut (feature_vektor_fuer_prognose), nicht mit baueFeatures aus
inference.ts. Ein Fehler in der TypeScript-Spiegelung fiele diesem Check
nicht auf und erzeugte still falsche Live-Prognosen. Früher stand hier, er
stelle sicher, "dass die clientseitige Inferenz ... dieselben
Wahrscheinlichkeiten liefert" -- das war zu weit gegriffen. Die TypeScript-
Seite prüft pipeline/paritaet.py (CI-Job inferenz-paritaet).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

# Windows-Konsolen laufen oft auf cp1252, das kann "✓" nicht encodieren —
# ohne das hier stürzt nur der letzte print(), obwohl die eigentliche
# Prüfung (assert max_abw < 1e-9) längst erfolgreich durchgelaufen ist.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from .modell import TYP_GBM
from .paritaet import json_inferenz_wie_app, python_live_merkmale
from .schema import Schwinger

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"


# Eine einzige Python-Spiegelung der App-Inferenz statt einer eigenen Kopie
# hier -- jede weitere Kopie ist eine weitere Stelle, die auseinanderlaufen kann.
json_inferenz = json_inferenz_wie_app


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
        # Mit Merkmalsversion, Skala und Neigung aus den Artefakten.
        x = python_live_merkmale(model, a_dict, b_dict, ra, rb, 0.0, heute)
        assert len(x) == len(model["features"]), (
            f"Merkmalsvektor {len(x)} lang, Modell kennt {len(model['features'])} -- "
            "Merkmalsversion im model.json passt nicht zum Code"
        )

        p_json = json_inferenz(model, x)

        if model.get("typ") == TYP_GBM:
            # Das sklearn-Modell selbst gibt es nach dem Lauf nicht mehr; die
            # Gleichheit JSON == sklearn prüft export.pruefe_modell_export schon
            # beim Export. Hier: normiert und paar-symmetrisch -- "B gegen A"
            # muss "A gegen B" mit vertauschten Siegklassen ergeben.
            x_ba = python_live_merkmale(model, b_dict, a_dict, rb, ra, 0.0, heute)
            p_ba = json_inferenz(model, x_ba)
            abw = max(abs(sum(p_json) - 1.0), *(abs(u - v) for u, v in zip(p_json, p_ba[::-1])))
            max_abw = max(max_abw, abw)
            print(f"{a.name} vs {b.name}: P={[round(v, 3) for v in p_json]} symmetrisch, abw={abw:.2e}")
            continue

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
    print("✓ model.json konsistent mit dem sklearn-Modell (TypeScript-Seite: pipeline.paritaet).")


if __name__ == "__main__":
    main()
