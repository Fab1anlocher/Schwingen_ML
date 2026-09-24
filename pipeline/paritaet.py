"""Paritätsprüfung Web-App (TypeScript) <-> Pipeline (Python).

Die Web-App rechnet jede Prognose selbst: web/lib/inference.ts baut den
Merkmalsvektor (baueFeatures) und wendet die Gewichte aus model.json an,
web/lib/kopfAnKopf.ts verdichtet die direkten Duelle. Beides sind HAND-
GESPIEGELTE Kopien der Python-Logik. verify_inference prüft davon nichts:
es baut den Vektor mit Python und vergleicht nur model.json gegen sklearn.
Eine Abweichung in der TypeScript-Kopie erzeugte still falsche Live-
Prognosen -- und genau so ist es schon einmal passiert (rating_abstand wurde
in features.py ergänzt und in einer Kopie nie nachgezogen, s. verify_inference).

Ablauf:
  1. ``python -m pipeline.paritaet --out web/.paritaet/faelle.json``
     erzeugt Prüffälle aus den committeten ECHTEN Artefakten (Schwinger,
     Ratings, Modell, Kopf-an-Kopf) samt der von Python erwarteten Werte.
  2. ``cd web && npm run paritaet`` kompiliert die TypeScript-Module und
     rechnet dieselben Fälle nach (web/scripts/paritaet.cjs).

Die Fälle decken bewusst alle Datenlagen ab (Porträt/Stub in allen vier
Kombinationen, fehlende Physis, fehlendes Rating) und Paare mit echter
Kopf-an-Kopf-Historie in BEIDEN Richtungen (A < B und A > B), weil die
Richtungsumkehr ein eigener Fehlerpunkt ist.

Geprüft wird gegen das committete model.json, wie die App es ausliefert --
auch wenn es dem Code einen Lauf hinterherhinkt.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date
from pathlib import Path

from .features import feature_vektor_fuer_prognose, _kopf_an_kopf_vorteil
from .schema import Schwinger, hat_portraet

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"
_FELDER = {f for f in Schwinger.__dataclass_fields__}
_CODE = {"A": "sieg_a", "D": "gestellt", "B": "sieg_b"}
_PUNKTE = {"sieg_a": 1.0, "gestellt": 0.5, "sieg_b": 0.0}


def _schwinger(d: dict) -> Schwinger:
    return Schwinger(**{k: v for k, v in d.items() if k in _FELDER})


def _rating(ratings: dict, elo_start: float, sid: str) -> dict:
    """Genau der Fallback der App: unbekannt -> Startwert, 0 Gänge."""
    return ratings.get(sid) or {"elo": elo_start, "n_gaenge": 0}


def json_inferenz_wie_app(model: dict, x: list[float]) -> list[float]:
    """Zeilengetreue Spiegelung von prognostiziere() in inference.ts.

    Inklusive des Kürzens auf die Merkmale, die DIESES model.json kennt --
    ein Modell, das dem Code hinterherhinkt, sieht nur die ersten N.
    """
    n = len(model["features"])
    x = x[:n]
    mu, sigma = model["standardisierung"]["mu"], model["standardisierung"]["sigma"]
    z = [(x[i] - mu[i]) / (sigma[i] or 1) for i in range(n)]
    logits = [
        sum(w * z[i] for i, w in enumerate(model["coef"][k])) + model["intercept"][k]
        for k in range(len(model["coef"]))
    ]
    m = max(logits)
    e = [math.exp(l - m) for l in logits]
    s = sum(e)
    return [v / s for v in e]


def python_live_merkmale(a: dict, b: dict, ra: dict, rb: dict, h2h: float, datum: str) -> list[float]:
    """Der Merkmalsvektor mit genau den Eingaben, die die App verwendet.

    Elo und Gänge aus ratings.json, Form aus schwinger.json, Attribute aus
    schwinger.json, Kopf-an-Kopf aus der API. Muss mit baueFeatures() in
    inference.ts übereinstimmen -- das prüft npm run paritaet.
    """
    return feature_vektor_fuer_prognose(
        ra["elo"], rb["elo"], a["form"], b["form"], ra["n_gaenge"], rb["n_gaenge"],
        _schwinger(a), _schwinger(b), datum, h2h,
    )


def _h2h_python(a_id: str, b_id: str, treffer_kanonisch: list[dict]) -> float:
    """Kopf-an-Kopf-Vorteil wie im Training: Historie aus Sicht der kleineren ID."""
    klein, gross = (a_id, b_id) if a_id < b_id else (b_id, a_id)
    punkte = [_PUNKTE[t["ergebnis"]] for t in treffer_kanonisch]
    return _kopf_an_kopf_vorteil(a_id, b_id, {(klein, gross): punkte} if punkte else {})


def _treffer_kanonisch(kk: dict, eid_von: dict, a_id: str, b_id: str) -> list[dict]:
    """Was die API /api/kopf-an-kopf liefert: aus Sicht der kleineren ID."""
    klein, gross = (a_id, b_id) if a_id < b_id else (b_id, a_id)
    if klein not in kk["index"] or gross not in kk["index"]:
        return []
    key = f"{kk['index'][klein]}_{kk['index'][gross]}"
    return [{"event_id": eid_von.get(e, str(e)), "ergebnis": _CODE[c]} for e, c in kk["paare"].get(key, [])]


def erzeuge_faelle(artefakte: Path = ART, n_je_gruppe: int = 40, seed: int = 7) -> dict:
    model = json.loads((artefakte / "model.json").read_text(encoding="utf-8"))
    rat = json.loads((artefakte / "ratings.json").read_text(encoding="utf-8"))
    ratings, elo_start = rat["ratings"], rat["elo_start"]
    schwinger = {s["id"]: s for s in json.loads((artefakte / "schwinger.json").read_text(encoding="utf-8"))["schwinger"]}
    kk = json.loads((artefakte / "kopf_an_kopf.json").read_text(encoding="utf-8"))
    eid_von = {i: e for e, i in kk["event_index"].items()}
    wid = {i: s for s, i in kk["index"].items()}

    rng = random.Random(seed)
    por = [s for s in schwinger.values() if hat_portraet(s.get("quellen"))]
    stub = [s for s in schwinger.values() if not hat_portraet(s.get("quellen"))]
    paare: list[tuple[str, dict, dict]] = []
    for name, (gA, gB) in {
        "portraet-portraet": (por, por), "portraet-stub": (por, stub),
        "stub-portraet": (stub, por), "stub-stub": (stub, stub),
    }.items():
        for _ in range(n_je_gruppe):
            paare.append((name, rng.choice(gA), rng.choice(gB)))

    # Paare mit echter Kopf-an-Kopf-Historie, in beiden Richtungen.
    mit_historie = [k for k, v in kk["paare"].items() if len(v) >= 2]
    rng.shuffle(mit_historie)
    for i, key in enumerate(mit_historie[: 2 * n_je_gruppe]):
        ia, ib = map(int, key.split("_"))
        a, b = schwinger.get(wid[ia]), schwinger.get(wid[ib])
        if a is None or b is None:
            continue
        paare.append(("historie-a<b", a, b) if i % 2 == 0 else ("historie-a>b", b, a))

    # Grenzfall: Schwinger ohne Rating -> Fallback der App (elo_start, 0 Gänge).
    paare.append(("ohne-rating", {**rng.choice(por), "id": "unbekannt|x"}, rng.choice(stub)))

    datum = date.today().isoformat()  # die App rechnet das Alter mit dem aktuellen Jahr
    faelle = []
    for gruppe, a, b in paare:
        if a["id"] == b["id"]:
            continue
        ra, rb = _rating(ratings, elo_start, a["id"]), _rating(ratings, elo_start, b["id"])
        treffer = _treffer_kanonisch(kk, eid_von, a["id"], b["id"])
        h2h = _h2h_python(a["id"], b["id"], treffer)
        x = python_live_merkmale(a, b, ra, rb, h2h, datum)
        faelle.append({
            "gruppe": gruppe, "a": a, "b": b, "rating_a": ra, "rating_b": rb,
            "treffer_kanonisch": treffer,
            "erwartet": {"h2h": h2h, "merkmale": x, "wahrscheinlichkeiten": json_inferenz_wie_app(model, x)},
        })
    return {"model": model, "jahr": date.today().year, "faelle": faelle}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prüffälle für die TS/Python-Parität erzeugen.")
    ap.add_argument("--out", default=str(ROOT / "web" / ".paritaet" / "faelle.json"))
    ap.add_argument("--n", type=int, default=40, help="Paare je Datenlage-Gruppe")
    args = ap.parse_args(argv)
    daten = erzeuge_faelle(n_je_gruppe=args.n)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    gruppen: dict[str, int] = {}
    for f in daten["faelle"]:
        gruppen[f["gruppe"]] = gruppen.get(f["gruppe"], 0) + 1
    print(f"{len(daten['faelle'])} Prüffälle -> {out}")
    print("  " + ", ".join(f"{g}: {n}" for g, n in sorted(gruppen.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
