"""Prognose-Check je Fest (Roadmap F1): wie gut lag das Modell im Rückblick?

Für jede auswertbare Saison wird das Modell verwendet, das VOR dieser Saison
galt -- trainiert auf allem davor, mit denselben Einstellungen wie im
Betrieb. Die Merkmale jedes Gangs zeigen ohnehin den Stand vor seinem Fest
(features.py). So entsteht genau die Prognose, die man damals hätte sehen
können, und keine, die das Ergebnis schon kannte.

Je Fest:
  treffer          Anteil Gänge, bei denen der wahrscheinlichste Ausgang eintrat
  treffer_elo      dasselbe für die reine Elo-Prognose (Vergleichsanker)
  p_eingetreten    mittlere Wahrscheinlichkeit, die das Modell dem tatsächlichen
                   Ausgang gab -- ehrlicher als "Treffer", weil ein Gestellter
                   fast nie der wahrscheinlichste Ausgang ist, aber oft 30-50 %
                   bekommt
  gestellt_*       vorhergesagte gegen eingetretene Gestellt-Quote

Ausgewertet werden die Holdout-Saison (Vorhersagen aus train.trainiere) und
davor jede Saison, vor der mindestens ``MIN_TRAININGSZEILEN`` eingeschwungene
Trainingszeilen liegen. Früher gäbe es nur ein Modell aus der Einschwingphase,
dessen Treffer nichts über das heutige Modell sagen.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .config import MODELL_TYP
from .modell import trainiere_modell
from .ratings import EloModell
from .train import einschwing_ende

# Spiegelzeilen mitgezählt (je Gang zwei Zeilen): rund eine halbe Saison.
MIN_TRAININGSZEILEN = 20_000


def auswertbare_saisons(meta, holdout: int) -> list[int]:
    """Saisons vor dem Holdout mit genug eingeschwungenem Training davor."""
    ende = einschwing_ende(meta)
    if ende is None:
        return []
    jahre = sorted({int(m["datum"][:4]) for m in meta})
    out = []
    for j in jahre:
        if j >= holdout:
            continue
        n = sum(1 for m in meta if int(m["datum"][:4]) < j and m["datum"] >= ende)
        if n >= MIN_TRAININGSZEILEN:
            out.append(j)
    return out


def _vorhersagen_saison(X, y, meta, saison: int, typ: str) -> tuple[np.ndarray, np.ndarray]:
    """(Zeilenindizes der Saison ohne Spiegelzeilen, Wahrscheinlichkeiten)."""
    from .train import trainings_maske

    train = trainings_maske(meta, y, saison)
    datum_tr = [m["datum"] for m, drin in zip(meta, train) if drin]
    modell = trainiere_modell(X[train], y[train], datum_tr, typ)
    idx = np.array([i for i, m in enumerate(meta)
                    if int(m["datum"][:4]) == saison and not m.get("augmented")], dtype=int)
    return idx, modell.predict_proba(X[idx]) if len(idx) else np.empty((0, 3))


def prognose_check(X, y, meta, snapshots, holdout: int, p_holdout: np.ndarray,
                   typ: str = MODELL_TYP) -> dict:
    """{"feste": {event_id: {...}}, "saisons": {"2026": {...}}} -- s. Moduldoku.

    ``p_holdout``: die Testvorhersagen aus train.trainiere, in der Reihenfolge
    der Holdout-Zeilen ohne Spiegelzeilen (wie _split_zeitlich sie auswählt).
    """
    X, y = np.asarray(X), np.asarray(y)
    elo = EloModell()
    snap = {(s["event_id"], s["schwinger_a_id"], s["schwinger_b_id"]): s for s in snapshots}

    teile: list[tuple[int, np.ndarray, np.ndarray]] = []
    for saison in auswertbare_saisons(meta, holdout):
        idx, p = _vorhersagen_saison(X, y, meta, saison, typ)
        teile.append((saison, idx, p))
    idx_holdout = np.array([i for i, m in enumerate(meta)
                            if int(m["datum"][:4]) >= holdout and not m.get("augmented")], dtype=int)
    if len(idx_holdout) == len(p_holdout):
        teile.append((holdout, idx_holdout, np.asarray(p_holdout)))

    summen: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    saison_summen: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for saison, idx, p in teile:
        for i, probs in zip(idx, p):
            m = meta[i]
            wahr = int(y[i])
            s = snap.get((m["event_id"], m["schwinger_a_id"], m["schwinger_b_id"]))
            for ziel in (summen[m["event_id"]], saison_summen[str(saison)]):
                ziel["n"] += 1
                ziel["treffer"] += float(int(np.argmax(probs)) == wahr)
                ziel["p_eingetreten"] += float(probs[wahr])
                ziel["gestellt_vorhergesagt"] += float(probs[1])  # Klassen: sieg_a, gestellt, sieg_b
                ziel["gestellt_eingetreten"] += float(wahr == 1)
                if s is not None:
                    pe = elo.wahrscheinlichkeiten(s["elo_a_pre"], s["elo_b_pre"])
                    ziel["n_elo"] += 1
                    ziel["treffer_elo"] += float(int(np.argmax(pe)) == wahr)
        for fest in {meta[i]["event_id"] for i in idx}:
            saison_summen[str(saison)]["n_feste"] += 1

    return {
        "feste": {eid: _verdichte(z) for eid, z in summen.items()},
        "saisons": {j: {**_verdichte(z), "n_feste": int(z["n_feste"])}
                    for j, z in sorted(saison_summen.items())},
    }


def _verdichte(z: dict) -> dict:
    n = int(z["n"])
    return {
        "n": n,
        "treffer": round(z["treffer"] / n, 4),
        "treffer_elo": round(z["treffer_elo"] / z["n_elo"], 4) if z["n_elo"] else None,
        "p_eingetreten": round(z["p_eingetreten"] / n, 4),
        "gestellt_vorhergesagt": round(z["gestellt_vorhergesagt"] / n, 4),
        "gestellt_eingetreten": round(z["gestellt_eingetreten"] / n, 4),
    }

