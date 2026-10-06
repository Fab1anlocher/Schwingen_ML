"""Datenqualitätsbericht aus ``artifacts/report.json`` (Markdown).

Beantwortet nach jedem Lauf die Frage "kann ich diesen Zahlen trauen?", ohne
dass man JSON lesen muss. Läuft im Update-Workflow ins Job-Summary:

    python -m pipeline.datenqualitaet >> "$GITHUB_STEP_SUMMARY"

Lokal einfach ``python -m pipeline.datenqualitaet``.
"""
from __future__ import annotations

import json

from . import config

# Ab hier gilt ein Wert als auffällig (nicht automatisch als falsch).
GRENZE_VERLUSTQUOTE = 0.10
GRENZE_UNVOLLSTAENDIG = 0.10
GRENZE_TAGE_OHNE_FEST = 21
# Anteil der PDF-Blöcke, deren Notensumme nicht zum Punktetotal passt. Normal
# 0 %; vor dem Fix von D4 (Niederlage als "0") waren es 2023 fast alle.
GRENZE_PUNKTETOTAL = 0.02
# Anteil Schwinger-Fest-Paare, deren Gänge nicht zur Resultatfolge der
# Rangliste passen (ranglisten.resultat_abgleich).
GRENZE_RESULTAT = 0.03


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
    pt = dq.get("punktetotal") or {}
    if pt.get("anteil_abweichend") is not None:
        a = pt["anteil_abweichend"]
        z += [f"| Notensumme ≠ Punktetotal (Blöcke) | {a:.1%} von {_tausender(pt['bloecke_geprueft'])} | "
              f"{_ampel(a <= GRENZE_PUNKTETOTAL, warn=a > GRENZE_PUNKTETOTAL)} |"]
    z += [""]
    auffaellig = {j: c for j, c in (pt.get("je_jahr") or {}).items()
                  if c.get("geprueft") and c["abweichend"] / c["geprueft"] > GRENZE_PUNKTETOTAL}
    if auffaellig:
        z += ["Notensumme passt nicht zum Punktetotal (Parser liest das PDF-Format falsch?): "
              + ", ".join(f"{j}: {c['abweichend']} von {c['geprueft']}" for j, c in auffaellig.items()), ""]
    if pt.get("eintraege_ohne_total"):
        z += [f"_{_tausender(pt['eintraege_ohne_total'])} Roh-Einträge aus älteren Cache-Ständen ohne "
              "Punktetotal (ungeprüft; ein voller Refetch füllt es nach)._", ""]

    # Abzeichen-Erkennung. Soll-Ist-Vergleich gegen den Kranzstatus aus dem
    # Porträt: das Abzeichen hängt am Schwinger, an jedem Fest müssen also
    # genau die markiert sein, die laut Porträt einen Kranzstatus tragen.
    ap = dq.get("abzeichen_plausibilitaet") or {}
    if ap.get("n_feste_mit_kranzern"):
        ok = bool(ap.get("plausibel"))
        z += ["**Statusabzeichen-Erkennung**", ""]
        z += [f"- {_ampel(ok, warn=not ok)} Trefferquote je Fest (Median): "
              f"{ap.get('trefferquote_median', 0):.0%} der laut Porträt erwarteten "
              "Abzeichen gefunden"]
        z += ["  (100 % sind nicht zu erwarten: der Kranzstatus im Porträt ist der "
              "heutige Stand, das Abzeichen in der PDF der Stand am Fest)"]
        z += [f"- {ap.get('abzeichen_gesamt', 0)} Abzeichen über "
              f"{ap['n_feste_mit_kranzern']} Feste mit Kranzern im Feld"]
        ohne = ap.get("feste_ohne_abzeichen", 0)
        if ohne:
            anteil = ap.get("anteil_feste_ohne_abzeichen", 0)
            refetch = bool(ap.get("hinweis_refetch"))
            z += [f"- {_ampel(not refetch, warn=refetch)} {ohne} Feste ohne ein einziges "
                  f"erkanntes Abzeichen ({anteil:.1%})"]
            if refetch:
                z += ["- Ein solcher Anteil ist die Signatur von Altbestand in "
                      "`artifacts/raw`, der vor dem Parser-Fix eingelesen wurde. "
                      "Behebt sich nur durch einen vollen Refetch "
                      "(`fetch_raw --seit-datum 2023-01-01`)."]
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
        z += [f"**Ergebnisverteilung**: {anteile}",
              "  (sieg_a vs. sieg_b ist kein Signal: A/B wird alphabetisch per ID "
              "vergeben, und Stub-IDs sortieren häufiger nach vorne)", ""]

    modell = report.get("modell") or {}
    baseline = report.get("baseline_elo") or {}
    if modell and baseline:
        z += ["**Modell vs. Elo-Baseline** (identische Holdout-Gänge)", "",
              f"- Log-Loss {modell.get('log_loss')} vs. {baseline.get('log_loss')} "
              f"({_ampel(bool(report.get('schlaegt_baseline')))})",
              f"- Accuracy {modell.get('accuracy')} vs. {baseline.get('accuracy')}", ""]

    # Nur Porträt-gegen-Porträt: die ehrliche Messung der wrestlerischen
    # Merkmale, weil nur dort Physis/Verband/Schwünge beidseitig vorliegen.
    np_ = report.get("nur_portraet") or {}
    m, b = np_.get("modell") or {}, np_.get("baseline_elo") or {}
    if m.get("n"):
        z += [f"**Nur Porträt-gegen-Porträt** ({m['n']} Gänge, "
              f"{m.get('anteil_am_test', 0):.0%} des Tests)", "",
              f"- Accuracy {m.get('accuracy')} vs. Baseline {b.get('accuracy', '?')}",
              f"- Log-Loss {m.get('log_loss')} vs. Baseline {b.get('log_loss', '?')}", ""]

    # P6: Datenabdeckung und Verbandsschätzung (mit Selbstprüfung je Lauf).
    ab = (report.get("datenqualitaet") or {}).get("datenabdeckung") or {}
    vs = ab.get("teilverband_schaetzung") or {}
    if ab.get("n_schwinger"):
        z += [f"**Datenabdeckung**: {ab['n_portraet']} von {ab['n_schwinger']} Schwingern mit "
              f"Porträt ({ab['anteil_portraet']:.0%})", ""]
        if vs:
            quote = vs.get("trefferquote")
            z += [f"- Teilverband geschätzt: {vs.get('n_geschaetzt', 0)} von {vs.get('n_ohne_verband')} "
                  f"ohne Porträt ({_ampel(bool(vs.get('angewandt')))})",
                  f"- Selbstprüfung an {vs.get('pruef_faelle')} Porträts: "
                  f"{quote:.1%} richtig" if quote is not None else "- Selbstprüfung: keine Prüffälle", ""]

    # Offizielle Schlussranglisten (Kränze, Klub, Verband über den Klub).
    rl = (report.get("datenqualitaet") or {}).get("ranglisten") or {}
    if rl.get("n_feste"):
        vk = rl.get("verband_ueber_klub") or {}
        ko = rl.get("konsistenz") or {}
        ohne = rl.get("kranzfeste_ohne_kranz", 0)
        z += [f"**Schlussranglisten**: {rl['n_feste']} Feste, {rl.get('n_nicht_lesbar', 0)} nicht lesbar, "
              f"{rl.get('anteil_namen_aufgeloest', 0):.1%} der Namen zugeordnet", "",
              f"- Kranzquote (Median je Festtyp): {rl.get('kranzquote_median')}",
              f"- Kranzfeste ohne einen einzigen Kranz: {ohne} ({_ampel(ohne == 0, warn=0 < ohne <= 3)})",
              f"- Kranzquote ausserhalb 12-21 % (üblich 15-18 %): {rl.get('kranzquote_ausserhalb', 0)} "
              f"({_ampel(rl.get('kranzquote_ausserhalb', 0) == 0, warn=0 < rl.get('kranzquote_ausserhalb', 0) <= 3)})"
              + (f" -- {'; '.join(rl['beispiele_kranzquote_ausserhalb'])}"
                 if rl.get("beispiele_kranzquote_ausserhalb") else ""),
              f"- Klub bekannt bei {rl.get('klub_abdeckung_aktive', 0):.0%} der Aktiven; "
              f"Verband über Klub für {vk.get('n_zugeordnet', 0)} ohne Porträt "
              f"(Prüfung {vk.get('trefferquote')})",
              f"- Klub wie im Porträt: {ko.get('klub_wie_porträt')}; "
              f"Kranzgewinner ohne Porträt: {ko.get('kranzgewinner_ohne_porträt')}", ""]
        ra = rl.get("resultat_abgleich") or {}
        if ra.get("geprueft"):
            ab = 1 - ra["anteil_gleich"]
            z += [f"**Gänge gegen die Rangliste** (Resultatfolge \"+-o++\" je Schwinger und Fest, "
                  f"unabhängiges Dokument): {ra['geprueft']} geprüft, {ab:.1%} abweichend "
                  f"{_ampel(ab <= GRENZE_RESULTAT, warn=ab > GRENZE_RESULTAT)}", "",
                  f"- mehr Gänge als laut Rangliste: {ra['mehr_gaenge']} (falsch zugeordnet), "
                  f"weniger: {ra['weniger_gaenge']} (auch: Gegner nicht auflösbar), "
                  f"gleich viele, andere Ausgänge: {ra['andere_ausgaenge']}",
                  "- je Jahr: " + ", ".join(f"{j} {v['abweichend']}/{v['geprueft']}"
                                            for j, v in ra.get("je_jahr", {}).items()),
                  f"- Feste mit über 5 % Abweichung: {ra.get('feste_ueber_5_prozent', 0)}"
                  + (f" -- {'; '.join(ra['schlechteste_feste'][:5])}" if ra.get("schlechteste_feste") else ""),
                  f"- Ranglisten mit deutlich weniger Teilnehmern als Schwinger mit Gängen: "
                  f"{ra.get('ranglisten_unvollstaendig', 0)}"
                  + (f" -- {'; '.join(ra['beispiele_ranglisten_unvollstaendig'][:3])}"
                     if ra.get("beispiele_ranglisten_unvollstaendig") else ""), ""]

    # Stimmt P(Gestellt)? Die einzige Klasse, die fast nie die wahrscheinlichste
    # ist -- Accuracy und Log-Loss allein zeigen es nicht.
    kal = report.get("gestellt_kalibrierung") or {}
    if kal.get("n"):
        abstand = abs(kal["vorhergesagt"] - kal["eingetreten"])
        z += [f"**Gestellt-Kalibrierung** (Modell {report.get('modell_typ', 'lr')}, "
              f"Merkmalsversion {report.get('merkmal_version', 1)})", "",
              f"- vorhergesagt {kal['vorhergesagt']:.1%} / eingetreten {kal['eingetreten']:.1%} "
              f"({_ampel(abstand < 0.02, warn=0.02 <= abstand < 0.04)})",
              f"- ECE {kal['ece']:.2%}, AUC {kal.get('auc')}", ""]
    # Verlauf (Roadmap T1): ist dieser Lauf deutlich schlechter als die letzten?
    ht = report.get("haertetest") or {}
    if ht.get("status") and ht["status"] != "nicht_eingefroren":
        z += [f"**Härtetest** ({ht['status']}): "
              + (f"{_ampel(False)} {ht['warnung']}" if ht.get("warnung")
                 else f"{_ampel(True)} eingefrorenes Modell und Eingaben unverändert"), ""]
    verlauf = report.get("modell_verlauf") or {}
    if verlauf.get("n_laeufe"):
        warnung = verlauf.get("warnung")
        z += [f"**Modellgüte im Verlauf** ({verlauf['n_laeufe']} Tage): "
              + (f"{_ampel(False)} {warnung}" if warnung else f"{_ampel(True)} kein Rückschritt"), ""]
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
