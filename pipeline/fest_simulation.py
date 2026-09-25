"""Fest-Simulation (Monte Carlo): ein ganzes Schwingfest tausendfach durchspielen.

Aus den Paar-Wahrscheinlichkeiten des Modells (Sieg / Gestellt / Niederlage)
entsteht so, was ein Einzelgang nicht sagt: wie wahrscheinlich ein Schwinger
das Fest gewinnt, in den Schlussgang kommt oder einen Kranz holt.

Ablauf je Durchgang (vereinfachte, dokumentierte Regeln):

  Die Paarungen bestimmt im echten Fest ein Einteilungskampfgericht vor
  jedem Gang von Hand: gleich Starke gegeneinander, nach Punkten und Verlauf,
  keine Wiederholungen. Nachgebildet und an den echten Paarungen 2026
  kalibriert (mittlerer Elo-Abstand der Gegner real 108, simuliert 116;
  Gestellte real 22.1 %, simuliert 21.6 % -- streng nach Punkten waren es
  55 und 30 %: zu viele Gleichstarke, zu viele Gestellte):

  Gang 1       Anschwingen: die stärksten ``anschwingen_anteil`` (nach Elo)
               1-2, 3-4, ...; das übrige Feld zufällig gemischt.
  Gang 2..     nach Punkten mit Ermessensspielraum: Punkte + ``spielraum``
               * Zufall(0..1) bestimmen die Reihenfolge; gepaart wird mit dem
               Nächsten, gegen den noch nicht geschwungen wurde.
  Ausstich     nach bestimmten Gängen schwingt nur der beste Anteil weiter
               (``ausstiche``: [(nach Gang, Anteil weiter)]). Gemessen an
               den Gangzahlen je Teilnehmer 2025/26: an Kranzfesten scheiden
               nach Gang 4 rund 20 % aus; am Eidgenössischen (8 Gänge) nach
               Gang 4 rund 18 %, nach Gang 6 schwingt gut die Hälfte weiter.
  Schlussgang  im letzten Gang die zwei Punktbesten gegeneinander.
  Festsieger   der Sieger des Schlussgangs; bei gestelltem Schlussgang, wer
               am meisten Punkte hat.
  Kränze       die besten ``kranzquote`` (üblich 15-18 %) nach Punkten; bei
               Punktgleichheit an der Grenze alle.

Noten (Notengebung, s. CLAUDE.md): Sieg 10.00 (Plattwurf) oder 9.75,
Gestellt 8.75 oder 9.00 (technisch hochstehend), Niederlage 8.50 oder 8.75
(offensiv); im Schlussgang 10.00 / 8.75 vorgeschrieben. Wer bei ungerader
Zahl keinen Gegner bekommt, erhält 9.00. Die Anteile der Varianten stehen in
``NOTEN``.

Zufall: mulberry32 mit festem Startwert, dieselbe Folge von Zufallszahlen in
derselben Reihenfolge wie web/lib/simulation.ts -- beide liefern bei gleichem
Feld, gleichen Wahrscheinlichkeiten und gleichem Startwert exakt dieselben
Zählungen (geprüft in der Paritätsprüfung).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Anteil der besseren Note je Ausgang, gemessen auf allen Gängen 2023-2026
# (Messung "noten" auf den Rohdaten, 25.09.2026): Sieg 10.00 52.2 % / 9.75
# 47.6 %, Gestellt 9.00 31.4 % / 8.75 68.4 %, Niederlage 8.75 10.9 % /
# 8.50 88.9 %.
NOTEN = {"plattwurf": 0.52, "aktiv_gestellt": 0.31, "offensiv_verloren": 0.11}
FREILOS_NOTE = 9.0


def mulberry32(seed: int):
    """Zufallszahlen in [0, 1), bitgleich zu mulberry32 in JavaScript."""
    a = seed & 0xFFFFFFFF

    def imul(x: int, y: int) -> int:
        return (x * y) & 0xFFFFFFFF

    def naechste() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return naechste


@dataclass
class Regeln:
    gaenge: int = 6
    ausstiche: list = field(default_factory=lambda: [(4, 0.8)])
    kranzquote: float = 0.16
    noten: dict = field(default_factory=lambda: dict(NOTEN))
    anschwingen_anteil: float = 0.2
    spielraum: float = 1.0


# Regeln je Festtyp (s. Moduldoku). Regionalfeste: 6 Gänge, kein Ausstich,
# keine Kränze. Spiegelt REGELN_JE_TYP in web/lib/simulation.ts.
REGELN_JE_TYP = {
    "kantonal": Regeln(6, [(4, 0.8)], 0.16),
    "teilverband": Regeln(6, [(4, 0.8)], 0.16),
    "berg": Regeln(6, [(4, 0.8)], 0.16),
    "eidgenoessisch": Regeln(8, [(4, 0.82), (6, 0.55)], 0.15),
    "regional": Regeln(6, [], 0.0),
}


@dataclass
class Ergebnis:
    """Zählungen über alle Durchgänge, je Teilnehmer (Index wie die Eingabe)."""
    n_sim: int
    festsieg: list[int]
    schlussgang: list[int]
    kranz: list[int]
    punkte_summe: list[float]
    kranzgrenze_summe: float = 0.0

    def anteile(self) -> list[dict]:
        return [{
            "festsieg": self.festsieg[i] / self.n_sim,
            "schlussgang": self.schlussgang[i] / self.n_sim,
            "kranz": self.kranz[i] / self.n_sim,
            "punkte": self.punkte_summe[i] / self.n_sim,
        } for i in range(len(self.festsieg))]


def simuliere(p_sieg, p_gestellt, regeln: Regeln | None = None, *, n_sim: int = 1000,
              seed: int = 1) -> Ergebnis:
    """Simuliert ein Fest ``n_sim`` Mal.

    Teilnehmer 0..n-1 in Setzreihenfolge (stärkster zuerst, s. Anschwingen).
    ``p_sieg[i][j]``: P(i gewinnt gegen j); ``p_gestellt[i][j]``: P(gestellt).
    Beide Matrizen müssen paar-konsistent sein (p_sieg[j][i] = P(j gewinnt)).
    """
    r = regeln or Regeln()
    n = len(p_sieg)
    rng = mulberry32(seed)
    erg = Ergebnis(n_sim, [0] * n, [0] * n, [0] * n, [0.0] * n)
    if n < 2:
        return erg
    weiter_nach = {nach: math.ceil(anteil * n) for nach, anteil in r.ausstiche}
    # floor(x + 0.5) wie Math.round in JavaScript -- Pythons round() rundet
    # .5 zur geraden Zahl und wiche dann ab (etwa 0.15 * 30 = 4.5).
    n_kranz = math.floor(r.kranzquote * n + 0.5)
    platt, aktiv_g, offensiv = (r.noten["plattwurf"], r.noten["aktiv_gestellt"],
                                r.noten["offensiv_verloren"])

    for _ in range(n_sim):
        punkte = [0.0] * n
        gegner = [set() for _ in range(n)]
        aktiv = list(range(n))
        schluss = None          # (i, j, Ergebnis) des Schlussgangs
        for gang in range(1, r.gaenge + 1):
            k = weiter_nach.get(gang - 1)
            if k is not None and k < len(aktiv):
                aktiv = sorted(aktiv, key=lambda i: (-punkte[i], i))[:k]
            ist_schlussgang = gang == r.gaenge and len(aktiv) >= 2
            if gang == 1:
                k = int(r.anschwingen_anteil * n) // 2 * 2
                rest = list(range(k, n))
                for a in range(len(rest) - 1, 0, -1):     # Fisher-Yates
                    b = int(rng() * (a + 1))
                    rest[a], rest[b] = rest[b], rest[a]
                reihe = list(range(k)) + rest
            else:
                schluessel = {i: punkte[i] + r.spielraum * rng() for i in aktiv}
                reihe = sorted(aktiv, key=lambda i: (-schluessel[i], i))
            paare = []
            if ist_schlussgang:
                # Der Schlussgang geht an die zwei Punktbesten -- ohne Spielraum.
                beste = sorted(aktiv, key=lambda i: (-punkte[i], i))[:2]
                paare.append((beste[0], beste[1]))
                reihe = [i for i in reihe if i not in beste]
            offen = list(reihe)
            while len(offen) >= 2:
                i = offen.pop(0)
                k = next((x for x, j in enumerate(offen) if j not in gegner[i]), 0)
                paare.append((i, offen.pop(k)))
            if offen:                               # ungerade: Freilos
                punkte[offen[0]] += FREILOS_NOTE
            for nr, (i, j) in enumerate(paare):
                z = rng()
                pa, pg = p_sieg[i][j], p_gestellt[i][j]
                schlussgang = ist_schlussgang and nr == 0
                if z < pa:
                    sieger, verlierer = i, j
                elif z < pa + pg:
                    sieger = verlierer = None
                else:
                    sieger, verlierer = j, i
                if sieger is None:
                    punkte[i] += 9.0 if rng() < aktiv_g else 8.75
                    punkte[j] += 9.0 if rng() < aktiv_g else 8.75
                elif schlussgang:
                    punkte[sieger] += 10.0
                    punkte[verlierer] += 8.75
                else:
                    punkte[sieger] += 10.0 if rng() < platt else 9.75
                    punkte[verlierer] += 8.75 if rng() < offensiv else 8.5
                gegner[i].add(j)
                gegner[j].add(i)
                if schlussgang:
                    schluss = (i, j, sieger)

        rang = sorted(range(n), key=lambda i: (-punkte[i], i))
        if schluss is not None:
            erg.schlussgang[schluss[0]] += 1
            erg.schlussgang[schluss[1]] += 1
            sieger = schluss[2] if schluss[2] is not None else rang[0]
        else:
            sieger = rang[0]
        erg.festsieg[sieger] += 1
        if n_kranz > 0:
            grenze = punkte[rang[n_kranz - 1]]
            erg.kranzgrenze_summe += grenze
            for i in range(n):
                if punkte[i] >= grenze:
                    erg.kranz[i] += 1
        for i in range(n):
            erg.punkte_summe[i] += punkte[i]
    return erg


# --- Rückblick: stimmt die Simulation? -----------------------------------------
# Jedes Kranzfest der Holdout-Saison wird mit dem Modell simuliert, das VOR der
# Saison galt, und mit dem Stand jedes Schwingers vor dem Fest -- genau die
# Vorhersage, die man damals hätte machen können. Verglichen mit den echten
# Kränzen und Festsiegern der Schlussrangliste, und mit derselben Simulation
# auf reinen Elo-Wahrscheinlichkeiten.

KRANZFEST_TYPEN = ("kantonal", "teilverband", "berg", "eidgenoessisch")
KALIBRIERUNG_GRENZEN = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.9, 1.0001)
BACKTEST_SIMULATIONEN = 200


def _paar_matrizen(teilnehmer, p_paar):
    """p_paar(i, j) -> (P(i gewinnt), P(gestellt), P(j gewinnt)) für i < j."""
    n = len(teilnehmer)
    sieg = [[0.0] * n for _ in range(n)]
    gestellt = [[0.0] * n for _ in range(n)]
    for (i, j), (pa, pg, pb) in p_paar:
        sieg[i][j], sieg[j][i] = pa, pb
        gestellt[i][j] = gestellt[j][i] = pg
    return sieg, gestellt


def _brier(p, y) -> float:
    return float(sum((a - b) ** 2 for a, b in zip(p, y)) / len(p)) if p else float("nan")


def backtest(gaenge, snapshots, schwinger, modell, saison: int, ranglisten_feste: dict,
             kranz_je_fest: dict, *, n_sim: int = BACKTEST_SIMULATIONEN, seed: int = 1) -> dict | None:
    """Simuliert jedes Kranzfest von ``saison`` und vergleicht mit dem Resultat.

    ``ranglisten_feste``: ranglisten.fest_ueberblick (Sieger je Fest);
    ``kranz_je_fest``: {event_id: {schwinger_id: Kranz ja/nein}}.
    """
    from dataclasses import replace

    import numpy as np

    from .features import baue_features
    from .ratings import EloModell

    typ = {g.event_id: g.fest_typ for g in gaenge}
    elo_modell = EloModell()
    teil: list[dict] = []          # je Teilnehmer mit Rangliste
    feste: list[dict] = []         # je Fest

    def pro_fest(eid, datum, teilnehmer, vektor, elo):
        kranz = kranz_je_fest.get(eid) or {}
        if (not datum.startswith(str(saison)) or typ.get(eid) not in KRANZFEST_TYPEN
                or not any(kranz.values()) or len(teilnehmer) < 8):
            return      # Kilchberg/Unspunnen vergeben keine Kränze; ohne Rangliste kein Vergleich
        n = len(teilnehmer)
        paare = [(i, j) for i in range(n) for j in range(i + 1, n)]
        P = modell.predict_proba(np.array([vektor(teilnehmer[i], teilnehmer[j]) for i, j in paare]))
        m_sieg, m_gestellt = _paar_matrizen(teilnehmer, zip(paare, P.tolist()))
        e_sieg, e_gestellt = _paar_matrizen(teilnehmer, (
            ((i, j), elo_modell.wahrscheinlichkeiten(elo[teilnehmer[i]], elo[teilnehmer[j]]))
            for i, j in paare))
        # Die tatsächliche Kranzquote des Fests: gemessen wird, WER die
        # Kränze holt, nicht wie viele es gibt.
        regeln = replace(REGELN_JE_TYP[typ[eid]], kranzquote=sum(kranz.values()) / len(kranz))
        m = simuliere(m_sieg, m_gestellt, regeln, n_sim=n_sim, seed=seed).anteile()
        e = simuliere(e_sieg, e_gestellt, regeln, n_sim=n_sim, seed=seed).anteile()
        sieger = set((ranglisten_feste.get(eid) or {}).get("sieger") or [])
        for k, sid in enumerate(teilnehmer):
            if sid in kranz:
                teil.append({"kranz": float(kranz[sid]), "modell": m[k]["kranz"], "elo": e[k]["kranz"]})
        if sieger & set(teilnehmer):
            def rang(anteile):
                return sorted(range(n), key=lambda k: -anteile[k]["festsieg"])
            rm, re_ = rang(m), rang(e)
            feste.append({
                "p_modell": sum(m[k]["festsieg"] for k in range(n) if teilnehmer[k] in sieger),
                "p_elo": sum(e[k]["festsieg"] for k in range(n) if teilnehmer[k] in sieger),
                "favorit_modell": teilnehmer[rm[0]] in sieger,
                "favorit_elo": teilnehmer[re_[0]] in sieger,
                "top3_modell": bool(sieger & {teilnehmer[k] for k in rm[:3]}),
                "top3_elo": bool(sieger & {teilnehmer[k] for k in re_[:3]}),
                "n": n,
            })

    baue_features(gaenge, snapshots, schwinger, augment=False, pro_fest=pro_fest)
    if not teil:
        return None

    y = [t["kranz"] for t in teil]
    konstant = sum(y) / len(y)
    kalibrierung = []
    for lo, hi in zip(KALIBRIERUNG_GRENZEN, KALIBRIERUNG_GRENZEN[1:]):
        gruppe = [t for t in teil if lo <= t["modell"] < hi]
        if gruppe:
            kalibrierung.append({
                "von": lo, "bis": min(hi, 1.0), "n": len(gruppe),
                "vorhergesagt": round(sum(t["modell"] for t in gruppe) / len(gruppe), 4),
                "eingetreten": round(sum(t["kranz"] for t in gruppe) / len(gruppe), 4),
            })
    mittel = lambda schl: round(sum(f[schl] for f in feste) / len(feste), 4) if feste else None  # noqa: E731
    return {
        "saison": saison,
        "n_feste": len(feste),
        "n_teilnahmen": len(teil),
        "n_simulationen": n_sim,
        "kranz": {
            "brier_modell": round(_brier([t["modell"] for t in teil], y), 4),
            "brier_elo": round(_brier([t["elo"] for t in teil], y), 4),
            "brier_konstant": round(_brier([konstant] * len(y), y), 4),
            "kalibrierung": kalibrierung,
        },
        "festsieg": {
            "p_sieger_modell": mittel("p_modell"),
            "p_sieger_elo": mittel("p_elo"),
            "favorit_modell": mittel("favorit_modell"),
            "favorit_elo": mittel("favorit_elo"),
            "top3_modell": mittel("top3_modell"),
            "top3_elo": mittel("top3_elo"),
            "mittlere_feldgroesse": round(sum(f["n"] for f in feste) / len(feste), 1) if feste else None,
        },
    }
