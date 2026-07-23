"""Schwingertypen per K-Means-Clustering + KNN-Ähnlichkeit (echtes ML statt
Hand-Heuristik).

Ersetzt fuer die "Schwingertypen"-Ansicht UND die "Ähnliche Schwinger"-Anzeige
die hand-gewichtete Distanz aus web/lib/aehnlichkeit.ts durch echtes
Clustering/KNN. Nutzt bewusst das VOLLE verfügbare Profil eines Schwingers
(Physis, Stil, Erfolg/Elo, Erfahrung, Alter) statt einer vorab eingeschränkten
Merkmalsauswahl -- das unsupervised Verfahren soll selbst finden, welche
Struktur in den Daten steckt, statt dass wir sie vorher wegkuratieren.

Merkmale (alle aus echten Portrait-/Gang-Daten, keine synthetischen Zusatzwerte):
  - Gewicht, Grösse
  - Kompaktheits-Index (Gewicht / (Grösse/100)², BMI-artig) -- eigene
    Dimension fuer "kompakt/stämmig vs. schlank/lang", die aus den rohen
    Gewicht/Grösse-Werten allein nicht linear herauskommt.
  - Elo-Rating, Erfahrung (Anzahl gewertete Gänge), Alter, Kranzstatus (ordinal)
  - Bevorzugte Schwünge als One-Hot -- Schwelle statt fixer Top-N-Liste,
    Namen werden vorher gross/klein-normalisiert (Rohdaten schreiben
    "innerer Haken" und "Innerer Haken" uneinheitlich).

K wird per Silhouette-Score automatisch aus einem Bereich gewaehlt statt
willkuerlich fixiert -- ML-6-Prinzip dieses Projekts (Metriken statt Gefühl).
Eine 2D-PCA-Projektion macht das Ergebnis als Streudiagramm visualisierbar.

Zur Interpretierbarkeit bekommt jeder Cluster zusätzlich:
  - "typische_vertreter": die 3 Schwinger am nächsten am Cluster-Zentrum.
  - "auszeichnung": die Merkmale, die den Cluster am stärksten vom
    Gesamtdurchschnitt unterscheiden (grösster |z-Wert| des Zentrums).
  - "teilverband_schwerpunkt": Teilverband, der in diesem Cluster deutlich
    überrepräsentiert ist gegenüber der Gesamtverteilung -- rein
    beschreibend, fliesst NICHT ins Clustering selbst ein.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors

from .config import SEED
from .schema import KRANZSTATUS_ORDINAL, Schwinger

N_AEHNLICHSTE = 5
N_VERTRETER = 3
MIN_SCHWUNG_HAEUFIGKEIT = 10  # Schwelle statt fixer Top-N-Liste (datengetrieben)
K_BEREICH = range(3, 9)

_FIXE_MERKMALE = ["gewicht_kg", "groesse_cm", "kompaktheit", "elo", "erfahrung", "alter", "kranzstatus"]
_MERKMAL_LABEL = {
    "gewicht_kg": ("schwer", "leicht"),
    "groesse_cm": ("gross", "klein"),
    "kompaktheit": ("kompakt/stämmig gebaut", "schlank für die Grösse"),
    "elo": ("starkes Elo-Rating", "schwaches Elo-Rating"),
    "erfahrung": ("erfahren (viele Gänge)", "wenig erfahren"),
    "alter": ("älter", "jünger"),
    "kranzstatus": ("hoher Kranzstatus (Kranz/Eidg./König)", "kein/niedriger Kranzstatus"),
}


def _hat_profildaten(s: Schwinger) -> bool:
    return s.gewicht_kg is not None and s.groesse_cm is not None


def _normiert(name: str) -> str:
    """Gross-/Kleinschreibung vereinheitlichen (Rohdaten uneinheitlich, z.B.
    "innerer Haken" vs. "Innerer Haken" -- sonst zwei Spalten für dasselbe."""
    return name.strip()[:1].lower() + name.strip()[1:] if name.strip() else name


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


def _auszeichnung(zentrum_std: np.ndarray, merkmal_namen: list[str], top_n: int = 2) -> str:
    """Menschlicher Satz: welche Merkmale unterscheiden diesen Cluster am
    stärksten vom Gesamtdurchschnitt (0 im standardisierten Raum)?"""
    reihenfolge = np.argsort(-np.abs(zentrum_std))[:top_n]
    teile = []
    for idx in reihenfolge:
        name = merkmal_namen[idx]
        z = zentrum_std[idx]
        if abs(z) < 0.3:
            continue  # zu nah am Durchschnitt, keine echte Auszeichnung
        if name in _MERKMAL_LABEL:
            hoch, tief = _MERKMAL_LABEL[name]
            teile.append(f"überdurchschnittlich {hoch}" if z > 0 else f"eher {tief}")
        elif z > 0:
            teile.append(f"bevorzugt auffällig oft {name}")
    return " · ".join(teile) if teile else "nahe am Durchschnitt in allen Merkmalen"


def berechne_cluster(schwinger: dict[str, Schwinger], elo_modell, referenz_jahr: int) -> dict | None:
    """K-Means über das volle Schwinger-Profil; None wenn zu wenig Profildaten."""
    kandidaten = [(sid, s) for sid, s in schwinger.items() if _hat_profildaten(s)]
    if len(kandidaten) < 3 * K_BEREICH.stop:  # genug Punkte pro moeglichem Cluster
        return None

    top_schwuenge = _ermittle_top_schwuenge(kandidaten)
    merkmal_namen = _FIXE_MERKMALE + top_schwuenge

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

    # Teilverband-Gesamtverteilung als Referenz fuer "Schwerpunkt" je Cluster.
    verband_gesamt: Counter[str] = Counter(
        s.teilverband for _, s in kandidaten if s.teilverband
    )
    n_mit_verband = sum(verband_gesamt.values())

    zusammenfassung = []
    for cluster_id in range(bestes_k):
        mask = labels == cluster_id
        mitglieder = X[mask]
        mitglieder_paare = [kandidaten[i] for i in range(len(kandidaten)) if mask[i]]

        schwuenge_zaehler: Counter[str] = Counter()
        for _, s in mitglieder_paare:
            for name in s.bevorzugte_schwuenge or []:
                schwuenge_zaehler[_normiert(name)] += 1
        top3_schwuenge = [n for n, _ in schwuenge_zaehler.most_common(3)]

        zentrum_std = bestes_modell.cluster_centers_[cluster_id]
        auszeichnung = _auszeichnung(zentrum_std, merkmal_namen)

        # Naeheste Mitglieder zum Zentrum (im standardisierten Raum) als
        # konkrete, greifbare "typische Vertreter" dieses Typs.
        mitglieder_idx = [i for i in range(len(kandidaten)) if mask[i]]
        distanzen_zentrum = np.linalg.norm(X_std[mitglieder_idx] - zentrum_std, axis=1)
        reihenfolge = np.argsort(distanzen_zentrum)[:N_VERTRETER]
        typische_vertreter = [ids[mitglieder_idx[i]] for i in reihenfolge]

        verband_cluster: Counter[str] = Counter(
            s.teilverband for _, s in mitglieder_paare if s.teilverband
        )
        teilverband_schwerpunkt = None
        n_cluster_verband = sum(verband_cluster.values())
        if n_cluster_verband >= 5 and n_mit_verband > 0:
            anteile = {
                v: (n / n_cluster_verband) / (verband_gesamt[v] / n_mit_verband)
                for v, n in verband_cluster.items()
            }
            bester = max(anteile, key=anteile.get)
            if anteile[bester] >= 1.3:  # deutlich überrepräsentiert, nicht nur Rauschen
                teilverband_schwerpunkt = bester

        zusammenfassung.append({
            "cluster": cluster_id,
            "n": int(mask.sum()),
            "gewicht_avg": round(float(mitglieder[:, 0].mean()), 1),
            "groesse_avg": round(float(mitglieder[:, 1].mean()), 1),
            "kompaktheit_avg": round(float(mitglieder[:, 2].mean()), 2),
            "elo_avg": round(float(mitglieder[:, 3].mean()), 1),
            "erfahrung_avg": round(float(mitglieder[:, 4].mean()), 1),
            "alter_avg": round(float(mitglieder[:, 5].mean()), 1),
            "top_schwuenge": top3_schwuenge,
            "auszeichnung": auszeichnung,
            "typische_vertreter": typische_vertreter,
            "teilverband_schwerpunkt": teilverband_schwerpunkt,
        })

    return {
        "k": bestes_k,
        "silhouette": round(float(beste_silhouette), 3),
        "merkmale": merkmal_namen,
        "punkte": punkte,
        "cluster_zusammenfassung": zusammenfassung,
        "aehnlichste": aehnlichste,
    }
