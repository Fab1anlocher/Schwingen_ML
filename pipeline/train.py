"""Training des Prognosemodells + Evaluation (ML-3, ML-6, ML-7).

- Das Modell selbst (Gradient Boosting oder LR) kommt aus modell.py.
- Zeitlicher Train/Test-Split (jüngste Saison = Holdout), NICHT zufällig (ML-5).
- Zwei Modelle (Roadmap M5): das EVALUATIONSMODELL sieht die Holdout-Saison
  nicht und liefert alle Kennzahlen; AUSGELIEFERT wird danach ein zweites,
  mit denselben Einstellungen auf allen Trainingszeilen INKLUSIVE der
  Holdout-Saison. Sonst lernte das App-Modell nie aus der laufenden Saison --
  rückwirkend gemessen kostet eine fehlende Saison 0.009 Log-Loss (Test 2026
  mit Training bis 2024: 0.7294, bis 2025: 0.7207).
- Metriken: Log-Loss (primär), Accuracy, MAE/MSE auf dem Punktwert des Gangs
  (s. pipeline/metriken.py), Vergleich gegen Elo-Baseline.
- Merkmalswichtigkeit als eigenständiges Deliverable (ML-7 / FR-4).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from sklearn.metrics import log_loss, accuracy_score, confusion_matrix

from .config import SEED, KLASSEN, EINSCHWINGPHASE_TAGE, MODELL_TYP
from .features import FEATURE_NAMES, FEATURE_LABELS
from .metriken import punktwert_fehlermasse, gestellt_kalibrierung
from .modell import Prognosemodell, trainiere_modell


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

    Die Einschwingphase bleibt aus dem Training draussen, s. trainings_maske.
    """
    X_arr, y_arr = np.asarray(X), np.asarray(y)
    train = trainings_maske(meta, y_arr, holdout_ab_jahr)
    test = np.array([_ist_testzeile(m, holdout_ab_jahr) for m in meta], dtype=bool)
    datum_tr = [m["datum"] for m, drin in zip(meta, train) if drin]
    return X_arr[train], y_arr[train], X_arr[test], y_arr[test], datum_tr


def einschwing_ende(meta) -> str | None:
    """Erstes Datum (ISO) NACH der Einschwingphase; None ohne Daten."""
    if not meta:
        return None
    beginn = date.fromisoformat(min(m["datum"] for m in meta))
    return (beginn + timedelta(days=EINSCHWINGPHASE_TAGE)).isoformat()


def trainings_maske(meta, y, holdout_ab_jahr: int) -> np.ndarray:
    """Welche Zeilen ins Training gehen -- geteilt von train und benchmark.

    Alles vor dem Holdout-Jahr, OHNE die Einschwingphase: im ersten Jahr der
    Datenbasis haben die Ratings noch keine Historie hinter sich (Streuung 41
    statt 77+), und die Gestellt-Quote lag dort deutlich höher (2023: 28.4 %,
    danach konstant ~21.5 %). Diese Gänge liefern Historie für Elo, Form und
    Neigung, lehren das Modell aber ein Verhältnis, das später nicht mehr gilt.
    Gemessen (mit Streuungs-Skalierung): Test-Log-Loss 0.7607 -> 0.7503,
    Validierung 2025 0.7941 -> 0.7771.

    Bleibt nach dem Ausschluss kein brauchbares Training übrig (weniger als
    zwei Klassen, z.B. bei kurzen Datenbasen), gilt die Maske ohne Ausschluss.
    """
    y = np.asarray(y)
    vor_holdout = np.array([int(m["datum"][:4]) < holdout_ab_jahr for m in meta], dtype=bool)
    ende = einschwing_ende(meta)
    if ende is None:
        return vor_holdout
    eingeschwungen = np.array([m["datum"] >= ende for m in meta], dtype=bool)
    maske = vor_holdout & eingeschwungen
    if len(np.unique(y[maske])) < 2:
        return vor_holdout
    return maske


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


def trainiere(X, y, meta, typ: str = MODELL_TYP) -> dict:
    """Trainiert das Prognosemodell, evaluiert zeitlich getrennt, gibt den Report zurück."""
    holdout = bestimme_holdout_jahr(meta)
    Xtr, ytr, Xte, yte, datum_tr = _split_zeitlich(X, y, meta, holdout)

    if len(Xtr) == 0 or len(np.unique(ytr)) < 2:
        if len(X) < 2 or len(np.unique(y)) < 2:
            raise RuntimeError(
                "Zu wenig Trainingsdaten für das Prognosemodell: "
                f"{len(X)} Beispiele, {len(np.unique(y))} Klassen."
            )
        X_arr = np.asarray(X)
        y_arr = np.asarray(y)
        alle_daten = [m["datum"] for m in meta]
        if len(X_arr) >= 3:
            Xtr, ytr, datum_tr = X_arr[:-1], y_arr[:-1], alle_daten[:-1]
            Xte = X_arr[-1:]
            yte = y_arr[-1:]
        else:
            Xtr, ytr, datum_tr = X_arr, y_arr, alle_daten
            Xte = np.empty((0, X_arr.shape[1] if X_arr.ndim == 2 else 0))
            yte = np.empty((0,), dtype=int)
        if len(np.unique(ytr)) < 2:
            Xtr, ytr, datum_tr = X_arr, y_arr, alle_daten
            Xte = np.empty((0, X_arr.shape[1] if X_arr.ndim == 2 else 0))
            yte = np.empty((0,), dtype=int)

    # Mittel/Streuung aus TRAIN stecken im Modell und landen im Artefakt:
    # die LR rechnet standardisiert, beide Typen nutzen das Mittel als
    # neutralen Wert der Erklärbalken.
    modell = trainiere_modell(Xtr, ytr, datum_tr, typ)

    labels_idx = list(range(len(KLASSEN)))
    p_test = modell.predict_proba(Xte) if len(Xte) else np.empty((0, len(KLASSEN)))

    if len(Xte):
        y_pred = np.argmax(p_test, axis=1)
        ll = log_loss(yte, p_test, labels=labels_idx)
        acc = accuracy_score(yte, y_pred)
        # Konfusionsmatrix (ML-6): Zeile = tatsächliche, Spalte = vorhergesagte Klasse.
        cm = confusion_matrix(yte, y_pred, labels=labels_idx).tolist()
        # MAE/MSE auf dem Punktwert des Gangs (s. pipeline/metriken.py) -- die
        # einzige Kennzahl hier, die in der Einheit des Ergebnisses selbst steht.
        fehler = punktwert_fehlermasse(p_test, yte)
        kalibrierung = gestellt_kalibrierung(p_test, yte)
    else:
        ll, acc = float("nan"), float("nan")
        cm = None
        fehler = {"mae": float("nan"), "mse": float("nan")}
        kalibrierung = None

    nur_portraet = _bewerte_nur_portraet(p_test, yte, meta, holdout, labels_idx)

    # Roadmap M5: ausgeliefert wird ein Modell, das auch die Holdout-Saison
    # gesehen hat. Nur wenn es überhaupt einen Holdout gab (sonst ist das
    # Evaluationsmodell schon auf allem trainiert).
    ausgeliefert, n_ausgeliefert = modell, int(len(Xtr))
    if len(Xte):
        alle = trainings_maske(meta, np.asarray(y), holdout + 1)
        datum_alle = [m["datum"] for m, drin in zip(meta, alle) if drin]
        ausgeliefert = trainiere_modell(np.asarray(X)[alle], np.asarray(y)[alle], datum_alle, typ)
        n_ausgeliefert = int(alle.sum())

    return {
        # Evaluationsmodell: Kennzahlen, Merkmalswichtigkeit (auf den Testgängen).
        "modell": modell,
        # Ausgeliefert (model.json): zusätzlich auf der Holdout-Saison trainiert.
        "modell_ausgeliefert": ausgeliefert,
        "n_train_ausgeliefert": n_ausgeliefert,
        "modell_typ": modell.typ,
        "n_baeume": ausgeliefert.n_baeume,
        # Für Merkmalswichtigkeit (Permutation), Export-Prüfung und den
        # Prognose-Check je Fest (prognose_check.py).
        "X_test": np.asarray(Xte),
        "y_test": np.asarray(yte),
        "p_test": np.asarray(p_test),
        "holdout_jahr": holdout,
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
        "log_loss": float(ll),
        "accuracy": float(acc),
        "mae": float(fehler["mae"]),
        "mse": float(fehler["mse"]),
        "confusion_matrix": cm,
        "nur_portraet": nur_portraet,
        "kalibrierung": kalibrierung,
        # Ab wann trainiert wird (davor: Einschwingphase, nur Historie).
        "training_ab": _training_ab(meta, y, holdout),
    }


def _training_ab(meta, y, holdout: int) -> str | None:
    """Frühestes Datum einer Trainingszeile (für den Report)."""
    if not meta:
        return None
    maske = trainings_maske(meta, y, holdout)
    daten = [m["datum"] for m, drin in zip(meta, maske) if drin]
    return min(daten) if daten else None


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


# Obergrenze der Testgänge für die Permutations-Wichtigkeit (Laufzeit).
MAX_PERMUTATION = 8000


def feature_wichtigkeit(train_res: dict) -> list[dict]:
    """Globale Merkmalswichtigkeit (ML-7 / FR-4, AK-4.1/4.2).

    Logistic Regression: mittlerer Betrag der standardisierten Koeffizienten
    über die Klassen (plus die Koeffizienten selbst).
    Gradient Boosting: Permutations-Wichtigkeit -- um wie viel der Log-Loss
    auf den Testgängen steigt, wenn dieses Merkmal zufällig vertauscht wird.
    Das ist modellunabhängig und direkt lesbar ("so viel schlechter ohne").
    """
    modell: Prognosemodell = train_res["modell"]
    if modell.typ == "lr":
        coefs = modell.sk.coef_            # (n_klassen, n_features)
        wichtig = np.abs(coefs).mean(axis=0)
        koeff = {i: {KLASSEN[k]: float(coefs[k, i]) for k in range(len(KLASSEN))}
                 for i in range(len(FEATURE_NAMES))}
    else:
        wichtig = _permutations_wichtigkeit(modell, train_res["X_test"], train_res["y_test"])
        koeff = {}
    eintraege = []
    for i, name in enumerate(FEATURE_NAMES):
        eintraege.append({
            "feature": name,
            "label": FEATURE_LABELS.get(name, name),
            "wichtigkeit": float(wichtig[i]),
            "koeffizienten": koeff.get(i),
        })
    eintraege.sort(key=lambda e: e["wichtigkeit"], reverse=True)
    return eintraege


def _permutations_wichtigkeit(modell: Prognosemodell, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    if len(X) == 0 or len(np.unique(y)) < 2:
        return np.zeros(len(FEATURE_NAMES))
    rng = np.random.default_rng(SEED)
    if len(X) > MAX_PERMUTATION:
        auswahl = rng.choice(len(X), MAX_PERMUTATION, replace=False)
        X, y = X[auswahl], y[auswahl]
    labels = list(range(len(KLASSEN)))
    basis = log_loss(y, modell.predict_proba(X), labels=labels)
    out = np.zeros(X.shape[1])
    for i in range(X.shape[1]):
        Xp = X.copy()
        Xp[:, i] = rng.permutation(Xp[:, i])
        out[i] = max(0.0, log_loss(y, modell.predict_proba(Xp), labels=labels) - basis)
    return out
