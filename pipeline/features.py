"""Merkmalsbildung als A-minus-B-Differenzen (ML-4, paar-symmetrisch).

KEIN DATA LEAKAGE (ML-5, R-2): Form- und Rating-Merkmale nutzen nur Gänge
VOR dem jeweiligen Gang. Die Gänge werden chronologisch verarbeitet und
Form-Zustände erst NACH Feature-Berechnung aktualisiert.
"""
from __future__ import annotations

import math
from collections import deque, defaultdict
from itertools import groupby

from .config import ELO_START, FORM_FENSTER_K, GESTELLT_NEIGUNG_K, MERKMAL_VERSION, PAAR_GESTELLT_K
from .schema import Schwinger, KRANZSTATUS_ORDINAL, hat_portraet
from .labels import GangResultat


# Reihenfolge der numerischen Merkmale = Spaltenreihenfolge im Modell-Artefakt.
# Fest-Typ (bergfest/gross_fest) war früher Teil der Merkmale, per Ablation
# aber ohne messbaren Effekt (Log-Loss/Accuracy unverändert bis leicht besser
# ohne) — vermutlich reines Konfundieren mit rating_diff (stärkere Schwinger
# treten öfter an Grossanlässen an). Deshalb entfernt; Event.typ bleibt als
# Datenfeld (Anzeige/Filter) erhalten, nur nicht mehr als Modell-Merkmal.
FEATURE_NAMES = [
    "rating_diff",       # (Elo A - Elo B) / Streuung aktiver Ratings, Stand vor dem Fest
    "rating_abstand",    # |Elo A - Elo B| / Streuung: Nähe der Ratings (symmetrisch)
    "form_diff",         # Siegquote letzte K A - B (leak-frei)
    "kranz_diff",        # Kranzstatus-Ordinal A - B
    "alter_diff",        # Alter A - B (Jahre)
    "gewicht_diff",      # kg A - B (aktuelle Portraitwerte, R-3)
    "groesse_diff",      # cm A - B
    "erfahrung_diff",    # log(1+Gänge A) - log(1+Gänge B), Stand vor dem Fest
    "same_teilverband",  # 1 wenn gleicher Teilverband (symmetrisch)
    "schwung_overlap",   # Überschneidung bevorzugter Schwünge (0..1)
    "schwung_count_diff",  # Anzahl bevorzugter Schwünge A - B
    "kopf_an_kopf",      # Bisherige direkte Duelle A vs B, leak-frei + geglättet
    # Porträt vorhanden A - B, in {-1, 0, 1}. Macht die DATENLAGE zu einem
    # offenen Merkmal: 76 % des Kaders haben kein Porträt und damit weder
    # Physis noch Verband noch Schwünge noch Kranzstatus. Porträt-Schwinger
    # schlagen Stubs rund 68 % zu 13 %. Ohne dieses Merkmal musste das Modell
    # die Datenlücke über Ersatzgrössen lernen -- vor allem über kranz_diff,
    # das bei Stubs strukturell 0 ist -- und die App erklärte eine Prognose
    # dann mit "Kranzstärke", wo in Wahrheit "hat ein Profil" stand.
    # Bewusst ans ENDE gestellt: model.json-Koeffizienten sind positions-
    # gebunden, die übrigen Indizes bleiben so unverändert.
    "portraet_diff",
    # Gestellt-Neigung des Paars: mittlere (geschrumpfte) Gestellt-Quote beider
    # Schwinger minus Gesamtdurchschnitt -- symmetrisch, 0 = durchschnittlich.
    # Manche Schwinger stellen fast jeden zweiten Gang, andere nie (Spanne
    # 0-63 %), und das ist eine stabile Eigenschaft (erste gegen zweite
    # Karrierehälfte r = 0.67). Ohne sie konnte das Modell Gestellte kaum
    # unterscheiden (AUC 0.64 -> 0.72 mit diesem Merkmal).
    "gestellt_neigung",
    # --- ab Merkmalsversion 3 (beide symmetrisch) ---
    # Gestellt-Bilanz DIESES Paars: Anteil gestellter bisheriger Duelle,
    # geschrumpft gegen die Erwartung aus den beiden Einzelneigungen, minus
    # diese Erwartung. 0 = ohne Duelle oder wie erwartet. Die Einzelneigung
    # allein sieht es nicht: Orlik und Staudenmann stellen gegen das Feld
    # selten (21 % / 17 %), gegeneinander 5 von 6 Mal. Paare mit >= 2 Duellen,
    # davon >= die Hälfte gestellt: 42 % gestellt, v2 sagte 32 % voraus.
    "paar_gestellt",
    # Spitzen-Niveau: wie stark der SCHWÄCHERE der beiden ist, in Streuungen
    # über dem Startwert, unten bei 0 abgeschnitten -- hoch nur, wenn BEIDE
    # stark sind. Spitzenschwinger schlagen das Feld und haben darum eine
    # tiefe Einzelneigung; treffen zwei aufeinander, wird aber öfter gestellt
    # (oberstes 1 %: 29.7 %). Version 2 sagte dort 18.2 % voraus -- mit
    # steigendem Niveau sogar WENIGER Gestellte, genau falsch herum.
    "spitzen_niveau",
]

# Die ersten N Merkmale je Merkmalsversion (neue Merkmale nur hinten anhängen).
MERKMALE_JE_VERSION = {1: 13, 2: 14, 3: 16}

# Schrumpfungsstärke für kopf_an_kopf: entspricht K "neutralen Phantom-Duellen"
# gegen die die echte Bilanz gemittelt wird, damit ein einzelnes Duell nicht
# sofort auf ±1 ausschlägt (kleine Stichprobe, Effekt soll mit mehr Duellen
# wachsen — Empirical-Bayes-Glättung).
KOPF_AN_KOPF_K = 2.0

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
    "kopf_an_kopf": "Bisherige direkte Duelle",
    "portraet_diff": "Porträt/Profildaten vorhanden",
    "gestellt_neigung": "Gestellt-Neigung beider Schwinger",
    "paar_gestellt": "Gestellt-Bilanz dieses Paars",
    "spitzen_niveau": "Spitzenpaarung (beide stark)",
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


def _kopf_an_kopf_vorteil(a_id: str, b_id: str, historie: dict[tuple[str, str], list[float]]) -> float:
    """Geglättete Kopf-an-Kopf-Bilanz A vs. B aus VORHERIGEN Duellen (leak-frei).

    `historie` speichert je Paar eine Liste von Punkten aus Sicht des
    kanonisch kleineren Schwinger-ID-Strings (1.0 Sieg / 0.5 Gestellt / 0.0
    Niederlage) — dieselbe Konvention wie GangResultat.schwinger_a_id.
    Rückgabe: ~0 ohne Historie, sonst in Richtung ±1 je nach A-Bilanz,
    mit Empirical-Bayes-Glättung gegen 0.5 (s. KOPF_AN_KOPF_K).
    """
    kanonisch_a_klein = a_id < b_id
    key = (a_id, b_id) if kanonisch_a_klein else (b_id, a_id)
    punkte = historie.get(key)
    if not punkte:
        return 0.0
    n = len(punkte)
    punkte_a = sum(punkte) if kanonisch_a_klein else n - sum(punkte)
    # = 2 * (geglättete Quote - 0.5), umgeformt zu (2 * Punkte_A - n) / (n + K):
    # der Zähler ist eine ganze Zahl (Punkte in Halben), gerundet wird nur die
    # eine Division. Damit ist der Wert exakt antisymmetrisch (B-Sicht = -A-Sicht)
    # und in TypeScript bitgleich (kopfAnKopf.ts). Die frühere Form über
    # 1 - Quote wich im letzten Bit ab (-0.33333333333333337 gegen
    # -0.33333333333333326) -- egal für die LR, aber ein Baum kann seine
    # Schwelle genau dazwischen legen und dann anders entscheiden.
    return (2.0 * punkte_a - n) / (n + KOPF_AN_KOPF_K)


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

    Alle Gänge eines Fests sehen denselben Stand, den VOR dem Fest: Form,
    Kopf-an-Kopf und Gestellt-Neigung werden erst nach dem ganzen Fest
    fortgeschrieben, Elo kommt aus den ebenso eingefrorenen Snapshots
    (Begründung und Messung s. ratings.fahre_elo_durch).

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
    paar_hist: dict[tuple[str, str], list[float]] = defaultdict(list)
    # Zähler für die Gestellt-Neigung: Gänge und davon gestellte, je Schwinger.
    neigung_n: dict[str, int] = defaultdict(int)
    neigung_d: dict[str, int] = defaultdict(int)
    gesamt_n = gesamt_d = 0

    X: list[list[float]] = []
    y: list[int] = []
    meta: list[dict] = []

    geordnet = sorted(gaenge, key=lambda g: (g.datum, g.event_id))
    for _, fest_iter in groupby(geordnet, key=lambda g: (g.datum, g.event_id)):
        fest = [g for g in fest_iter
                if g.schwinger_a_id in schwinger and g.schwinger_b_id in schwinger]
        # Gesamtdurchschnitt VOR dem Fest. Beim allerersten Fest gibt es keinen --
        # dort ist aber auch jede Neigung gleich der Basis, das Paar-Merkmal also
        # exakt 0; der Startwert kürzt sich heraus.
        basis = gesamt_d / gesamt_n if gesamt_n else 0.0

        for gang in fest:
            a_id, b_id = gang.schwinger_a_id, gang.schwinger_b_id
            sa, sb = schwinger[a_id], schwinger[b_id]
            snap = snap_idx.get(gang.event_id + a_id + b_id, {})
            elo_a = snap.get("elo_a_pre", 1500.0)
            elo_b = snap.get("elo_b_pre", 1500.0)
            n_a = snap.get("n_a_pre", 0)
            n_b = snap.get("n_b_pre", 0)
            skala = snap.get("elo_streuung", 100.0)

            form_a = _form_wert(form_hist[a_id])
            form_b = _form_wert(form_hist[b_id])
            h2h_a = _kopf_an_kopf_vorteil(a_id, b_id, paar_hist)
            neigung_a = _neigung(neigung_d[a_id], neigung_n[a_id], basis)
            neigung_b = _neigung(neigung_d[b_id], neigung_n[b_id], basis)
            neigung = paar_neigung(neigung_a, neigung_b, basis)
            # paar_hist hält Punkte aus Sicht der kleineren ID; 0.5 = gestellt.
            duelle = paar_hist.get((a_id, b_id), [])
            bilanz = paar_gestellt(len(duelle), sum(1 for p in duelle if p == 0.5),
                                   neigung_a, neigung_b)

            X.append(_feature_vektor(elo_a, elo_b, form_a, form_b, n_a, n_b, sa, sb,
                                     gang.datum, h2h_a, elo_skala=skala,
                                     gestellt_neigung=neigung, paar_gestellt=bilanz))
            label = klass_idx[gang.ergebnis]
            y.append(label)
            meta.append(
                {
                    "event_id": gang.event_id,
                    "datum": gang.datum,
                    "schwinger_a_id": a_id,
                    "schwinger_b_id": b_id,
                    "n_a": n_a,
                    "n_b": n_b,
                    # Roher Elo-Abstand: die Elo-Baseline im Benchmark braucht ihn,
                    # und aus rating_diff lässt er sich seit der Skalierung mit der
                    # Streuung nicht mehr zurückrechnen.
                    "elo_diff": elo_a - elo_b,
                    # Für die getrennte Auswertung nur auf Porträt-gegen-Porträt-
                    # Gängen -- dort messen Physis/Verband/Schwünge wirklich etwas.
                    "beide_portraet": hat_portraet(sa.quellen) and hat_portraet(sb.quellen),
                }
            )

            if augment:
                # Die Neigung ist symmetrisch und bleibt; alles Gerichtete dreht.
                X.append(_feature_vektor(elo_b, elo_a, form_b, form_a, n_b, n_a, sb, sa,
                                         gang.datum, -h2h_a, elo_skala=skala,
                                         gestellt_neigung=neigung, paar_gestellt=bilanz))
                y.append({0: 2, 1: 1, 2: 0}[label])
                meta.append({**meta[-1], "augmented": True, "elo_diff": elo_b - elo_a})

        # Erst NACH dem ganzen Fest fortschreiben.
        for gang in fest:
            a_id, b_id = gang.schwinger_a_id, gang.schwinger_b_id
            if gang.ergebnis == "sieg_a":
                punkte_a = 1.0
            elif gang.ergebnis == "sieg_b":
                punkte_a = 0.0
            else:
                punkte_a = 0.5
            form_hist[a_id].append(punkte_a)
            form_hist[b_id].append(1.0 - punkte_a)
            # a_id ist bereits die kanonisch kleinere ID (GangResultat-Invariante).
            paar_hist[(a_id, b_id)].append(punkte_a)
            v = 1 if gang.ergebnis == "gestellt" else 0
            for sid in (a_id, b_id):
                neigung_n[sid] += 1
                neigung_d[sid] += v
            gesamt_n += 1
            gesamt_d += v

    return X, y, meta


def _feature_vektor(
    elo_a, elo_b, form_a, form_b, n_a, n_b, sa: Schwinger, sb: Schwinger, datum: str,
    kopf_an_kopf_a: float = 0.0,
    *,
    version: int = MERKMAL_VERSION,
    elo_skala: float = 100.0,
    gestellt_neigung: float = 0.0,
    paar_gestellt: float = 0.0,
) -> list[float]:
    """Merkmalsvektor A-vs-B -- die EINZIGE Definition. Training, Live-Prognose,
    verify_inference und die Paritätsprüfung rufen alle diese Funktion auf.

    version 1 (ältere ausgelieferte Modelle): Elo-Abstand / 100, Erfahrung als
    rohe Differenz, keine Gestellt-Neigung. version 2: Elo-Abstand / elo_skala
    (Streuung der aktiven Ratings), Erfahrung logarithmisch, Gestellt-Neigung
    angehängt. version 3: zusätzlich Gestellt-Bilanz des Paars (wird
    übergeben) und Spitzen-Niveau (aus Elo und Skala). Die App spiegelt alle
    Versionen (web/lib/inference.ts).
    """
    kranz_a = KRANZSTATUS_ORDINAL.get(sa.kranzstatus, 0)
    kranz_b = KRANZSTATUS_ORDINAL.get(sb.kranzstatus, 0)
    v2 = version >= 2
    skala = elo_skala if v2 else 100.0
    vektor = [
        (elo_a - elo_b) / skala,                        # rating_diff
        abs(elo_a - elo_b) / skala,                     # rating_abstand (symmetrisch)
        form_a - form_b,                                # form_diff
        float(kranz_a - kranz_b),                       # kranz_diff
        _diff_oder_null(_alter(sa, datum), _alter(sb, datum)),  # alter_diff
        _diff_oder_null(sa.gewicht_kg, sb.gewicht_kg),  # gewicht_diff
        _diff_oder_null(sa.groesse_cm, sb.groesse_cm),  # groesse_diff
        # Erfahrung = Gänge seit Datenbeginn; der Median wächst von 15 (2023)
        # auf 126 (2026). Als rohe Differenz verzerrt das jedes Jahr mehr, und
        # der 200. Gang lehrt weniger als der 20. Logarithmisch war der grösste
        # Einzelgewinn (Test-Log-Loss -0.03).
        (math.log1p(n_a) - math.log1p(n_b)) if v2 else float(n_a - n_b),  # erfahrung_diff
        1.0 if sa.teilverband and sa.teilverband == sb.teilverband else 0.0,
        _schwung_overlap(sa, sb),                        # schwung_overlap
        float(len(sa.bevorzugte_schwuenge) - len(sb.bevorzugte_schwuenge)),
        kopf_an_kopf_a,                                  # kopf_an_kopf
        float(hat_portraet(sa.quellen)) - float(hat_portraet(sb.quellen)),  # portraet_diff
    ]
    if v2:
        vektor.append(gestellt_neigung)                  # gestellt_neigung
    if version >= 3:
        vektor.append(paar_gestellt)                     # paar_gestellt
        vektor.append(spitzen_niveau(elo_a, elo_b, skala))  # spitzen_niveau
    return vektor


def _neigung(gestellt: float, gaenge: float, basis: float) -> float:
    """Geschrumpfte Gestellt-Quote EINES Schwingers (Empirical Bayes)."""
    return (gestellt + GESTELLT_NEIGUNG_K * basis) / (gaenge + GESTELLT_NEIGUNG_K)


def paar_gestellt(duelle: int, gestellt: int, neigung_a: float, neigung_b: float) -> float:
    """Gestellt-Bilanz eines Paars über die Erwartung hinaus (Empirical Bayes).

    Erwartung = Mittel der beiden Einzelneigungen. Die eigene Quote wird mit
    PAAR_GESTELLT_K Phantom-Duellen gegen sie geschrumpft; zurück kommt der
    Überschuss. Ohne Duelle exakt 0.
    """
    erwartung = (neigung_a + neigung_b) / 2.0
    return (gestellt + PAAR_GESTELLT_K * erwartung) / (duelle + PAAR_GESTELLT_K) - erwartung


def spitzen_niveau(elo_a: float, elo_b: float, skala: float) -> float:
    """Stärke des schwächeren Schwingers in Streuungen über dem Startwert, >= 0."""
    return max(0.0, (min(elo_a, elo_b) - ELO_START) / skala)


def paar_neigung(neigung_a: float, neigung_b: float, basis: float) -> float:
    """Gestellt-Neigung des Paars: Mittel beider Schwinger minus Durchschnitt."""
    return (neigung_a + neigung_b) / 2.0 - basis


def feature_vektor_fuer_prognose(
    elo_a, elo_b, form_a, form_b, n_a, n_b, sa: Schwinger, sb: Schwinger, datum: str,
    kopf_an_kopf_a: float = 0.0,
    *,
    modell_config: dict | None = None,
    neigung_a: float | None = None,
    neigung_b: float | None = None,
    duelle: int = 0,
    duelle_gestellt: int = 0,
) -> list[float]:
    """Live-Prognose: der Vektor so, wie die App ihn für DIESES Modell baut.

    modell_config ist model.json["config"]: daraus kommen Merkmalsversion,
    Elo-Skala und Gestellt-Basis. Ohne Versionseintrag gilt Version 1 -- so
    rechnet ein Modell, das dem Code hinterherhinkt, mit seiner eigenen
    Definition weiter. neigung_a/_b sind die exportierten Werte je Schwinger
    (schwinger.json); fehlen sie, gilt die Basis (neutral), wie in der App.

    kopf_an_kopf_a: geglättete bisherige A-vs-B-Bilanz, s. _kopf_an_kopf_vorteil
    (in der App: web/lib/kopfAnKopf.ts). duelle / duelle_gestellt: Anzahl
    bisheriger Duelle des Paars und davon gestellte (Version 3).
    """
    cfg = modell_config or {}
    version = int(cfg.get("merkmal_version", 1))
    if version < 2:
        return _feature_vektor(elo_a, elo_b, form_a, form_b, n_a, n_b, sa, sb, datum,
                               kopf_an_kopf_a, version=1)
    basis = float(cfg["gestellt_basis"])
    na = basis if neigung_a is None else neigung_a
    nb = basis if neigung_b is None else neigung_b
    return _feature_vektor(
        elo_a, elo_b, form_a, form_b, n_a, n_b, sa, sb, datum, kopf_an_kopf_a,
        version=version,
        elo_skala=float(cfg["elo_streuung"]),
        gestellt_neigung=paar_neigung(na, nb, basis),
        paar_gestellt=paar_gestellt(duelle, duelle_gestellt, na, nb) if version >= 3 else 0.0,
    )


def gestellt_neigung_aktuell(
    gaenge: list[GangResultat], schwinger: dict[str, Schwinger]
) -> tuple[dict[str, float], float]:
    """Neigung je Schwinger NACH allen Gängen + Gesamtdurchschnitt (für den Export).

    Zählt genau die Gänge, die auch baue_features zählt (beide Schwinger
    bekannt), damit Live-Wert und Trainingsmerkmal dieselbe Grösse sind.
    """
    gestellt: dict[str, int] = defaultdict(int)
    anzahl: dict[str, int] = defaultdict(int)
    n_ges = d_ges = 0
    for g in gaenge:
        if g.schwinger_a_id not in schwinger or g.schwinger_b_id not in schwinger:
            continue
        v = 1 if g.ergebnis == "gestellt" else 0
        for sid in (g.schwinger_a_id, g.schwinger_b_id):
            anzahl[sid] += 1
            gestellt[sid] += v
        n_ges += 1
        d_ges += v
    basis = d_ges / n_ges if n_ges else 0.0
    return {sid: _neigung(gestellt[sid], anzahl[sid], basis) for sid in anzahl}, basis
