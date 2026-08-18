"""Datenqualitätsbericht aus ``artifacts/report.json`` (Markdown).

Beantwortet nach jedem Lauf die Frage "kann ich diesen Zahlen trauen?", ohne
dass man JSON lesen muss. Läuft im Update-Workflow ins Job-Summary:

    python -m pipeline.datenqualitaet >> "$GITHUB_STEP_SUMMARY"

Lokal einfach ``python -m pipeline.datenqualitaet``.
"""
from __future__ import annotations

import json
import sys

from . import config

# Ab hier gilt ein Wert als auffällig (nicht automatisch als falsch).
GRENZE_VERLUSTQUOTE = 0.10
GRENZE_UNVOLLSTAENDIG = 0.10
GRENZE_TAGE_OHNE_FEST = 21


def _tausender(wert) -> str:
    """Zahl mit Schweizer Tausendertrennung; fehlende Werte als "?".

    Vorher stand hier ``f"{wert:,}"`` direkt auf dem Rohwert -- mit dem
    Default "?" (Report ohne ``datenbasis``) warf das ``ValueError`` und riss
    den kompletten Qualitätsbericht mit, statt eine Lücke auszuweisen.
    """
    if not isinstance(wert, (int, float)):
        return "?"
    return f"{wert:,}".replace(",", "'")


def _ampel(ok: bool, warn: bool = False) -> str:
    return "⚠️" if warn else ("✅" if ok else "❌")


def _zeilen(report: dict) -> list[str]:
    dq = report.get("datenqualitaet") or {}
    basis = report.get("datenbasis") or {}
    z: list[str] = ["## Datenqualität", ""]
    # Immer ausweisen, WELCHEN Lauf dieser Bericht beschreibt: bei einem
    # abgebrochenen Lauf bleibt report.json unverändert, der Bericht zeigt dann
    # den letzten erfolgreichen Stand -- das darf nicht wie "aktuell" aussehen.
    if report.get("erstellt"):
        z += [f"_Report erstellt: {report['erstellt']} (Lauf `{report.get('lauf_id', '?')}`)_", ""]

    if not dq:
        z += ["_Kein Datenqualitätsblock im Report (Lauf mit älterer Pipeline-Version)._", ""]
        return z

    zeitraum = dq.get("feste_zeitraum") or {}
    tage = dq.get("tage_seit_juengstem_fest")
    verlust = dq.get("verlustquote")
    unvollstaendig = dq.get("anteil_unvollstaendiger_gaenge")

    z += ["| Kennzahl | Wert | Status |", "|---|---:|:--:|"]
    z += [f"| Gänge (dedupliziert) | {_tausender(basis.get('n_gaenge'))} | |"]
    z += [f"| Schwinger im Kader | {_tausender(basis.get('n_schwinger'))} | |"]
    if zeitraum:
        z += [f"| Zeitraum der Feste | {zeitraum.get('von')} – {zeitraum.get('bis')} | |"]
    if tage is not None:
        z += [f"| Tage seit jüngstem Fest | {tage} | "
              f"{_ampel(tage <= GRENZE_TAGE_OHNE_FEST, warn=tage > GRENZE_TAGE_OHNE_FEST)} |"]
    if verlust is not None:
        z += [f"| Verworfene Roh-Einträge | {verlust:.1%} | "
              f"{_ampel(verlust <= GRENZE_VERLUSTQUOTE, warn=verlust > GRENZE_VERLUSTQUOTE)} |"]
    if unvollstaendig is not None:
        z += [f"| Gänge mit nur einer Perspektive | {unvollstaendig:.1%} | "
              f"{_ampel(unvollstaendig <= GRENZE_UNVOLLSTAENDIG, warn=unvollstaendig > GRENZE_UNVOLLSTAENDIG)} |"]
    z += [""]

    # Kranz-Erkennung. Die Quote je Kranzfest ist der einzige Selbsttest dafür,
    # ob der PDF-Parser die Kranz-Sterne überhaupt findet.
    kp = dq.get("kranz_plausibilitaet") or {}
    if kp.get("n_kranzfeste"):
        lo, hi = kp.get("erwartungsband", [0.08, 0.25])
        ok = bool(kp.get("plausibel"))
        z += ["**Kranz-Erkennung**", ""]
        z += [f"- {_ampel(ok, warn=not ok)} Kranzquote je Kranzfest (Median): "
              f"{kp.get('kranzquote_median', 0):.1%} — erwartet {lo:.0%}–{hi:.0%}"]
        z += [f"- {kp.get('kraenze_gesamt', 0)} Kränze über {kp['n_kranzfeste']} Kranzfeste"]
        if kp.get("kranzfeste_ohne_kranz"):
            z += [f"- {_ampel(False, warn=True)} {kp['kranzfeste_ohne_kranz']} Kranzfeste "
                  "ohne einen einzigen erkannten Kranz"]
        if not ok:
            z += ["- Liegt die Quote deutlich unter dem Band, findet der PDF-Parser die "
                  "Kranz-Sterne nicht (`schlussgang_pdf._kranz_abtrennen`)."]
        z.append("")

    # Kommende Feste (FR-2). Mitten in der Saison ist eine leere Vorschau ein
    # Fehler der Beschaffung, kein Normalzustand -- darum mit Ampel und Grund.
    kf = dq.get("kommende_feste")
    if kf is not None:
        n = kf.get("n", 0)
        z += ["**Kommende Feste (Vorschau)**", ""]
        z += [f"- {_ampel(n > 0, warn=n == 0)} {n} Fest(e) geladen"
              + (f", Quelle `{kf.get('quelle')}`" if kf.get("quelle") else "")
              + (f", nächstes am {kf['naechstes']}" if kf.get("naechstes") else "")]
        z += [f"- davon mit veröffentlichten Paarungen: {kf.get('n_mit_paarungen', 0)}"]
        for v in kf.get("versuche") or []:
            if v.get("fehler"):
                z.append(f"- Pfad `{v.get('pfad')}` fehlgeschlagen: {v['fehler']}")
        z.append("")

    if dq.get("roh_eintraege_verworfen"):
        z += ["**Verworfene Roh-Einträge nach Grund**", ""]
        for grund, n in sorted(dq["roh_eintraege_verworfen"].items(), key=lambda x: -x[1]):
            z.append(f"- `{grund}`: {n}")
        z.append("")
    if dq.get("beispiele_unaufloesbare_namen"):
        z += ["**Nicht auflösbare Namen (Beispiele)**", "",
              ", ".join(f"`{n}`" for n in dq["beispiele_unaufloesbare_namen"]), ""]
    if dq.get("ergebnisverteilung"):
        anteile = ", ".join(f"{k} {v:.1%}" for k, v in dq["ergebnisverteilung"].items())
        z += [f"**Ergebnisverteilung**: {anteile}", ""]

    modell = report.get("modell") or {}
    baseline = report.get("baseline_elo") or {}
    if modell and baseline:
        z += ["**Modell vs. Elo-Baseline**", "",
              f"- Log-Loss {modell.get('log_loss')} vs. {baseline.get('log_loss')} "
              f"({_ampel(bool(report.get('schlaegt_baseline')))})",
              f"- Accuracy {modell.get('accuracy')} vs. {baseline.get('accuracy')}", ""]
    return z


def main() -> int:
    pfad = config.ARTIFACTS_DIR / "report.json"
    if not pfad.exists():
        print(f"Kein Report unter {pfad} — zuerst die Pipeline ausführen.")
        return 1
    print("\n".join(_zeilen(json.loads(pfad.read_text(encoding="utf-8")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
