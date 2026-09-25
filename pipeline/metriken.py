"""Fehlermasse für numerische Vorhersagen: MAE und MSE.

Beide messen, wie weit Vorhersagen von den echten Werten entfernt liegen --
im Gegensatz zu Log-Loss und Accuracy, die auf Klassen bzw. Wahrscheinlichkeiten
schauen.

    MAE = 1/n * sum |y_i - yhat_i|
    MSE = 1/n * sum (y_i - yhat_i)^2

Der Unterschied ist die Gewichtung grosser Fehler:

* **MAE** behandelt alle Fehler gleich und steht in derselben Einheit wie das
  Target. Das Ergebnis ist direkt lesbar ("im Schnitt 0.42 daneben").
* **MSE** quadriert, grosse Ausreisser dominieren den Score also deutlich
  stärker. Nützlich, wenn grosse Fehlschätzungen überproportional teuer sind.

**Was ist hier überhaupt eine Zahl?** Das Produktionsmodell sagt keine Zahl
vorher, sondern eine Verteilung über drei Klassen (sieg_a / gestellt / sieg_b).
MAE und MSE brauchen aber ein numerisches Target. Der Umweg führt über den
Punktwert eines Gangs aus Sicht von Schwinger A, den die Elo-Stufe ohnehin
schon benutzt (s. ratings.EloModell.update: "Sieg=1, Gestellt=0.5,
Niederlage=0"):

* echter Wert   y    = 1.0 / 0.5 / 0.0, je nach Ausgang
* Vorhersage    yhat = P(sieg_a) * 1.0 + P(gestellt) * 0.5 + P(sieg_b) * 0.0
                     = der erwartete Punktwert

Damit ist yhat eine echte Zahl zwischen 0 und 1, und MAE sagt: "im Schnitt
liegt die Prognose um X Punktwert neben dem tatsächlichen Ausgang".

**Abgrenzung zum Brier-Score** (benchmark._brier_score): der ist die
quadratische Abweichung über den ganzen Wahrscheinlichkeitsvektor gegen das
One-Hot-Ergebnis, misst also auch die Kalibrierung der Gestellt-Klasse. Das
MSE hier verdichtet dieselbe Prognose vorher auf eine Zahl. Beide sind
quadratische Masse, aber nicht dasselbe -- ein Modell kann den erwarteten
Punktwert gut treffen und die Verteilung trotzdem schlecht kalibrieren
(z.B. 50/0/50 statt 0/100/0 bei einem Gestellt: gleicher Punktwert 0.5,
deutlich schlechterer Brier-Score).
"""
from __future__ import annotations

import numpy as np

from .config import KLASSEN

# Punktwert eines Gangs aus Sicht von Schwinger A. Bewusst als Mapping über
# den Klassennamen und nicht als Positionsliste: KLASSEN ist anderswo
# sortierungsrelevant, eine Umsortierung dort darf hier nicht still das
# Target verdrehen.
PUNKTWERT_JE_KLASSE = {
    "sieg_a": 1.0,
    "gestellt": 0.5,
    "sieg_b": 0.0,
}

_PUNKTWERT_VEKTOR = np.array([PUNKTWERT_JE_KLASSE[k] for k in KLASSEN])


def mae(y_true, y_pred) -> float:
    """Mean Absolute Error -- durchschnittliche Fehlergrösse, alle Fehler gleich.

    Ergebnis in derselben Einheit wie das Target.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"Formen passen nicht: {y_true.shape} vs. {y_pred.shape}")
    if y_true.size == 0:
        return float("nan")
    return float(np.mean(np.abs(y_true - y_pred)))


def mse(y_true, y_pred) -> float:
    """Mean Squared Error -- grosse Fehler zählen überproportional stark.

    Einheit ist das Quadrat der Target-Einheit, der Wert ist also nicht
    direkt als "so viel daneben" lesbar (dafür MAE nehmen).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise ValueError(f"Formen passen nicht: {y_true.shape} vs. {y_pred.shape}")
    if y_true.size == 0:
        return float("nan")
    return float(np.mean((y_true - y_pred) ** 2))


def punktwert_aus_klasse(y) -> np.ndarray:
    """Klassenindizes (in KLASSEN-Reihenfolge) -> echter Punktwert je Gang."""
    y = np.asarray(y, dtype=int)
    return _PUNKTWERT_VEKTOR[y]


def erwarteter_punktwert(p) -> np.ndarray:
    """3-Klassen-Verteilung -> erwarteter Punktwert (Zahl zwischen 0 und 1)."""
    p = np.asarray(p, dtype=float)
    if p.ndim != 2 or p.shape[1] != len(KLASSEN):
        raise ValueError(f"Erwarte (n, {len(KLASSEN)})-Matrix, bekommen: {p.shape}")
    return p @ _PUNKTWERT_VEKTOR


def punktwert_fehlermasse(p, y) -> dict[str, float]:
    """MAE und MSE einer 3-Klassen-Prognose auf dem Punktwert des Gangs."""
    y_true = punktwert_aus_klasse(y)
    y_pred = erwarteter_punktwert(p)
    return {"mae": mae(y_true, y_pred), "mse": mse(y_true, y_pred)}


def gestellt_kalibrierung(p, y, *, n_stufen: int = 10) -> dict:
    """Wie gut stimmt P(gestellt) mit der tatsächlichen Gestellt-Quote überein?

    Accuracy und Log-Loss sagen dazu wenig: "Gestellt" ist fast nie die
    wahrscheinlichste Klasse, ein Modell kann es also komplett falsch
    einschätzen, ohne dass die Accuracy es merkt. Darum getrennt:

    * vorhergesagt / eingetreten: mittlere P(gestellt) gegen die echte Quote
      -- liegt das auseinander, ist das Modell systematisch zu hoch/zu tief.
    * ECE (Expected Calibration Error): Gänge nach P(gestellt) in gleich
      grosse Stufen geteilt, je Stufe |vorhergesagt - eingetreten|, nach
      Grösse gewichtet. 0 = perfekt kalibriert.
    * AUC: trennt das Modell gestellte von entschiedenen Gängen überhaupt?
      0.5 = Zufall.
    * stufen: die Kalibrierungskurve selbst (für die Analyse-Seite).
    """
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    if not len(y):
        return {"n": 0}
    i_g = KLASSEN.index("gestellt")
    pg = p[:, i_g]
    ist_g = (y == i_g).astype(float)

    # Gleich grosse Stufen über die Rangfolge -- robust gegen Bindungen, die
    # bei Quantilgrenzen leere oder doppelte Stufen erzeugen.
    reihenfolge = np.argsort(pg, kind="stable")
    stufen = []
    ece = 0.0
    for teil in np.array_split(reihenfolge, min(n_stufen, len(y))):
        if not len(teil):
            continue
        vorh, eing = float(pg[teil].mean()), float(ist_g[teil].mean())
        ece += len(teil) / len(y) * abs(vorh - eing)
        stufen.append({"n": int(len(teil)), "vorhergesagt": round(vorh, 4),
                       "eingetreten": round(eing, 4)})

    return {
        "n": int(len(y)),
        "vorhergesagt": round(float(pg.mean()), 4),
        "eingetreten": round(float(ist_g.mean()), 4),
        "ece": round(ece, 4),
        "auc": _auc(pg, ist_g),
        "stufen": stufen,
    }



def _auc(score: np.ndarray, positiv: np.ndarray) -> float | None:
    """ROC-AUC; None, wenn nur eine der beiden Gruppen vorkommt."""
    if positiv.min() == positiv.max():
        return None
    from sklearn.metrics import roc_auc_score
    return round(float(roc_auc_score(positiv, score)), 4)
