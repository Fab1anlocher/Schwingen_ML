"""Messungen, die die Rohdaten brauchen (Roadmap D3/D1).

Die Rohdaten (``artifacts/raw``) liegen nur im Actions-Cache. Was dort steht,
aber nicht in den committeten Artefakten -- etwa die Note je Gang --, lässt
sich nur auf dem Runner messen: Workflow "Messung auf Rohdaten"
(``.github/workflows/messung.yml``) führt ``python -m pipeline.messung <name>``
aus und schreibt die Ausgabe (Markdown) ins Job-Summary.

Messungen:
  noten     Verteilung der Noten je Ausgang (Plausibilität gegen die
            Notengebung) und ob Noten-Merkmale das Modell verbessern (D1).
  siegart   Gewinnen starke Schwinger eher mit 10.00? Nach Stärke und
            Elo-Abstand getrennt, als Eigenschaft der Person und als
            Merkmal im Modell.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict

import numpy as np

# Notengebung (s. CLAUDE.md, ROADMAP D1): Plattwurf-Sieg 10.00, Sieg 9.75,
# Gestellt 8.75 (technisch hochstehend bis 9.00), Niederlage 8.50 (offensiv
# 8.75). Im Schlussgang sind 10.00/8.75 vorgeschrieben -- die Statistik-PDF
# kennzeichnet ihn nicht, er ist darum mitgezählt (1 von rund 300 Gängen je Fest).
PLATTWURF = 10.0
AKTIV_GESTELLT = 9.0
OFFENSIV_VERLOREN = 8.75
# Geschrumpft wie die Gestellt-Neigung: so viele "Phantom-Gänge" zum Mittel.
NOTEN_K = 10.0

NOTEN_MERKMALE = ["plattwurf_diff", "offensiv_diff", "aktiv_gestellt"]
NOTEN_SYMMETRISCH = {"aktiv_gestellt"}


def _lade_gaenge():
    from .labels import dedupliziere
    from .scrape import lade_echte_daten

    schwinger, events, roh, _ = lade_echte_daten(mit_bericht=True)
    gaenge, _ = dedupliziere(roh)
    return schwinger, gaenge


def _ausgang(g, seite: str) -> tuple[str, float | None]:
    """(sieg|gestellt|niederlage, Note) aus Sicht von A oder B."""
    note = g.note_a if seite == "a" else g.note_b
    if g.ergebnis == "gestellt":
        return "gestellt", note
    gewinner_a = g.ergebnis == "sieg_a"
    return ("sieg" if gewinner_a == (seite == "a") else "niederlage"), note


def verteilung(gaenge) -> list[str]:
    """Markdown: welche Noten je Ausgang vorkommen."""
    je = defaultdict(Counter)
    ohne = 0
    for g in gaenge:
        for seite in ("a", "b"):
            ausgang, note = _ausgang(g, seite)
            if note is None:
                ohne += 1
                continue
            je[ausgang][round(note, 2)] += 1
    z = ["## Noten je Ausgang", "",
         f"{2 * len(gaenge)} Gang-Perspektiven, davon {ohne} ohne Note "
         f"({ohne / max(1, 2 * len(gaenge)):.1%}).", "",
         "| Ausgang | n | häufigste Noten (Anteil) |", "|---|---:|---|"]
    for ausgang in ("sieg", "gestellt", "niederlage"):
        c = je[ausgang]
        n = sum(c.values())
        top = ", ".join(f"{k:.2f} ({v / n:.1%})" for k, v in c.most_common(6)) if n else "-"
        z.append(f"| {ausgang} | {n} | {top} |")
    return z + [""]


def noten_merkmale(gaenge, meta) -> np.ndarray:
    """Noten-Merkmale je Zeile von ``meta``, Stand VOR dem Fest (leak-frei).

    Je Schwinger: Anteil Plattwürfe an den Siegen, Anteil "offensiver"
    Niederlagen (>= 8.75), Anteil aktiver Gestellter (>= 9.00) -- je gegen den
    bisherigen Gesamtschnitt geschrumpft. Merkmale: Differenz A - B für die
    ersten beiden, Mittel beider minus Schnitt für das dritte (symmetrisch).
    Spiegelzeilen (``augmented``) sehen B gegen A.
    """
    zaehler = defaultdict(lambda: defaultdict(float))   # sid -> {sieg, platt, niederlage, ...}
    gesamt = defaultdict(float)
    stand: dict[tuple, tuple] = {}

    def quote(sid, treffer, basis):
        z = zaehler[sid]
        schnitt = gesamt[treffer] / gesamt[basis] if gesamt[basis] else 0.0
        return (z[treffer] + NOTEN_K * schnitt) / (z[basis] + NOTEN_K), schnitt

    je_fest = defaultdict(list)
    for g in gaenge:
        je_fest[(g.datum, g.event_id)].append(g)
    for (_, eid), liste in sorted(je_fest.items()):
        # 1. Stand vor dem Fest für alle Gänge dieses Fests festhalten.
        for g in liste:
            werte = {}
            for sid in (g.schwinger_a_id, g.schwinger_b_id):
                platt, _ = quote(sid, "platt", "sieg")
                off, _ = quote(sid, "offensiv", "niederlage")
                aktiv, schnitt_aktiv = quote(sid, "aktiv", "gestellt")
                werte[sid] = (platt, off, aktiv, schnitt_aktiv)
            a, b = werte[g.schwinger_a_id], werte[g.schwinger_b_id]
            stand[(eid, g.schwinger_a_id, g.schwinger_b_id)] = (
                a[0] - b[0], a[1] - b[1], (a[2] + b[2]) / 2 - a[3])
        # 2. Danach die Noten dieses Fests einrechnen.
        for g in liste:
            for seite, sid in (("a", g.schwinger_a_id), ("b", g.schwinger_b_id)):
                ausgang, note = _ausgang(g, seite)
                if note is None:
                    continue
                if ausgang == "sieg":
                    paar = ("platt", "sieg", note >= PLATTWURF)
                elif ausgang == "niederlage":
                    paar = ("offensiv", "niederlage", note >= OFFENSIV_VERLOREN)
                else:
                    paar = ("aktiv", "gestellt", note >= AKTIV_GESTELLT)
                treffer, basis, ja = paar
                zaehler[sid][basis] += 1
                zaehler[sid][treffer] += ja
                gesamt[basis] += 1
                gesamt[treffer] += ja

    out = np.zeros((len(meta), len(NOTEN_MERKMALE)))
    for i, m in enumerate(meta):
        w = stand.get((m["event_id"], m["schwinger_a_id"], m["schwinger_b_id"]))
        if w is None:
            continue
        platt, off, aktiv = w
        if m.get("augmented"):
            platt, off = -platt, -off
        out[i] = (platt, off, aktiv)
    return out


def _mit_zusatzmerkmalen(namen: list[str], symmetrisch: set[str]):
    """Kontext: modell.py kennt vorübergehend zusätzliche Merkmale (nur für Messungen)."""
    import contextlib

    from . import modell

    @contextlib.contextmanager
    def ctx():
        alt = modell.FEATURE_NAMES, modell.SYMMETRISCH
        modell.FEATURE_NAMES = list(alt[0]) + namen
        modell.SYMMETRISCH = frozenset(alt[1] | symmetrisch)
        try:
            yield
        finally:
            modell.FEATURE_NAMES, modell.SYMMETRISCH = alt
    return ctx()


def noten() -> list[str]:
    from .features import baue_features
    from .harness import bewerte
    from .ratings import fahre_elo_durch
    from .train import bestimme_holdout_jahr

    schwinger, gaenge = _lade_gaenge()
    z = ["# Messung: Noten je Gang (Roadmap D1)", ""] + verteilung(gaenge)

    _, snapshots = fahre_elo_durch(gaenge)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    X, y = np.asarray(X), np.asarray(y)
    N = noten_merkmale(gaenge, meta)
    test = bestimme_holdout_jahr(meta)
    jahre = (test - 1, test)                     # Validierung, Test
    basis = bewerte(X, y, meta, jahre)
    with _mit_zusatzmerkmalen(NOTEN_MERKMALE, NOTEN_SYMMETRISCH):
        mit = bewerte(np.hstack([X, N]), y, meta, jahre)
    val, tst = jahre
    z += ["## Noten-Merkmale im Modell", "",
          f"Validierung {val} / Test {tst}, Log-Loss (tiefer = besser). Übernehmen nur, "
          "wenn beide Jahre besser werden.", "",
          f"| | Val {val} | Test {tst} | Acc Test | AUC Gestellt Test |", "|---|---:|---:|---:|---:|"]
    for name, r in (("heute", basis), (f"+ Noten ({', '.join(NOTEN_MERKMALE)})", mit)):
        z.append(f"| {name} | {r[val]['log_loss']} | {r[tst]['log_loss']} | "
                 f"{r[tst]['accuracy']} | {r[tst]['auc_gestellt']} |")
    z.append("")
    for name, spalte in zip(NOTEN_MERKMALE, N.T):
        z.append(f"- `{name}`: Mittel {spalte.mean():+.4f}, Streuung {spalte.std():.4f}")
    return z + [""]


# --- Siegart: gewinnen starke Schwinger anders? ------------------------------
#
# Frage aus dem Projekt: Gewinnen sehr starke Schwinger eher mit der 10.00
# (Plattwurf)? Und wenn ja -- liegt es an ihrer Stärke selbst oder nur daran,
# dass sie meist gegen Schwächere antreten? Ist die Neigung zum Plattwurf eine
# Eigenschaft des Schwingers, und sagt sie etwas über kommende Gänge?

MIN_GAENGE_ELO = 10      # Elo erst ab so vielen erfassten Gängen eine Messung
MIN_SIEGE_PERSON = 40    # Siege je Schwinger für Aussagen über ihn selbst
ABSTAND_STUFEN = [(-np.inf, -100, "Sieger >100 schwächer"),
                  (-100, 0, "Sieger 0–100 schwächer"),
                  (0, 100, "Sieger 0–100 stärker"),
                  (100, 200, "Sieger 100–200 stärker"),
                  (200, np.inf, "Sieger >200 stärker")]


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


def siege_mit_elo(gaenge, snapshots, min_gaenge: int = MIN_GAENGE_ELO) -> list[dict]:
    """Je entschiedenem Gang mit beiden Noten: Sieger, Verlierer, Elo vor dem Fest.

    Nur Gänge, in denen beide schon ``min_gaenge`` erfasste Gänge haben (sonst
    ist Elo noch kaum eine Messung), ohne Schlussgang-Verdacht.
    """
    elo = {(s["event_id"], s["schwinger_a_id"], s["schwinger_b_id"]): s for s in snapshots}
    ohne = schlussgang_verdacht(gaenge)
    zeilen = []
    for i, g in enumerate(gaenge):
        if g.ergebnis == "gestellt" or i in ohne or g.note_a is None or g.note_b is None:
            continue
        s = elo.get((g.event_id, g.schwinger_a_id, g.schwinger_b_id))
        if s is None or min(s["n_a_pre"], s["n_b_pre"]) < min_gaenge:
            continue
        a_gewinnt = g.ergebnis == "sieg_a"
        zeilen.append({
            "sieger": g.schwinger_a_id if a_gewinnt else g.schwinger_b_id,
            "verlierer": g.schwinger_b_id if a_gewinnt else g.schwinger_a_id,
            "elo_s": s["elo_a_pre"] if a_gewinnt else s["elo_b_pre"],
            "elo_v": s["elo_b_pre"] if a_gewinnt else s["elo_a_pre"],
            "platt": (g.note_a if a_gewinnt else g.note_b) >= PLATTWURF,
            "offensiv": (g.note_b if a_gewinnt else g.note_a) >= OFFENSIV_VERLOREN,
            "fest_typ": g.fest_typ,
            "datum": g.datum,
        })
    return zeilen


def logit(X: np.ndarray, y: np.ndarray, iterationen: int = 25) -> tuple[np.ndarray, np.ndarray]:
    """Logistische Regression (Newton), gibt Koeffizienten und Standardfehler."""
    b = np.zeros(X.shape[1])
    for _ in range(iterationen):
        p = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (p * (1 - p))[:, None])
        b = b + np.linalg.solve(H, X.T @ (y - p))
    p = 1 / (1 + np.exp(-X @ b))
    H = X.T @ (X * (p * (1 - p))[:, None])
    return b, np.sqrt(np.diag(np.linalg.inv(H)))


def _stufen_tabelle(titel, spalte, werte, treffer, stufen, n_name="Siege") -> list[str]:
    z = [f"| {titel} | {n_name} | {spalte} |", "|---|---:|---:|"]
    for von, bis, name in stufen:
        m = (werte >= von) & (werte < bis)
        if m.sum():
            z.append(f"| {name} | {int(m.sum())} | {treffer[m].mean():.1%} |")
    return z + [""]


def _quantil_stufen(werte, k: int, einheit: str = "Elo") -> list[tuple]:
    g = np.quantile(werte, np.linspace(0, 1, k + 1))
    g[-1] = np.inf
    return [(g[i], g[i + 1], f"{einheit} {g[i]:.0f}–{g[i + 1]:.0f}" if i < k - 1
             else f"{einheit} ab {g[i]:.0f}") for i in range(k)]


def siegart_bericht(zeilen: list[dict], namen: dict[str, str] | None = None,
                    elo_heute: dict[str, float] | None = None) -> list[str]:
    """Markdown: Plattwurf-Anteil nach Stärke und Abstand, Modell, Personen."""
    namen, elo_heute = namen or {}, elo_heute or {}
    elo_s = np.array([r["elo_s"] for r in zeilen], dtype=float)
    elo_v = np.array([r["elo_v"] for r in zeilen], dtype=float)
    platt = np.array([r["platt"] for r in zeilen], dtype=float)
    offensiv = np.array([r["offensiv"] for r in zeilen], dtype=float)
    abstand = elo_s - elo_v
    z = [f"{len(zeilen)} entschiedene Gänge (beide mit ≥ {MIN_GAENGE_ELO} erfassten Gängen, "
         f"ohne Schlussgang-Verdacht). Plattwurf-Anteil insgesamt {platt.mean():.1%}.", ""]

    z += ["## Nach Stärke des Siegers (Elo vor dem Fest, Fünftel)", ""]
    z += _stufen_tabelle("Sieger", "mit 10.00", elo_s, platt, _quantil_stufen(elo_s, 5))
    z += ["## Nach Elo-Abstand Sieger − Verlierer", ""]
    z += _stufen_tabelle("Abstand", "mit 10.00", abstand, platt, ABSTAND_STUFEN)

    # Stärke und Abstand hängen zusammen (Starke treffen meist Schwächere).
    # Kreuztabelle und Regression trennen die beiden.
    drittel = _quantil_stufen(elo_s, 3)
    abst = [(-np.inf, 0, "schwächer"), (0, 150, "0–150 stärker"), (150, np.inf, ">150 stärker")]
    z += ["## Stärke und Abstand getrennt", "",
          "| Sieger | " + " | ".join(n for *_, n in abst) + " |", "|---|" + "---:|" * len(abst)]
    for von, bis, name in drittel:
        zelle = []
        for a_von, a_bis, _ in abst:
            m = (elo_s >= von) & (elo_s < bis) & (abstand >= a_von) & (abstand < a_bis)
            zelle.append(f"{platt[m].mean():.1%} ({int(m.sum())})" if m.sum() >= 30 else "–")
        z.append(f"| {name} | " + " | ".join(zelle) + " |")
    X = np.column_stack([np.ones(len(zeilen)), (elo_s - elo_s.mean()) / 100, abstand / 100])
    b, se = logit(X, platt)
    p0 = platt.mean()
    z += ["", "Logistische Regression P(10.00) ~ Elo Sieger + Abstand, je 100 Elo:", "",
          "| | Koeffizient | SE | z | ≈ Prozentpunkte |", "|---|---:|---:|---:|---:|"]
    for name, k in (("Elo des Siegers", 1), ("Abstand zum Verlierer", 2)):
        z.append(f"| {name} | {b[k]:+.3f} | {se[k]:.3f} | {b[k] / se[k]:+.1f} | "
                 f"{b[k] * p0 * (1 - p0) * 100:+.1f} |")
    z.append("")

    # Die Verliererseite: halten Starke auch in der Niederlage besser mit?
    z += ["## Verlierer: offensive Niederlage (8.75) nach Stärke des Verlierers", ""]
    z += _stufen_tabelle("Verlierer", "mit 8.75", elo_v, offensiv, _quantil_stufen(elo_v, 5),
                         "Niederlagen")

    je_typ = defaultdict(list)
    for r in zeilen:
        je_typ[r["fest_typ"]].append(r["platt"])
    je_jahr = defaultdict(list)
    for r in zeilen:
        je_jahr[r["datum"][:4]].append(r["platt"])
    z += ["## Nach Festtyp und Jahr", "", "| | Siege | mit 10.00 |", "|---|---:|---:|"]
    for k, v in sorted(je_typ.items(), key=lambda kv: -len(kv[1])):
        z.append(f"| {k} | {len(v)} | {np.mean(v):.1%} |")
    for k, v in sorted(je_jahr.items()):
        z.append(f"| {k} | {len(v)} | {np.mean(v):.1%} |")
    z.append("")

    # Eigenschaft der Person? Erwartung je Sieg aus der Regression (Stärke und
    # Abstand herausgerechnet), dann die Abweichung in zwei Hälften der Siege.
    erwartet = 1 / (1 + np.exp(-X @ b))
    je_person = defaultdict(list)
    for i, r in enumerate(zeilen):
        je_person[r["sieger"]].append(i)
    personen = [sid for sid, idx in je_person.items() if len(idx) >= MIN_SIEGE_PERSON]
    if len(personen) >= 10:
        h1, h2, roh1, roh2 = [], [], [], []
        for sid in personen:
            idx = sorted(je_person[sid], key=lambda i: zeilen[i]["datum"])
            gerade, ungerade = idx[0::2], idx[1::2]
            roh1.append(platt[gerade].mean())
            roh2.append(platt[ungerade].mean())
            h1.append((platt[gerade] - erwartet[gerade]).mean())
            h2.append((platt[ungerade] - erwartet[ungerade]).mean())
        z += ["## Ist der Plattwurf eine Eigenschaft des Schwingers?", "",
              f"{len(personen)} Schwinger mit ≥ {MIN_SIEGE_PERSON} Siegen; Siege abwechselnd "
              "auf zwei Hälften verteilt. Korrelation der Hälften:", "",
              f"- Plattwurf-Anteil roh: r = {np.corrcoef(roh1, roh2)[0, 1]:+.2f}",
              f"- nach Herausrechnen von Stärke und Abstand: r = {np.corrcoef(h1, h2)[0, 1]:+.2f}",
              ""]
        rang = sorted(personen, key=lambda s: -elo_heute.get(s, 0))[:12]
        z += ["Die zwölf Elo-Stärksten davon:", "",
              "| Schwinger | Siege | mit 10.00 | erwartet | Differenz |", "|---|---:|---:|---:|---:|"]
        for sid in rang:
            idx = je_person[sid]
            z.append(f"| {namen.get(sid, sid)} | {len(idx)} | {platt[idx].mean():.0%} | "
                     f"{erwartet[idx].mean():.0%} | {platt[idx].mean() - erwartet[idx].mean():+.0%} |")
        z.append("")
    return z


def siegart() -> list[str]:
    from .features import baue_features
    from .harness import bewerte
    from .ratings import fahre_elo_durch
    from .train import bestimme_holdout_jahr

    schwinger, gaenge = _lade_gaenge()
    elo_modell, snapshots = fahre_elo_durch(gaenge)
    namen = {sid: s.name for sid, s in schwinger.items()}
    elo_heute = dict(elo_modell.ratings)
    z = ["# Messung: Siegart nach Stärke (gewinnen Starke eher mit 10.00?)", ""]
    z += siegart_bericht(siege_mit_elo(gaenge, snapshots), namen, elo_heute)

    # Sagt die Plattwurf-Neigung (Stand vor dem Fest) kommende Gänge voraus,
    # über das hinaus, was das Modell schon weiss? Nur dieses eine Merkmal.
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    X, y = np.asarray(X), np.asarray(y)
    N = noten_merkmale(gaenge, meta)
    test = bestimme_holdout_jahr(meta)
    jahre = (test - 1, test)
    basis = bewerte(X, y, meta, jahre)
    with _mit_zusatzmerkmalen(["plattwurf_diff"], set()):
        mit = bewerte(np.hstack([X, N[:, :1]]), y, meta, jahre)
    val, tst = jahre
    z += ["## Sagt die Plattwurf-Neigung kommende Gänge voraus?", "",
          "Merkmal `plattwurf_diff` (Anteil Plattwürfe an den Siegen, Stand vor dem Fest, "
          "A − B) zusätzlich im Modell. Log-Loss, tiefer = besser:", "",
          f"| | Val {val} | Test {tst} |", "|---|---:|---:|"]
    for name, r in (("heute", basis), ("+ plattwurf_diff", mit)):
        z.append(f"| {name} | {r[val]['log_loss']} | {r[tst]['log_loss']} |")
    return z + [""]


MESSUNGEN = {"noten": noten, "siegart": siegart}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in MESSUNGEN:
        print(f"Aufruf: python -m pipeline.messung <{'|'.join(MESSUNGEN)}>", file=sys.stderr)
        return 2
    print("\n".join(MESSUNGEN[argv[0]]()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
