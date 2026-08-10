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
from .features import FEATURE_NAMES, FEATURE_LABELS, FORM_LANG_FENSTER
from .schema import KRANZSTATUS_ORDINAL


def _write(pfad: Path, obj) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def serialisiere_gbm(gbm) -> dict:
    """Serialisiert einen GradientBoostingClassifier zu JSON-Bäumen (§7, ML-3).

    Rohscore je Klasse k = init_raw[k] + learning_rate * Σ_stages Blattwert;
    danach Softmax. Ermöglicht triviale, exakt spiegelbare JS-Inferenz.
    """
    import numpy as _np

    def _tree(dtr) -> dict:
        t = dtr.tree_
        return {
            "children_left": [int(x) for x in t.children_left],
            "children_right": [int(x) for x in t.children_right],
            "feature": [int(x) for x in t.feature],
            "threshold": [float(x) for x in t.threshold],
            "value": [float(v) for v in t.value[:, 0, 0]],
        }

    n_features = gbm.n_features_in_
    init_raw = gbm._raw_predict_init(_np.zeros((1, n_features)))[0]
    # estimators_: (n_stages, n_klassen) DecisionTreeRegressor
    stages = [[_tree(gbm.estimators_[s][k]) for k in range(gbm.estimators_.shape[1])]
              for s in range(gbm.estimators_.shape[0])]
    return {
        "typ": "gradient_boosting",
        "klassen": KLASSEN,
        "features": FEATURE_NAMES,
        "learning_rate": float(gbm.learning_rate),
        "init_raw": [float(x) for x in init_raw],
        "stages": stages,
    }


def _dump_beide(name: str, obj) -> None:
    """Schreibt ein Artefakt nach /artifacts und web/public/data."""
    _write(config.ARTIFACTS_DIR / name, obj)
    _write(config.WEB_PUBLIC_DIR / name, obj)


def exportiere_modell(train_res: dict, fi_lr: list[dict], fi_gbm: list[dict]) -> None:
    """Logistic-Regression- + Gradient-Boosting-Modelle für JS-Inferenz (§7)."""
    lr = train_res["lr"]["modell"]
    artefakt = {
        "schema_version": config.SCHEMA_VERSION,
        "typ": "logistic_regression_multinomial",
        "klassen": KLASSEN,
        "features": FEATURE_NAMES,
        "feature_labels": FEATURE_LABELS,
        "standardisierung": {
            "mu": [float(x) for x in train_res["mu"]],
            "sigma": [float(x) for x in train_res["sigma"]],
        },
        "coef": [[float(v) for v in row] for row in lr.coef_],
        "intercept": [float(v) for v in lr.intercept_],
        "bestes_modell": train_res["bestes"],  # "lr" | "gbm"
        "config": {
            "min_gaenge_fuer_sicherheit": MIN_GAENGE_FUER_SICHERHEIT,
            "form_fenster_k": FORM_FENSTER_K,
            "form_lang_fenster": FORM_LANG_FENSTER,
            "elo_start": config.ELO_START,
            "kranzstatus_ordinal": KRANZSTATUS_ORDINAL,
        },
        "erstellt": datetime.now(timezone.utc).isoformat(),
    }
    _dump_beide("model.json", artefakt)

    # Gradient Boosting als eigenes Artefakt (Tree-JSON).
    gbm_art = serialisiere_gbm(train_res["gbm"]["modell"])
    gbm_art["schema_version"] = config.SCHEMA_VERSION
    gbm_art["erstellt"] = datetime.now(timezone.utc).isoformat()
    _dump_beide("model_gbm.json", gbm_art)

    _dump_beide("feature_importance.json", {
        "schema_version": config.SCHEMA_VERSION,
        "klassen": KLASSEN,
        "features": fi_lr,          # LR-Koeffizienten (Richtung + Stärke)
        "features_gbm": fi_gbm,     # GBM-Impurity-Importance
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


def exportiere_schwinger(schwinger: dict, stats_aktuell: dict) -> None:
    """schwinger.json: Profil + aktuelle Laufzeit-Stats (für Live-Prognose, FR-5).

    stats_aktuell[sid] = {form, form_lang, career}. Sensible Felder werden NICHT
    exportiert (NFR-5): kein Geburtsdatum, nur Jahrgang; Anzeige nutzt Alter.
    """
    default = {"form": 0.5, "form_lang": 0.5, "career": 0.5}
    liste = []
    for sid, s in schwinger.items():
        st = stats_aktuell.get(sid, default)
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
            "form": st["form"],
            "form_lang": st["form_lang"],
            "career": st["career"],
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


def _modell_block(m: dict) -> dict:
    def r(x, n=4):
        return round(x, n) if x == x else None  # None statt NaN (JSON)
    blk = {
        "log_loss": r(m["log_loss"]),
        "accuracy": r(m["accuracy"]),
        "brier": r(m["brier"]),
        "cv_log_loss": r(m.get("cv_log_loss", float("nan"))),
        "reliability": m.get("reliability", []),
    }
    if "params" in m:
        blk["params"] = m["params"]
    return blk


def exportiere_report(train_res: dict, baseline: dict, warnungen: list[str],
                      n_gaenge: int, n_schwinger: int) -> None:
    """report.json: Trainingslauf-Bericht (ML-6, reproduzierbar, versioniert).

    Vergleicht Logistic Regression, Gradient Boosting und Elo-Baseline auf dem
    zeitlichen Holdout inkl. Kalibrierung.
    """
    lr, gbm = train_res["lr"], train_res["gbm"]
    base_ll = baseline["log_loss"]
    bestes = train_res["bestes"]
    best_ll = (gbm if bestes == "gbm" else lr)["log_loss"]
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "erstellt": datetime.now(timezone.utc).isoformat(),
        "seed": config.SEED,
        "datenbasis": {"n_gaenge": n_gaenge, "n_schwinger": n_schwinger},
        "holdout_jahr": train_res["holdout_jahr"],
        "n_train": train_res["n_train"],
        "n_test": train_res["n_test"],
        "bestes_modell": bestes,
        "logistic_regression": _modell_block(lr),
        "gradient_boosting": _modell_block(gbm),
        "baseline_elo": {
            "log_loss": round(base_ll, 4),
            "accuracy": round(baseline["accuracy"], 4),
        },
        # Rückwärtskompatibel: „modell" = bestes Modell.
        "modell": _modell_block(gbm if bestes == "gbm" else lr),
        "schlaegt_baseline": bool(best_ll < base_ll),
        "verbesserung_log_loss": round(base_ll - best_ll, 4),
        "parsing_warnungen": warnungen[:50],
        "n_parsing_warnungen": len(warnungen),
    }
    _dump_beide("report.json", obj)
    return obj
