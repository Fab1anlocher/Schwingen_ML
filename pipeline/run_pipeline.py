"""Orchestrator der gesamten Pipeline (FR-6, AK-6.1/6.2).

Ablauf:
  1. Daten beziehen (synthetisch ODER echte Scraper).
  2. Labels ableiten + deduplizieren + validieren (§4.3).
  3. Elo-Baseline chronologisch berechnen (leak-freie Pre-Gang-Ratings).
  4. Merkmale bilden (leak-frei, augmentiert).
  5. Logistic Regression trainieren + zeitlich evaluieren.
  6. Artefakte als JSON exportieren.

Reproduzierbar über festen SEED (NFR-3). Aufruf:
    python -m pipeline.run_pipeline [--source synth|scrape]
"""
from __future__ import annotations

import argparse
from collections import deque, defaultdict

from . import config, export
from .config import FORM_FENSTER_K
from .labels import dedupliziere
from .ratings import fahre_elo_durch, bewerte_baseline, berechne_ueberraschung
from .features import baue_features
from .train import trainiere, feature_wichtigkeit


def _lade_daten(source: str):
    if source == "synth":
        from .synth import erzeuge_datensatz
        return erzeuge_datensatz()
    elif source == "scrape":
        from .scrape import lade_echte_daten
        return lade_echte_daten()
    raise ValueError(f"Unbekannte Quelle: {source}")


def _aktuelle_form(gaenge) -> dict:
    """Form-Zustand NACH allen Gängen (für Live-Prognose-Artefakt)."""
    hist = defaultdict(lambda: deque(maxlen=FORM_FENSTER_K))
    for g in sorted(gaenge, key=lambda x: (x.datum, x.event_id)):
        if g.ergebnis == "sieg_a":
            hist[g.schwinger_a_id].append(1.0); hist[g.schwinger_b_id].append(0.0)
        elif g.ergebnis == "sieg_b":
            hist[g.schwinger_a_id].append(0.0); hist[g.schwinger_b_id].append(1.0)
        else:
            hist[g.schwinger_a_id].append(0.5); hist[g.schwinger_b_id].append(0.5)
    return {sid: (sum(h) / len(h) if h else 0.5) for sid, h in hist.items()}


def main(source: str = "synth") -> dict:
    config.ensure_dirs()
    print(f"[1/6] Lade Daten (Quelle={source}) ...", flush=True)
    schwinger, events, roh = _lade_daten(source)
    print(f"      {len(schwinger)} Schwinger, {len(events)} Feste, {len(roh)} Roh-Einträge", flush=True)

    print("[2/6] Labels ableiten + deduplizieren + validieren ...", flush=True)
    gaenge, warnungen = dedupliziere(roh)
    print(f"      {len(gaenge)} deduplizierte Gänge, {len(warnungen)} Warnungen", flush=True)

    print("[3/6] Elo-Baseline (chronologisch, leak-frei) ...", flush=True)
    elo_modell, snapshots = fahre_elo_durch(gaenge)
    baseline = bewerte_baseline(gaenge, snapshots, config.KLASSEN)
    print(f"      Baseline Log-Loss={baseline['log_loss']:.4f} Acc={baseline['accuracy']:.4f}", flush=True)

    print("[4/6] Merkmale bilden (leak-frei, augmentiert) ...", flush=True)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    print(f"      {len(X)} Trainingsbeispiele x {len(X[0]) if X else 0} Merkmale", flush=True)

    print("[5/6] Logistic Regression trainieren + zeitlich evaluieren ...", flush=True)
    train_res = trainiere(X, y, meta)
    fi = feature_wichtigkeit(train_res["modell"], train_res["sigma"])
    print(f"      Modell   Log-Loss={train_res['log_loss']:.4f} "
          f"Acc={train_res['accuracy']:.4f} (Holdout {train_res['holdout_jahr']})", flush=True)

    print("[6/6] Artefakte exportieren ...", flush=True)
    form_aktuell = _aktuelle_form(gaenge)
    ueberraschung = berechne_ueberraschung(gaenge, snapshots)
    export.exportiere_modell(train_res, fi)
    export.exportiere_ratings(elo_modell, schwinger)
    export.exportiere_schwinger(schwinger, form_aktuell, ueberraschung)
    export.exportiere_kopf_an_kopf(gaenge)
    # Kommende Feste (FR-2): bei echten Daten aus dem Agenda-Scraper.
    kommende = []
    if source == "scrape":
        try:
            from .scrape import lade_kommende_feste
            kommende = lade_kommende_feste()
        except Exception as e:  # noqa: BLE001
            print(f"      (Agenda konnte nicht geladen werden: {e})", flush=True)
    export.exportiere_events(events, kommende)
    report = export.exportiere_report(
        train_res, baseline, warnungen, len(gaenge), len(schwinger)
    )

    print("\n=== Ergebnis ===", flush=True)
    print(f"Log-Loss  Modell={report['modell']['log_loss']}  "
          f"Baseline={report['baseline_elo']['log_loss']}  "
          f"schlägt Baseline: {report['schlaegt_baseline']}", flush=True)
    print(f"Artefakte in: {config.ARTIFACTS_DIR}  und  {config.WEB_PUBLIC_DIR}", flush=True)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synth", "scrape"], default="synth")
    args = ap.parse_args()
    main(args.source)
