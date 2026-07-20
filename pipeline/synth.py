"""Synthetischer Daten-Generator (Entwicklung/Demo).

Erzeugt realistische Schwinger, Feste und Roh-Gang-Einträge (beide PDF-
Perspektiven), damit die gesamte Pipeline ohne Live-Scraping end-to-end
läuft und die Web-App echte Artefakte hat. Reproduzierbar über SEED.

Sobald die echten Scraper (pipeline/scrape/) angebunden sind, ersetzt deren
Output diese Funktion 1:1 (gleiches Schema).
"""
from __future__ import annotations

import random

from .config import SEED, FEST_TYPEN
from .schema import Schwinger, Event, schwinger_key
from .labels import RohGangEintrag

_VORNAMEN = [
    "Christian", "Joel", "Fabian", "Samuel", "Werner", "Matthias", "Armon",
    "Domenic", "Curdin", "Benji", "Marcel", "Nick", "Michael", "Damian",
    "Roman", "Pirmin", "Kilian", "Lario", "Adrian", "Sven", "Remo", "Andreas",
    "Thomas", "Bernhard", "Florian", "Marco", "Reto", "Stefan", "Patrick",
]
_NACHNAMEN = [
    "Stucki", "Wicki", "Giger", "Orlik", "Schurtenberger", "Staudenmann",
    "Gnägi", "Suppiger", "Reichmuth", "von Weissenfluh", "Ott", "Schlegel",
    "Vogt", "Käser", "Odermatt", "Bieri", "Herger", "Roth", "Forrer",
    "Krähenbühl", "Marti", "Notz", "Räbmatter", "Egger", "Bürgler",
]
_KANTONE = ["BE", "LU", "SZ", "SG", "TG", "ZH", "AG", "GR", "OW", "NW", "UR", "FR", "VS"]
_TEILVERBAENDE = ["berner", "innerschweizer", "nordostschweizer",
                  "nordwestschweizer", "suedwestschweizer"]
_SCHWUENGE = ["Kurz", "Wyberhaggen", "Brienzer", "Übersprung", "Kurzzug",
              "Gammen", "Hüfter", "Bur", "Fussstich"]
_KRANZSTUFEN = ["kein", "kranzer", "eidgenosse", "koenig"]


def _kranz_gewicht(staerke: float) -> str:
    if staerke > 0.90:
        return "koenig"
    if staerke > 0.70:
        return "eidgenosse"
    if staerke > 0.40:
        return "kranzer"
    return "kein"


def erzeuge_schwinger(n: int, rng: random.Random) -> dict[str, Schwinger]:
    schwinger: dict[str, Schwinger] = {}
    versuche = 0
    while len(schwinger) < n and versuche < n * 10:
        versuche += 1
        name = f"{rng.choice(_VORNAMEN)} {rng.choice(_NACHNAMEN)}"
        jahrgang = rng.randint(1990, 2004)
        key = schwinger_key(name, jahrgang)
        if key in schwinger:
            continue
        staerke = rng.betavariate(2, 2)          # latente Stärke 0..1
        tv = rng.choice(_TEILVERBAENDE)
        schwinger[key] = Schwinger(
            id=key,
            name=name,
            jahrgang=jahrgang,
            groesse_cm=round(rng.gauss(185, 7), 0),
            gewicht_kg=round(rng.gauss(110, 12), 0),
            kranzstatus=_kranz_gewicht(staerke),
            teilverband=tv,
            kanton=rng.choice(_KANTONE),
            schwingklub=f"SK {rng.choice(_NACHNAMEN)}tal",
            senne_turner=rng.choice(["senne", "turner"]),
            schwinger_seit=jahrgang + rng.randint(6, 12),
            bevorzugte_schwuenge=rng.sample(_SCHWUENGE, k=rng.randint(1, 3)),
            quellen=["synthetisch"],
        )
        # latente Stärke fürs Ergebnis-Sampling merken (nicht im Schema).
        schwinger[key]._staerke = staerke  # type: ignore[attr-defined]
    return schwinger


def _note_fuer(symbol: str, rng: random.Random) -> float:
    if symbol == "+":
        return rng.choice([10.0, 9.75])
    if symbol == "-":
        return rng.choice([8.75, 9.00, 9.25])
    return round(rng.uniform(8.5, 9.0) * 4) / 4


def _sample_ergebnis(sa: Schwinger, sb: Schwinger, rng: random.Random) -> tuple[str, str]:
    """Ergebnis-Symbole (A, B) aus latenter Stärke + Rauschen."""
    da = getattr(sa, "_staerke", 0.5) + rng.gauss(0, 0.15)
    db = getattr(sb, "_staerke", 0.5) + rng.gauss(0, 0.15)
    diff = da - db
    if abs(diff) < 0.06:
        return "-", "-"                    # Gestellt
    if diff > 0:
        return "+", "o"                    # A siegt
    return "o", "+"                        # B siegt


def erzeuge_datensatz(
    n_schwinger: int = 120,
    n_events: int = 40,
    saison_start: int = 2022,
    saison_ende: int = 2025,
) -> tuple[dict[str, Schwinger], list[Event], list[RohGangEintrag]]:
    rng = random.Random(SEED)
    schwinger = erzeuge_schwinger(n_schwinger, rng)
    ids = list(schwinger.keys())

    events: list[Event] = []
    roh: list[RohGangEintrag] = []

    for e in range(n_events):
        jahr = rng.randint(saison_start, saison_ende)
        monat = rng.randint(4, 9)
        tag = rng.randint(1, 28)
        datum = f"{jahr:04d}-{monat:02d}-{tag:02d}"
        typ = rng.choices(FEST_TYPEN, weights=[1, 2, 5, 4, 6])[0]
        ev_id = f"synth-{e:03d}"
        events.append(
            Event(id=ev_id, name=f"Schwingfest {e:03d} {jahr}", datum=datum,
                  typ=typ, quelle="synthetisch", ort=rng.choice(_KANTONE))
        )
        # Teilnehmerfeld + Paarungen.
        n_teiln = rng.randint(16, 40)
        teilnehmer = rng.sample(ids, k=min(n_teiln, len(ids)))
        n_gaenge = rng.randint(4, 6)
        for _ in range(n_gaenge * len(teilnehmer) // 2):
            a, b = rng.sample(teilnehmer, 2)
            sym_a, sym_b = _sample_ergebnis(schwinger[a], schwinger[b], rng)
            # Beide PDF-Perspektiven erzeugen (§4.3 Regel 2).
            roh.append(RohGangEintrag(ev_id, datum, a, b, sym_a, _note_fuer(sym_a, rng), typ))
            roh.append(RohGangEintrag(ev_id, datum, b, a, sym_b, _note_fuer(sym_b, rng), typ))

    return schwinger, events, roh
