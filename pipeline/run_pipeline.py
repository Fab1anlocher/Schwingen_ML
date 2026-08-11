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
import sys
from collections import deque, defaultdict
from datetime import date

# Windows-Konsole/Dateiausgabe nutzt sonst cp1252 und stürzt bei Sonderzeichen
# (Umlaute, Σ, …) mit UnicodeEncodeError ab. UTF-8 erzwingen, Fehler ersetzen.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - ältere Streams ohne reconfigure
        pass

from . import config, export
from .config import FORM_FENSTER_K
from .labels import dedupliziere
from .ratings import fahre_elo_durch, bewerte_baseline, berechne_ueberraschung
from .features import baue_features
# sklearn-abhängige Module (train/benchmark/clustering) werden bewusst ERST in
# main() importiert -- nach dem Daten-Fetch, damit das Einlesen sofort startet
# statt am langsamen sklearn/scipy-Import zu hängen.


def _lade_daten(source: str):
    """(schwinger, events, roh, bericht) -- bericht ist None bei synth."""
    if source == "synth":
        from .synth import erzeuge_datensatz
        schwinger, events, roh = erzeuge_datensatz()
        return schwinger, events, roh, None
    if source == "scrape":
        from .scrape import lade_echte_daten
        return lade_echte_daten(mit_bericht=True)
    raise ValueError(f"Unbekannte Quelle: {source}")


# --- Sicherheitsnetz gegen stillen Datenverlust (NFR-1) -------------------
# Der taegliche Lauf holt nur ein kurzes Zeitfenster nach und baut auf dem
# Rohdaten-Cache auf. Geht dabei etwas schief, darf NICHT stillschweigend ein
# auf Bruchteilen trainiertes Modell exportiert und committet werden.
#
# Frueher verglich diese Pruefung nur "Gaenge neu vs. Gaenge im letzten
# Report" -- und konnte dadurch nicht zwischen "Cache kaputt" und "Verarbeitung
# kaputt" unterscheiden. Sie ist 20 Tage in Folge gelaufen und hat den Workflow
# dauerhaft blockiert, obwohl der Download einwandfrei funktionierte: der
# Fehler lag in der Namensaufloesung. Deshalb wird jetzt getrennt geprueft.

# Anteil der Roh-Eintraege, der hoechstens verworfen werden darf.
MAX_VERLUSTQUOTE = 0.25
# Anteil, den Rohabdeckung bzw. abgeleitete Gaenge gegenueber dem letzten Lauf
# mindestens halten muessen.
MIN_ANTEIL_VORLAUF = 0.5


def _voriger_report() -> dict | None:
    pfad = config.ARTIFACTS_DIR / "report.json"
    if not pfad.exists():
        return None
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - kaputtes Altartefakt ist kein Abbruchgrund
        return None


def _pruefe_datenqualitaet(source: str, bericht, n_gaenge_neu: int, *, streng: bool = True) -> None:
    if source != "scrape" or bericht is None:
        return

    # 1. Verarbeitung: wie viel der geladenen Rohdaten kommt tatsaechlich an?
    if bericht.verlustquote > MAX_VERLUSTQUOTE:
        raise RuntimeError(
            f"Zu viele Roh-Einträge verworfen: {bericht.verlustquote:.1%} von "
            f"{bericht.n_roh_gesamt} (Grenze {MAX_VERLUSTQUOTE:.0%}). "
            f"Gründe: {dict(bericht.verworfen)}. "
            f"Unauflösbare Namen (Beispiele): {bericht.beispiele_unaufloesbar[:5]}. "
            "Das deutet auf einen Fehler in der Identitätsauflösung hin, nicht auf "
            "fehlende Daten -- Lauf abgebrochen, Artefakte bleiben unverändert."
        )
    if not streng:
        return

    alt = _voriger_report()
    if not alt:
        return
    vorher = (alt.get("datenqualitaet") or {}).get("roh_eintraege_gelesen")

    # 2. Rohabdeckung: der additive Cache darf nie schrumpfen.
    if vorher and bericht.n_roh_gesamt < vorher * MIN_ANTEIL_VORLAUF:
        raise RuntimeError(
            f"Rohdaten-Abdeckung eingebrochen: {bericht.n_roh_gesamt} Einträge neu vs. "
            f"{vorher} zuvor. Der Rohdaten-Cache ist vermutlich verloren gegangen -- "
            "Workflow einmalig mit „Volle Historie neu laden“ starten."
        )

    # 3. Abgeleitete Gaenge: nur pruefen, wenn die Rohabdeckung intakt ist,
    #    sonst wuerde Punkt 2 doppelt und irrefuehrend melden.
    n_alt = (alt.get("datenbasis") or {}).get("n_gaenge")
    if n_alt and n_gaenge_neu < n_alt * MIN_ANTEIL_VORLAUF and (
        not vorher or bericht.n_roh_gesamt >= vorher * MIN_ANTEIL_VORLAUF
    ):
        raise RuntimeError(
            f"Abgeleitete Gänge eingebrochen: {n_gaenge_neu} neu vs. {n_alt} zuvor, "
            f"obwohl die Rohabdeckung stimmt ({bericht.n_roh_gesamt} Einträge). "
            "Das ist ein Verarbeitungsfehler -- Lauf abgebrochen."
        )


def _datenqualitaet(bericht, gaenge, events, warnungen: list[str]) -> dict:
    """Nachvollziehbare Kennzahlen darüber, was aus den Rohdaten geworden ist.

    Landet in report.json und ist damit von Lauf zu Lauf vergleichbar --
    Grundlage sowohl für die Volumenprüfung als auch für die Frage "kann ich
    diesen Zahlen trauen?".
    """
    from collections import Counter

    kategorien: Counter = Counter()
    for w in warnungen:
        if "nur eine Perspektive" in w:
            kategorien["nur_eine_perspektive"] += 1
        elif "Inkonsistente Symbole" in w:
            kategorien["inkonsistente_symbole"] += 1
        else:
            kategorien["sonstige"] += 1

    daten = sorted(e.datum for e in events if e.datum)
    ergebnisse = Counter(g.ergebnis for g in gaenge)
    n = len(gaenge) or 1
    qualitaet = {
        "warnungen_nach_kategorie": dict(kategorien),
        "anteil_unvollstaendiger_gaenge": round(kategorien["nur_eine_perspektive"] / n, 4),
        "ergebnisverteilung": {k: round(v / n, 4) for k, v in sorted(ergebnisse.items())},
        "feste_zeitraum": {"von": daten[0], "bis": daten[-1]} if daten else None,
        "tage_seit_juengstem_fest": (
            (date.today() - date.fromisoformat(daten[-1])).days if daten else None
        ),
    }
    if bericht is not None:
        qualitaet.update(bericht.als_dict())
    return qualitaet


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


def main(source: str = "synth", *, streng: bool = True) -> dict:
    config.ensure_dirs()
    print(f"[1/8] Lade Daten (Quelle={source}) ...", flush=True)
    schwinger, events, roh, bericht = _lade_daten(source)
    print(f"      {len(schwinger)} Schwinger, {len(events)} Feste, {len(roh)} Roh-Einträge", flush=True)
    if bericht is not None:
        print(
            f"      Rohdaten: {bericht.n_roh_uebernommen}/{bericht.n_roh_gesamt} übernommen "
            f"({bericht.verlustquote:.1%} verworfen) -- {dict(bericht.verworfen)}",
            flush=True,
        )
        if bericht.events_verworfen:
            print(f"      Feste verworfen: {dict(bericht.events_verworfen)}", flush=True)

    print("[2/8] Labels ableiten + deduplizieren + validieren ...", flush=True)
    gaenge, warnungen = dedupliziere(roh)
    print(f"      {len(gaenge)} deduplizierte Gänge, {len(warnungen)} Warnungen", flush=True)
    _pruefe_datenqualitaet(source, bericht, len(gaenge), streng=streng)

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
        train_res, baseline, warnungen, len(gaenge), len(schwinger),
        datenqualitaet=_datenqualitaet(bericht, gaenge, events, warnungen),
    )

    print("\n=== Ergebnis ===", flush=True)
    print(f"Log-Loss  Modell={report['modell']['log_loss']}  "
          f"Baseline={report['baseline_elo']['log_loss']}  "
          f"schlägt Baseline: {report['schlaegt_baseline']}", flush=True)
    dq = report.get("datenqualitaet") or {}
    if dq.get("feste_zeitraum"):
        print(f"Daten     {dq['feste_zeitraum']['von']} .. {dq['feste_zeitraum']['bis']}  "
              f"(jüngstes Fest vor {dq['tage_seit_juengstem_fest']} Tagen)", flush=True)
    if "verlustquote" in dq:
        print(f"Ingest    {dq['roh_eintraege_uebernommen']}/{dq['roh_eintraege_gelesen']} "
              f"Roh-Einträge übernommen ({dq['verlustquote']:.1%} verworfen)", flush=True)
    print(f"Artefakte in: {config.ARTIFACTS_DIR}  und  {config.WEB_PUBLIC_DIR}", flush=True)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Schwingen-ML-Pipeline (Daten -> Modell -> Artefakte).")
    ap.add_argument("--source", choices=["synth", "scrape"], default="synth",
                    help="synth = synthetische Demodaten (offline), scrape = artifacts/raw")
    ap.add_argument(
        "--ohne-volumenpruefung",
        action="store_true",
        help="Vergleich mit dem vorigen Lauf überspringen (nur für den bewussten "
             "Neuaufbau nach vollem Refetch; die Verlustquoten-Prüfung bleibt aktiv).",
    )
    args = ap.parse_args()
    main(args.source, streng=not args.ohne_volumenpruefung)
