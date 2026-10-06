"""Härtetest: ein eingefrorenes Modell an einer Saison messen, die beim Bauen
niemand kannte.

Warum: Die Kennzahlen der Analyse-Seite stammen von 2025 und 2026, und beide
Saisons dienten auch zur Auswahl des Modells (jeder Schritt wurde nur
übernommen, wenn er dort besser war). Sie sind darum leicht optimistisch.
Ehrlich ist erst eine Saison, die nach dem Festlegen beginnt.

Ablauf:

1. **Einfrieren** (einmal, Workflow "Datenpipeline aktualisieren" mit
   ``haertetest_einfrieren``): das ausgelieferte model.json wird nach
   ``artifacts/haertetest_modell.json`` kopiert -- mit Zeitpunkt, Code-Commit,
   Prüfsumme und einem Fingerabdruck (Prognosen für die letzten Gänge vor
   dem Einfrieren). Der Commit des Bots belegt, dass das Modell vor der
   Prüfsaison feststand. Einzelne Gänge lassen sich nicht im Voraus
   festhalten: die Einteilung entsteht erst am Fest.
2. **Jeder Lauf danach**: dieses Modell rechnet jeden Gang der Prüfsaison mit
   dem Stand der Schwinger vor dem jeweiligen Fest -- genau wie die App.
   Kennzahlen mit 95-%-Bereichen (Bootstrap über Feste) und der Vergleich mit
   Elo stehen in ``haertetest.json``.
3. **Wache**: Stimmt die Prüfsumme noch? Liefern die Referenzgänge noch
   dieselben Prognosen? Wenn nicht, hat sich Code oder Datengrundlage
   verändert, das Modell sieht andere Eingaben als beim Einfrieren -- das
   steht dann im Ergebnis, statt still weiterzumessen.

Gerechnet wird mit den exportierten Bäumen (``baeume_wahrscheinlichkeiten``,
vektorisiert), nicht mit sklearn: geprüft wird das Artefakt selbst.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np

from .modell import TYP_GBM

# Die Saison, an der das eingefrorene Modell gemessen wird.
PRUEFSAISON = 2027
# So viele der jüngsten Gänge vor dem Einfrieren bilden den Fingerabdruck.
REFERENZ_GAENGE = 2000
# Ab diesen Anteilen gilt die Eingabe als unverändert: Datenkorrekturen an
# einzelnen alten Festen sollen nicht Alarm schlagen, eine Änderung am
# Merkmals- oder Rating-Code (betrifft fast alle Gänge) schon.
MIN_ANTEIL_GEFUNDEN = 0.9
MIN_ANTEIL_GLEICH = 0.98
GLEICH_TOLERANZ = 1e-9
DATEINAME = "haertetest_modell.json"


def pruefsumme(modell: dict) -> str:
    """SHA-256 des Modells in kanonischer Form (sortierte Schlüssel)."""
    roh = json.dumps(modell, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _baeume(stufe: dict) -> list[tuple]:
    """Bäume einer Stufe als Arrays (Merkmal, Schwelle, links, rechts, Wert, Blatt)."""
    aus = []
    for baum in stufe["baeume"]:
        blatt = np.array([not isinstance(k, list) for k in baum])
        aus.append((
            np.array([0 if b else k[0] for b, k in zip(blatt, baum)], dtype=int),
            np.array([0.0 if b else k[1] for b, k in zip(blatt, baum)]),
            np.array([i if b else k[2] for i, (b, k) in enumerate(zip(blatt, baum))], dtype=int),
            np.array([i if b else k[3] for i, (b, k) in enumerate(zip(blatt, baum))], dtype=int),
            np.array([float(k) if b else 0.0 for b, k in zip(blatt, baum)]),
            blatt,
        ))
    return aus


def _baeume_summe(basis: float, baeume: list[tuple], X: np.ndarray) -> np.ndarray:
    """Rohwert einer Boosting-Stufe für alle Zeilen: basis + Summe der Bäume in
    derselben Reihenfolge wie paritaet._stufe (gleiche Summationsfolge).
    Links, wenn x[Merkmal] <= Schwelle (export._baum_json)."""
    r = np.full(len(X), float(basis))
    zeilen = np.arange(len(X))
    for merkmal, schwelle, links, rechts, wert, blatt in baeume:
        knoten = np.zeros(len(X), dtype=int)
        offen = ~blatt[knoten]
        while offen.any():
            k = knoten[offen]
            nach_links = X[zeilen[offen], merkmal[k]] <= schwelle[k]
            knoten[offen] = np.where(nach_links, links[k], rechts[k])
            offen = ~blatt[knoten]
        r += wert[knoten]
    return r


def baeume_wahrscheinlichkeiten(modell: dict, X: np.ndarray) -> np.ndarray:
    """P(Sieg A, Gestellt, Sieg B) aus einem model.json, für viele Gänge auf
    einmal. Rechnet wie paritaet.json_inferenz_wie_app (die Zeile-für-Zeile-
    Spiegelung der App): Merkmale auf die des Modells gekürzt, Boosting mit
    der gespiegelten Paarung gemittelt, LR standardisiert mit Softmax."""
    X = np.asarray(X, dtype=float)[:, : len(modell["features"])]
    if modell.get("typ") == TYP_GBM:
        Xs = X * np.asarray(modell["spiegel"], dtype=float)

        def stufe(name: str) -> tuple[np.ndarray, np.ndarray]:
            st = modell["stufen"][name]
            baeume = _baeume(st)
            sig = lambda r: 1.0 / (1.0 + np.exp(-r))  # noqa: E731
            return (sig(_baeume_summe(st["basis"], baeume, X)),
                    sig(_baeume_summe(st["basis"], baeume, Xs)))

        g1, g2 = stufe("gestellt")
        s1, s2 = stufe("sieg")
        g = (g1 + g2) / 2
        s = (s1 + (1 - s2)) / 2
        return np.column_stack([(1 - g) * s, g, (1 - g) * (1 - s)])
    mu = np.asarray(modell["standardisierung"]["mu"], dtype=float)
    sigma = np.asarray(modell["standardisierung"]["sigma"], dtype=float)
    sigma = np.where(sigma == 0, 1.0, sigma)   # wie die App: Streuung 0 -> 1
    z = ((X - mu) / sigma) @ np.asarray(modell["coef"], dtype=float).T + np.asarray(modell["intercept"])
    z = np.exp(z - z.max(axis=1, keepdims=True))
    return z / z.sum(axis=1, keepdims=True)


def _schluessel(m: dict) -> str:
    return f"{m['event_id']}|{m['schwinger_a_id']}|{m['schwinger_b_id']}"


def _originale(meta) -> np.ndarray:
    return np.array([not m.get("augmented") for m in meta])


def einfrieren(modell: dict, X, meta, *, saison: int = PRUEFSAISON, code_commit: str | None = None,
               jetzt: datetime | None = None, vorgaenger: dict | None = None) -> dict:
    """Das eingefrorene Objekt: Modell, Prüfsumme, Fingerabdruck.

    Nur Gänge VOR der Prüfsaison zählen zum Fingerabdruck -- das Modell darf
    die Prüfsaison nicht kennen; liegt schon ein Gang von ihr vor, wird nicht
    eingefroren. Darum ist auch das Ersetzen eines eingefrorenen Modells
    (``vorgaenger``) nur bis dahin möglich, etwa nach einer Datenkorrektur;
    Datum und Prüfsumme jedes Vorgängers bleiben in "vorgaenger" stehen.
    """
    X = np.asarray(X, dtype=float)
    orig = _originale(meta)
    jahre = np.array([int(m["datum"][:4]) for m in meta])
    if (orig & (jahre >= saison)).any():
        raise RuntimeError(f"Es liegen schon Gänge der Prüfsaison {saison} vor -- zu spät zum Einfrieren.")
    idx = np.where(orig)[0]
    idx = idx[np.argsort([meta[i]["datum"] for i in idx], kind="stable")][-REFERENZ_GAENGE:]
    p = baeume_wahrscheinlichkeiten(modell, X[idx]) if len(idx) else np.empty((0, 3))
    return {
        "schema_version": "1.0.0",
        "saison": saison,
        "eingefroren_am": (jetzt or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "code_commit": code_commit,
        "merkmal_version": (modell.get("config") or {}).get("merkmal_version", 1),
        "pruefsumme": pruefsumme(modell),
        "referenz": [{"gang": _schluessel(meta[i]), "p": [float(v) for v in p[k]]}
                     for k, i in enumerate(idx)],
        "modell": modell,
        "vorgaenger": _vorgaenger(vorgaenger),
    }


def _vorgaenger(alt: dict | None) -> list[dict]:
    """Kette der ersetzten Einfrierungen, älteste zuerst."""
    if alt is None:
        return []
    return list(alt.get("vorgaenger") or []) + [
        {k: alt.get(k) for k in ("eingefroren_am", "pruefsumme", "code_commit")}]


def _wache(eingefroren: dict, X: np.ndarray, meta) -> dict:
    """Prüfsumme und Fingerabdruck gegen den heutigen Stand."""
    zeile = {_schluessel(m): i for i, m in enumerate(meta) if not m.get("augmented")}
    ref = [r for r in eingefroren["referenz"] if r["gang"] in zeile]
    gleich = 0
    if ref:
        p = baeume_wahrscheinlichkeiten(eingefroren["modell"], X[[zeile[r["gang"]] for r in ref]])
        alt = np.array([r["p"] for r in ref])
        gleich = int((np.abs(p - alt).max(axis=1) <= GLEICH_TOLERANZ).sum())
    n_ref = len(eingefroren["referenz"])
    anteil_gefunden = len(ref) / n_ref if n_ref else 0.0
    anteil_gleich = gleich / len(ref) if ref else 0.0
    unveraendert = pruefsumme(eingefroren["modell"]) == eingefroren["pruefsumme"]
    eingaben_gleich = anteil_gefunden >= MIN_ANTEIL_GEFUNDEN and anteil_gleich >= MIN_ANTEIL_GLEICH
    warnung = None
    if not unveraendert:
        warnung = "Das eingefrorene Modell wurde verändert (Prüfsumme stimmt nicht)."
    elif not eingaben_gleich:
        warnung = ("Die Referenzgänge ergeben andere Prognosen als beim Einfrieren "
                   f"({anteil_gleich:.0%} gleich, {anteil_gefunden:.0%} gefunden): Merkmals-/Rating-Code "
                   "oder Datengrundlage hat sich verändert.")
    return {
        "modell_unveraendert": unveraendert,
        "eingaben_unveraendert": eingaben_gleich,
        "referenz_gefunden": round(anteil_gefunden, 4),
        "referenz_gleich": round(anteil_gleich, 4),
        "warnung": warnung,
    }


def _kennzahlen(p: np.ndarray, y: np.ndarray) -> dict:
    p_ein = np.clip(p[np.arange(len(y)), y], 1e-15, 1.0)
    onehot = np.zeros_like(p)
    onehot[np.arange(len(y)), y] = 1.0
    return {
        "treffer": round(float((p.argmax(1) == y).mean()), 6),
        "log_loss": round(float(-np.log(p_ein).mean()), 4),
        "brier": round(float(((p - onehot) ** 2).sum(1).mean()), 4),
    }


def auswerten(eingefroren: dict | None, X, y, meta, *, X_version=None) -> dict:
    """haertetest.json: Status, Wache und -- sobald die Prüfsaison läuft --
    die Kennzahlen des eingefrorenen Modells.

    ``X_version``: Merkmale in der Version des eingefrorenen Modells, falls
    sie von der aktuellen abweicht (sonst wird ``X`` genommen).
    """
    if eingefroren is None:
        return {"schema_version": "1.0.0", "status": "nicht_eingefroren", "saison": PRUEFSAISON}
    from .benchmark import _fit_predict, elo_baseline_wahrscheinlichkeiten
    from .features import FEATURE_NAMES
    from .train import konfidenzintervalle, trainings_maske

    X = np.asarray(X, dtype=float)
    Xm = np.asarray(X_version, dtype=float) if X_version is not None else X
    y = np.asarray(y)
    saison = eingefroren["saison"]
    aus = {
        "schema_version": "1.0.0",
        "saison": saison,
        "eingefroren_am": eingefroren["eingefroren_am"],
        "code_commit": eingefroren.get("code_commit"),
        "pruefsumme": eingefroren["pruefsumme"],
        "merkmal_version": eingefroren.get("merkmal_version"),
        "vorgaenger": eingefroren.get("vorgaenger") or [],
        "wache": _wache(eingefroren, Xm, meta),
    }
    jahre = np.array([int(m["datum"][:4]) for m in meta])
    test = _originale(meta) & (jahre == saison)
    if not test.any():
        return {**aus, "status": "wartet", "n": 0}

    yt = y[test]
    test_meta = [m for m, d in zip(meta, test) if d]
    p = baeume_wahrscheinlichkeiten(eingefroren["modell"], Xm[test])
    # Vergleich: Elo allein -- die feste Formel und die angepasste (gelernt an
    # allem VOR der Prüfsaison, wie im Benchmark).
    elo_diff = np.array([m["elo_diff"] for m in test_meta], dtype=float)
    p_formel = elo_baseline_wahrscheinlichkeiten(elo_diff)
    train = trainings_maske(meta, y, saison) & (jahre < saison)
    spalten = [FEATURE_NAMES.index("rating_diff"), FEATURE_NAMES.index("rating_abstand")]
    p_elo = _fit_predict(X[train][:, spalten], y[train], X[test][:, spalten])
    return {
        **aus,
        "status": "laeuft",
        "n": int(test.sum()),
        "n_feste": len({m["event_id"] for m in test_meta}),
        "bis": max(m["datum"] for m in test_meta),
        "modell": {
            **_kennzahlen(p, yt),
            "p_eingetreten": round(float(p[np.arange(len(yt)), yt].mean()), 4),
            "gestellt_vorhergesagt": round(float(p[:, 1].mean()), 4),
            "gestellt_eingetreten": round(float((yt == 1).mean()), 4),
        },
        "konfidenz": konfidenzintervalle(p, yt, test_meta),
        "elo_angepasst": _kennzahlen(p_elo, yt),
        "elo_formel": _kennzahlen(p_formel, yt),
    }
