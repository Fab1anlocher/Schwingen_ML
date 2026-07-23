"""Orchestrator der gesamten Pipeline (FR-6, AK-6.1/6.2).

Ablauf:
  1. Daten beziehen (synthetisch ODER echte Scraper).
  2. Labels ableiten + deduplizieren + validieren (§4.3).
  3. Elo-Baseline chronologisch berechnen (leak-freie Pre-Gang-Ratings).
  4. Merkmale bilden (leak-frei, augmentiert).
  5. Logistic Regression trainieren + zeitlich evaluieren.
  6. 4-Wege-Benchmark (Heuristik/Elo/ML ohne Elo/ML komplett) auf demselben Holdout.
  7. Schwingertypen per K-Means-Clustering (Physis + Stil).
  8. Artefakte als JSON exportieren.

Reproduzierbar über festen SEED (NFR-3). Aufruf:
    python -m pipeline.run_pipeline [--source synth|scrape]
"""
from __future__ import annotations

import argparse
import json
from collections import deque, defaultdict

from . import config, export
from .config import FORM_FENSTER_K
from .labels import dedupliziere
from .ratings import fahre_elo_durch, bewerte_baseline, berechne_ueberraschung
from .features import baue_features
# sklearn-abhängige Module (train/benchmark/clustering) werden bewusst ERST in
# main() importiert -- nach dem Daten-Fetch. So läuft das (bei esv stundenlange)
# Datenholen sofort los, statt am langsamen sklearn/scipy-Import zu hängen.


def _lade_daten(source: str, *, von_jahr: int = 2010, mit_portraets: bool = True):
    if source == "synth":
        from .synth import erzeuge_datensatz
        return erzeuge_datensatz()
    elif source == "scrape":
        from .scrape import lade_echte_daten
        return lade_echte_daten()
    elif source == "esv":
        from datetime import date
        from .scrape.esv_laden import lade_esv_daten
        heute = date.today()
        return lade_esv_daten(
            von_jahr, heute.year, aktuelles_jahr=heute.year, mit_portraets=mit_portraets
        )
    raise ValueError(f"Unbekannte Quelle: {source}")


# Sicherheitsnetz gegen den taeglichen Update-Workflow (NFR-1): der laedt
# Rohdaten nur inkrementell fuer ein kurzes Zeitfenster (fetch_raw
# --seit-datum), da artifacts/raw/ nicht zwischen CI-Laeufen persistiert
# wird (zu gross fuers Repo). Faellt dieser Fetch aus irgendeinem Grund auf
# ein winziges Zeitfenster ohne Historie zurueck, wuerde run_pipeline sonst
# das produktive, auf der vollen Historie trainierte Modell stillschweigend
# durch ein auf ein paar hundert Gaengen trainiertes ersetzen UND committen.
# Deshalb: bricht hart ab, statt ein drastisch kleineres Modell zu exportieren.
MIN_DATENVOLUMEN_ANTEIL = 0.5


def _pruefe_datenvolumen(source: str, n_gaenge_neu: int) -> None:
    if source != "scrape":
        return
    report_pfad = config.ARTIFACTS_DIR / "report.json"
    if not report_pfad.exists():
        return
    try:
        alt = json.loads(report_pfad.read_text(encoding="utf-8"))
        n_gaenge_alt = alt["datenbasis"]["n_gaenge"]
    except Exception:  # noqa: BLE001 - fehlendes/kaputtes altes Artefakt ist kein Grund zum Abbruch
        return
    if n_gaenge_neu < n_gaenge_alt * MIN_DATENVOLUMEN_ANTEIL:
        raise RuntimeError(
            f"Datenvolumen eingebrochen: {n_gaenge_neu} Gänge neu vs. {n_gaenge_alt} zuvor "
            f"(< {MIN_DATENVOLUMEN_ANTEIL:.0%}). Breche ab, statt das produktive Modell mit "
            "einem auf Bruchteil der Historie trainierten zu überschreiben -- vermutlich hat "
            "fetch_raw nur ein kurzes Zeitfenster geladen (kein voller Rohdaten-Refetch)."
        )


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


def _anzahl_kraenze(gaenge) -> dict:
    """Anzahl Feste mit Kranz je Schwinger, aus den Kranz-Sternen der Statistik-
    PDF-Kopfzeilen (schlussgang_pdf._STERN_RE) -- kein Schwellenwert-Raten
    unsererseits, die Quelle markiert den Kranz direkt pro Fest."""
    feste: dict[str, set] = defaultdict(set)
    for g in gaenge:
        if g.kranz_a:
            feste[g.schwinger_a_id].add(g.event_id)
        if g.kranz_b:
            feste[g.schwinger_b_id].add(g.event_id)
    return {sid: len(evts) for sid, evts in feste.items()}


def _aktive_schwinger(gaenge, referenz_jahr: int) -> set:
    """Schwinger mit mind. einem Gang im aktuellsten Jahr der Datenbasis --
    filtert Karteileichen (z.B. zurückgetretene Schwinger) aus der
    Standardansicht der Schwinger-Liste, ohne sie aus den Daten zu löschen."""
    aktive: set = set()
    for g in gaenge:
        if int(g.datum[:4]) == referenz_jahr:
            aktive.add(g.schwinger_a_id)
            aktive.add(g.schwinger_b_id)
    return aktive


def main(source: str = "synth", *, von_jahr: int = 2010, mit_portraets: bool = True) -> dict:
    config.ensure_dirs()
    print(f"[1/8] Lade Daten (Quelle={source}) ...", flush=True)
    schwinger, events, roh = _lade_daten(source, von_jahr=von_jahr, mit_portraets=mit_portraets)
    print(f"      {len(schwinger)} Schwinger, {len(events)} Feste, {len(roh)} Roh-Einträge", flush=True)

    print("[2/8] Labels ableiten + deduplizieren + validieren ...", flush=True)
    gaenge, warnungen = dedupliziere(roh)
    print(f"      {len(gaenge)} deduplizierte Gänge, {len(warnungen)} Warnungen", flush=True)
    _pruefe_datenvolumen(source, len(gaenge))

    print("[3/8] Elo-Baseline (chronologisch, leak-frei) ...", flush=True)
    elo_modell, snapshots = fahre_elo_durch(gaenge)
    baseline = bewerte_baseline(gaenge, snapshots, config.KLASSEN)
    print(f"      Baseline Log-Loss={baseline['log_loss']:.4f} Acc={baseline['accuracy']:.4f}", flush=True)

    print("[4/8] Merkmale bilden (leak-frei, augmentiert) ...", flush=True)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    print(f"      {len(X)} Trainingsbeispiele x {len(X[0]) if X else 0} Merkmale", flush=True)

    print("[5/8] Logistic Regression trainieren + zeitlich evaluieren ...", flush=True)
    print("      (lade sklearn – beim ersten Mal 10-30 s) ...", flush=True)
    from .train import trainiere, feature_wichtigkeit
    from .benchmark import fuehre_benchmark_durch
    from .clustering import berechne_cluster
    train_res = trainiere(X, y, meta)
    fi = feature_wichtigkeit(train_res["modell"], train_res["sigma"])
    print(f"      Modell   Log-Loss={train_res['log_loss']:.4f} "
          f"Acc={train_res['accuracy']:.4f} (Holdout {train_res['holdout_jahr']})", flush=True)

    print("[6/8] 4-Wege-Benchmark (Heuristik/Elo/ML ohne Elo/ML komplett) ...", flush=True)
    benchmark_res = fuehre_benchmark_durch(X, y, meta)
    if benchmark_res is None:
        print("      übersprungen (Datenbasis deckt nur eine Saison ab, kein sinnvoller Split)", flush=True)
    else:
        for key, werte in benchmark_res["kandidaten"].items():
            print(f"      {key:16s} Acc={werte['accuracy']:.4f}  Brier={werte['brier_score']:.4f}", flush=True)

    print("[7/8] Schwingertypen (K-Means über volles Profil, nur Aktive) ...", flush=True)
    referenz_jahr = max(int(g.datum[:4]) for g in gaenge)
    aktive = _aktive_schwinger(gaenge, referenz_jahr)
    # Nur aktive Schwinger clustern -- die "Typen" sollen den aktuellen Kader
    # abbilden, nicht Zurückgetretene. Zugleich Basis für "ähnliche Schwinger".
    aktive_schwinger = {sid: s for sid, s in schwinger.items() if sid in aktive}
    cluster_res = berechne_cluster(aktive_schwinger, elo_modell, referenz_jahr)
    if cluster_res is None:
        print("      übersprungen (zu wenig Schwinger mit Gewicht+Grösse)", flush=True)
    else:
        print(f"      k={cluster_res['k']}  Silhouette={cluster_res['silhouette']:.3f}  "
              f"({len(cluster_res['punkte'])} Schwinger)", flush=True)

    print("[8/8] Artefakte exportieren ...", flush=True)
    form_aktuell = _aktuelle_form(gaenge)
    ueberraschung = berechne_ueberraschung(gaenge, snapshots)
    kraenze = _anzahl_kraenze(gaenge)
    export.exportiere_modell(train_res, fi)
    export.exportiere_ratings(elo_modell, schwinger)
    export.exportiere_schwinger(schwinger, form_aktuell, ueberraschung, kraenze, aktive)
    export.exportiere_kopf_an_kopf(gaenge)
    export.exportiere_kantone(schwinger, elo_modell, gaenge)
    export.exportiere_cluster(cluster_res)
    if benchmark_res is not None:
        export.exportiere_benchmark(benchmark_res)
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
    ap.add_argument("--source", choices=["synth", "scrape", "esv"], default="synth")
    ap.add_argument("--von-jahr", type=int, default=2010, help="Startjahr (nur source=esv)")
    ap.add_argument("--ohne-portraets", action="store_true",
                    help="esv ohne Porträt-Anreicherung (schneller, ohne Physis/Alter/Schwünge)")
    args = ap.parse_args()
    main(args.source, von_jahr=args.von_jahr, mit_portraets=not args.ohne_portraets)
