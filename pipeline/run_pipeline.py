"""Orchestrator der gesamten Pipeline (FR-6, AK-6.1/6.2).

Ablauf:
  1. Daten beziehen (synthetisch ODER echte Scraper).
  2. Labels ableiten + deduplizieren + validieren (§4.3).
  3. Elo-Baseline chronologisch berechnen (leak-freie Pre-Gang-Ratings).
  4. Merkmale bilden (leak-frei, augmentiert).
  5. Logistic Regression trainieren + zeitlich evaluieren.
  6. Artefakte als JSON exportieren.

Reproduzierbar über festen SEED (NFR-3). Aufruf:
    python -m pipeline.run_pipeline [--source synth|esv]
"""
from __future__ import annotations

import argparse
from collections import deque, defaultdict

from . import config, export
from .config import FORM_FENSTER_K
from .labels import dedupliziere
from .ratings import fahre_elo_durch, bewerte_baseline
from .features import baue_features
from .train import trainiere, feature_wichtigkeit, feature_wichtigkeit_gbm


def _lade_daten(source: str):
    if source == "synth":
        from .synth import erzeuge_datensatz
        return erzeuge_datensatz()
    elif source in ("schlussgang", "esv", "scrape"):
        from .scrape import lade_echte_daten
        return lade_echte_daten(source)
    raise ValueError(f"Unbekannte Quelle: {source}")


def _aktuelle_stats(gaenge) -> dict:
    """Zustand NACH allen Gängen je Schwinger: {form, form_lang, career}.

    Für die Live-Prognose-Artefakte (identische Merkmale wie im Training).
    """
    from .features import FORM_LANG_FENSTER
    form = defaultdict(lambda: deque(maxlen=FORM_FENSTER_K))
    form_lang = defaultdict(lambda: deque(maxlen=FORM_LANG_FENSTER))
    pts = defaultdict(float)
    n = defaultdict(int)
    for g in sorted(gaenge, key=lambda x: (x.datum, x.event_id)):
        s_a = 1.0 if g.ergebnis == "sieg_a" else (0.0 if g.ergebnis == "sieg_b" else 0.5)
        for sid, s in ((g.schwinger_a_id, s_a), (g.schwinger_b_id, 1.0 - s_a)):
            form[sid].append(s); form_lang[sid].append(s)
            pts[sid] += s; n[sid] += 1
    alle = set(form) | set(n)
    return {
        sid: {
            "form": round(sum(form[sid]) / len(form[sid]), 3) if form[sid] else 0.5,
            "form_lang": round(sum(form_lang[sid]) / len(form_lang[sid]), 3) if form_lang[sid] else 0.5,
            "career": round(pts[sid] / n[sid], 3) if n[sid] else 0.5,
        }
        for sid in alle
    }


def main(source: str = "synth") -> dict:
    config.ensure_dirs()
    print(f"[1/6] Lade Daten (Quelle={source}) ...")
    schwinger, events, roh = _lade_daten(source)
    print(f"      {len(schwinger)} Schwinger, {len(events)} Feste, {len(roh)} Roh-Einträge")

    print("[2/6] Labels ableiten + deduplizieren + validieren ...")
    gaenge, warnungen = dedupliziere(roh)
    print(f"      {len(gaenge)} deduplizierte Gänge, {len(warnungen)} Warnungen")

    print("[3/6] Elo-Baseline (chronologisch, leak-frei) ...")
    elo_modell, snapshots = fahre_elo_durch(gaenge)
    baseline = bewerte_baseline(gaenge, snapshots, config.KLASSEN)
    print(f"      Baseline Log-Loss={baseline['log_loss']:.4f} Acc={baseline['accuracy']:.4f}")

    print("[4/6] Merkmale bilden (leak-frei, augmentiert) ...")
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    print(f"      {len(X)} Trainingsbeispiele x {len(X[0]) if X else 0} Merkmale")

    print("[5/6] Modelle trainieren (LR + Gradient Boosting) + zeitlich evaluieren ...")
    train_res = trainiere(X, y, meta)
    fi_lr = feature_wichtigkeit(train_res["lr"]["modell"], train_res["sigma"])
    fi_gbm = feature_wichtigkeit_gbm(train_res["gbm"]["modell"])
    lr, gbm = train_res["lr"], train_res["gbm"]
    print(f"      LR   Log-Loss={lr['log_loss']:.4f} Acc={lr['accuracy']:.4f} "
          f"Brier={lr['brier']:.4f}")
    print(f"      GBM  Log-Loss={gbm['log_loss']:.4f} Acc={gbm['accuracy']:.4f} "
          f"Brier={gbm['brier']:.4f}  (Params {gbm.get('params')})")
    print(f"      Bestes Modell: {train_res['bestes'].upper()} (Holdout {train_res['holdout_jahr']})")

    print("[6/6] Artefakte exportieren ...")
    stats_aktuell = _aktuelle_stats(gaenge)
    export.exportiere_modell(train_res, fi_lr, fi_gbm)
    export.exportiere_ratings(elo_modell, schwinger)
    export.exportiere_schwinger(schwinger, stats_aktuell)
    # Kommende Feste (FR-2): bei echten Daten aus dem Agenda-Scraper.
    kommende = []
    if source in ("schlussgang", "esv", "scrape"):
        try:
            from .scrape import lade_kommende_feste
            kommende = lade_kommende_feste()
        except Exception as e:  # noqa: BLE001
            print(f"      (Agenda konnte nicht geladen werden: {e})")
    export.exportiere_events(events, kommende)
    report = export.exportiere_report(
        train_res, baseline, warnungen, len(gaenge), len(schwinger)
    )

    print("\n=== Ergebnis ===")
    print(f"Log-Loss  Modell={report['modell']['log_loss']}  "
          f"Baseline={report['baseline_elo']['log_loss']}  "
          f"schlägt Baseline: {report['schlaegt_baseline']}")
    print(f"Artefakte in: {config.ARTIFACTS_DIR}  und  {config.WEB_PUBLIC_DIR}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synth", "schlussgang", "esv", "scrape"],
                    default="synth")
    args = ap.parse_args()
    main(args.source)
