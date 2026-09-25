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

from .features import MERKMALE_JE_VERSION, feature_vektor_fuer_prognose, _kopf_an_kopf_vorteil
from .modell import TYP_GBM, TYP_LR
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


def _baum_wert(baum: list, x: list[float]) -> float:
    """Ein exportierter Baum (export._baum_json): links, wenn x <= Schwelle."""
    i = 0
    while True:
        k = baum[i]
        if not isinstance(k, list):
            return k
        i = k[2] if x[k[0]] <= k[1] else k[3]


def _stufe(stufe: dict, x: list[float]) -> float:
    """Eine Boosting-Stufe: Sigmoid(basis + Summe der Bäume), Reihenfolge wie
    in inference.ts, damit beide bitgleich rechnen."""
    r = stufe["basis"]
    for baum in stufe["baeume"]:
        r += _baum_wert(baum, x)
    return 1.0 / (1.0 + math.exp(-r))


def _gbm_wahrscheinlichkeiten(model: dict, x: list[float]) -> list[float]:
    xs = [xi * si for xi, si in zip(x, model["spiegel"])]
    st = model["stufen"]
    g = (_stufe(st["gestellt"], x) + _stufe(st["gestellt"], xs)) / 2
    s = (_stufe(st["sieg"], x) + (1 - _stufe(st["sieg"], xs))) / 2
    return [(1 - g) * s, g, (1 - g) * (1 - s)]


def json_inferenz_wie_app(model: dict, x: list[float]) -> list[float]:
    """Zeilengetreue Spiegelung von wahrscheinlichkeiten() in inference.ts.

    Inklusive des Kürzens auf die Merkmale, die DIESES model.json kennt --
    ein Modell, das dem Code hinterherhinkt, sieht nur die ersten N.
    Boosting: zwei Stufen, je gemittelt mit der gespiegelten Paarung,
    s. modell.py.
    """
    n = len(model["features"])
    x = x[:n]
    if model.get("typ") == TYP_GBM:
        return _gbm_wahrscheinlichkeiten(model, x)
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


def python_live_merkmale(
    model: dict, a: dict, b: dict, ra: dict, rb: dict, h2h: float, datum: str,
    duelle: int = 0, duelle_gestellt: int = 0,
) -> list[float]:
    """Der Merkmalsvektor mit genau den Eingaben, die die App verwendet.

    Elo und Gänge aus ratings.json, Form, Attribute und Gestellt-Neigung aus
    schwinger.json, Kopf-an-Kopf und Paar-Bilanz aus der API, Merkmals-
    version/Skala/Basis aus model.json. Muss mit baueFeatures() in
    inference.ts übereinstimmen -- das prüft npm run paritaet.
    """
    return feature_vektor_fuer_prognose(
        ra["elo"], rb["elo"], a["form"], b["form"], ra["n_gaenge"], rb["n_gaenge"],
        _schwinger(a), _schwinger(b), datum, h2h,
        modell_config=model.get("config"),
        neigung_a=a.get("gestellt_neigung"),
        neigung_b=b.get("gestellt_neigung"),
        duelle=duelle, duelle_gestellt=duelle_gestellt,
    )


# Was Version 1 NICHT kannte -- für das Ableiten eines v1-Modells (s. unten).
_NUR_AB_V2 = ("merkmal_version", "elo_streuung", "gestellt_basis")


def lr_gestalt(model: dict) -> dict:
    """Ein LR-model.json derselben Merkmale -- für die Übergangsfälle.

    Ist das ausgelieferte Modell selbst eine LR, ist es das. Ist es ein
    Boosting-Modell, entsteht eine LR-Gestalt mit festen, beliebigen
    Koeffizienten: geprüft wird ja nicht ihr Inhalt, sondern dass die App ein
    LR-model.json (das vorige Prod-Modell, oder ein älterer Lauf) weiter
    richtig rechnet.
    """
    if model.get("typ") != TYP_GBM:
        return model
    n = len(model["features"])
    rng = random.Random(11)
    zeile = [round(rng.uniform(-0.8, 0.8), 6) for _ in range(n)]
    gestellt = [round(rng.uniform(-0.3, 0.3), 6) for _ in range(n)]
    return {
        **{k: v for k, v in model.items() if k not in ("stufen", "spiegel")},
        "typ": TYP_LR,
        "coef": [zeile, gestellt, [-v for v in zeile]],
        "intercept": [0.1, -0.2, 0.1],
    }


def modell_version(model: dict) -> int:
    return int(model.get("config", {}).get("merkmal_version", 1))


def als_modell_version(model: dict, version: int) -> dict:
    """Dasselbe Modell in der Gestalt, die ein Lauf mit ``version`` schrieb.

    Kein trainiertes Modell, nur die Gestalt: die ersten N Merkmale und die
    Versionsangabe (Version 1 hatte keine). Damit prüft die Parität auch den
    Fall, dass die App ein ÄLTERES model.json bekommt als ihr Code (Übergang,
    oder ein Lauf ist fehlgeschlagen) -- dann muss sie nach DESSEN Version
    rechnen, nicht nach der eigenen.
    """
    n = MERKMALE_JE_VERSION[version]
    if version == 1:
        cfg = {k: v for k, v in model["config"].items() if k not in _NUR_AB_V2}
    else:
        cfg = {**model["config"], "merkmal_version": version}
    return {
        **model,
        "features": model["features"][:n],
        "standardisierung": {k: v[:n] for k, v in model["standardisierung"].items()},
        "coef": [zeile[:n] for zeile in model["coef"]],
        "config": cfg,
    }


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
    alle = por + stub
    paare: list[tuple[str, dict, dict]] = []
    for name, (gA, gB) in {
        "portraet-portraet": (por, por), "portraet-stub": (por, stub),
        "stub-portraet": (stub, por), "stub-stub": (stub, stub),
    }.items():
        if not gA or not gB:
            continue  # z.B. synthetische Daten: dort hat jeder ein Porträt
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
    paare.append(("ohne-rating", {**rng.choice(por or alle), "id": "unbekannt|x"}, rng.choice(stub or alle)))
    # Grenzfall: Neigung fehlt -> Basis, neutral. Abwechselnd als fehlender
    # Eintrag (älteres schwinger.json) bei A und als null (keine Gänge) bei B.
    for i in range(max(2, n_je_gruppe // 4)):
        a, b = rng.choice(por or alle), rng.choice(stub or alle)
        if i % 2 == 0:
            a = {k: v for k, v in a.items() if k != "gestellt_neigung"}
        else:
            b = {**b, "gestellt_neigung": None}
        paare.append(("ohne-neigung", a, b))

    # Ältere Gestalten des ausgelieferten Modells (Übergang: neuer Code,
    # älteres model.json). Paare mit Historie, damit auch Kopf-an-Kopf und
    # Paar-Bilanz dort geprüft werden, wo eine Version sie (noch) nicht kennt.
    # Ältere Versionen immer als LR (so wurden sie ausgeliefert); bei einem
    # Boosting-Modell zusätzlich die LR der aktuellen Version ("lr") -- das
    # ist der Übergang vom vorigen Prod-Modell.
    lr = lr_gestalt(model)
    modelle_alt = {f"v{v}": als_modell_version(lr, v) for v in range(1, modell_version(model))}
    if lr is not model:
        modelle_alt["lr"] = lr
    for name in modelle_alt:
        for i in range(n_je_gruppe):
            if i % 2 == 0 and mit_historie:
                ia, ib = map(int, rng.choice(mit_historie).split("_"))
                a, b = schwinger.get(wid[ia]), schwinger.get(wid[ib])
                if a is not None and b is not None:
                    paare.append((f"modell-{name}", a, b))
                    continue
            paare.append((f"modell-{name}", rng.choice(alle), rng.choice(alle)))

    datum = date.today().isoformat()  # die App rechnet das Alter mit dem aktuellen Jahr
    faelle = []
    for gruppe, a, b in paare:
        if a["id"] == b["id"]:
            continue
        alt = gruppe.removeprefix("modell-") if gruppe.startswith("modell-") else None
        m = modelle_alt[alt] if alt else model
        ra, rb = _rating(ratings, elo_start, a["id"]), _rating(ratings, elo_start, b["id"])
        treffer = _treffer_kanonisch(kk, eid_von, a["id"], b["id"])
        h2h = _h2h_python(a["id"], b["id"], treffer)
        duelle = len(treffer)
        gestellt = sum(1 for t in treffer if t["ergebnis"] == "gestellt")
        x = python_live_merkmale(m, a, b, ra, rb, h2h, datum, duelle, gestellt)
        faelle.append({
            "gruppe": gruppe, "a": a, "b": b, "rating_a": ra, "rating_b": rb,
            "treffer_kanonisch": treffer,
            **({"modell": alt} if alt else {}),
            "erwartet": {"h2h": h2h, "duelle": duelle, "duelle_gestellt": gestellt,
                         "merkmale": x, "wahrscheinlichkeiten": json_inferenz_wie_app(m, x)},
        })
    return {"model": model, "modelle_alt": modelle_alt, "jahr": date.today().year, "faelle": faelle,
            "simulationen": simulations_faelle()}


def simulations_faelle() -> list[dict]:
    """Fest-Simulation (fest_simulation.simuliere) gegen web/lib/simulation.ts:
    ungerades Feld (Freilos), beide Regelwerke (ein bzw. zwei Ausstiche),
    zufällige, paar-konsistente Wahrscheinlichkeiten. Erwartet werden exakt
    dieselben Zählungen -- gleicher Zufallsgenerator, gleiche Reihenfolge."""
    from .fest_simulation import REGELN_JE_TYP, simuliere

    rng = random.Random(5)
    faelle = []
    for typ, n, n_sim, seed in (("kantonal", 13, 150, 11), ("eidgenoessisch", 21, 80, 3)):
        sieg = [[0.0] * n for _ in range(n)]
        gestellt = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                g = rng.uniform(0.05, 0.45)
                pa = (1 - g) * rng.random()
                sieg[i][j], sieg[j][i], gestellt[i][j], gestellt[j][i] = pa, 1 - g - pa, g, g
        r = REGELN_JE_TYP[typ]
        e = simuliere(sieg, gestellt, r, n_sim=n_sim, seed=seed)
        faelle.append({
            "typ": typ, "p_sieg": sieg, "p_gestellt": gestellt, "n_sim": n_sim, "seed": seed,
            "regeln": {"gaenge": r.gaenge, "ausstiche": [list(a) for a in r.ausstiche],
                       "kranzquote": r.kranzquote, "noten": r.noten,
                       "anschwingen_anteil": r.anschwingen_anteil, "spielraum": r.spielraum},
            "erwartet": {"festsieg": e.festsieg, "schlussgang": e.schlussgang, "kranz": e.kranz,
                         "punkte_summe": e.punkte_summe, "kranzgrenze_summe": e.kranzgrenze_summe},
        })
    return faelle


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
