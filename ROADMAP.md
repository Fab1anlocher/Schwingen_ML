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

Validierung 2025 durchgehend gleichsinnig (0.8537 → 0.7771). Verworfen, weil
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

## P6 — Datenabdeckung erhöhen

**Priorität mittel · Aufwand gross — behebt P2 an der Wurzel**

Nur 706 von 2904 Schwingern haben ein Porträt. P2 macht die Lücke sichtbar,
schliesst sie aber nicht. Eine zweite Quelle für Physis und Verband der übrigen
76 % — z.B. die ESV-Ranglisten — würde P2 und P3 zugleich verbessern. Nicht als
Ersatz für schlussgang.ch, sondern als Ergänzung.

Vorher klären: Erlaubt die Quelle das Abrufen (robots.txt, Nutzungsbedingungen)?
Ein früherer ESV-Teilbaum wurde entfernt, weil der Host CI-Runner mit 403
sperrte.

## P7 — Kleinkram

- `diagnose_agenda` ungetestet.
- ✅ A/B-Zuteilung per Alphabet ist die Ursache der schiefen
  Ergebnisverteilung (35 % / 42 %): im README erklärt und im Qualitätsbericht
  als Artefakt gekennzeichnet.
- `benchmark.py → ml_ohne_elo` enthält `kranz_diff` — misst damit teilweise
  ebenfalls die Datenlage statt „Physis, Stil, Verband".
