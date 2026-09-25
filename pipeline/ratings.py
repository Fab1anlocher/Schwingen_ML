"""Elo-Baseline (ML-2).

Jedes komplexere Modell muss diese schlagen. Ratings werden STRIKT zeitlich
fortlaufend berechnet (Gänge chronologisch), damit sie als leak-freies
Merkmal (Rating VOR dem Gang) dienen können (ML-5, R-2).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import groupby

from .config import (
    ELO_START, ELO_K, ELO_DRAW_WIDTH, FEST_K_GEWICHT,
    ELO_STREUUNG_AKTIV_TAGE, ELO_STREUUNG_MIN_AKTIVE,
    ELO_STREUUNG_ERSATZ, ELO_STREUUNG_UNTERGRENZE,
)
from .labels import GangResultat


@dataclass
class EloModell:
    k: float = ELO_K
    draw_width: float = ELO_DRAW_WIDTH
    ratings: dict[str, float] = field(default_factory=dict)
    gaenge_gezaehlt: dict[str, int] = field(default_factory=dict)
    # Datum (ISO) des letzten Gangs je Schwinger -- für die Streuung der
    # AKTIVEN Ratings (elo_streuung): Zurückgetretene behalten ihr Rating
    # eingefroren und würden die Streuung sonst verfälschen.
    letzter_gang: dict[str, str] = field(default_factory=dict)
    # K-Gewicht je Fest-Stufe (Eidgenössisch zählt am meisten). Unbekannte
    # Stufe -> 0.6 (mittlere Gewichtung), damit Fremddaten nicht ausschlagen.
    fest_gewicht: dict = field(default_factory=lambda: dict(FEST_K_GEWICHT))

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
        k = self.k * self.fest_gewicht.get(gang.fest_typ, 0.6)
        self.ratings[a] = ra + k * (s_a - e_a)
        self.ratings[b] = rb + k * ((1.0 - s_a) - (1.0 - e_a))
        self.gaenge_gezaehlt[a] = self.gaenge_gezaehlt.get(a, 0) + 1
        self.gaenge_gezaehlt[b] = self.gaenge_gezaehlt.get(b, 0) + 1
        self.letzter_gang[a] = gang.datum
        self.letzter_gang[b] = gang.datum


def elo_streuung(modell: EloModell, stichtag: str) -> float:
    """Streuung der Ratings aller Schwinger mit einem Gang in den letzten
    ELO_STREUUNG_AKTIV_TAGE vor dem Stichtag -- die Einheit, in der der
    Elo-Abstand als Merkmal gemessen wird (Merkmalsversion 2).

    Warum überhaupt: die Ratings driften auseinander, solange das System
    einschwingt (2023: 41, 2024: 77, 2025: 107, 2026: 126). In absoluten
    Punkten bekäme derselbe echte Stärkeunterschied jedes Jahr mehr Abstand.
    In Einheiten der aktuellen Streuung bleibt das Merkmal über die Jahre
    vergleichbar -- und die Kalibrierung von P(gestellt) stimmt wieder.

    ISO-Daten vergleichen sich als Strings korrekt; das spart das Parsen
    tausender Daten je Fest.
    """
    grenze = (date.fromisoformat(stichtag) - timedelta(days=ELO_STREUUNG_AKTIV_TAGE)).isoformat()
    werte = [modell.get(sid) for sid, tag in modell.letzter_gang.items() if tag >= grenze]
    if len(werte) < ELO_STREUUNG_MIN_AKTIVE:
        return ELO_STREUUNG_ERSATZ
    mittel = sum(werte) / len(werte)
    streuung = math.sqrt(sum((w - mittel) ** 2 for w in werte) / len(werte))
    return max(streuung, ELO_STREUUNG_UNTERGRENZE)


def fahre_elo_durch(gaenge: list[GangResultat]) -> tuple[EloModell, list[dict]]:
    """Berechnet Elo chronologisch und gibt je Gang den Stand VOR DEM FEST zurück.

    Alle Gänge eines Fests sehen denselben Stand -- den vor dem ersten Gang --,
    fortgeschrieben wird erst danach. Früher bekam jeder Gang den Stand nach
    den im selben Fest zuvor VERARBEITETEN Gängen. Die Verarbeitungsreihenfolge
    innerhalb eines Fests ist aber nicht die Gangreihenfolge, sondern die
    Blockreihenfolge der Statistik-PDF, und die folgt dem SCHLUSSRANG. Damit
    flossen Ergebnisse desselben Tages in einer ergebnisabhängigen Reihenfolge
    in die Merkmale ein. Die App wiederum prognostiziert immer aus dem Stand
    vor einem Fest -- Training und Betrieb passten nicht zusammen.
    Gemessen an echten Daten: Test-Log-Loss 0.8314 -> 0.8204 allein dadurch.

    Die Fortschreibung selbst ist unverändert (gleiche Reihenfolge, gleiche
    Updates), die Ratings in ratings.json bleiben also dieselben.
    """
    modell = EloModell()
    snapshots: list[dict] = []
    geordnet = sorted(gaenge, key=lambda g: (g.datum, g.event_id))
    for (datum, _), fest in groupby(geordnet, key=lambda g: (g.datum, g.event_id)):
        fest = list(fest)
        streuung = elo_streuung(modell, datum)
        for gang in fest:
            snapshots.append(
                {
                    "event_id": gang.event_id,
                    "schwinger_a_id": gang.schwinger_a_id,
                    "schwinger_b_id": gang.schwinger_b_id,
                    "elo_a_pre": modell.get(gang.schwinger_a_id),
                    "elo_b_pre": modell.get(gang.schwinger_b_id),
                    "n_a_pre": modell.gaenge_gezaehlt.get(gang.schwinger_a_id, 0),
                    "n_b_pre": modell.gaenge_gezaehlt.get(gang.schwinger_b_id, 0),
                    "elo_streuung": streuung,
                }
            )
        for gang in fest:
            modell.update(gang)
    return modell, snapshots


def berechne_ueberraschung(gaenge: list[GangResultat], snapshots: list[dict],
                           ab_datum: str | None = None) -> dict[str, dict]:
    """Überraschungs-Index je Schwinger: tatsächliche vs. Elo-erwartete Punkte.

    Nutzt dieselben leak-freien Pre-Gang-Ratings wie die Features (ML-5) und
    dieselbe klassische Elo-Erwartung wie EloModell.update() (Sieg=1,
    Gestellt=0.5, Niederlage=0). Index = Mittel über alle Gänge eines
    Schwingers; positiv = übertrifft die Elo-Erwartung im Schnitt, negativ =
    bleibt darunter. Ergänzt die globale Feature-Wichtigkeit (ML-7) um eine
    Pro-Schwinger-Sicht.

    ``ab_datum``: nur Gänge ab diesem Datum zählen (die Pipeline übergibt das
    Ende der Einschwingphase). Davor liegen alle Ratings noch nahe beim
    Startwert: jeder Spitzenschwinger "übertraf die Erwartung", und sein
    grösster Überraschungssieg fiel in die ersten Wochen 2023 -- Orlik
    "schlug Thomas Bucher (17 Elo-Punkte Unterschied)".
    """
    idx = {s["event_id"] + s["schwinger_a_id"] + s["schwinger_b_id"]: s for s in snapshots}
    summe: dict[str, float] = defaultdict(float)
    anzahl: dict[str, int] = defaultdict(int)
    bester: dict[str, dict] = {}

    for gang in gaenge:
        if ab_datum and gang.datum < ab_datum:
            continue
        snap = idx.get(gang.event_id + gang.schwinger_a_id + gang.schwinger_b_id)
        if snap is None:
            continue
        ra, rb = snap["elo_a_pre"], snap["elo_b_pre"]
        e_a = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
        if gang.ergebnis == "sieg_a":
            s_a = 1.0
        elif gang.ergebnis == "gestellt":
            s_a = 0.5
        else:
            s_a = 0.0

        for sid, gegner_id, s_x, e_x, eigenes_elo, gegner_elo in (
            (gang.schwinger_a_id, gang.schwinger_b_id, s_a, e_a, ra, rb),
            (gang.schwinger_b_id, gang.schwinger_a_id, 1.0 - s_a, 1.0 - e_a, rb, ra),
        ):
            ueberraschung = s_x - e_x
            summe[sid] += ueberraschung
            anzahl[sid] += 1
            if s_x == 1.0 and (sid not in bester or ueberraschung > bester[sid]["ueberraschung"]):
                bester[sid] = {
                    "ueberraschung": round(ueberraschung, 3),
                    "gegner_id": gegner_id,
                    "event_id": gang.event_id,
                    "datum": gang.datum,
                    "eigenes_elo": round(eigenes_elo, 1),
                    "gegner_elo": round(gegner_elo, 1),
                }

    return {
        sid: {
            "index": round(summe[sid] / n, 4),
            "n": n,
            "groesster_erfolg": bester.get(sid),
        }
        for sid, n in anzahl.items()
    }


def bewerte_baseline(
    gaenge: list[GangResultat],
    snapshots: list[dict],
    klassen: list[str],
    *,
    nur_gaenge: set | None = None,
) -> dict:
    """Log-Loss & Accuracy der Elo-only-Baseline (ML-6, Vergleichsanker).

    ``nur_gaenge`` schränkt auf eine Menge von (event_id, a_id, b_id) ein --
    gedacht für den Holdout des Modells. Ohne diese Einschränkung lief die
    Baseline über ALLE Gänge 2023-2026, während das Modell nur den Holdout
    sah: der Satz "schlägt die Baseline" verglich damit zwei verschiedene
    Mengen unterschiedlicher Grösse aus verschiedenen Jahren.
    """
    modell = EloModell()
    idx = {s["event_id"] + s["schwinger_a_id"] + s["schwinger_b_id"]: s for s in snapshots}
    eps = 1e-15
    ll_summe = 0.0
    korrekt = 0
    n = 0
    for gang in gaenge:
        if nur_gaenge is not None and (
            gang.event_id, gang.schwinger_a_id, gang.schwinger_b_id
        ) not in nur_gaenge:
            continue
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
