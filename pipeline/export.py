"""Export aller Artefakte als JSON (§7, NFR-6).

Alle Artefakte landen sowohl in /artifacts (versioniert im Repo) als auch in
web/public/data (von der Web-App clientseitig geladen).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import config
from .config import KLASSEN, MIN_GAENGE_FUER_SICHERHEIT, FORM_FENSTER_K
from .features import FEATURE_NAMES, FEATURE_LABELS
from .schema import KRANZSTATUS_ORDINAL


def _write(pfad: Path, obj) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _dump_beide(name: str, obj) -> None:
    """Schreibt ein Artefakt nach /artifacts und web/public/data."""
    _write(config.ARTIFACTS_DIR / name, obj)
    _write(config.WEB_PUBLIC_DIR / name, obj)


def exportiere_modell(train_res: dict, feature_importance: list[dict]) -> None:
    """Logistic-Regression-Gewichte für JS-Inferenz (§7)."""
    modell = train_res["modell"]
    artefakt = {
        "schema_version": config.SCHEMA_VERSION,
        "typ": "logistic_regression_multinomial",
        "klassen": KLASSEN,
        "features": FEATURE_NAMES,
        "feature_labels": FEATURE_LABELS,
        # Standardisierung (muss in JS exakt so angewandt werden).
        "standardisierung": {
            "mu": [float(x) for x in train_res["mu"]],
            "sigma": [float(x) for x in train_res["sigma"]],
        },
        # coef_: (n_klassen, n_features); intercept_: (n_klassen,)
        "coef": [[float(v) for v in row] for row in modell.coef_],
        "intercept": [float(v) for v in modell.intercept_],
        "config": {
            "min_gaenge_fuer_sicherheit": MIN_GAENGE_FUER_SICHERHEIT,
            "form_fenster_k": FORM_FENSTER_K,
            "elo_start": config.ELO_START,
            "kranzstatus_ordinal": KRANZSTATUS_ORDINAL,
        },
        "erstellt": datetime.now(timezone.utc).isoformat(),
    }
    _dump_beide("model.json", artefakt)
    _dump_beide("feature_importance.json", {
        "schema_version": config.SCHEMA_VERSION,
        "klassen": KLASSEN,
        "features": feature_importance,
    })


def exportiere_ratings(elo_modell, schwinger: dict) -> None:
    """ratings.json: aktuelles Elo + Gang-Zahl je Schwinger."""
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "elo_start": config.ELO_START,
        "ratings": {
            sid: {
                "elo": round(elo_modell.get(sid), 1),
                "n_gaenge": elo_modell.gaenge_gezaehlt.get(sid, 0),
            }
            for sid in schwinger
        },
    }
    _dump_beide("ratings.json", obj)


def exportiere_schwinger(
    schwinger: dict, form_aktuell: dict, ueberraschung: dict | None = None
) -> None:
    """schwinger.json: Profil + aktuelle Form (für Live-Prognose & Suche FR-5).

    Sensible Felder werden NICHT exportiert (NFR-5): kein Geburtsdatum, nur
    Jahrgang bleibt intern; Anzeige nutzt Alter.
    """
    ueberraschung = ueberraschung or {}
    liste = []
    for sid, s in schwinger.items():
        u = ueberraschung.get(sid)
        groesster_erfolg = None
        if u and u.get("groesster_erfolg"):
            ge = u["groesster_erfolg"]
            gegner = schwinger.get(ge["gegner_id"])
            groesster_erfolg = {
                "gegner_name": gegner.name if gegner else ge["gegner_id"],
                "event_id": ge["event_id"],
                "datum": ge["datum"],
                "eigenes_elo": ge["eigenes_elo"],
                "gegner_elo": ge["gegner_elo"],
            }
        liste.append({
            "id": sid,
            "name": s.name,
            "jahrgang": s.jahrgang,
            "groesse_cm": s.groesse_cm,
            "gewicht_kg": s.gewicht_kg,
            "kranzstatus": s.kranzstatus,
            "teilverband": s.teilverband,
            "kanton": s.kanton,
            "schwingklub": s.schwingklub,
            "bevorzugte_schwuenge": s.bevorzugte_schwuenge,
            "form": round(form_aktuell.get(sid, 0.5), 3),
            "ueberraschungsindex": u["index"] if u else None,
            "n_bewertete_gaenge": u["n"] if u else 0,
            "groesster_erfolg": groesster_erfolg,
            "quellen": s.quellen,
        })
    liste.sort(key=lambda x: x["name"])
    _dump_beide("schwinger.json", {
        "schema_version": config.SCHEMA_VERSION,
        "schwinger": liste,
    })


def exportiere_events(events: list, kommende: list | None = None) -> None:
    """events.json: vergangene Feste + kommende Feste/Paarungen (FR-2)."""
    _dump_beide("events.json", {
        "schema_version": config.SCHEMA_VERSION,
        "vergangene": [e.to_dict() for e in events],
        "kommende": kommende or [],
    })


_ERGEBNIS_CODE = {"sieg_a": "A", "gestellt": "D", "sieg_b": "B"}


def _leerer_eintrag() -> dict:
    return {
        "n_schwinger": 0, "elo_summe": 0.0, "n_top": 0,
        "n_kranzer": 0, "n_eidgenosse": 0, "n_koenig": 0,
        "n_siege": 0, "n_gestellt": 0, "n_niederlagen": 0,
    }


def _eintrag_zu_dict(name: str, e: dict) -> dict:
    return {
        "kanton": name,
        "n_schwinger": e["n_schwinger"],
        "elo_avg": round(e["elo_summe"] / e["n_schwinger"], 1) if e["n_schwinger"] else None,
        "n_top_schwinger": e["n_top"],
        "n_kranzer": e["n_kranzer"],
        "n_eidgenosse": e["n_eidgenosse"],
        "n_koenig": e["n_koenig"],
        "n_siege": e["n_siege"],
        "n_gestellt": e["n_gestellt"],
        "n_niederlagen": e["n_niederlagen"],
    }


def _gauverband_stats(schwinger: dict, elo_modell, gaenge: list) -> tuple[dict[str, dict], float]:
    """Rohe Statistik je Kantonal-/Gauverband (Schwinger.kanton, 29 Verbände).

    Ein Wurf pro Schwinger in GENAU einen Verband — anders als die daraus
    abgeleiteten politischen Kantone (mehrere Verbände wie Bern: Oberland/
    Emmental/... fallen dort zusammen, s. exportiere_kantone).
    """
    elos = [elo_modell.get(sid) for sid in schwinger]
    schwelle_top = float(np.percentile(elos, 90)) if len(elos) >= 10 else max(elos, default=0.0)

    verbaende: dict[str, dict] = {}
    sid_zu_verband: dict[str, str] = {}

    for sid, s in schwinger.items():
        if not s.kanton:
            continue
        sid_zu_verband[sid] = s.kanton
        e = verbaende.setdefault(s.kanton, _leerer_eintrag())
        elo = elo_modell.get(sid)
        e["n_schwinger"] += 1
        e["elo_summe"] += elo
        if elo >= schwelle_top:
            e["n_top"] += 1
        if s.kranzstatus == "kranzer":
            e["n_kranzer"] += 1
        elif s.kranzstatus == "eidgenosse":
            e["n_eidgenosse"] += 1
        elif s.kranzstatus == "koenig":
            e["n_koenig"] += 1

    for g in gaenge:
        for sid, ist_a in ((g.schwinger_a_id, True), (g.schwinger_b_id, False)):
            verband = sid_zu_verband.get(sid)
            if verband is None:
                continue
            e = verbaende[verband]
            if g.ergebnis == "gestellt":
                e["n_gestellt"] += 1
            elif (g.ergebnis == "sieg_a") == ist_a:
                e["n_siege"] += 1
            else:
                e["n_niederlagen"] += 1

    return verbaende, schwelle_top


def exportiere_kantone(schwinger: dict, elo_modell, gaenge: list) -> None:
    """kantone.json + gauverbaende.json: Statistik für Schweiz-Karte & Detailansicht.

    Beide werden aus derselben Kantonal-/Gauverband-Aggregation abgeleitet
    (pipeline/kantone.py): kantone.json summiert Verbände auf den politischen
    Kanton (für die Karte, z.B. Bern: alle 6 Regionalverbände zusammen);
    gauverbaende.json behält die 29 Verbände einzeln (z.B. für eine Bern-
    interne Detailansicht ohne Kartenverzerrung, da echte Gauverband-Grenzen
    nicht dem politischen Kanton entsprechen und nicht als Karte verfügbar sind).
    """
    from .kantone import kantone_fuer

    verbaende, schwelle_top = _gauverband_stats(schwinger, elo_modell, gaenge)

    kantone: dict[str, dict] = {}
    for verband_name, e in verbaende.items():
        for kanton in kantone_fuer(verband_name):
            k = kantone.setdefault(kanton, _leerer_eintrag())
            for feld in k:
                k[feld] += e[feld]

    kantone_liste = sorted((_eintrag_zu_dict(n, e) for n, e in kantone.items()), key=lambda x: x["kanton"])
    _dump_beide("kantone.json", {
        "schema_version": config.SCHEMA_VERSION,
        "top_schwelle_elo": round(schwelle_top, 1),
        "kantone": kantone_liste,
    })

    gauverband_liste = sorted((_eintrag_zu_dict(n, e) for n, e in verbaende.items()), key=lambda x: x["kanton"])
    _dump_beide("gauverbaende.json", {
        "schema_version": config.SCHEMA_VERSION,
        "top_schwelle_elo": round(schwelle_top, 1),
        "gauverbaende": gauverband_liste,
    })


def exportiere_kopf_an_kopf(gaenge: list) -> None:
    """Kompakter Kopf-an-Kopf-Index je Paar (schwinger_a_id < schwinger_b_id).

    Bewusst NICHT in web/public/data (clientseitig geladen): bei 100k+ Gängen
    wäre das ein zu grosser Download für eine Detail-Ansicht, die pro Aufruf
    nur EIN Paar braucht. Wird stattdessen serverseitig von einer Next.js-
    Route gelesen (web/app/api/kopf-an-kopf), die nur das angefragte Paar
    zurückgibt.

    Da diese Datei (anders als artifacts/raw/) für den Vercel-Build committed
    sein muss, ist die Kodierung bewusst knapp gehalten: numerischer Index
    statt voller Schwinger-IDs als Paar-Schlüssel, 1-Buchstabe-Ergebniscode,
    Datum/Fest-Typ nicht dupliziert (Client kennt sie schon aus events.json).
    Ohne das wäre die Datei >19 MB und würde bei jedem täglichen Cron-Commit
    unbegrenzt weiterwachsen (§NFR-1 täglicher Lauf).
    """
    index: dict[str, int] = {}
    event_index: dict[str, int] = {}

    def _idx(sid: str, register: dict[str, int]) -> int:
        if sid not in register:
            register[sid] = len(register)
        return register[sid]

    paare: dict[str, list] = {}
    for g in gaenge:
        key = f"{_idx(g.schwinger_a_id, index)}_{_idx(g.schwinger_b_id, index)}"
        paare.setdefault(key, []).append(
            [_idx(g.event_id, event_index), _ERGEBNIS_CODE[g.ergebnis]]
        )
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "index": index,
        "event_index": event_index,
        "paare": paare,
    }
    _write(config.ARTIFACTS_DIR / "kopf_an_kopf.json", obj)
    _write(config.WEB_SERVER_DATA_DIR / "kopf_an_kopf.json", obj)


def exportiere_cluster(cluster_res: dict | None) -> None:
    """cluster.json: Schwingertypen (K-Means über Physis+Stil, s. pipeline/clustering.py).

    None wenn zu wenig Schwinger mit Profildaten (z.B. synthetische Demodaten) --
    dann bleibt eine evtl. vorher exportierte Datei unangetastet (kein Überschreiben
    mit leerem/irreführendem Zustand, gleiche Konvention wie exportiere_benchmark).
    """
    if cluster_res is None:
        return
    _dump_beide("cluster.json", {
        "schema_version": config.SCHEMA_VERSION,
        **cluster_res,
    })


_KANDIDAT_LABELS = {
    "kranz_heuristik": "Kranz-Heuristik",
    "elo_baseline": "Elo-Baseline",
    "ml_ohne_elo": "ML ohne Elo/Historie",
    "ml_komplett": "ML komplett (Champion)",
}


def exportiere_benchmark(benchmark_res: dict) -> None:
    """benchmark.json: 4-Wege-Vergleich Heuristik/Elo/ML-ohne-Elo/ML-komplett.

    Siehe pipeline/benchmark.py für Methodik (identischer Holdout, nur echte
    -- nicht augmentierte -- Testgänge, Accuracy + multiklassiger Brier-Score).
    """
    kandidaten = [
        {
            "key": key,
            "label": _KANDIDAT_LABELS.get(key, key),
            "accuracy": werte["accuracy"],
            "brier_score": werte["brier_score"],
        }
        for key, werte in benchmark_res["kandidaten"].items()
    ]
    _dump_beide("benchmark.json", {
        "schema_version": config.SCHEMA_VERSION,
        "holdout_jahr": benchmark_res["holdout_jahr"],
        "n_test": benchmark_res["n_test"],
        "kandidaten": kandidaten,
    })


def exportiere_report(train_res: dict, baseline: dict, warnungen: list[str],
                      n_gaenge: int, n_schwinger: int) -> None:
    """report.json: Trainingslauf-Bericht (ML-6, reproduzierbar, versioniert)."""
    ll = train_res["log_loss"]
    base_ll = baseline["log_loss"]
    acc = train_res["accuracy"]
    base_acc = baseline["accuracy"]
    erreicht_log_loss = bool(ll < base_ll)
    erreicht_accuracy = bool(acc >= base_acc)
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "erstellt": datetime.now(timezone.utc).isoformat(),
        "lauf_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "seed": config.SEED,
        "datenbasis": {"n_gaenge": n_gaenge, "n_schwinger": n_schwinger},
        "holdout_jahr": train_res["holdout_jahr"],
        "n_train": train_res["n_train"],
        "n_test": train_res["n_test"],
        "modell": {
            "log_loss": round(ll, 4),
            "accuracy": round(train_res["accuracy"], 4),
        },
        "baseline_elo": {
            "log_loss": round(base_ll, 4),
            "accuracy": round(base_acc, 4),
        },
        "schlaegt_baseline": erreicht_log_loss,
        "accuracy_gg_baseline": round(acc - base_acc, 4),
        "verbesserung_log_loss": round(base_ll - ll, 4),
        "klassen": KLASSEN,
        "konfusionsmatrix": train_res.get("confusion_matrix"),
        "erfolgskriterien": {
            "log_loss_besser_als_baseline": erreicht_log_loss,
            "accuracy_mindestens_baseline": erreicht_accuracy,
            "gesamt_erfuellt": bool(erreicht_log_loss and erreicht_accuracy),
        },
        "parsing_warnungen": warnungen[:50],
        "n_parsing_warnungen": len(warnungen),
    }
    _dump_beide("report.json", obj)
    return obj
