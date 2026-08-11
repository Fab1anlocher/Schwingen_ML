"""Training der Logistic Regression + Evaluation (ML-3, ML-6, ML-7).

- Zeitlicher Train/Test-Split (jüngste Saison = Holdout), NICHT zufällig (ML-5).
- Metriken: Log-Loss (primär), Accuracy, Vergleich gegen Elo-Baseline.
- Export der Gewichte als JSON für triviale clientseitige JS-Inferenz (§7).
- Feature-Wichtigkeit als eigenständiges Deliverable (ML-7 / FR-4).
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, accuracy_score, confusion_matrix

from .config import SEED, KLASSEN
from .features import FEATURE_NAMES, FEATURE_LABELS


def _split_zeitlich(X, y, meta, holdout_ab_jahr: int):
    """Split nach Datum: Gänge >= holdout_ab_jahr sind Test (ML-5)."""
    Xtr, ytr, Xte, yte = [], [], [], []
    for xi, yi, mi in zip(X, y, meta):
        jahr = int(mi["datum"][:4])
        if jahr >= holdout_ab_jahr:
            Xte.append(xi); yte.append(yi)
        else:
            Xtr.append(xi); ytr.append(yi)
    return np.array(Xtr), np.array(ytr), np.array(Xte), np.array(yte)


def bestimme_holdout_jahr(meta) -> int:
    """Jüngste vorkommende Saison als Holdout."""
    jahre = sorted({int(m["datum"][:4]) for m in meta})
    return jahre[-1] if len(jahre) > 1 else jahre[0]


def trainiere(X, y, meta) -> dict:
    """Trainiert LR, evaluiert zeitlich getrennt, gibt Ergebnis-Report zurück."""
    holdout = bestimme_holdout_jahr(meta)
    Xtr, ytr, Xte, yte = _split_zeitlich(X, y, meta, holdout)

    if len(Xtr) == 0 or len(np.unique(ytr)) < 2:
        if len(X) < 2 or len(np.unique(y)) < 2:
            raise RuntimeError(
                "Zu wenig Trainingsdaten für Logistic Regression: "
                f"{len(X)} Beispiele, {len(np.unique(y))} Klassen."
            )
        X_arr = np.asarray(X)
        y_arr = np.asarray(y)
        if len(X_arr) >= 3:
            Xtr = X_arr[:-1]
            ytr = y_arr[:-1]
            Xte = X_arr[-1:]
            yte = y_arr[-1:]
        else:
            Xtr = X_arr
            ytr = y_arr
            Xte = np.empty((0, X_arr.shape[1] if X_arr.ndim == 2 else 0))
            yte = np.empty((0,), dtype=int)
        if len(np.unique(ytr)) < 2:
            Xtr = X_arr
            ytr = y_arr
            Xte = np.empty((0, X_arr.shape[1] if X_arr.ndim == 2 else 0))
            yte = np.empty((0,), dtype=int)

    # Standardisierung (Mittel/Std aus TRAIN) -> im Artefakt gespeichert,
    # damit die JS-Inferenz identisch skaliert.
    mu = np.asarray(Xtr).mean(axis=0)
    sigma = np.asarray(Xtr).std(axis=0)
    sigma[sigma == 0] = 1.0
    Xtr_s = (Xtr - mu) / sigma
    Xte_s = (Xte - mu) / sigma

    modell = LogisticRegression(
        class_weight=None,
        max_iter=2000,
        C=1.0,
        random_state=SEED,
    )
    modell.fit(Xtr_s, ytr)

    labels_idx = list(range(len(KLASSEN)))
    p_test = modell.predict_proba(Xte_s) if len(Xte_s) else np.empty((0, len(KLASSEN)))

    if len(Xte_s):
        y_pred = modell.predict(Xte_s)
        ll = log_loss(yte, p_test, labels=labels_idx)
        acc = accuracy_score(yte, y_pred)
        # Konfusionsmatrix (ML-6): Zeile = tatsächliche, Spalte = vorhergesagte Klasse.
        cm = confusion_matrix(yte, y_pred, labels=labels_idx).tolist()
    else:
        ll, acc = float("nan"), float("nan")
        cm = None

    return {
        "modell": modell,
        "mu": mu,
        "sigma": sigma,
        "holdout_jahr": holdout,
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
        "log_loss": float(ll),
        "accuracy": float(acc),
        "confusion_matrix": cm,
    }


def feature_wichtigkeit(modell: LogisticRegression, sigma: np.ndarray) -> list[dict]:
    """Globale Merkmalswichtigkeit (ML-7 / FR-4, AK-4.1/4.2).

    Standardisierte Koeffizienten je Klasse; Wichtigkeit = mittlerer Betrag
    über die Klassen. Explizit inkl. Gewicht/Grösse/Schwünge-relevanter Merkmale.
    """
    coefs = modell.coef_            # (n_klassen, n_features)
    wichtig = np.abs(coefs).mean(axis=0)
    eintraege = []
    for i, name in enumerate(FEATURE_NAMES):
        eintraege.append({
            "feature": name,
            "label": FEATURE_LABELS.get(name, name),
            "wichtigkeit": float(wichtig[i]),
            "koeffizienten": {KLASSEN[k]: float(coefs[k, i]) for k in range(len(KLASSEN))},
        })
    eintraege.sort(key=lambda e: e["wichtigkeit"], reverse=True)
    return eintraege
