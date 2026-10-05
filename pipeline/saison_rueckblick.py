"""Saisonrückblick (Seite /rueckblick): was eine Saison ausgemacht hat.

Je Saison:
* Eckdaten: Feste, Gänge, aktive Schwinger, Anteil Gestellte.
* Aufsteiger: grösster Elo-Gewinn über die Saison (Stand vor dem ersten bis
  nach dem letzten Fest), nur wer genug Gänge hatte -- sonst ist der Gewinn
  vor allem das Einschwingen eines Neulings.
* Kränze je Schwinger in dieser Saison (aus den Schlussranglisten).
* Überraschungen: Siege, die das Modell von vor der Saison am wenigsten
  erwartet hatte (prognose_check).

Festsiege, Kranzfeste und die Trefferquote je Fest stehen schon in
schwinger.json und events.json; die Seite liest sie dort.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import groupby

from .ratings import EloModell

# Mindestzahl Gänge in der Saison für die Aufsteiger-Liste.
MIN_GAENGE_AUFSTEIGER = 15
# Ab dieser Zahl Feste gilt ein Jahr als Saison (2023 begann der Datenbestand im April).
MIN_FESTE_SAISON = 20
TOP = 10


def elo_je_saison(gaenge) -> dict[int, dict]:
    """Je Saison: Elo vor dem ersten und nach dem letzten Fest, Gänge je Schwinger.

    Fährt Elo genauso durch wie ratings.fahre_elo_durch (gleiche Reihenfolge,
    gleiche Updates), merkt sich aber die Stände an den Saisongrenzen.
    """
    modell = EloModell()
    aus: dict[int, dict] = {}
    geordnet = sorted(gaenge, key=lambda g: (g.datum, g.event_id))
    for jahr, gaenge_jahr in groupby(geordnet, key=lambda g: int(g.datum[:4])):
        gaenge_jahr = list(gaenge_jahr)
        # Stand vor dem ersten Gang der Saison, je Schwinger beim ersten
        # Auftritt abgelesen (so gilt auch ein abweichender Startwert für
        # Neulinge, s. EloModell.get).
        vorher: dict[str, float] = {}
        neu: set[str] = set()
        n = defaultdict(int)
        for _, fest in groupby(gaenge_jahr, key=lambda g: (g.datum, g.event_id)):
            for gang in fest:
                for sid in (gang.schwinger_a_id, gang.schwinger_b_id):
                    if sid not in vorher:
                        vorher[sid] = modell.get(sid)
                        if modell.gaenge_gezaehlt.get(sid, 0) == 0:
                            neu.add(sid)
                modell.update(gang)
                n[gang.schwinger_a_id] += 1
                n[gang.schwinger_b_id] += 1
        aus[jahr] = {"vorher": vorher, "nachher": dict(modell.ratings), "gaenge": dict(n),
                     "neu": neu,
                     "feste": len({g.event_id for g in gaenge_jahr}),
                     "n_gaenge": len(gaenge_jahr),
                     "gestellt": sum(g.ergebnis == "gestellt" for g in gaenge_jahr),
                     "von": gaenge_jahr[0].datum, "bis": gaenge_jahr[-1].datum}
    return aus


def kraenze_je_saison(teilnahmen) -> dict[int, dict[str, int]]:
    """Kränze je Saison und Schwinger aus den Schlussranglisten."""
    aus: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in teilnahmen:
        if t.kranz:
            aus[int(t.datum[:4])][t.schwinger_id] += 1
    return {j: dict(v) for j, v in aus.items()}


def rueckblick(gaenge, schwinger: dict, *, kraenze: dict[int, dict[str, int]] | None = None,
               ueberraschungen: dict[str, list[dict]] | None = None) -> dict:
    """saison_rueckblick.json: {"saisons": {"2026": {...}, ...}}."""
    name = lambda sid: schwinger[sid].name if sid in schwinger else sid  # noqa: E731
    elo = elo_je_saison(gaenge)
    saisons = {}
    for jahr, e in sorted(elo.items()):
        if e["feste"] < MIN_FESTE_SAISON:
            continue
        auf = []
        for sid, n in e["gaenge"].items():
            if n < MIN_GAENGE_AUFSTEIGER:
                continue
            vor, nach = e["vorher"][sid], e["nachher"][sid]
            auf.append({"id": sid, "name": name(sid), "elo_vorher": round(vor, 1),
                        "elo_nachher": round(nach, 1), "gewinn": round(nach - vor, 1), "gaenge": n,
                        "neu": sid in e["neu"]})
        auf.sort(key=lambda a: -a["gewinn"])
        kr = sorted(((kraenze or {}).get(jahr, {})).items(), key=lambda kv: (-kv[1], name(kv[0])))
        saisons[str(jahr)] = {
            "von": e["von"], "bis": e["bis"],
            "n_feste": e["feste"], "n_gaenge": e["n_gaenge"],
            "n_schwinger": len(e["gaenge"]),
            "anteil_gestellt": round(e["gestellt"] / e["n_gaenge"], 4) if e["n_gaenge"] else None,
            "aufsteiger": auf[:TOP],
            "kraenze": [{"id": sid, "name": name(sid), "kraenze": n} for sid, n in kr[:TOP]],
            "ueberraschungen": [
                {**u, "sieger_name": name(u["sieger"]), "verlierer_name": name(u["verlierer"])}
                for u in (ueberraschungen or {}).get(str(jahr), [])],
        }
    return {"schema_version": "1.0.0", "saisons": saisons}
