"""Ähnliche Schwinger per KNN über das Porträt-Profil.

Für die Anzeige "Ähnliche Schwinger" im Profil: die nächsten Nachbarn im
standardisierten Raum aus Physis, Stil, Elo, Erfahrung, Alter und
Kranzstatus. Nur Schwinger mit Gewicht und Grösse (Porträt).

Bis 06.10.2026 stand hier auch ein K-Means über dasselbe Profil für die Seite
"Typen". Es fand keine Struktur (Silhouette 0.24, Gruppen 434 / 82 / 10,
im Kern "stark gegen den Rest") und wurde durch die Stil-Typen ersetzt
(``stiltypen.py``). Für Ähnlichkeit taugt der Raum weiterhin: dort zählt
die Nähe einzelner Punkte, keine Gruppengrenze.

Merkmale (alle aus echten Porträt-/Gang-Daten):
  - Gewicht, Grösse, Kompaktheits-Index (Gewicht / (Grösse/100)², BMI-artig)
  - Elo-Rating, Erfahrung (Anzahl gewertete Gänge), Alter, Kranzstatus (ordinal)
  - Bevorzugte Schwünge als One-Hot -- Schwelle statt fixer Top-N-Liste,
    Namen werden vorher gross/klein-normalisiert (Rohdaten schreiben
    "innerer Haken" und "Innerer Haken" uneinheitlich).
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.neighbors import NearestNeighbors

from .schema import KRANZSTATUS_ORDINAL, Schwinger

N_AEHNLICHSTE = 5
MIN_SCHWUNG_HAEUFIGKEIT = 10  # Schwelle statt fixer Top-N-Liste (datengetrieben)
MIN_KANDIDATEN = 10

_FIXE_MERKMALE = ["gewicht_kg", "groesse_cm", "kompaktheit", "elo", "erfahrung", "alter", "kranzstatus"]


def _hat_profildaten(s: Schwinger) -> bool:
    return s.gewicht_kg is not None and s.groesse_cm is not None


def _normiert(name: str) -> str:
    """Gross-/Kleinschreibung vereinheitlichen (Rohdaten uneinheitlich, z.B.
    "innerer Haken" vs. "Innerer Haken" -- sonst zwei Spalten für dasselbe).
    Schwünge sind Nomen, darum mit Grossbuchstaben: "Innerer Haken", "Kurz".
    Spiegelt web/lib/labels.ts:schwungName."""
    return name.strip()[:1].upper() + name.strip()[1:] if name.strip() else name


def _ermittle_top_schwuenge(kandidaten: list[tuple[str, Schwinger]]) -> list[str]:
    zaehler: Counter[str] = Counter()
    for _, s in kandidaten:
        for name in s.bevorzugte_schwuenge or []:
            zaehler[_normiert(name)] += 1
    return [name for name, n in zaehler.most_common() if n >= MIN_SCHWUNG_HAEUFIGKEIT]


def _feature_vektor(
    sid: str, s: Schwinger, elo_modell, referenz_jahr: int, top_schwuenge: list[str]
) -> list[float]:
    schwuenge = {_normiert(n) for n in (s.bevorzugte_schwuenge or [])}
    kompaktheit = s.gewicht_kg / (s.groesse_cm / 100.0) ** 2
    alter = float(referenz_jahr - s.jahrgang) if s.jahrgang else float("nan")
    return [
        float(s.gewicht_kg),
        float(s.groesse_cm),
        float(kompaktheit),
        float(elo_modell.get(sid)),
        float(elo_modell.gaenge_gezaehlt.get(sid, 0)),
        alter,
        float(KRANZSTATUS_ORDINAL.get(s.kranzstatus, 0)),
        *(1.0 if name in schwuenge else 0.0 for name in top_schwuenge),
    ]


def berechne_aehnlichste(schwinger: dict[str, Schwinger], elo_modell, referenz_jahr: int) -> dict | None:
    """KNN über das Porträt-Profil; None wenn zu wenig Profildaten."""
    kandidaten = [(sid, s) for sid, s in schwinger.items() if _hat_profildaten(s)]
    if len(kandidaten) < MIN_KANDIDATEN:
        return None

    top_schwuenge = _ermittle_top_schwuenge(kandidaten)
    ids = [sid for sid, _ in kandidaten]
    X = np.array([
        _feature_vektor(sid, s, elo_modell, referenz_jahr, top_schwuenge)
        for sid, s in kandidaten
    ])

    # Alter kann fehlen (kein Jahrgang bekannt) -- mit dem Spaltenmittel
    # auffuellen statt den Schwinger auszuschliessen, damit ein einzelnes
    # fehlendes Merkmal nicht die sonst vollstaendigen Profildaten verwirft.
    alter_idx = _FIXE_MERKMALE.index("alter")
    spalte = X[:, alter_idx]
    fehlt = np.isnan(spalte)
    if fehlt.any():
        mittel = float(np.mean(spalte[~fehlt])) if not fehlt.all() else 0.0
        X[:, alter_idx] = np.where(fehlt, mittel, spalte)

    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_std = (X - mu) / sigma

    nn = NearestNeighbors(n_neighbors=min(N_AEHNLICHSTE + 1, len(X_std)))
    nn.fit(X_std)
    distanzen, indizes = nn.kneighbors(X_std)
    aehnlichste: dict[str, list[dict]] = {}
    for i, sid in enumerate(ids):
        treffer = [
            {"schwinger_id": ids[j], "score": round(float(1.0 / (1.0 + dist)), 3)}
            for dist, j in zip(distanzen[i], indizes[i])
            if j != i
        ]
        aehnlichste[sid] = treffer[:N_AEHNLICHSTE]

    return {"merkmale": _FIXE_MERKMALE + top_schwuenge, "aehnlichste": aehnlichste}
