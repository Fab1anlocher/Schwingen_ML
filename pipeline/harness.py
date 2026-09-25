"""Echte-Daten-Harness: Modelländerungen an echten Daten messen, ohne Rohdaten.

Die Rohdaten (``artifacts/raw``) liegen nur im Cache von GitHub Actions, und
schlussgang.ch ist nicht aus jeder Umgebung erreichbar. Die committeten
Artefakte reichen aber, um die Pipeline-Eingabe nachzubauen:

* ``artifacts/kopf_an_kopf.json`` hält JEDEN Gang (Paar, Fest, Ergebnis),
* ``artifacts/events.json`` Datum und Typ jedes Fests,
* ``artifacts/schwinger.json`` die Schwinger samt Porträt-Attributen.

Daraus entstehen dieselben ``GangResultat``-Objekte, die ``run_pipeline``
aus den Rohdaten baut -- mit einer Einschränkung: die Reihenfolge der Gänge
INNERHALB eines Fests ist nicht rekonstruierbar. Seit alle Merkmale den Stand
vor dem Fest nutzen (Merkmalsversion 2), spielt das für die Merkmale keine
Rolle mehr; die Elo-Fortschreibung innerhalb eines Fests weicht minimal ab
(Stand Merkmalsversion 3: Test-Log-Loss hier 0.7400, im echten Lauf 0.7404).

Vorgehen für eine Modelländerung (so entstanden Merkmalsversion 2 und 3):

    from pipeline.harness import lade, bewerte
    X, y, meta = lade()                      # Merkmale wie im echten Lauf
    basis = bewerte(X, y, meta)              # Validierung 2025 + Test 2026
    X2 = ...                                 # Variante, gleiche Zeilen
    neu = bewerte(X2, y, meta)

Übernehmen nur, wenn Validierung UND Test besser werden -- ein Gewinn nur
auf einem der beiden ist meist Rauschen oder Überanpassung an ein Jahr.

Aufruf ``python -m pipeline.harness`` gibt die Kennzahlen des aktuellen Codes aus.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import numpy as np

from .labels import GangResultat
from .schema import Schwinger

ARTEFAKTE = Path(__file__).resolve().parent.parent / "artifacts"
_ERGEBNIS = {"A": "sieg_a", "D": "gestellt", "B": "sieg_b"}
_SYMBOLE = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}


def lade_schwinger(artefakte: Path = ARTEFAKTE) -> dict[str, Schwinger]:
    felder = {f.name for f in fields(Schwinger)}
    roh = json.loads((artefakte / "schwinger.json").read_text(encoding="utf-8"))["schwinger"]
    return {d["id"]: Schwinger(**{k: v for k, v in d.items() if k in felder}) for d in roh}


def lade_gaenge(artefakte: Path = ARTEFAKTE) -> list[GangResultat]:
    """Alle Gänge aus dem Kopf-an-Kopf-Index (s. export.exportiere_kopf_an_kopf)."""
    kk = json.loads((artefakte / "kopf_an_kopf.json").read_text(encoding="utf-8"))
    feste = {e["id"]: e for e in json.loads((artefakte / "events.json").read_text(encoding="utf-8"))["vergangene"]}
    schwinger_von = {i: sid for sid, i in kk["index"].items()}
    fest_von = {i: eid for eid, i in kk["event_index"].items()}
    gaenge: list[GangResultat] = []
    for paar, duelle in kk["paare"].items():
        ia, ib = map(int, paar.split("_"))
        a, b = schwinger_von[ia], schwinger_von[ib]  # a ist die kanonisch kleinere ID
        for fest_idx, code in duelle:
            fest = feste.get(fest_von[fest_idx])
            if fest is None:
                continue
            ergebnis = _ERGEBNIS[code]
            sa, sb = _SYMBOLE[ergebnis]
            gaenge.append(GangResultat(
                event_id=fest["id"], datum=fest["datum"], schwinger_a_id=a, schwinger_b_id=b,
                symbol_a=sa, note_a=None, symbol_b=sb, note_b=None,
                ergebnis=ergebnis, fest_typ=fest["typ"],
            ))
    return gaenge


def lade(artefakte: Path = ARTEFAKTE):
    """(X, y, meta) genau wie run_pipeline sie baut (Elo -> Merkmale, gespiegelt)."""
    from .features import baue_features
    from .ratings import fahre_elo_durch

    gaenge, schwinger = lade_gaenge(artefakte), lade_schwinger(artefakte)
    _, snapshots = fahre_elo_durch(gaenge)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    return np.asarray(X), np.asarray(y), meta


def bewerte(X, y, meta, jahre: tuple[int, ...] = (2025, 2026)) -> dict[int, dict]:
    """Je Testjahr: trainieren auf allem davor (echte Trainingsmaske inkl.
    Einschwingphase), bewerten auf diesem Jahr ohne Spiegelzeilen."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

    from .config import SEED
    from .train import trainings_maske

    X, y = np.asarray(X), np.asarray(y)
    jahr = np.array([int(m["datum"][:4]) for m in meta])
    gespiegelt = np.array([bool(m.get("augmented")) for m in meta])
    out = {}
    for j in jahre:
        train = trainings_maske(meta, y, j) & (jahr < j)
        test = (jahr == j) & ~gespiegelt
        mu, sd = X[train].mean(0), X[train].std(0)
        sd[sd == 0] = 1.0
        modell = LogisticRegression(max_iter=3000, C=1.0, random_state=SEED)
        modell.fit((X[train] - mu) / sd, y[train])
        p = modell.predict_proba((X[test] - mu) / sd)
        out[j] = {
            "log_loss": round(float(log_loss(y[test], p, labels=[0, 1, 2])), 4),
            "accuracy": round(float(accuracy_score(y[test], p.argmax(1))), 4),
            "auc_gestellt": round(float(roc_auc_score(y[test] == 1, p[:, 1])), 4),
            "gestellt_vorhergesagt": round(float(p[:, 1].mean()), 4),
            "gestellt_eingetreten": round(float((y[test] == 1).mean()), 4),
            "n": int(test.sum()),
        }
    return out


if __name__ == "__main__":
    X, y, meta = lade()
    print(f"{len(X)} Zeilen x {X.shape[1]} Merkmale")
    for j, k in bewerte(X, y, meta).items():
        print(f"Test {j}: {k}")
