"""Stil-Typen: WIE ein Schwinger seine Gänge entscheidet, nicht wie stark er ist.

Ersetzt am 06.10.2026 das K-Means über das volle Porträt-Profil (Physis,
Elo, Erfahrung, Alter, Kranzstatus, Schwünge). Das fand keine Struktur:
Silhouette 0.24, drei Gruppen mit 434 / 82 / 10 Schwingern, im Kern "die
Starken" (Elo und Kranzstatus) gegen den Rest und zehn, die den Schlungg
mögen. Stärke zeigen Elo und Kränze schon; ein Typ soll etwas anderes sagen.

Darum zwei Eigenschaften, die als stabile Eigenschaft der Person gemessen
sind (Messung "siegart", ROADMAP D1; Gestellt-Neigung, Merkmalsversion 2),
beide gegen die ERWARTUNG gerechnet, damit Stärke und Gegner nicht als Stil
erscheinen:

  plattwurf  Anteil der Siege mit 10.00 minus Erwartung aus Elo-Abstand,
             eigener Stärke und Benotung des Fests (ohne die eigenen Siege).
             Gegen Schwächere wirft jeder öfter platt -- das ist kein Stil.
  gestellt   Anteil gestellter Gänge minus Erwartung aus Elo-Abstand, Niveau
             der Paarung und Gestellt-Quote des Fests. Treffen zwei Starke
             aufeinander, wird öfter gestellt -- auch das ist kein Stil.

Beide geschrumpft wie die Gestellt-Neigung (K "Phantom-Gänge" ohne
Abweichung), damit wenige Gänge keine Extremwerte erzeugen. Der Typ folgt
aus der Lage auf beiden Achsen (in Standardabweichungen, Schwelle
SCHWELLE_Z); die Schwellen stehen im Artefakt, die App zeichnet sie ein.

Ausgenommen sind mutmassliche Schlussgänge (10.00/8.75 vorgeschrieben,
``schlussgang_verdacht``) und Gänge, in denen ein Schwinger noch keine
MIN_GAENGE_ELO Gänge hatte (Elo noch kaum eine Messung).

Jeder Lauf misst zusätzlich, ob die Achsen eine Eigenschaft der Person sind
(Korrelation zweier Hälften der Gänge) und wie stark sie mit dem Elo
zusammenhängen. Die App zeigt beides.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from .clustering import _normiert
from .labels import GangResultat
from .schema import Schwinger

# Notengebung (CLAUDE.md, ROADMAP D1): Plattwurf-Sieg 10.00, Sieg 9.75;
# im Schlussgang sind 10.00/8.75 vorgeschrieben.
PLATTWURF = 10.0
OFFENSIV_VERLOREN = 8.75

MIN_GAENGE_ELO = 10      # Elo des Gegners und eigenes Elo erst ab hier eine Messung
MIN_GAENGE = 40          # Gänge je Schwinger für einen Typ
MIN_SIEGE = 15           # Siege mit Note je Schwinger für einen Typ
K_PLATTWURF = 20.0       # Phantom-Siege ohne Abweichung (Schrumpfung)
K_GESTELLT = 20.0        # Phantom-Gänge ohne Abweichung, wie die Gestellt-Neigung
MIN_FEST_GAENGE = 20     # darunter gilt für das Fest die Gesamtquote
SCHWELLE_Z = 0.5         # ab so vielen Standardabweichungen gilt eine Achse als ausgeprägt
N_BEKANNTESTE = 6

TYPEN = ["werfer", "lauerer", "bollwerk", "bodenarbeiter", "entscheider", "allrounder"]


def schlussgang_verdacht(gaenge) -> set[int]:
    """Indizes der Gänge, die der Schlussgang sein könnten.

    Die Statistik-PDF kennzeichnet den Schlussgang nicht, dort sind aber
    10.00/8.75 vorgeschrieben -- ein Spitzenschwinger bekäme so einen
    geschenkten "Plattwurf". Ausgenommen wird darum jeder Sieg des
    Punktbesten eines Fests mit 10.00 gegen 8.75. Das trifft den Schlussgang
    fast immer und nimmt dem Punktbesten höchstens einzelne echte Plattwürfe
    weg (die Messung wird dadurch eher gegen die Vermutung verzerrt).
    """
    summe = defaultdict(float)
    for g in gaenge:
        for sid, note in ((g.schwinger_a_id, g.note_a), (g.schwinger_b_id, g.note_b)):
            if note is not None:
                summe[(g.event_id, sid)] += note
    beste: dict[str, tuple[str, float]] = {}
    for (eid, sid), p in summe.items():
        if eid not in beste or p > beste[eid][1]:
            beste[eid] = (sid, p)
    verdacht = set()
    for i, g in enumerate(gaenge):
        if g.ergebnis == "gestellt" or g.event_id not in beste:
            continue
        a_gewinnt = g.ergebnis == "sieg_a"
        sieger = g.schwinger_a_id if a_gewinnt else g.schwinger_b_id
        n_s, n_v = (g.note_a, g.note_b) if a_gewinnt else (g.note_b, g.note_a)
        if sieger == beste[g.event_id][0] and n_s == PLATTWURF and n_v == OFFENSIV_VERLOREN:
            verdacht.add(i)
    return verdacht


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 0.02, 0.98)
    return np.log(p / (1 - p))


def _fest_quote(zeilen: list[dict], schluessel: str, faktor: int = 1) -> np.ndarray:
    """Quote des Fests OHNE die Gänge dieses Schwingers (Benotung, Festtyp).

    Benoten die Kampfrichter eines Fests grosszügig, sähe das sonst wie ein
    Stil der Schwinger aus, die meist dort antreten. ``faktor``: wie oft ein
    eigener Gang in den Zeilen des Fests steht -- bei den Gestellt-Zeilen
    zweimal (auch beim Gegner, mit demselben Ausgang). Bliebe die Zeile des
    Gegners drin, stünde der eigene Ausgang in der Erwartung.
    """
    gesamt = float(np.mean([z[schluessel] for z in zeilen])) if zeilen else 0.5
    f_s, f_n = defaultdict(float), defaultdict(int)
    p_s, p_n = defaultdict(float), defaultdict(int)
    for z in zeilen:
        f_s[z["event_id"]] += z[schluessel]
        f_n[z["event_id"]] += 1
        p_s[(z["event_id"], z["sid"])] += z[schluessel]
        p_n[(z["event_id"], z["sid"])] += 1
    quote = []
    for z in zeilen:
        e, k = z["event_id"], (z["event_id"], z["sid"])
        n = f_n[e] - faktor * p_n[k]
        quote.append((f_s[e] - faktor * p_s[k]) / n if n >= MIN_FEST_GAENGE else gesamt)
    return np.array(quote)


def _erwartung(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Erwartete Wahrscheinlichkeit je Zeile (logistische Regression)."""
    from sklearn.linear_model import LogisticRegression

    if len(set(y.tolist())) < 2:
        return np.full(len(y), float(y.mean()) if len(y) else 0.0)
    modell = LogisticRegression(C=1e6, max_iter=1000)
    modell.fit(X, y)
    return modell.predict_proba(X)[:, 1]


def _zeilen(gaenge: list[GangResultat], snapshots: list[dict]) -> tuple[list[dict], list[dict]]:
    """Gestellt-Zeilen (je Gang und Schwinger) und Plattwurf-Zeilen (je Sieg)."""
    elo = {(s["event_id"], s["schwinger_a_id"], s["schwinger_b_id"]): s for s in snapshots}
    ohne = schlussgang_verdacht(gaenge)
    gestellt, platt = [], []
    for i, g in enumerate(gaenge):
        s = elo.get((g.event_id, g.schwinger_a_id, g.schwinger_b_id))
        if s is None or min(s["n_a_pre"], s["n_b_pre"]) < MIN_GAENGE_ELO:
            continue
        ea, eb = s["elo_a_pre"], s["elo_b_pre"]
        ist_gestellt = 1.0 if g.ergebnis == "gestellt" else 0.0
        for sid in (g.schwinger_a_id, g.schwinger_b_id):
            gestellt.append({"sid": sid, "event_id": g.event_id, "datum": g.datum,
                             "y": ist_gestellt, "abstand": abs(ea - eb) / 100.0,
                             "niveau": max(0.0, (min(ea, eb) - 1500.0) / 100.0)})
        if g.ergebnis == "gestellt" or i in ohne or g.note_a is None or g.note_b is None:
            continue
        a_gewinnt = g.ergebnis == "sieg_a"
        sieger = g.schwinger_a_id if a_gewinnt else g.schwinger_b_id
        e_s, e_v = (ea, eb) if a_gewinnt else (eb, ea)
        note = g.note_a if a_gewinnt else g.note_b
        platt.append({"sid": sieger, "event_id": g.event_id, "datum": g.datum,
                      "y": 1.0 if note >= PLATTWURF else 0.0,
                      "abstand": (e_s - e_v) / 100.0, "staerke": (e_s - 1500.0) / 100.0})
    return gestellt, platt


def _mit_erwartung(zeilen: list[dict], merkmale: list[str], faktor: int = 1) -> None:
    """Ergänzt je Zeile "p" (Erwartung) aus den Merkmalen und der Fest-Quote."""
    if not zeilen:
        return
    quote = _fest_quote(zeilen, "y", faktor)
    X = np.column_stack([[z[m] for z in zeilen] for m in merkmale] + [_logit(quote)])
    y = np.array([z["y"] for z in zeilen])
    for z, p in zip(zeilen, _erwartung(X, y)):
        z["p"] = float(p)


def _je_person(zeilen: list[dict], k: float) -> dict[str, dict]:
    """Je Schwinger: n, beobachtete Quote, erwartete Quote, geschrumpfte Abweichung."""
    summen: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for z in zeilen:
        s = summen[z["sid"]]
        s[0] += 1
        s[1] += z["y"]
        s[2] += z["p"]
    return {sid: {"n": int(n), "quote": y / n, "erwartet": p / n, "abweichung": (y - p) / (n + k)}
            for sid, (n, y, p) in summen.items()}


def _haelften_r(zeilen: list[dict], personen: set[str]) -> float | None:
    """Korrelation der Abweichung in zwei Hälften der Zeilen (abwechselnd nach
    Datum verteilt) -- misst, ob die Achse eine Eigenschaft der Person ist."""
    je: dict[str, list[dict]] = defaultdict(list)
    for z in zeilen:
        if z["sid"] in personen:
            je[z["sid"]].append(z)
    h1, h2 = [], []
    for liste in je.values():
        liste.sort(key=lambda z: (z["datum"], z["event_id"]))
        a, b = liste[0::2], liste[1::2]
        if len(a) >= 5 and len(b) >= 5:
            h1.append(np.mean([z["y"] - z["p"] for z in a]))
            h2.append(np.mean([z["y"] - z["p"] for z in b]))
    if len(h1) < 10:
        return None
    return round(float(np.corrcoef(h1, h2)[0, 1]), 3)


def typ_von(z_platt: float, z_gestellt: float, schwelle: float = SCHWELLE_Z) -> str:
    """Typ aus der Lage auf beiden Achsen (in Standardabweichungen)."""
    if z_platt >= schwelle:
        return "lauerer" if z_gestellt >= schwelle else "werfer"
    if z_gestellt >= schwelle:
        return "bollwerk"
    if z_platt <= -schwelle:
        return "bodenarbeiter"
    if z_gestellt <= -schwelle:
        return "entscheider"
    return "allrounder"


def _korrelation(a: list[float], b: list[float]) -> float | None:
    if len(a) < 10 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 3)


def berechne_stiltypen(
    gaenge: list[GangResultat],
    snapshots: list[dict],
    schwinger: dict[str, Schwinger],
    elo_modell,
    aktive: set[str],
) -> dict | None:
    """Stil-Typ je aktivem Schwinger mit genug Gängen; None ohne Datenbasis."""
    g_zeilen, p_zeilen = _zeilen(gaenge, snapshots)
    if not p_zeilen or not g_zeilen:
        return None
    _mit_erwartung(g_zeilen, ["abstand", "niveau"], faktor=2)
    _mit_erwartung(p_zeilen, ["abstand", "staerke"])
    gestellt = _je_person(g_zeilen, K_GESTELLT)
    platt = _je_person(p_zeilen, K_PLATTWURF)

    personen = sorted(
        sid for sid in aktive
        if sid in schwinger and gestellt.get(sid, {}).get("n", 0) >= MIN_GAENGE
        and platt.get(sid, {}).get("n", 0) >= MIN_SIEGE
    )
    if len(personen) < 30:
        return None

    a_p = np.array([platt[sid]["abweichung"] for sid in personen])
    a_g = np.array([gestellt[sid]["abweichung"] for sid in personen])
    sd_p = float(a_p.std()) or 1.0
    sd_g = float(a_g.std()) or 1.0
    elo_jetzt = {sid: float(elo_modell.get(sid)) for sid in personen}

    punkte = []
    for i, sid in enumerate(personen):
        p, g = platt[sid], gestellt[sid]
        punkte.append({
            "schwinger_id": sid,
            "typ": typ_von(a_p[i] / sd_p, a_g[i] / sd_g),
            # in Prozentpunkten, damit die App die Achsen lesbar beschriften kann
            "plattwurf": round(100 * float(a_p[i]), 2),
            "gestellt": round(100 * float(a_g[i]), 2),
            "plattwurf_quote": round(p["quote"], 3),
            "plattwurf_erwartet": round(p["erwartet"], 3),
            "gestellt_quote": round(g["quote"], 3),
            "gestellt_erwartet": round(g["erwartet"], 3),
            "n_siege": p["n"],
            "n_gaenge": g["n"],
            "elo": round(elo_jetzt[sid], 1),
        })

    typen = []
    for typ in TYPEN:
        mitglieder = [pt for pt in punkte if pt["typ"] == typ]
        if not mitglieder:
            continue
        ids = [pt["schwinger_id"] for pt in mitglieder]
        gewichte = [schwinger[sid].gewicht_kg for sid in ids if schwinger[sid].gewicht_kg]
        groessen = [schwinger[sid].groesse_cm for sid in ids if schwinger[sid].groesse_cm]
        schwuenge: Counter[str] = Counter(
            _normiert(n) for sid in ids for n in (schwinger[sid].bevorzugte_schwuenge or []))
        # "Am ausgeprägtesten": das Mitglied, das am weitesten in die Richtung
        # des Typs liegt (Allrounder: am nächsten an der Mitte).
        richtung = {"werfer": (1, -0.5), "lauerer": (1, 1), "bollwerk": (-0.5, 1),
                    "bodenarbeiter": (-1, -0.5), "entscheider": (0, -1)}.get(typ)

        def lage(pt):
            zp, zg = pt["plattwurf"] / (100 * sd_p), pt["gestellt"] / (100 * sd_g)
            if richtung is None:
                return -(zp * zp + zg * zg)
            return richtung[0] * zp + richtung[1] * zg

        typen.append({
            "typ": typ,
            "n": len(mitglieder),
            "elo_avg": round(float(np.mean([pt["elo"] for pt in mitglieder])), 1),
            "gewicht_avg": round(float(np.mean(gewichte)), 1) if len(gewichte) >= 5 else None,
            "groesse_avg": round(float(np.mean(groessen)), 1) if len(groessen) >= 5 else None,
            "n_physis": len(gewichte),
            "plattwurf_quote_avg": round(float(np.mean([pt["plattwurf_quote"] for pt in mitglieder])), 3),
            "gestellt_quote_avg": round(float(np.mean([pt["gestellt_quote"] for pt in mitglieder])), 3),
            "top_schwuenge": [n for n, _ in schwuenge.most_common(3)],
            "bekannteste": [pt["schwinger_id"] for pt in
                            sorted(mitglieder, key=lambda pt: -pt["elo"])[:N_BEKANNTESTE]],
            "ausgepraegteste": max(mitglieder, key=lage)["schwinger_id"],
        })

    elo_liste = [elo_jetzt[sid] for sid in personen]
    return {
        "n_schwinger": len(punkte),
        "n_gaenge": len(g_zeilen) // 2,
        "n_siege": len(p_zeilen),
        "schwelle_z": SCHWELLE_Z,
        # Schwellen in Prozentpunkten (wie die Achsen der Punkte)
        "schwelle_plattwurf": round(100 * SCHWELLE_Z * sd_p, 2),
        "schwelle_gestellt": round(100 * SCHWELLE_Z * sd_g, 2),
        "plattwurf_basis": round(float(np.mean([z["y"] for z in p_zeilen])), 3),
        "gestellt_basis": round(float(np.mean([z["y"] for z in g_zeilen])), 3),
        "pruefung": {
            "haelften_r_plattwurf": _haelften_r(p_zeilen, set(personen)),
            "haelften_r_gestellt": _haelften_r(g_zeilen, set(personen)),
            "r_achsen": _korrelation(a_p.tolist(), a_g.tolist()),
            "r_elo_plattwurf": _korrelation(a_p.tolist(), elo_liste),
            "r_elo_gestellt": _korrelation(a_g.tolist(), elo_liste),
        },
        "mindestens": {"gaenge": MIN_GAENGE, "siege": MIN_SIEGE},
        "typen": typen,
        "punkte": punkte,
    }
