"""Schwingertypen per K-Means-Clustering + KNN-Ähnlichkeit (echtes ML statt
Hand-Heuristik).

Ersetzt fuer die "Schwingertypen"-Ansicht UND die "Ähnliche Schwinger"-Anzeige
die hand-gewichtete Distanz aus web/lib/aehnlichkeit.ts durch echtes
Clustering/KNN ueber Physis + Stil (Gewicht, Grösse, bevorzugte Schwünge) --
bewusst OHNE Elo/Kranzstatus, damit "ähnlich"/"Typ" wirklich Körperbau+Stil
meint und nicht Erfolg misst (Nutzerwunsch: "Klassifikation ... anstelle
von Elo").

K wird per Silhouette-Score automatisch aus einem Bereich gewaehlt statt
willkuerlich fixiert -- ML-6-Prinzip dieses Projekts (Metriken statt Gefühl).
Eine 2D-PCA-Projektion macht das Ergebnis als Streudiagramm visualisierbar.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors

from .config import SEED
from .schema import Schwinger

N_AEHNLICHSTE = 5

# Haeufigste bevorzugte Schwuenge in den echten Daten (s. artifacts/schwinger.json);
# als One-Hot-Merkmale genutzt. Seltenere Schwuenge fliessen nicht separat ein,
# um das Clustering nicht auf Dutzende duenn besetzte Spalten zu verteilen.
TOP_SCHWUENGE = [
    "Kurz", "Fussstich", "Brienzer", "Höfter", "Wyberhaken",
    "Gammen", "Übersprung", "innerer Haken",
]

K_BEREICH = range(3, 9)


def _hat_profildaten(s: Schwinger) -> bool:
    return s.gewicht_kg is not None and s.groesse_cm is not None


def _feature_vektor(s: Schwinger) -> list[float]:
    schwuenge = set(s.bevorzugte_schwuenge or [])
    return [
        float(s.gewicht_kg),
        float(s.groesse_cm),
        *(1.0 if name in schwuenge else 0.0 for name in TOP_SCHWUENGE),
    ]


def berechne_cluster(schwinger: dict[str, Schwinger]) -> dict | None:
    """K-Means über Physis+Stil; None wenn zu wenig Schwinger mit Profildaten."""
    kandidaten = [(sid, s) for sid, s in schwinger.items() if _hat_profildaten(s)]
    if len(kandidaten) < 3 * K_BEREICH.stop:  # genug Punkte pro moeglichem Cluster
        return None

    ids = [sid for sid, _ in kandidaten]
    X = np.array([_feature_vektor(s) for _, s in kandidaten])
    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_std = (X - mu) / sigma

    bestes_k, bestes_modell, beste_silhouette = None, None, -1.0
    for k in K_BEREICH:
        modell = KMeans(n_clusters=k, n_init=10, random_state=SEED)
        labels = modell.fit_predict(X_std)
        if len(set(labels)) < 2:
            continue  # z.B. bei stark duplizierten Punkten -> Silhouette undefiniert
        score = silhouette_score(X_std, labels)
        if score > beste_silhouette:
            bestes_k, bestes_modell, beste_silhouette = k, modell, score

    if bestes_modell is None:
        return None
    labels = bestes_modell.labels_
    pca = PCA(n_components=2, random_state=SEED)
    koordinaten = pca.fit_transform(X_std)

    # KNN im selben standardisierten Merkmalsraum -- ersetzt die alte
    # Hand-Heuristik in web/lib/aehnlichkeit.ts fuer "Ähnliche Schwinger".
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

    punkte = [
        {
            "schwinger_id": sid,
            "cluster": int(label),
            "pca_x": round(float(x), 3),
            "pca_y": round(float(y), 3),
        }
        for sid, label, (x, y) in zip(ids, labels, koordinaten)
    ]

    zusammenfassung = []
    for cluster_id in range(bestes_k):
        mask = labels == cluster_id
        mitglieder = X[mask]
        mitglieder_paare = [kandidaten[i] for i in range(len(kandidaten)) if mask[i]]
        schwuenge_zaehler: dict[str, int] = {}
        for _, s in mitglieder_paare:
            for name in s.bevorzugte_schwuenge or []:
                schwuenge_zaehler[name] = schwuenge_zaehler.get(name, 0) + 1
        top_schwuenge = sorted(schwuenge_zaehler, key=schwuenge_zaehler.get, reverse=True)[:3]
        zusammenfassung.append({
            "cluster": cluster_id,
            "n": int(mask.sum()),
            "gewicht_avg": round(float(mitglieder[:, 0].mean()), 1),
            "groesse_avg": round(float(mitglieder[:, 1].mean()), 1),
            "top_schwuenge": top_schwuenge,
        })

    return {
        "k": bestes_k,
        "silhouette": round(float(beste_silhouette), 3),
        "punkte": punkte,
        "cluster_zusammenfassung": zusammenfassung,
        "aehnlichste": aehnlichste,
    }
