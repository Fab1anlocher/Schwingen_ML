# Roadmap

Stand: Gesamtanalyse vom 24.09.2026. Jeder Punkt beruht auf einer Messung an
den echten Artefakten, nicht auf einer Vermutung — die Zahlen stehen dabei.

Die Reihenfolge folgt den Abhängigkeiten: erst muss die **Messung** stimmen
(P1), sonst lässt sich keine spätere Modelländerung bewerten; erst muss das
Modell **ehrlich** erklären (P2), bevor es besser rechnen soll (P3).

## Was solide ist

Leak-freie Merkmale (nur Daten von *vor* dem Gang), zeitlicher statt
zufälliger Holdout, täglicher Lauf mit Abbruchbedingungen statt stillem
Commit schlechter Daten, Verlustquote unter 1 %, 185 Tests. Die Befunde unten
sind Mess- und Deutungsfehler — keine kaputte Pipeline.

---

## ✅ P1 — Modellbewertung misst richtig

**Erledigt.** Zwei getrennte Messfehler, beide an der Kernaussage „schlägt die
Elo-Baseline":

- **Spiegelzeilen im Testset.** Jeder Gang wird fürs Training zusätzlich als
  B-gegen-A angelegt. `_split_zeitlich` trennte aber nur nach Datum, jeder
  Testgang stand doppelt drin: `n_test` 72'970 statt 36'485, Konfusionsmatrix
  erzwungen symmetrisch. `benchmark.py` filterte diese Zeilen bereits heraus.
- **Baseline auf anderer Menge.** `bewerte_baseline` lief über alle Gänge
  2023–2026, das Modell nur über den Holdout. Berichtet wurde ein Vorsprung von
  +3.96 pp Accuracy; auf identischen Gängen sind es **+2.72 pp**.

Jetzt: Test ohne Spiegelzeilen, Baseline auf exakt denselben Gängen
(`holdout_gang_schluessel`).

## ✅ P2 — Datenlücke offen statt verdeckt

**Erledigt.** 76 % des Kaders (2198 von 2904) haben kein Porträt und damit zu
100 % keine Physis, keinen Verband, keine Schwünge, keinen Kranzstatus.
schlussgang.ch porträtiert nur Kranzer und besser — `kranz_diff ≠ 0` hiess
damit faktisch „einer hat ein Profil". Porträt schlägt Stub 68 % zu 13 %.

Jetzt: Merkmal `portraet_diff`; datenabhängige Merkmale erscheinen in der App
nicht mehr als Grund, wenn sie für die Paarung auf fehlenden Daten beruhen;
`report.json` → `nur_portraet` misst Modell und Baseline zusätzlich nur auf
Porträt-gegen-Porträt-Gängen.

**Ergebnis des ersten echten Laufs (24.09.2026):** `kranz_diff` verliert rund
70 % seines Gewichts (0.166 → 0.049), `portraet_diff` übernimmt es offen
(0.124). Der Kranzstatus hatte also tatsächlich überwiegend „hat ein Profil"
transportiert. Und auf Porträt-gegen-Porträt-Gängen (9'319) ist das Modell
**praktisch gleich gut wie Elo allein** (Log-Loss 0.9254 vs. 0.9299, Accuracy
57.7 % vs. 58.0 %): Physis, Verband und Schwünge bringen über Elo hinaus nichts
Messbares, obwohl sie dort vollständig vorliegen.

---

## ✅ P3 — Gestellt-Prognose und Merkmale

**Erledigt.** Der Befund „Gestellt wird praktisch nie vorhergesagt" (2.2 % der
Gänge als wahrscheinlichste Klasse, Recall 4.5 %) war zur Hälfte ein
Deutungsfehler: Gestellt ist fast nie der *wahrscheinlichste* Ausgang, und die
App zeigt Wahrscheinlichkeiten, keine Klassen. Die richtige Frage ist, ob
P(Gestellt) **stimmt** und ob das Modell gestellte Gänge **erkennt**. Beides
wird jetzt gemessen (`report.json` → `gestellt_kalibrierung`: vorhergesagt vs.
eingetreten, ECE, AUC, Kalibrierungskurve auf der Analyse-Seite).

Umgesetzt als Merkmalsversion 2 (Details und Zerlegung im README):
Stand vor dem Fest, Gestellt-Neigung, Erfahrung logarithmisch, Elo-Abstand pro
Streuung, Einschwingphase. Test 2026, gleiche 36'485 Gänge:

| | vorher | jetzt |
|---|---:|---:|
| Log-Loss | 0.8314 | **0.7503** |
| Accuracy | 63.9 % | **68.2 %** |
| AUC Gestellt | 0.640 | **0.736** |
| P(Gestellt) vorhergesagt / eingetreten | — | 20.5 % / 21.1 % |
| Recall Gestellt (als wahrscheinlichste Klasse) | 4.5 % | 20.7 % |
| nur Porträt-gegen-Porträt: Accuracy (Elo 58.0 %) | 57.7 % | **61.6 %** |

Validierung 2025 durchgehend gleichsinnig (0.8537 → 0.7771). Nachgezogen als
Merkmalsversion 3: Spitzen-Niveau und Gestellt-Bilanz des Paars. Spitzen-
paarungen bekamen vorher 18 % Gestellt bei 30 % eingetreten, jetzt 29.6 %;
Test-Log-Loss 0.7503 → 0.7491 (README, Abschnitt Merkmalsversion 3). Verworfen, weil
gemessen schlechter: `class_weight="balanced"` (P(Gestellt) 30 % statt 21 %,
Log-Loss +0.024), Regularisierung (ohne Effekt), 2023 hart ausschliessen
(schwächer als die Einschwingphase).

Nebenbei behoben: symmetrische Merkmale (gleicher Verband, Ausgeglichenheit,
ähnlicher Stil) wurden in der App einem Schwinger gutgeschrieben, obwohl sie
nur zwischen Sieg und Gestellt verschieben — jetzt neutral als „Gestellt ±X".

## ✅ P4 — Sicherheitslücken im Web-Stack

**Erledigt — aber anders als ursprünglich geplant.** Der Plan war „`next` auf
14.2.35". Nachgemessen: auch 14.2.35, die letzte 14er, hat noch **23 offene
Advisories**, darunter Remote Code Execution in der Image-Optimierung und XSS
im App Router. Next 14 bekommt diese Fixes nicht mehr; der Patch-Sprung wäre
eine Scheinlösung gewesen.

Umgesetzt: Next 15.5.26 + React 19 (kleinster sicherer Major-Schritt; 15 wird
parallel zu 16 gepatcht), `overrides: postcss ≥ 8.5.28` (auch Next 15 pinnt
das verwundbare 8.4.31). `npm audit`: 0 Befunde. Build, Typecheck und alle
Seiten im Browser (Desktop + mobil, Funktionsprüfung) fehlerfrei. Neu:
CI-Job `abhaengigkeiten-audit` und Dependabot.

**Offen:** Next 16 (Turbopack-Build, `middleware` → `proxy`, entfernte
Sync-APIs) — eigenes Vorhaben, sobald 15 aus dem Support fällt. Dependabot-
Sicherheitsupdates müssen einmalig in den Repo-Einstellungen aktiviert werden
(Settings → Code security → Dependabot security updates).

## ✅ P5 — Parität TypeScript ↔ Python automatisch geprüft

**Erledigt.** `pipeline/paritaet.py` erzeugt ~240 Prüffälle aus den echten
Artefakten, `npm run paritaet` rechnet sie mit der App-Logik nach: Merkmale,
Kopf-an-Kopf (inkl. Richtungsumkehr) und Wahrscheinlichkeiten. Läuft in jedem
PR und im täglichen Lauf vor dem Commit neuer Artefakte. Mutationstest: sechs
absichtlich eingebaute Fehler, alle erkannt. `verify_inference` nutzt jetzt
dieselbe Python-Spiegelung statt einer eigenen Kopie.

## ✅ P6 — Datenabdeckung erhöhen (soweit messbar möglich)

**Teilweise erledigt — was sich belegen liess, ist umgesetzt; der Rest ist
blockiert und so benannt.**

Ausgangslage: 706 von 2904 Schwingern (24 %) haben ein Porträt; die übrigen
2198 haben zu 100 % keine Physis, keinen Verband, keinen Kranzstatus. In
2026 stammen 60 % aller Gangteilnahmen von Schwingern ohne Porträt. Die
Porträts selbst sind fast vollständig (Gewicht 695/706, Grösse 693/706,
Verband 706/706; Schwünge nur 418/706 — die Quelle führt sie nicht immer).

- **Teilverband aus Festbesuchen geschätzt** (`pipeline/verbandsschaetzung.py`).
  An Kantonal-, Teilverbands- und Regionalfesten startet fast nur, wer dem
  Verband angehört. Validiert an den Porträt-Schwingern mit bekanntem Verband
  (Leave-one-out): **99.8 % richtig** (1 Fehler auf 583). Mit nur einem Fest
  wären es 89.5 %, darum mindestens 3 zuordenbare Feste. Die Prüfung läuft
  **bei jedem Lauf** erneut; unter 97 % wird nichts geschätzt.
  Ergebnis: **1649 von 2198** Schwingern ohne Porträt haben jetzt einen
  Verband; bekannt sind damit 81 % des Kaders statt 24 % (aktive 2026: 90 %).
  In der App als „geschätzt" gekennzeichnet, Suche und Filter finden sie.
- **Bewusst nicht ins Modell:** mit geschätzten Verbänden gälte „gleicher
  Verband" für 73 % der Gänge statt 17 % — Test-Log-Loss 0.7503 → 0.7512,
  also schlechter. Eigenes Feld `teilverband_geschaetzt`; das Modell nutzt
  weiter nur den gemessenen Verband.
- **Gespaltene Identitäten geprüft:** 66 Porträts ohne einen Gang seit 2023
  (fast alle Jahrgang ≤ 1998, also wohl zurückgetreten). Keines davon ist ein
  übersehener Stub: die drei Namensähnlichkeiten sind nachweislich andere
  Personen (anderer Nachname bzw. anderer Verband laut Festbesuchen).
- **ESV-Ranglisten: gelöst über schlussgang.ch.** esv.ch sperrt Cloud-IPs
  weiterhin (schon `robots.txt` antwortet 403 — über GitHub-Runner geprüft,
  25.09.2026). Eine Sonde fand aber: schlussgang.ch führt zu jedem Fest die
  offizielle **Schlussrangliste des ESV** (`field_final_ranking_pdf`, Fusszeile
  „Quelle: ESV"), für 480 von 481 Festen seit 2023 — mit Schwingklub, Wohnort,
  Senn/Turner, Kranzabzeichen und Kranz JEDES Teilnehmers. Umgesetzt
  (`scrape/schlussgang_rangliste.py`, `ranglisten.py`): echte **Kranzzahlen
  seit 2023** (481 Feste, 0 unlesbar, 99.4 % der Namen zugeordnet; Moser
  z.B. 33), Klub/Kranzstatus/Senn-Turner auch ohne Porträt, Teilverband und
  Gauverband über den Klub (Leave-one-out 99.1 %; gemessener Verband bei
  92.5 % der Aktiven statt 29 %). Lücke: Freiburger Kantonalfest 2023 ohne
  Status-Einträge in der Quelle. Was die Ranglisten
  nicht enthalten: Gewicht, Grösse, Jahrgang (nur bei Namensvettern) — Physis
  bleibt für Schwinger ohne Porträt unbekannt.

## ✅ Betrieb: CI auf Artefakt-Commits, Sicherheits-Audit

- **Bot-Commits ohne CI.** Pushes mit dem `GITHUB_TOKEN` lösen keine
  push-Läufe aus, und PR-Läufe daraus warten seit Juni 2026 auf Freigabe
  („action_required"). `update.yml` startet die CI nach seinem Commit jetzt
  selbst per `workflow_dispatch` (davon ausgenommen) — die täglichen
  Artefakt-Commits auf main laufen damit erstmals durch die volle CI.
- **Dependabot-Sicherheitsupdates** lassen sich nur in den Repo-Einstellungen
  einschalten. Ersatz: `sicherheit.yml` prüft täglich `npm audit` und
  `pip-audit`, legt bei Befund ein Issue an (und schlägt fehl → Mail) und
  schliesst es bei Entwarnung. Die Einstellung zusätzlich einzuschalten
  schadet nicht (Settings → Code security → Dependabot security updates).

## P7 — Kleinkram

- `diagnose_agenda` ungetestet.
- ✅ A/B-Zuteilung per Alphabet ist die Ursache der schiefen
  Ergebnisverteilung (35 % / 42 %): im README erklärt und im Qualitätsbericht
  als Artefakt gekennzeichnet.
- `benchmark.py → ml_ohne_elo` enthält `kranz_diff` — misst damit teilweise
  ebenfalls die Datenlage statt „Physis, Stil, Verband".
