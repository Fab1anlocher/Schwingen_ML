"""Merkmalsbildung als A-minus-B-Differenzen (ML-4, paar-symmetrisch).

KEIN DATA LEAKAGE (ML-5, R-2): Form- und Rating-Merkmale nutzen nur Gänge
VOR dem jeweiligen Gang. Die Gänge werden chronologisch verarbeitet und
Form-Zustände erst NACH Feature-Berechnung aktualisiert.
"""
from __future__ import annotations

from collections import deque, defaultdict

from .config import FORM_FENSTER_K
from .schema import Schwinger, KRANZSTATUS_ORDINAL
from .labels import GangResultat


# Reihenfolge der numerischen Merkmale = Spaltenreihenfolge im Modell-Artefakt.
# Fest-Typ (bergfest/gross_fest) war früher Teil der Merkmale, per Ablation
# aber ohne messbaren Effekt (Log-Loss/Accuracy unverändert bis leicht besser
# ohne) — vermutlich reines Konfundieren mit rating_diff (stärkere Schwinger
# treten öfter an Grossanlässen an). Deshalb entfernt; Event.typ bleibt als
# Datenfeld (Anzeige/Filter) erhalten, nur nicht mehr als Modell-Merkmal.
FEATURE_NAMES = [
    "rating_diff",       # Elo A - Elo B (leak-frei, pre-gang)
    "rating_abstand",    # |Elo A - Elo B|: Nähe der Ratings (symmetrisch, für "gestellt")
    "form_diff",         # Siegquote letzte K A - B (leak-frei)
    "kranz_diff",        # Kranzstatus-Ordinal A - B
    "alter_diff",        # Alter A - B (Jahre)
    "gewicht_diff",      # kg A - B (aktuelle Portraitwerte, R-3)
    "groesse_diff",      # cm A - B
    "erfahrung_diff",    # Anzahl bisheriger Gänge A - B (leak-frei)
    "same_teilverband",  # 1 wenn gleicher Teilverband (symmetrisch)
    "schwung_overlap",   # Überschneidung bevorzugter Schwünge (0..1)
    "schwung_count_diff",  # Anzahl bevorzugter Schwünge A - B
]

# Menschenlesbare Labels für Erklärbarkeit (FR-3).
FEATURE_LABELS = {
    "rating_diff": "Rating-Vorsprung (Elo)",
    "rating_abstand": "Rating-Nähe (ausgeglichenes Paar)",
    "form_diff": "aktuelle Form (letzte Gänge)",
    "kranz_diff": "Kranzstatus",
    "alter_diff": "Altersunterschied",
    "gewicht_diff": "Gewichtsunterschied",
    "groesse_diff": "Grössenunterschied",
    "erfahrung_diff": "Erfahrung (Anzahl Gänge)",
    "same_teilverband": "gleicher Teilverband",
    "schwung_overlap": "Übereinstimmung bevorzugter Schwünge",
    "schwung_count_diff": "Unterschied Anzahl bevorzugter Schwünge",
}


def _form_wert(historie: deque) -> float:
    """Siegquote (Sieg=1, Gestellt=0.5, Niederlage=0) im Fenster, 0.5 wenn leer."""
    if not historie:
        return 0.5
    return sum(historie) / len(historie)


def _alter(schwinger: Schwinger, datum: str) -> float | None:
    if schwinger.jahrgang is None:
        return None
    jahr = int(datum[:4])
    return float(jahr - schwinger.jahrgang)


def _diff_oder_null(a, b) -> float:
    """Differenz zweier optionaler Werte; 0.0 wenn einer fehlt (Imputation, R-4)."""
    if a is None or b is None:
        return 0.0
    return float(a - b)


def _schwung_overlap(sa: Schwinger, sb: Schwinger) -> float:
    """Jaccard-Überlappung der bevorzugten Schwünge (0..1)."""
    a = set(sa.bevorzugte_schwuenge or [])
    b = set(sb.bevorzugte_schwuenge or [])
    union = a | b
    if not union:
        return 0.0
    return float(len(a & b) / len(union))


def baue_features(
    gaenge: list[GangResultat],
    snapshots: list[dict],
    schwinger: dict[str, Schwinger],
    augment: bool = True,
) -> tuple[list[list[float]], list[int], list[dict]]:
    """Baut Feature-Matrix, Labels und Metadaten je Gang (chronologisch).

    augment=True fügt jeden Gang zusätzlich in vertauschter Reihenfolge (B vs A)
    mit gespiegeltem Label hinzu -> erzwingt paar-symmetrisches Modell.

    Rückgabe: (X, y, meta) mit y in {0:sieg_a, 1:gestellt, 2:sieg_b}.
    """
    from .config import KLASSEN
    klass_idx = {k: i for i, k in enumerate(KLASSEN)}

    snap_idx = {
        s["event_id"] + s["schwinger_a_id"] + s["schwinger_b_id"]: s for s in snapshots
    }
    form_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_FENSTER_K))

    X: list[list[float]] = []
    y: list[int] = []
    meta: list[dict] = []

    for gang in sorted(gaenge, key=lambda g: (g.datum, g.event_id)):
        a_id, b_id = gang.schwinger_a_id, gang.schwinger_b_id
        sa = schwinger.get(a_id)
        sb = schwinger.get(b_id)
        if sa is None or sb is None:
            continue

        snap = snap_idx.get(gang.event_id + a_id + b_id, {})
        elo_a = snap.get("elo_a_pre", 1500.0)
        elo_b = snap.get("elo_b_pre", 1500.0)
        n_a = snap.get("n_a_pre", 0)
        n_b = snap.get("n_b_pre", 0)

        # Merkmale VOR dem Gang berechnen (leak-frei).
        form_a = _form_wert(form_hist[a_id])
        form_b = _form_wert(form_hist[b_id])

        feats = _feature_vektor(elo_a, elo_b, form_a, form_b, n_a, n_b, sa, sb, gang.datum)
        label = klass_idx[gang.ergebnis]
        X.append(feats)
        y.append(label)
        meta.append(
            {
                "event_id": gang.event_id,
                "datum": gang.datum,
                "schwinger_a_id": a_id,
                "schwinger_b_id": b_id,
                "n_a": n_a,
                "n_b": n_b,
            }
        )

        if augment:
            feats_swap = _feature_vektor(elo_b, elo_a, form_b, form_a, n_b, n_a, sb, sa, gang.datum)
            label_swap = {0: 2, 1: 1, 2: 0}[label]
            X.append(feats_swap)
            y.append(label_swap)
            meta.append({**meta[-1], "augmented": True})

        # NACH Feature-Berechnung Form aktualisieren.
        if gang.ergebnis == "sieg_a":
            form_hist[a_id].append(1.0)
            form_hist[b_id].append(0.0)
        elif gang.ergebnis == "sieg_b":
            form_hist[a_id].append(0.0)
            form_hist[b_id].append(1.0)
        else:
            form_hist[a_id].append(0.5)
            form_hist[b_id].append(0.5)

    return X, y, meta


def _feature_vektor(
    elo_a, elo_b, form_a, form_b, n_a, n_b, sa: Schwinger, sb: Schwinger, datum: str,
) -> list[float]:
    kranz_a = KRANZSTATUS_ORDINAL.get(sa.kranzstatus, 0)
    kranz_b = KRANZSTATUS_ORDINAL.get(sb.kranzstatus, 0)
    return [
        (elo_a - elo_b) / 100.0,                       # rating_diff (skaliert)
        abs(elo_a - elo_b) / 100.0,                     # rating_abstand (symmetrisch)
        form_a - form_b,                                # form_diff
        float(kranz_a - kranz_b),                       # kranz_diff
        _diff_oder_null(_alter(sa, datum), _alter(sb, datum)),  # alter_diff
        _diff_oder_null(sa.gewicht_kg, sb.gewicht_kg),  # gewicht_diff
        _diff_oder_null(sa.groesse_cm, sb.groesse_cm),  # groesse_diff
        float(n_a - n_b),                               # erfahrung_diff
        1.0 if sa.teilverband and sa.teilverband == sb.teilverband else 0.0,
        _schwung_overlap(sa, sb),                        # schwung_overlap
        float(len(sa.bevorzugte_schwuenge) - len(sb.bevorzugte_schwuenge)),
    ]


def feature_vektor_fuer_prognose(
    elo_a, elo_b, form_a, form_b, n_a, n_b, sa: Schwinger, sb: Schwinger, datum: str,
) -> list[float]:
    """Öffentliche Variante für Live-Prognose (identische Berechnung)."""
    return _feature_vektor(elo_a, elo_b, form_a, form_b, n_a, n_b, sa, sb, datum)
