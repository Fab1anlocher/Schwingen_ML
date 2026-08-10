"""Training & Evaluation: Logistic Regression + Gradient Boosting (ML-3/6/7).

- Zeitlicher Train/Test-Split (jüngste Saison = Holdout), NICHT zufällig (ML-5).
- Zwei Modelle: Logistic Regression (interpretierbar, FR-4) und Gradient
  Boosting (stärker, ML-3). Beide gegen die Elo-Baseline gemessen.
- Zeitbasierte Cross-Validation (TimeSeriesSplit) als Robustheitsmass.
- Kalibrierung: Brier-Score + Reliability-Bins (ML-6).
- Export beider Modelle als JSON für clientseitige Inferenz.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, accuracy_score
from sklearn.model_selection import TimeSeriesSplit

from .config import SEED, KLASSEN
from .features import FEATURE_NAMES, FEATURE_LABELS

_LABELS_IDX = list(range(len(KLASSEN)))


def _split_zeitlich(X, y, meta, holdout_ab_jahr: int):
    """Split nach Datum: Gänge >= holdout_ab_jahr sind Test (ML-5)."""
    Xtr, ytr, Xte, yte = [], [], [], []
    for xi, yi, mi in zip(X, y, meta):
        if int(mi["datum"][:4]) >= holdout_ab_jahr:
            Xte.append(xi); yte.append(yi)
        else:
            Xtr.append(xi); ytr.append(yi)
    return np.array(Xtr), np.array(ytr), np.array(Xte), np.array(yte)


def bestimme_holdout_jahr(meta) -> int:
    jahre = sorted({int(m["datum"][:4]) for m in meta})
    return jahre[-1] if len(jahre) > 1 else jahre[0]


def _brier_multiclass(y_true, proba) -> float:
    """Mittlerer Brier-Score über die Klassen (0 = perfekt)."""
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y_true)), y_true] = 1.0
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def _reliability_bins(y_true, proba, n_bins: int = 10) -> list[dict]:
    """Reliability-Diagramm-Daten: Konfidenz vs. tatsächliche Trefferquote (ML-6)."""
    conf = proba.max(axis=1)
    pred = proba.argmax(axis=1)
    korrekt = (pred == y_true).astype(float)
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        maske = (conf >= lo) & (conf < hi if i < n_bins - 1 else conf <= hi)
        if maske.sum() == 0:
            continue
        bins.append({
            "bin": round((lo + hi) / 2, 3),
            "konfidenz": round(float(conf[maske].mean()), 4),
            "trefferquote": round(float(korrekt[maske].mean()), 4),
            "anzahl": int(maske.sum()),
        })
    return bins


def _cv_log_loss(modell_factory, X, y, n_splits: int = 4) -> float:
    """Zeitbasierte CV (TimeSeriesSplit) — Robustheitsmass, respektiert Zeitordnung."""
    if len(X) < (n_splits + 1) * 5:
        return float("nan")
    tscv = TimeSeriesSplit(n_splits=n_splits)
    lls = []
    for tr, va in tscv.split(X):
        m = modell_factory()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[va])
        try:
            lls.append(log_loss(y[va], p, labels=_LABELS_IDX))
        except ValueError:
            continue
    return float(np.mean(lls)) if lls else float("nan")


def _eval(modell, Xte, yte) -> dict:
    if len(Xte) == 0:
        return {"log_loss": float("nan"), "accuracy": float("nan"), "brier": float("nan"),
                "reliability": []}
    p = modell.predict_proba(Xte)
    return {
        "log_loss": float(log_loss(yte, p, labels=_LABELS_IDX)),
        "accuracy": float(accuracy_score(yte, modell.predict(Xte))),
        "brier": _brier_multiclass(yte, p),
        "reliability": _reliability_bins(yte, p),
    }


def trainiere(X, y, meta) -> dict:
    """Trainiert LR + GBM, evaluiert zeitlich getrennt, wählt das beste Modell."""
    holdout = bestimme_holdout_jahr(meta)
    Xtr, ytr, Xte, yte = _split_zeitlich(X, y, meta, holdout)

    # Fallback bei nur einer Saison / leerem Split: positionaler 80/20-Split
    # (chronologisch geordnet, letzte 20 % = Test).
    if len(Xtr) == 0 or len(Xte) == 0:
        n = len(X)
        cut = max(1, int(n * 0.8))
        Xtr = np.array(X[:cut]); ytr = np.array(y[:cut])
        Xte = np.array(X[cut:]) if n - cut else np.array(X[:0])
        yte = np.array(y[cut:]) if n - cut else np.array(y[:0])

    # --- Logistic Regression (standardisiert) ---------------------------
    mu = Xtr.mean(axis=0)
    sigma = Xtr.std(axis=0)
    sigma[sigma == 0] = 1.0
    Xtr_s, Xte_s = (Xtr - mu) / sigma, (Xte - mu) / sigma

    def lr_factory():
        return LogisticRegression(class_weight="balanced", max_iter=3000, C=1.0,
                                  random_state=SEED)
    lr = lr_factory()
    lr.fit(Xtr_s, ytr)
    lr_eval = _eval(lr, Xte_s, yte)
    lr_eval["cv_log_loss"] = _cv_log_loss(lr_factory, (X_std := (np.array(X) - mu) / sigma), np.array(y))

    # --- Gradient Boosting (rohe Merkmale, für einfachen Tree-Export) ---
    best_gbm, best_params, best_cv = _tune_gbm(Xtr, ytr)
    gbm = best_gbm
    gbm_eval = _eval(gbm, Xte, yte)
    gbm_eval["cv_log_loss"] = best_cv
    gbm_eval["params"] = best_params

    bestes = "gbm" if (gbm_eval["log_loss"] < lr_eval["log_loss"]) else "lr"

    return {
        "holdout_jahr": holdout, "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "mu": mu, "sigma": sigma,
        "lr": {"modell": lr, **lr_eval},
        "gbm": {"modell": gbm, **gbm_eval},
        "bestes": bestes,
        # Bequemer Direktzugriff auf das LR-Modell (für Feature-Wichtigkeit).
        "modell": lr,
        "log_loss": lr_eval["log_loss"], "accuracy": lr_eval["accuracy"],
    }


def _tune_gbm(Xtr, ytr):
    """Kleine zeitbasierte Rastersuche für das Gradient Boosting (ML-3)."""
    gitter = [
        {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 300},
        {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 300},
        {"learning_rate": 0.10, "max_depth": 3, "n_estimators": 200},
    ]

    def factory(p):
        return lambda: GradientBoostingClassifier(
            random_state=SEED, subsample=0.9, **p)

    bestes, best_p, best_cv = None, None, float("inf")
    for p in gitter:
        cv = _cv_log_loss(factory(p), np.array(Xtr), np.array(ytr))
        if not np.isnan(cv) and cv < best_cv:
            best_cv, best_p = cv, p
    if best_p is None:  # zu wenig Daten für CV -> vernünftiger Default
        best_p, best_cv = gitter[1], float("nan")
    modell = factory(best_p)()
    modell.fit(np.array(Xtr), np.array(ytr))
    return modell, best_p, best_cv


def feature_wichtigkeit(lr, sigma: np.ndarray) -> list[dict]:
    """Globale Merkmalswichtigkeit der Logistic Regression (ML-7 / FR-4)."""
    coefs = lr.coef_
    wichtig = np.abs(coefs).mean(axis=0)
    eintraege = [{
        "feature": name,
        "label": FEATURE_LABELS.get(name, name),
        "wichtigkeit": float(wichtig[i]),
        "koeffizienten": {KLASSEN[k]: float(coefs[k, i]) for k in range(len(KLASSEN))},
    } for i, name in enumerate(FEATURE_NAMES)]
    eintraege.sort(key=lambda e: e["wichtigkeit"], reverse=True)
    return eintraege


def feature_wichtigkeit_gbm(gbm) -> list[dict]:
    """Impurity-basierte Feature-Importance des Gradient Boosting (ML-7)."""
    imp = gbm.feature_importances_
    eintraege = [{
        "feature": name,
        "label": FEATURE_LABELS.get(name, name),
        "wichtigkeit": float(imp[i]),
    } for i, name in enumerate(FEATURE_NAMES)]
    eintraege.sort(key=lambda e: e["wichtigkeit"], reverse=True)
    return eintraege
