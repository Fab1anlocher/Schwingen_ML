"""Messungen, die die Rohdaten brauchen (Roadmap D3/D1).

Die Rohdaten (``artifacts/raw``) liegen nur im Actions-Cache. Was dort steht,
aber nicht in den committeten Artefakten -- etwa die Note je Gang --, lässt
sich nur auf dem Runner messen: Workflow "Messung auf Rohdaten"
(``.github/workflows/messung.yml``) führt ``python -m pipeline.messung <name>``
aus und schreibt die Ausgabe (Markdown) ins Job-Summary.

Messungen:
  noten   Verteilung der Noten je Ausgang (Plausibilität gegen die
          Notengebung) und ob Noten-Merkmale das Modell verbessern (D1).
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


MESSUNGEN = {"noten": noten}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in MESSUNGEN:
        print(f"Aufruf: python -m pipeline.messung <{'|'.join(MESSUNGEN)}>", file=sys.stderr)
        return 2
    print("\n".join(MESSUNGEN[argv[0]]()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
