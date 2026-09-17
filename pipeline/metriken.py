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
