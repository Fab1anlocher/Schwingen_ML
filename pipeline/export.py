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


def exportiere_schwinger(schwinger: dict, form_aktuell: dict) -> None:
    """schwinger.json: Profil + aktuelle Form (für Live-Prognose & Suche FR-5).

    Sensible Felder werden NICHT exportiert (NFR-5): kein Geburtsdatum, nur
    Jahrgang bleibt intern; Anzeige nutzt Alter.
    """
    liste = []
    for sid, s in schwinger.items():
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
