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
  festtag   Was bringen die Ergebnisse früherer Gänge desselben Fests
            (Live-Prognose)? Prüft zuerst, ob die PDF die Gangreihenfolge hat.
  historie  Gibt es Feste mit Statistik-PDF vor 2023 (längere Vorgeschichte)?
  rating_noten  Soll ein Plattwurf das Rating stärker bewegen (Siegqualität)?
  paarung   Warum 2023 so viele Gänge je Schwinger und Fest hat (D4): Cache je
            Jahr, dazu eine Stichprobe frisch geladen und neu geparst.
  vettern   Schwinger, die an einem Tag an zwei Festen oder mit > 8 Gängen an
            einem Fest stehen (ungetrennte Namensvettern), mit ihren
            Rangliste-Auftritten (Klub, Wohnort, Jahrgang).
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
            "event_id": g.event_id,
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
    # Gegenprobe: Benoten die Kampfrichter je Fest (und damit je Region, in der
    # ein Schwinger meist antritt) verschieden grosszügig, sähe das wie eine
    # Eigenschaft der Person aus. Darum zusätzlich die Plattwurf-Quote des
    # Fests OHNE die Siege dieses Schwingers als Merkmal.
    fest = [r.get("event_id", "") for r in zeilen]
    mit_fest = len(set(fest)) >= 20
    if mit_fest:
        f_summe, f_n = defaultdict(float), defaultdict(int)
        fs_summe, fs_n = defaultdict(float), defaultdict(int)
        for i, r in enumerate(zeilen):
            f_summe[fest[i]] += platt[i]
            f_n[fest[i]] += 1
            fs_summe[(fest[i], r["sieger"])] += platt[i]
            fs_n[(fest[i], r["sieger"])] += 1
        quote = np.array([
            (f_summe[f] - fs_summe[(f, r["sieger"])]) / (f_n[f] - fs_n[(f, r["sieger"])])
            if f_n[f] - fs_n[(f, r["sieger"])] >= 20 else p0
            for f, r in zip(fest, zeilen)])
        quote = np.clip(quote, 0.02, 0.98)
        Xf = np.column_stack([X, np.log(quote / (1 - quote))])
        bf, sef = logit(Xf, platt)
        erwartet_fest = 1 / (1 + np.exp(-Xf @ bf))
        grosse = [f_summe[f] / f_n[f] for f in f_n if f_n[f] >= 100]
        z += ["## Benoten die Feste verschieden?", "",
              f"Plattwurf-Quote je Fest (Feste mit ≥ 100 Siegen, n = {len(grosse)}): "
              f"Median {np.median(grosse):.1%}, 10.–90. Perzentil "
              f"{np.quantile(grosse, 0.1):.1%}–{np.quantile(grosse, 0.9):.1%}. "
              f"Koeffizient der Fest-Quote (logit) in der Regression: {bf[3]:+.2f} "
              f"(SE {sef[3]:.2f}); Elo des Siegers dann {bf[1]:+.3f}, Abstand {bf[2]:+.3f}.",
              ""]
    je_person = defaultdict(list)
    for i, r in enumerate(zeilen):
        je_person[r["sieger"]].append(i)
    personen = [sid for sid, idx in je_person.items() if len(idx) >= MIN_SIEGE_PERSON]
    if len(personen) >= 10:
        h1, h2, roh1, roh2, f1, f2 = [], [], [], [], [], []
        for sid in personen:
            idx = sorted(je_person[sid], key=lambda i: zeilen[i]["datum"])
            gerade, ungerade = idx[0::2], idx[1::2]
            roh1.append(platt[gerade].mean())
            roh2.append(platt[ungerade].mean())
            h1.append((platt[gerade] - erwartet[gerade]).mean())
            h2.append((platt[ungerade] - erwartet[ungerade]).mean())
            if mit_fest:
                f1.append((platt[gerade] - erwartet_fest[gerade]).mean())
                f2.append((platt[ungerade] - erwartet_fest[ungerade]).mean())
        z += ["## Ist der Plattwurf eine Eigenschaft des Schwingers?", "",
              f"{len(personen)} Schwinger mit ≥ {MIN_SIEGE_PERSON} Siegen; Siege abwechselnd "
              "auf zwei Hälften verteilt. Korrelation der Hälften:", "",
              f"- Plattwurf-Anteil roh: r = {np.corrcoef(roh1, roh2)[0, 1]:+.2f}",
              f"- nach Herausrechnen von Stärke und Abstand: r = {np.corrcoef(h1, h2)[0, 1]:+.2f}"]
        if mit_fest:
            z.append(f"- zusätzlich ohne die Benotung des Fests: r = {np.corrcoef(f1, f2)[0, 1]:+.2f}")
            erwartet = erwartet_fest
        z.append("")
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


# --- Festtag: was bringen die Ergebnisse der früheren Gänge desselben Fests? --
#
# Die Statistik-PDF listet je Schwinger seine Gänge untereinander. Ist das die
# Gangreihenfolge, steht ein Gang bei beiden Schwingern an derselben Stelle --
# das wird zuerst geprüft. Dann: Punkte und Siege vor diesem Gang (live
# bekannt, sobald die früheren Gänge geschwungen sind) als Merkmale.

FESTTAG_MERKMALE = ["festtag_punkte_diff", "festtag_siege_diff", "gang_nr"]
FESTTAG_SYMMETRISCH = {"gang_nr"}


def _lade_roh():
    from .labels import dedupliziere
    from .scrape import lade_echte_daten

    schwinger, events, roh, _ = lade_echte_daten(mit_bericht=True)
    gaenge, _ = dedupliziere(roh)
    return schwinger, roh, gaenge


def gang_positionen(roh) -> dict[tuple, int]:
    """(event, schwinger, gegner) -> Position in der Liste des Schwingers (ab 1)."""
    zaehler: dict[tuple, int] = defaultdict(int)
    pos = {}
    for r in roh:
        zaehler[(r.event_id, r.schwinger_id)] += 1
        pos[(r.event_id, r.schwinger_id, r.gegner_id)] = zaehler[(r.event_id, r.schwinger_id)]
    return pos


def festtag_merkmale(gaenge, roh, meta) -> tuple[np.ndarray, dict]:
    """Merkmale aus den früheren Gängen desselben Fests, je Zeile von meta."""
    pos = gang_positionen(roh)
    note = {(r.event_id, r.schwinger_id, r.gegner_id): (r.note, r.symbol) for r in roh}
    nr: dict[tuple, int] = {}
    gleich = 0
    for g in gaenge:
        pa = pos.get((g.event_id, g.schwinger_a_id, g.schwinger_b_id))
        pb = pos.get((g.event_id, g.schwinger_b_id, g.schwinger_a_id))
        if pa is not None and pa == pb:
            gleich += 1
            nr[(g.event_id, g.schwinger_a_id, g.schwinger_b_id)] = pa
    # Punkte und Siege je Schwinger VOR Gang k desselben Fests.
    stand: dict[tuple, list] = defaultdict(list)          # (event, sid) -> [(k, note, symbol)]
    for (eid, a, b), k in nr.items():
        for sid, gid in ((a, b), (b, a)):
            n, sym = note.get((eid, sid, gid), (None, None))
            stand[(eid, sid)].append((k, n or 0.0, sym))

    def vorher(eid, sid, k):
        frueher = [x for x in stand.get((eid, sid), []) if x[0] < k]
        return sum(x[1] for x in frueher), sum(1 for x in frueher if x[2] == "+")

    out = np.zeros((len(meta), len(FESTTAG_MERKMALE)))
    for i, m in enumerate(meta):
        a, b = m["schwinger_a_id"], m["schwinger_b_id"]
        schl = (m["event_id"], a, b) if (m["event_id"], a, b) in nr else (m["event_id"], b, a)
        k = nr.get(schl)
        if k is None:
            continue
        pa, sa = vorher(m["event_id"], a, k)
        pb, sb = vorher(m["event_id"], b, k)
        out[i] = (pa - pb, sa - sb, k)          # meta-Zeile sieht a gegen b (Spiegelzeilen schon vertauscht)
    return out, {"n_gaenge": len(gaenge), "anteil_gleiche_position": round(gleich / max(1, len(gaenge)), 4),
                 "verteilung_gang_nr": dict(sorted(Counter(nr.values()).items()))}


def festtag() -> list[str]:
    from .features import baue_features
    from .harness import bewerte
    from .ratings import fahre_elo_durch
    from .train import bestimme_holdout_jahr

    schwinger, roh, gaenge = _lade_roh()
    _, snapshots = fahre_elo_durch(gaenge)
    X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
    X, y = np.asarray(X), np.asarray(y)
    # Spiegelzeilen: meta trägt dort weiter a/b des Originals -- für die
    # Merkmale brauchen wir die Sicht der Zeile.
    meta_sicht = [{**m, "schwinger_a_id": m["schwinger_b_id"], "schwinger_b_id": m["schwinger_a_id"]}
                  if m.get("augmented") else m for m in meta]
    F, info = festtag_merkmale(gaenge, roh, meta_sicht)
    z = ["# Messung: Ergebnisse vom gleichen Festtag", "",
         f"{info['n_gaenge']} Gänge; bei {info['anteil_gleiche_position']:.1%} steht der Gang bei beiden "
         "Schwingern an derselben Position der Liste (= Gangreihenfolge belegt, wenn nahe 100 %).", "",
         f"Gänge je Position: {info['verteilung_gang_nr']}", ""]
    test = bestimme_holdout_jahr(meta)
    jahre = (test - 1, test)
    basis = bewerte(X, y, meta, jahre)
    zeilen = [("heute", basis)]
    with _mit_zusatzmerkmalen(["gang_nr"], FESTTAG_SYMMETRISCH):
        zeilen.append(("+ Gangnummer", bewerte(np.hstack([X, F[:, 2:]]), y, meta, jahre)))
    with _mit_zusatzmerkmalen(FESTTAG_MERKMALE, FESTTAG_SYMMETRISCH):
        zeilen.append(("+ Punkte/Siege vorher + Gangnummer", bewerte(np.hstack([X, F]), y, meta, jahre)))
    val, tst = jahre
    z += [f"| | LL Val {val} | Treffer Val | LL Test {tst} | Treffer Test |", "|---|---:|---:|---:|---:|"]
    for name, r in zeilen:
        z.append(f"| {name} | {r[val]['log_loss']} | {r[val]['accuracy']:.1%} | "
                 f"{r[tst]['log_loss']} | {r[tst]['accuracy']:.1%} |")
    return z + ["", "Achtung: Punkte/Siege vorher sind erst WÄHREND des Fests bekannt -- eine "
                "Live-Prognose, keine Prognose vor dem Fest.", ""]


# --- Historie: gibt es Statistik-PDFs vor dem heutigen Datenbeginn? ----------

def historie() -> list[str]:
    from .scrape.schlussgang_resultate import lade_gaenge_fuer_event, scrape_events

    events = scrape_events(None, seit_datum="2015-01-01")
    alt = [e for e in events if e["datum"] < "2023-01-01"]
    je_jahr = defaultdict(list)
    for e in alt:
        je_jahr[e["datum"][:4]].append(e)
    z = ["# Messung: Historie vor 2023", "",
         f"Feste ab 2015 laut API: {len(events)}, davon vor 2023: {len(alt)}.", "",
         "| Jahr | Feste | Stichprobe Statistik-PDF | Gänge je PDF |", "|---|---:|---:|---:|"]
    for jahr in sorted(je_jahr):
        stich = je_jahr[jahr][:: max(1, len(je_jahr[jahr]) // 4)][:4]
        ok, gaenge = 0, []
        for e in stich:
            try:
                n = len(lade_gaenge_fuer_event(e))
                ok += n > 0
                gaenge.append(n)
            except Exception:  # noqa: BLE001 - fehlende PDF zählt als "nicht vorhanden"
                pass
        z.append(f"| {jahr} | {len(je_jahr[jahr])} | {ok}/{len(stich)} | "
                 f"{round(sum(gaenge) / len(gaenge)) if gaenge else '-'} |")
    return z + [""]


# --- Noten im Rating: zählt ein Plattwurf mehr? (Roadmap D1) -----------------

def rating_noten() -> list[str]:
    """Rating mit Siegqualität: ein Sieg mit 10.00 bewegt beide Ratings um
    ELO_PLATTWURF_FAKTOR stärker. Gemessen auf dem aktuellen Rating."""
    from . import ratings
    from .features import baue_features
    from .harness import bewerte
    from .train import bestimme_holdout_jahr

    schwinger, gaenge = _lade_gaenge()
    original = ratings.EloModell
    zeilen = []
    try:
        for faktor in (1.0, 1.25, 1.5):
            ratings.EloModell = lambda f=faktor: original(plattwurf_faktor=f)
            _, snapshots = ratings.fahre_elo_durch(gaenge)
            X, y, meta = baue_features(gaenge, snapshots, schwinger, augment=True)
            test = bestimme_holdout_jahr(meta)
            jahre = (test - 1, test)
            zeilen.append((faktor, bewerte(np.asarray(X), np.asarray(y), meta, jahre)))
    finally:
        ratings.EloModell = original
    val, tst = jahre
    z = ["# Messung: Noten im Rating (Plattwurf zählt mehr)", "",
         f"| Plattwurf-Faktor | LL Val {val} | Treffer Val | LL Test {tst} | Treffer Test |",
         "|---|---:|---:|---:|---:|"]
    for faktor, r in zeilen:
        z.append(f"| {faktor} | {r[val]['log_loss']} | {r[val]['accuracy']:.1%} | "
                 f"{r[tst]['log_loss']} | {r[tst]['accuracy']:.1%} |")
    return z + [""]


# --- Paarung: warum 2023 so viele Gänge je Schwinger und Fest? (Roadmap D4) --

# Mehr Gänge kann ein Schwinger an einem Fest nicht haben (6, mit Ausstich 8).
MAX_GAENGE_FEST = 8


def paarung_kennzahlen(roh) -> dict[str, Counter]:
    """Je Jahr: Auftritte, davon mit > 8 Gängen, Paare, davon einseitig, Gestellte.

    "Einseitig" heisst: der Gang steht nur in der Liste EINES der beiden
    Schwinger. Im PDF steht jeder Gang zweimal; fehlt eine Seite, hängt
    der Eintrag womöglich am falschen Schwinger.
    """
    auftritt = Counter((r.event_id, r.schwinger_id) for r in roh)
    jahr = {r.event_id: r.datum[:4] for r in roh}
    paare: dict = defaultdict(dict)
    for r in roh:
        paare[(r.event_id, tuple(sorted((r.schwinger_id, r.gegner_id))))][r.schwinger_id] = r.symbol
    aus: dict[str, Counter] = defaultdict(Counter)
    for (eid, _), n in auftritt.items():
        aus[jahr[eid]]["auftritte"] += 1
        aus[jahr[eid]]["ueber8"] += n > MAX_GAENGE_FEST
    for (eid, _), seiten in paare.items():
        einseitig = len(seiten) == 1
        gestellt = any(s == "-" for s in seiten.values())
        c = aus[jahr[eid]]
        c["paare"] += 1
        c["einseitig"] += einseitig
        c["gestellt_einseitig" if einseitig else "gestellt_zweiseitig"] += gestellt
    return aus


def _block_kennzahlen(bloecke: list[dict]) -> dict:
    """Blöcke eines PDFs: Anzahl, > 8 Gänge, Notensumme == Total."""
    mit_total = [b for b in bloecke if b["total"] is not None
                 and all(g["note"] is not None for g in b["gaenge"])]
    passt = sum(abs(sum(g["note"] for g in b["gaenge"]) - b["total"]) < 0.01 for b in mit_total)
    return {"bloecke": len(bloecke),
            "ueber8": sum(len(b["gaenge"]) > MAX_GAENGE_FEST for b in bloecke),
            "eintraege": sum(len(b["gaenge"]) for b in bloecke),
            "total_passt": f"{passt}/{len(mit_total)}"}


def _spalten_zeilen(seiten) -> list[list[str]]:
    from .scrape.schlussgang_pdf import _gruppiere_zeilen, _spalte

    spalten: list[list[list[str]]] = [[], [], []]
    for woerter in seiten:
        eimer: list[list[dict]] = [[], [], []]
        for w in woerter:
            i = _spalte(w["x0"])
            if i is not None:
                eimer[i].append(w)
        for i in range(3):
            spalten[i].extend(_gruppiere_zeilen(eimer[i]))
    return spalten


def paarung() -> list[str]:
    import json

    from .scrape import RAW_DIR, lade_echte_daten
    from .scrape.http import hole
    from .scrape.schlussgang_pdf import extrahiere_woerter, pdf_url, tabellen_bloecke

    _, _, roh, _ = lade_echte_daten(mit_bericht=True)
    z = ["# Messung: Paarung der Gänge je Jahr (Roadmap D4)", "",
         "## Cache (so, wie die Feste damals geparst wurden)", "",
         "| Jahr | Auftritte | > 8 Gänge | Paare | einseitig | gestellt (einseitig) | gestellt (beidseitig) |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for j, c in sorted(paarung_kennzahlen(roh).items()):
        n1, n2 = c["einseitig"], c["paare"] - c["einseitig"]
        z.append(f"| {j} | {c['auftritte']} | {c['ueber8']} ({c['ueber8'] / c['auftritte']:.1%}) | "
                 f"{c['paare']} | {n1} ({n1 / c['paare']:.1%}) | "
                 f"{c['gestellt_einseitig'] / max(n1, 1):.1%} | {c['gestellt_zweiseitig'] / max(n2, 1):.1%} |")

    # Stichprobe: frisch laden und mit dem heutigen Parser lesen.
    events = json.loads((RAW_DIR / "events.json").read_text(encoding="utf-8"))["events"]
    roh_cache = json.loads((RAW_DIR / "gaenge.json").read_text(encoding="utf-8"))["gaenge"]
    cache_je_fest: dict[str, list[dict]] = defaultdict(list)
    for g in roh_cache:
        cache_je_fest[str(g["event_id"])].append(g)

    def ueber8(eintraege):
        return sum(n > MAX_GAENGE_FEST for n in Counter(g["schwinger_name"] for g in eintraege).values())

    jahr_feste = defaultdict(list)
    for e in events:
        if cache_je_fest.get(str(e["id"])):
            jahr_feste[e["datum"][:4]].append(e)
    stichprobe = sorted(jahr_feste["2023"], key=lambda e: -ueber8(cache_je_fest[str(e["id"])]))[:6]
    stichprobe += jahr_feste["2023"][::max(1, len(jahr_feste["2023"]) // 4)][:4]
    stichprobe += jahr_feste["2024"][::max(1, len(jahr_feste["2024"]) // 2)][:2]
    z += ["", "## Stichprobe: Cache gegen frisch geladen (heutiger Parser)", "",
          "| Fest | Datum | Einträge Cache | > 8 Cache | Einträge neu | > 8 neu | Blöcke neu | Total passt neu |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    beispiel = None
    for e in stichprobe:
        cache = cache_je_fest[str(e["id"])]
        try:
            seiten = extrahiere_woerter(hole(pdf_url(e["nid"]), binaer=True))
        except Exception as err:  # noqa: BLE001
            z.append(f"| {e['name']} | {e['datum']} | {len(cache)} | {ueber8(cache)} | Fehler: {err} | | | |")
            continue
        k = _block_kennzahlen(tabellen_bloecke(seiten))
        z.append(f"| {e['name']} | {e['datum']} | {len(cache)} | {ueber8(cache)} | "
                 f"{k['eintraege']} | {k['ueber8']} | {k['bloecke']} | {k['total_passt']} |")
        if beispiel is None and ueber8(cache):
            beispiel = (e, cache, seiten)

    if beispiel:
        e, cache, seiten = beispiel
        n = Counter(g["schwinger_name"] for g in cache)
        name = next(s for s, k in n.most_common() if k > MAX_GAENGE_FEST)
        z += ["", f"## Beispiel: {name} am {e['name']} ({n[name]} Gänge im Cache)", "",
              "Im Cache:", "", "```"]
        z += [f"{g['symbol']} {g['gegner_name']} {g['note']}" for g in cache if g["schwinger_name"] == name]
        z += ["```", "", "PDF-Zeilen rund um den Namen (Spalte, Zeile: Tokens):", "", "```"]
        teil = name.split()[0]
        for si, zeilen in enumerate(_spalten_zeilen(seiten)):
            for zi, tokens in enumerate(zeilen):
                if teil in tokens and _ist_kopf(tokens, name):
                    for zz in range(max(0, zi - 2), min(len(zeilen), zi + 18)):
                        z.append(f"{si},{zz}: {' | '.join(zeilen[zz])}")
                    z.append("...")
        z += ["```"]
    return z + [""]


def _ist_kopf(tokens: list[str], name: str) -> bool:
    return all(t in tokens for t in name.split())


# --- Namensvettern, die die Trennung nicht erwischt (Aufgabe "vettern") -------

def vettern_verdacht(roh) -> dict[str, Counter]:
    """ID -> {"doppeltage": Tage mit zwei Festen, "ueber8": Feste mit > 8 Gängen}."""
    n = Counter((r.event_id, r.schwinger_id) for r in roh)
    feste_je_tag: dict[tuple, set] = defaultdict(set)
    for r in roh:
        feste_je_tag[(r.schwinger_id, r.datum)].add(r.event_id)
    aus: dict[str, Counter] = defaultdict(Counter)
    for (_, sid), k in n.items():
        if k > MAX_GAENGE_FEST:
            aus[sid]["ueber8"] += 1
    for (sid, _), feste in feste_je_tag.items():
        if len(feste) > 1:
            aus[sid]["doppeltage"] += 1
    return aus


def vettern() -> list[str]:
    import json

    from .identity import namens_tokens
    from .namensvettern import _basisname
    from .scrape import RAW_DIR, lade_echte_daten

    schwinger, events, roh, bericht = lade_echte_daten(mit_bericht=True)
    fest = {e.id: e for e in events}
    verdacht = vettern_verdacht(roh)
    ranglisten = json.loads((RAW_DIR / "ranglisten.json").read_text(encoding="utf-8")).get("ranglisten", {})
    je_name: dict[tuple, list] = defaultdict(list)
    for eid, eintrag in ranglisten.items():
        if not isinstance(eintrag, dict) or eid not in fest:
            continue
        for e in eintrag.get("eintraege", []):
            basis, jahr = _basisname(str(e.get("name", "")))
            je_name[namens_tokens(basis)].append((fest[eid].datum, fest[eid].name, jahr, e))
    nv = dict(bericht.namensvettern)
    herk = dict(nv.pop("herkunft", {}) or {})
    alle = herk.pop("alle", [])
    herk.pop("beispiele", None)
    z = ["# Messung: Namensvettern, die die Trennung nicht erwischt", "",
         f"Stufe 1 (Teilverband): {json.dumps({k: v for k, v in nv.items() if k != 'beispiele'}, ensure_ascii=False)}", "",
         f"Stufe 2 (Herkunft): {json.dumps(herk, ensure_ascii=False)}", ""]
    z += [f"- {b}" for b in alle] + [""]

    def tabelle(name: str, n: int = 30) -> list[str]:
        zeilen = ["| Datum | Fest | Jahrgang | Wohnort | Klub | Rang | Punkte |", "|---|---|---|---|---|---|---:|"]
        for datum, fname, jahr, e in sorted(je_name.get(namens_tokens(name), []), key=lambda t: t[0])[-n:]:
            zeilen.append(f"| {datum} | {fname[:40]} | {jahr or ''} | {e.get('wohnort') or ''} | "
                          f"{e.get('schwingklub') or ''} | {e.get('rang')} | {e.get('punkte')} |")
        return zeilen + [""]

    # Stufe-2-Trennungen zum Nachprüfen (die ersten acht).
    for b in alle[:8]:
        name = b.split(":")[0]
        z += [f"## Getrennt: {b}", ""] + tabelle(name, 24)
    z += [f"Verdächtige IDs (Tage mit zwei Festen oder > {MAX_GAENGE_FEST} Gänge an einem Fest): {len(verdacht)}", ""]
    for sid, c in sorted(verdacht.items(), key=lambda kv: -(kv[1]["doppeltage"] * 3 + kv[1]["ueber8"]))[:12]:
        s = schwinger.get(sid)
        name = s.name if s else sid
        z += [f"## {name} (`{sid}`): {c['doppeltage']} Doppeltage, {c['ueber8']} Feste mit > 8 Gängen", ""]
        z += tabelle(name)
    return z


MESSUNGEN = {"noten": noten, "siegart": siegart, "festtag": festtag, "historie": historie,
             "rating_noten": rating_noten, "paarung": paarung, "vettern": vettern}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in MESSUNGEN:
        print(f"Aufruf: python -m pipeline.messung <{'|'.join(MESSUNGEN)}>", file=sys.stderr)
        return 2
    print("\n".join(MESSUNGEN[argv[0]]()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
