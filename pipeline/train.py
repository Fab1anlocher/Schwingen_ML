"""Training der Logistic Regression + Evaluation (ML-3, ML-6, ML-7).

- Zeitlicher Train/Test-Split (jüngste Saison = Holdout), NICHT zufällig (ML-5).
- Metriken: Log-Loss (primär), Accuracy, MAE/MSE auf dem Punktwert des Gangs
  (s. pipeline/metriken.py), Vergleich gegen Elo-Baseline.
- Export der Gewichte als JSON für triviale clientseitige JS-Inferenz (§7).
- Feature-Wichtigkeit als eigenständiges Deliverable (ML-7 / FR-4).
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, accuracy_score, confusion_matrix

from .config import SEED, KLASSEN
from .features import FEATURE_NAMES, FEATURE_LABELS
from .metriken import punktwert_fehlermasse


def _split_zeitlich(X, y, meta, holdout_ab_jahr: int):
    """Split nach Datum: Gänge >= holdout_ab_jahr sind Test (ML-5).

    Augmentierte Spiegelzeilen (B-gegen-A) gehören ins TRAINING -- sie erzwingen
    dort ein paar-symmetrisches Modell. Im TEST haben sie nichts verloren: jeder
    Gang stünde doppelt drin, einmal aus jeder Perspektive. benchmark.py filtert
    sie längst heraus ("sonst würde jeder Test-Gang doppelt gezählt"), train.py
    tat es nicht -- daher n_test = 72'970 statt der echten 36'485 und eine
    erzwungen symmetrische Konfusionsmatrix (Zeilensummen sieg_a und sieg_b
    exakt gleich). Die Accuracy blieb davon fast unberührt, die Matrix und jede
    daraus gelesene Per-Klassen-Aussage nicht.
    """
    Xtr, ytr, Xte, yte = [], [], [], []
    for xi, yi, mi in zip(X, y, meta):
        if int(mi["datum"][:4]) < holdout_ab_jahr:
            Xtr.append(xi); ytr.append(yi)
        elif _ist_testzeile(mi, holdout_ab_jahr):
            Xte.append(xi); yte.append(yi)
    return np.array(Xtr), np.array(ytr), np.array(Xte), np.array(yte)


def _ist_testzeile(m: dict, holdout_ab_jahr: int) -> bool:
    """Einzige Definition davon, was im Test steht -- geteilt von allen
    Stellen, die Testzeilen auswählen, damit sie nicht auseinanderlaufen."""
    return int(m["datum"][:4]) >= holdout_ab_jahr and not m.get("augmented")


def holdout_gang_schluessel(
    meta, holdout_ab_jahr: int, *, nur_beide_portraet: bool = False
) -> set:
    """Die Gänge, auf denen trainiere() das Modell bewertet -- als (event, a, b).

    Damit lässt sich die Elo-Baseline auf GENAU derselben Menge messen statt
    nur im selben Jahr; vorher lief sie über alle Gänge 2023-2026, während das
    Modell nur den Holdout sah. ``nur_beide_portraet`` liefert die Teilmenge
    für die getrennte Porträt-Auswertung.
    """
    return {
        (m["event_id"], m["schwinger_a_id"], m["schwinger_b_id"])
        for m in meta
        if _ist_testzeile(m, holdout_ab_jahr)
        and (not nur_beide_portraet or m.get("beide_portraet"))
    }


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
        # MAE/MSE auf dem Punktwert des Gangs (s. pipeline/metriken.py) -- die
        # einzige Kennzahl hier, die in der Einheit des Ergebnisses selbst steht.
        fehler = punktwert_fehlermasse(p_test, yte)
    else:
        ll, acc = float("nan"), float("nan")
        cm = None
        fehler = {"mae": float("nan"), "mse": float("nan")}

    nur_portraet = _bewerte_nur_portraet(p_test, yte, meta, holdout, labels_idx)

    return {
        "modell": modell,
        "mu": mu,
        "sigma": sigma,
        "holdout_jahr": holdout,
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
        "log_loss": float(ll),
        "accuracy": float(acc),
        "mae": float(fehler["mae"]),
        "mse": float(fehler["mse"]),
        "confusion_matrix": cm,
        "nur_portraet": nur_portraet,
    }


def _bewerte_nur_portraet(p_test, yte, meta, holdout: int, labels_idx) -> dict:
    """Kennzahlen nur auf Gängen, in denen BEIDE Schwinger ein Porträt haben.

    Nur hier existieren Physis, Verband, Schwünge und Kranzstatus auf beiden
    Seiten. Auf der Gesamtmenge vermischt sich, was das Modell über den
    Schwinger weiss, mit der Frage, ob es überhaupt etwas über ihn weiss --
    und Porträt-Schwinger schlagen Stubs rund 68 % zu 13 %. Diese Teilmenge
    ist deshalb die ehrliche Messung der wrestlerischen Merkmale.

    Die Testzeilen stehen in p_test/yte in derselben Reihenfolge wie die
    Testzeilen in meta -- beide über _ist_testzeile ausgewählt.
    """
    test_meta = [m for m in meta if _ist_testzeile(m, holdout)]
    if len(test_meta) != len(yte) or not len(yte):
        return {"n": 0}
    maske = np.array([bool(m.get("beide_portraet")) for m in test_meta])
    n = int(maske.sum())
    if n == 0:
        return {"n": 0}
    p_sub, y_sub = p_test[maske], yte[maske]
    fehler = punktwert_fehlermasse(p_sub, y_sub)
    return {
        "n": n,
        "anteil_am_test": round(n / len(yte), 4),
        "log_loss": round(float(log_loss(y_sub, p_sub, labels=labels_idx)), 4),
        "accuracy": round(float(np.mean(np.argmax(p_sub, axis=1) == y_sub)), 4),
        "mae": round(fehler["mae"], 4),
        "mse": round(fehler["mse"], 4),
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
