"""Elo-Baseline (ML-2).

Jedes komplexere Modell muss diese schlagen. Ratings werden STRIKT zeitlich
fortlaufend berechnet (Gänge chronologisch), damit sie als leak-freies
Merkmal (Rating VOR dem Gang) dienen können (ML-5, R-2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import ELO_START, ELO_K, ELO_DRAW_WIDTH
from .labels import GangResultat


@dataclass
class EloModell:
    k: float = ELO_K
    draw_width: float = ELO_DRAW_WIDTH
    ratings: dict[str, float] = field(default_factory=dict)
    gaenge_gezaehlt: dict[str, int] = field(default_factory=dict)

    def get(self, sid: str) -> float:
        return self.ratings.get(sid, ELO_START)

    def erwartung(self, ra: float, rb: float) -> float:
        """Erwartete Punkte für A (0..1) im klassischen Elo."""
        return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))

    def wahrscheinlichkeiten(self, ra: float, rb: float) -> tuple[float, float, float]:
        """P(sieg_a), P(gestellt), P(sieg_b) aus Ratingdifferenz.

        Gestellt wird über eine Draw-Breite um Ratinggleichheit modelliert
        (davidson-artig), damit die Baseline 3 Klassen ausgibt (R-1).
        """
        e_a = self.erwartung(ra, rb)          # 0..1
        # Wahrscheinlichkeit für Gestellt: maximal bei e_a=0.5, klein an den Rändern.
        p_draw = self.draw_width * (1.0 - abs(2 * e_a - 1.0))
        p_draw = max(0.0, min(0.6, p_draw))
        rest = 1.0 - p_draw
        p_a = rest * e_a
        p_b = rest * (1.0 - e_a)
        return p_a, p_draw, p_b

    def update(self, gang: GangResultat) -> None:
        """Aktualisiert Ratings NACH einem Gang (chronologisch aufrufen)."""
        a, b = gang.schwinger_a_id, gang.schwinger_b_id
        ra, rb = self.get(a), self.get(b)
        e_a = self.erwartung(ra, rb)
        # Tatsächliches Ergebnis für A: Sieg=1, Gestellt=0.5, Niederlage=0.
        if gang.ergebnis == "sieg_a":
            s_a = 1.0
        elif gang.ergebnis == "gestellt":
            s_a = 0.5
        else:
            s_a = 0.0
        self.ratings[a] = ra + self.k * (s_a - e_a)
        self.ratings[b] = rb + self.k * ((1.0 - s_a) - (1.0 - e_a))
        self.gaenge_gezaehlt[a] = self.gaenge_gezaehlt.get(a, 0) + 1
        self.gaenge_gezaehlt[b] = self.gaenge_gezaehlt.get(b, 0) + 1


def fahre_elo_durch(gaenge: list[GangResultat]) -> tuple[EloModell, list[dict]]:
    """Berechnet Elo chronologisch und gibt PRE-GANG-Ratings je Gang zurück.

    Die zurückgegebenen Snapshots (Rating VOR dem Gang) sind leak-frei als
    Merkmal verwendbar (ML-5).
    """
    modell = EloModell()
    snapshots: list[dict] = []
    for gang in sorted(gaenge, key=lambda g: (g.datum, g.event_id)):
        ra = modell.get(gang.schwinger_a_id)
        rb = modell.get(gang.schwinger_b_id)
        snapshots.append(
            {
                "event_id": gang.event_id,
                "schwinger_a_id": gang.schwinger_a_id,
                "schwinger_b_id": gang.schwinger_b_id,
                "elo_a_pre": ra,
                "elo_b_pre": rb,
                "n_a_pre": modell.gaenge_gezaehlt.get(gang.schwinger_a_id, 0),
                "n_b_pre": modell.gaenge_gezaehlt.get(gang.schwinger_b_id, 0),
            }
        )
        modell.update(gang)
    return modell, snapshots


def bewerte_baseline(
    gaenge: list[GangResultat], snapshots: list[dict], klassen: list[str]
) -> dict:
    """Log-Loss & Accuracy der Elo-only-Baseline (ML-6, Vergleichsanker)."""
    modell = EloModell()
    idx = {s["event_id"] + s["schwinger_a_id"] + s["schwinger_b_id"]: s for s in snapshots}
    eps = 1e-15
    ll_summe = 0.0
    korrekt = 0
    n = 0
    for gang in gaenge:
        key = gang.event_id + gang.schwinger_a_id + gang.schwinger_b_id
        snap = idx.get(key)
        if snap is None:
            continue
        p_a, p_draw, p_b = modell.wahrscheinlichkeiten(snap["elo_a_pre"], snap["elo_b_pre"])
        probs = {"sieg_a": p_a, "gestellt": p_draw, "sieg_b": p_b}
        p_wahr = max(eps, min(1 - eps, probs[gang.ergebnis]))
        ll_summe -= math.log(p_wahr)
        pred = max(probs, key=probs.get)
        if pred == gang.ergebnis:
            korrekt += 1
        n += 1
    return {
        "log_loss": ll_summe / n if n else float("nan"),
        "accuracy": korrekt / n if n else float("nan"),
        "n": n,
    }
