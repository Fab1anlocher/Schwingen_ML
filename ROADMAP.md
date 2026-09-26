# Roadmap

Jeder Punkt beruht auf einer Messung an den echten Artefakten, nicht auf
einer Vermutung — die Zahlen stehen dabei. Gemessen mit `pipeline/harness.py`:
trainiert auf allem vor dem Testjahr (echte Trainingsmaske), bewertet auf
Validierung 2025 und Test 2026. **Übernommen wird nur, was in beiden Jahren
besser wird.**

---

# Planung ab 26.09.2026

**Ausgangslage** (Merkmalsversion 3, nach der Namensvettern-Trennung):
Log-Loss Validierung 2025 **0.7627**, Test 2026 **0.7400**, Accuracy 68.7 %,
Gestellt 20.6 % vorhergesagt / 21.1 % eingetreten.

**Stand nach M1** (zweistufiges Boosting, 26.09.2026): Validierung **0.7400**,
Test **0.7207**, Accuracy 69.0 %, Gestellt 20.5 % / 21.1 %. **Mit M2**
(Zeitgewichtung): 0.7390 / 0.7203. Dazu **M5**: die App rechnet mit einem
Modell, das auch die laufende Saison gesehen hat.

## Übersicht und Reihenfolge

| # | Vorhaben | Gemessener Nutzen | Aufwand | Priorität |
|---|---|---|---|---|
| ✅ M1 | Gradient Boosting statt Logistic Regression | Log-Loss −0.023 (Val) / −0.019 (Test) — **erledigt** | 1–2 Tage | ~~1~~ |
| ✅ T1 | Modellgüte je Lauf historisieren + Warnung | **erledigt**, Verlauf ab 21.07.2026 | ½ Tag | ~~2~~ |
| ✅ M5 | Ausgeliefertes Modell auch auf der laufenden Saison trainieren | eine Saison mehr: Test 0.7294 → 0.7207 — **erledigt** | ½ Tag | ~~2~~ |
| ✅ F1 | Prognose-Check je Fest im Rückblick | 2026: 69 % Treffer (Elo 61 %) — **erledigt** | ½–1 Tag | ~~2~~ |
| ✅ D3 | Rohdaten wöchentlich sichern | Voraussetzung für D1/D2, Ausfallschutz — **erledigt** | ½ Tag | ~~3~~ |
| ✅ M2 | Jüngere Gänge stärker gewichten | Val 0.7400 → 0.7390, Test 0.7207 → 0.7203 — **erledigt** | ½ Tag | ~~3~~ |
| D1 | Noten je Gang (Plattwurf 10.00 vs. 9.75) nutzen | gemessen: Val −0.0027, Test −0.0039 (Messung ohne Ranglisten-Anreicherung) | 1 Tag | **2** |
| ✅ F4 | Fest-Simulator (Monte Carlo) mit Rückblick | Festsieger bekam Ø 27 % (Elo 18 %), Kranz-Brier 0.076 (Elo 0.081) — **erledigt** | 1–2 Tage | ~~–~~ |
| D2 | Gangnummer aus der Rangliste (Anschwingen, Ausstich) | offen — erst nach D3 messbar | 1 Tag | 4 |
| M3 | Heimvorteil (Fest des eigenen Verbands gegen Gäste) | +0.022 Punkte je Gästegang (2.6 SE) | ½ Tag | 5 |
| M4 | Unsicherheit bei Neulingen (Glicko-artig) | Paarungen mit < 5 Gängen: Log-Loss 0.771 (sonst 0.70–0.75) | 1–2 Tage | 5 |
| F2 | Elo-Verlauf im Schwinger-Profil | Produkt | 1 Tag | 5 |
| F3 | Vorschaubild für geteilte Prognose-Links | Produkt | ½ Tag | 6 |
| T2 | Frontend-Tests + Browser-Smoke-Test in der CI | Sicherheit | 1 Tag | 6 |
| T3 | Altlasten: `diagnose_agenda` testen, `ml_ohne_elo` ohne `kranz_diff` | Sauberkeit | ½ Tag | 6 |

Empfohlene Reihenfolge: ~~M1 mit T1~~, ~~M5 mit M2~~, ~~F1~~, ~~D3~~, ~~F4~~
(erledigt), als Nächstes **D1**: die Noten-Merkmale verbessern das Modell in
beiden Jahren (Messung `noten`, Val 0.7514 → 0.7487, Test 0.7271 → 0.7232);
für die Umsetzung müssen die Noten in die Artefakte oder die Merkmale im
Pipeline-Lauf entstehen, und die Messung ist mit der Ranglisten-Anreicherung
zu wiederholen.

## ✅ M1 — Gradient Boosting als Prognosemodell (erledigt 26.09.2026)

**Ergebnis.** Umgesetzt als **zweistufiges** Boosting (`pipeline/modell.py`):
erst P(Gestellt), dann P(Sieg A | entschieden), je mit Monotonie-Vorgaben und
gemittelt mit der gespiegelten Paarung (exakt symmetrisch).

| | Validierung 2025 | Test 2026 | Fehlrichtungen* |
|---|---:|---:|---:|
| Logistic Regression | 0.7627 | 0.7400 | – |
| Boosting, drei Klassen | 0.7388 | 0.7206 | 6.5 % / 8.2 % |
| Boosting, drei Klassen, min. 200 je Blatt | 0.7396 | 0.7203 | 6.6 % / 11.1 % |
| Zweistufig, Monotonie (Gestellt-Bilanz, -Neigung; Rating, Kopf-an-Kopf) | 0.7406 | 0.7213 | 0 % |
| + Gestellt-Stufe min. 100 je Blatt | 0.7398 | 0.7211 | 0 % |
| **+ Rating-Abstand monoton (fallend) → Produktion** | **0.7400** | **0.7207** | **0 %** |
| Zweistufig, zusätzlich Form/Kranz/Erfahrung monoton | 0.7465 | 0.7262 | 0 % |
| Zweistufig, Lernrate 0.05, 31 Blätter | 0.7414 | 0.7207 | 0 % |

\* Anteil der Paare mit Vorgeschichte, bei denen eine höhere Gestellt-Bilanz
die Gestellt-Chance um mehr als 1 Punkt **senkt** (Validierung / Test).
Anlass war Orlik–Staudenmann (5 von 6 Duellen gestellt): das Drei-Klassen-
Modell zeigte „Gestellt-Bilanz −8.7 %-Pkt.". Jetzt: 13 / 58 / 29 %,
Gestellt-Bilanz +5.2, Niveau der Paarung +27.4 %-Pkt. Richtung Gestellt.

Echter Lauf: Log-Loss 0.7207, Accuracy 69.0 %, Brier 0.416 (LR 0.426),
Gestellt-Kalibrierung in allen zehn Stufen getroffen (oberstes Zehntel 51.7 %
vorhergesagt / 51.7 % eingetreten). `model.json` 0.26 MB (gzip ~90 kB),
Parität TypeScript ↔ Python bitgleich (Abweichung 1e-16).

Ursprünglicher Befund und Plan:

**Befund.** Mit **denselben 16 Merkmalen** erreicht ein Gradient-Boosting-
Modell (`HistGradientBoostingClassifier`, 31 Blätter, Early Stopping) deutlich
mehr als die lineare Regression — in beiden Jahren:

| | Validierung 2025 | Test 2026 | AUC Gestellt (Test) |
|---|---:|---:|---:|
| Logistic Regression (heute) | 0.7627 | 0.7400 | 0.741 |
| Gradient Boosting | **0.7398** | **0.7204** | **0.750** |

Das ist mehr als die Merkmalsversionen 2 → 3 zusammen. Die Ursache liegt in der
Kalibrierung der Siegchancen: die LR überschätzt Aussenseiter (vorhergesagt
19.4 %, eingetreten 15.7 %) und unterschätzt Favoriten (59.6 % → 62.8 %,
79.9 % → 82.7 %). Mit Handarbeit an der LR ist das nicht zu holen: nichtlinearer
Elo-Abstand (d·|d|, d³) −0.0012, Elo-Trend über 12 Monate, Jugend-Merkmal und
d × Erfahrung je ±0.0000. Der Gewinn steckt in Wechselwirkungen.

**Umsetzung.**
1. `train.py`: Modelltyp wählbar; Boosting mit festem Seed, Early Stopping auf
   einem zeitlich letzten Teil des Trainings (nicht zufällig).
2. `export.py`: Bäume als kompaktes JSON in `model.json` (heute rund 30–40 k
   Knoten; Grösse messen, bei Bedarf Knotenzahl begrenzen), `modell_typ` und
   `merkmal_version` bleiben Pflichtfelder. LR bleibt als Rückfall und als
   Benchmark-Kandidat.
3. `web/lib/inference.ts`: Baumauswertung. **Symmetrie erzwingen**: Mittel aus
   P(A,B) und gespiegelt P(B,A). Die LR ist durch die Spiegelzeilen exakt
   symmetrisch, Bäume nur ungefähr — ohne Mittelung wiche „Orlik gegen
   Staudenmann" von „Staudenmann gegen Orlik" ab.
4. Erklärbalken: die heutige Gegenprobe (Merkmal auf neutralen Wert, neu
   rechnen) funktioniert modellunabhängig. Beiträge sind bei Bäumen nicht mehr
   additiv — der Hilfetext muss das sagen.
5. Parität (`paritaet.py`/`paritaet.cjs`) um den Baumpfad erweitern,
   `verify_inference` ebenso.

**Abnahme.** Validierung und Test besser als die LR; Parität grün; Symmetrie
bis 1e-12; Ladezeit von `model.json` auf Mobil gemessen; Orlik–Staudenmann und
fünf weitere Spitzenpaarungen plausibel erklärt.

**Risiko.** Erklärungen werden weniger „linear" lesbar; das Modell ist grösser.
Beides ist handhabbar; der Gewinn ist gross und in beiden Jahren gleichsinnig.

## ✅ M2 — Jüngere Gänge stärker gewichten (erledigt 26.09.2026)

Umgesetzt für das Boosting: Stichprobengewicht 0.5 ^ (Alter / 365 Tage),
Alter ab dem jüngsten Trainingsgang (`modell.zeitgewicht`). Gemessen:

| Halbwertszeit | Validierung 2025 | Test 2026 |
|---|---:|---:|
| ungewichtet | 0.7400 | 0.7207 |
| 180 Tage | 0.7404 | 0.7202 |
| **365 Tage** | **0.7390** | **0.7203** |
| 540 Tage | 0.7393 | 0.7209 |

Klein, aber in beiden Jahren besser. Nebenwirkung: mit Gewichten rechnet
sklearn die Bin-Grenzen als gewichtete Perzentile, ~5 s mehr je Fit.

Ursprünglicher Befund:

Lernkurve (Test 2026): nur mit 2025 trainiert ist die LR **besser** (0.7378)
als mit 2024–2025 (0.7398); beim Boosting gleich (0.7204). Mehr alte Daten
helfen also nicht, jüngere zählen mehr. Zu testen: Stichprobengewicht mit
Halbwertszeit 6–18 Monate. Gleich in der M1-Messung mitlaufen lassen.

**Verworfen, weil gemessen ohne Wirkung:** Elo-Trend (12 Monate), Jugend-
Merkmal, d × Erfahrung, mehr Trainingshistorie. Daten vor 2023 würden nur das
Elo-Aufwärmen verbessern, nicht das Training — erst angehen, wenn das nach M1
noch nötig erscheint.

## ✅ T1 — Modellgüte über die Zeit (erledigt 26.09.2026)

Umgesetzt: `artifacts/report_verlauf.json` (je Tag und Modellstand, ab
21.07.2026 aus der Git-Historie nachgetragen), Warnung im
Datenqualitätsbericht, Verlauf auf der Analyse-Seite. Ein Modellwechsel am
selben Tag behält den Punkt davor, damit der Sprung sichtbar bleibt.

Ursprünglicher Plan: Heute überschreibt jeder Lauf `report.json`; ob das
Modell über Wochen schlechter wird (neue Saison, Datenfehler), sieht niemand.
`artifacts/report_verlauf.json` hängt je Lauf Datum, Log-Loss, Accuracy,
Gestellt-Kalibrierung und Datenumfang an; der Lauf warnt im Job-Summary, wenn
der Log-Loss gegenüber dem Median der letzten 14 Läufe um mehr als 0.01
steigt. Die Analyse-Seite zeigt den Verlauf.

## ✅ M5 — Ausgeliefertes Modell auch auf der laufenden Saison trainieren (erledigt 26.09.2026)

**Umgesetzt.** `train.trainiere` fittet nach der Evaluation ein zweites Modell
auf allen Trainingszeilen inklusive der Holdout-Saison (gleiche Einstellungen,
Baumzahl neu zeitlich gewählt); das geht in `model.json`. Die Kennzahlen im
Report bleiben die des Evaluationsmodells; `report.json` →
`n_train_ausgeliefert` nennt den Umfang des ausgelieferten, die Analyse-Seite
sagt es dazu. Rückwirkend gemessen (Test 2026): Training bis 2024 0.7294,
bis 2025 0.7207 — eine fehlende Saison kostet also rund 0.009.

**Befund (beim Prüfen von M1).** `train.trainiere` fittet das Modell auf allem
**vor** der Holdout-Saison und liefert genau dieses Modell aus. Die jüngste
Saison (2026: 36'610 Gänge, ein Viertel der Daten) dient nur als Test — das
ausgelieferte Modell lernt nie aus ihr. Die Merkmale (Elo, Form, Neigung)
sind zwar aktuell, die Abbildung Merkmale → Wahrscheinlichkeit aber nicht.
M2 zeigt, dass jüngere Gänge mehr zählen.

**Plan.** Evaluation unverändert (Modell auf < Holdout, Kennzahlen auf der
Holdout-Saison), danach **auf allen Daten neu fitten** und dieses Modell
exportieren (gleiche Hyperparameter, Baumzahl neu zeitlich gewählt).
Messen lässt sich der Nutzen rückwirkend: Test 2026 mit Training bis 2024
gegen Training bis 2025 — das ist genau der Schritt „eine Saison mehr".
Der Report muss sagen, dass die Kennzahlen vom Evaluationsmodell stammen.

## ✅ F4 — Fest-Simulator (erledigt 26.09.2026)

Monte-Carlo-Simulation eines ganzen Fests (Seite „Simulator"), Regeln an den
echten Daten kalibriert (s. README „Fest-Simulator"). Die entscheidende
Kalibrierung war die Einteilung: streng nach Punkten gepaart, traf fast jeder
auf einen Gleichstarken (Elo-Abstand 55 statt real 108), das Modell sagte
darum 30 % Gestellte statt real 22 % voraus, und die Kranzchancen waren
schlechter als mit reinem Elo (Brier 0.121 gegen 0.116, Kränze dabei aus den
Gangresultaten angenähert). Mit Anschwingen der Spitze und Ermessensspielraum:
Elo-Abstand 116, Gestellte 21.6 %.

Rückblick mit den echten Schlussranglisten (38 Kranzfeste 2026, 5'419
Teilnahmen, Modell von vor der Saison):

| | Modell | nur Elo | ohne Wissen |
|---|---:|---:|---:|
| Kranz, Brier-Score | **0.076** | 0.081 | 0.135 |
| Wahrscheinlichkeit für den tatsächlichen Festsieger (Ø) | **27 %** | 18 % | |
| Favorit gewann das Fest | **50 %** | 47 % | |
| Sieger unter den drei Favoriten | 82 % | **87 %** | |

Kranzchancen ab 30 % gut kalibriert (z.B. 79 % vorhergesagt / 79 %
eingetreten); zwischen 5 und 30 % leicht zu hoch (9 % / 4 %, 22 % / 16 %).

Mögliche Verfeinerung: das Einteilungsgericht meidet auch Paarungen, die es in
derselben Saison schon oft gab — die Simulation nur Wiederholungen im Fest.

## ✅ F1 — Prognose-Check je Fest (erledigt 26.09.2026)

Umgesetzt in `pipeline/prognose_check.py`, angezeigt im Rückblick der
Feste-Seite (Spalte „Prognose" und Saison-Zusammenfassung mit Aufschlüsselung
nach Festtyp). Ausgewertet werden 2025 (Modell bis 2024) und 2026 (Modell bis
2025): Treffer 67.7 % / 69.0 % gegen Elo 61.1 % / 61.3 %; dem tatsächlichen
Ausgang gab das Modell im Schnitt 56.7 % / 58.2 %. Bergfeste und das
Eidgenössische sind am schwersten (58–62 %). Das Modell trifft an 263 von 270
Festen mindestens so oft wie Elo; darunter liegt es an vier Bergfesten
(Schwägalp 2025/2026, Rigi und Schwarzsee 2025, je 1–2 Punkte) und drei
kleinen Regionalfesten.

Ursprünglicher Plan:

Im Rückblick je Fest: wie oft lag das Modell richtig, wie gut war die
Gestellt-Chance — gerechnet mit dem Modell, das **vor** dem Fest galt. Für die
Holdout-Saison liegen diese Vorhersagen im Training ohnehin vor. Macht die
Qualität für Nutzer greifbar („am Brünig 2026: 74 % der Gänge richtig").

## ✅ D3 — Rohdaten sichern (erledigt 26.09.2026)

Umgesetzt auf zwei Wegen:
- **Sicherung:** `update.yml` lädt `artifacts/raw` sonntags (und auf Wunsch)
  als Workflow-Artefakt hoch, 90 Tage aufbewahrt.
- **Messen ohne Download:** Workflow „Messung auf Rohdaten" (`messung.yml`)
  lädt den Rohdaten-Cache nur lesend und führt `python -m pipeline.messung
  <name>` aus; das Ergebnis steht im Job-Summary. Erste Messung: `noten`
  (Verteilung je Ausgang und Noten-Merkmale im Modell, D1).

Ursprünglicher Plan:

`artifacts/raw` existiert nur im Actions-Cache. Geht er verloren, kostet der
Neuaufbau rund 20 Minuten, und lokal (ohne Zugang zu schlussgang.ch) lässt
sich nichts messen, was nicht in den Artefakten steht — etwa die Noten je Gang.
Plan: wöchentlich `ranglisten.json`, `gaenge.json` und `events.json`
komprimiert als Workflow-Artefakt sichern; der Harness kann sie optional laden.

## D1 / D2 — Noten und Gangnummer

* **D1 Noten:** Die Statistik-PDF führt je Gang die Note. Notengebung
  (normal 10.00 bis 8.50):

  | Ausgang | Note | Signal |
  |---|---|---|
  | Sieg mit Plattwurf | 10.00 | klare Überlegenheit |
  | Sieg (normal) | 9.75 | |
  | Gestellt (normal) | 8.75 | |
  | Gestellt, technisch hochstehend | bis 9.00 | aktiver, offensiver Gang |
  | Niederlage (normal) | 8.50 | |
  | Niederlage, offensiv/technisch versiert | 8.75 | Verlierer hat mitgeschwungen |
  | **Schlussgang** | Sieger 10.00, Verlierer 8.75 **vorgeschrieben**; Gestellt nach Platzkampfgericht | kein Signal |

  Mögliche Merkmale je Schwinger (Stand vor dem Fest, geschrumpft wie die
  Gestellt-Neigung): Anteil Plattwürfe an den Siegen (Dominanz), Anteil
  8.75 an den Niederlagen (Offensive), Anteil 9.00 an den Gestellten
  (aktive Gestellte); dazu Elo mit Siegqualität (Plattwurf zählt mehr).
  **Schlussgänge ausnehmen**: dort sind die Noten vorgeschrieben — ein
  Spitzenschwinger, der oft den Schlussgang verliert, bekäme sonst lauter
  „offensive" 8.75.
* **D2 Gangnummer:** die Rangliste führt je Schwinger die Resultatfolge
  („-+++++"), also die Reihenfolge der Gänge. Anschwingen (Spitzenpaarungen,
  mehr Gestellte) und Ausstich unterscheiden sich; live ist die Gangnummer aus
  der Einteilung bekannt.

Beides erst nach D3 messbar, weil die Artefakte weder Noten noch Gangnummer
enthalten.

**Messung „siegart“ (25.09.2026):** Gewinnen starke Schwinger eher mit der
10.00? 74 506 entschiedene Gänge 2023–2026 (beide mit ≥ 10 erfassten
Gängen, Schlussgänge über den Punktbesten des Fests ausgenommen).

| Sieger (Elo vor dem Fest) | schwächer als Gegner | 0–150 stärker | > 150 stärker |
|---|---:|---:|---:|
| unteres Drittel | 45.8 % | 48.8 % | 66.3 % |
| mittleres Drittel | 47.2 % | 51.5 % | 64.0 % |
| oberes Drittel | 48.0 % | 50.1 % | 60.9 % |

* **Roh ja, aber wegen der Gegner:** Das stärkste Fünftel gewinnt 56.5 % mit
  10.00, das schwächste 47.3 %. Entscheidend ist aber der **Abstand** zum
  Gegner (+6.6 Prozentpunkte je 100 Elo, z = 26), nicht die Stärke selbst
  (−0.7 je 100 Elo). Gegen Gleichstarke werfen Spitzenschwinger nicht öfter
  platt als andere; sie treffen nur öfter auf Schwächere.
* **Verlierer:** Starke verlieren offensiver, 8.75 statt 8.50 im stärksten
  Fünftel 16.0 %, im schwächsten 6.4 %.
* **Persönlicher Stil:** Über zwei Hälften der Siege ist die Plattwurf-Quote
  eines Schwingers stabil (r = 0.59, 716 Schwinger mit ≥ 40 Siegen). Daran
  ändert sich nichts, wenn man Stärke, Abstand und die Benotung des Fests
  herausrechnet: Die Feste benoten nur mässig verschieden (10.–90.
  Perzentil 46.7–58.2 %). Beispiele gegenüber der Erwartung aus Gegnern und
  Fest: Adrian Walther 73 % (+12), Michael Moser 67 % (+9), Lukas Bissig
  43 % (−14), Sinisha Lüscher 46 % (−11).
* **Für die Prognose wenig:** `plattwurf_diff` allein verbessert den
  Log-Loss nur knapp (Val 0.7411 → 0.7401, Test 0.7204 → 0.7200). Die drei
  Noten-Merkmale zusammen bringen mehr (s. Messung `noten` oben).
* **Folgen:** (1) Der Fest-Simulator nimmt 52 % Plattwürfe für jeden Sieg an;
  abhängig vom Elo-Abstand (49 % bis 66 %) und von der Stärke des Verlierers
  wäre die Punkteverteilung realistischer. (2) Die Siegart je Schwinger
  („wirft öfter platt als erwartet“) ist ein Profil-Merkmal mit echter
  Aussage. Beides braucht die Noten in den Artefakten, wie D1.

## M3 / M4 — kleinere Modellthemen

* **M3 Heimvorteil:** an Festen des eigenen Teilverbands gewinnen Einheimische
  gegen Gäste leicht mehr als erwartet (+0.022 Punkte je Gang, 1517
  Test-Gänge, 2.6 Standardfehler). Klein, betrifft nur Gästegänge — mit M1
  zusammen testen.
* **M4 Neulinge:** Paarungen mit einem Schwinger unter 5 Gängen haben Log-Loss
  0.771 (6 % der Gänge). Ein Rating mit Unsicherheit (Glicko) könnte das
  senken; aufwendiger, weil Elo überall verwendet wird.

## F2 / F3 / T2 / T3 — Produkt und Technik

* **F2 Elo-Verlauf** im Schwinger-Profil (Sparkline), Daten serverseitig wie
  der Kopf-an-Kopf-Index, damit der Download klein bleibt.
* **F3 Vorschaubild** für geteilte Prognose-Links (Open Graph über
  `next/og`): Paar und Prozente direkt im Chat sichtbar.
* **T2 Tests:** Unit-Tests für `lib/labels.ts`, `lib/teilverband.ts`, und ein
  Playwright-Smoke-Test in der CI (jede Seite lädt ohne Konsolenfehler, kein
  horizontales Scrollen auf Mobil) — heute nur manuell geprüft.
* **T3 Altlasten:** `diagnose_agenda` ist ungetestet; `benchmark.py →
  ml_ohne_elo` enthält `kranz_diff` und misst damit teilweise die Datenlage
  statt „Physis, Stil, Verband".

Kein Handlungsbedarf: `schwinger.json` ist 3.1 MB roh, aber 150 KB
komprimiert.

---

## ✅ Audit der Analyse-Seite (26.09.2026)

Jede Zahl der Seite nachgerechnet: Evaluationsmodell mit dem Harness
nachgebaut (Log-Loss 0.7203 statt 0.7204, Treffer 69.05 % statt 69.01 %; die
Abweichung kommt vom Nachbau aus den Artefakten), Bootstrap über Feste,
Gegenproben. Die berichteten Zahlen waren rechnerisch richtig; falsch oder
irreführend waren Vergleiche und Deutungen:

| Befund | Wirkung | Korrektur |
|---|---|---|
| Elo-Vergleich mit fester Formel, viel zu zaghaft (Favorit „64 %“ gewinnt in 85 %) | Vorsprung des Modells überzeichnet: Log-Loss 0.910 → 0.720 statt fair 0.857 → 0.720 | Kandidat `elo_angepasst` (nur Elo, Wahrscheinlichkeiten gelernt), die Seite vergleicht damit |
| Kranz-Faustregel: bei gleichem Status (65 % der Gänge) „Gestellt“ | „42 % Treffer“ klang nach „Kranzstatus taugt nichts“; mit Favorit sind es 77 % | Anteil ohne Favorit und Treffer mit Favorit im Artefakt und im Text |
| „Modell ohne Elo“ = „ohne Ergebnisse der Vergangenheit“ | falsch, es enthält den Kranzstatus | Text korrigiert |
| MAE als Fehlermass | belohnt Übertreibung: Faustregel 0.301 besser als Elo 0.338 | aus der Anzeige entfernt (bleibt im Artefakt), Log-Loss je Ansatz ergänzt |
| Merkmalswichtigkeit: 1 Vertauschung auf 8000 Gängen, bei 0 abgeschnitten | Plätze vertauscht, kleine Merkmale „0.000“ | 5 Wiederholungen auf allen Testgängen, Streuung im Artefakt |
| „…wie viel das Modell ohne dieses Merkmal verlöre“ | falsch: Kranzstatus 0.023 vertauscht, ohne ihn neu trainiert +0.0007 | Text: „so stark stützt sich das Modell darauf“ |
| „Merkmale Stand vor dem Fest“ | nicht für Porträt-Merkmale: Kranzstatus ist der heutige | offen benannt; Obergrenze gemessen: ohne Kranzstatus und Porträt-Angabe Test-Log-Loss +0.0015, Treffer −0.2 Pkt. |
| „ganze Saison 2026“ | 4 Feste stehen noch aus | „Saison 2026 bis 13.9.“ |
| keine Unsicherheit | 69.0 % wirkte exakt | 95-%-Bereiche, Bootstrap über die 133 Feste: Treffer 68.2–69.8 %, Log-Loss 0.709–0.732 |
| Boosting „deutlich besser“ als LR | übertrieben: −0.020 Log-Loss [−0.017, −0.022], +0.4 Pkt. Treffer [+0.1, +0.6] | „klein, aber in beiden Prüfsaisons“ |
| Eidgenössisch 2026 = 1 Fest (Kilchberg), 165 Gänge | Zeile wirkte gleichwertig | Feste, Gänge, Gestellt-Anteil je Festtyp, „wenig Daten“ |
| Schwünge: Ø Elo ohne Unsicherheit | Übersprung +60 wirkte echt, 95-%-Bereich ±61 | Fehlerbalken; kein Unterschied ist gesichert |
| Streudiagramme | Auswahl nur Porträt-Schwinger (fast nur Kranzer) dämpft r; Achsen zeigten den Rand (Alter „14“) | Hinweis, 95-%-Bereich für r, echte Extremwerte an der Achse |
| Alarmgrenze der Überwachung | Seite nahm den unteren Median, die Pipeline `np.median` | wie die Pipeline |
| Tabelle „Alle Läufe“ | Läufe bis 23.9. zählten jeden Gang doppelt, Werte nicht vergleichbar | Spalte Testgänge und Hinweis |
| Auswahl an 2025 und 2026 | Kennzahlen leicht optimistisch | offen benannt; unberührte Prüfsaison erst 2027 |

Zusätzlich sichtbar gemacht: Unter Porträt-Schwingern (26 % der Gänge)
trifft das Modell 62.8 % (Elo 58.3 %) — die 69 % insgesamt kommen auch von
vielen ungleichen Paarungen.

Offen: Kranzstatus zum Zeitpunkt des Gangs (aus den Sternen der Rangliste
bzw. dem Statusabzeichen der Statistik-PDF) statt aus dem heutigen Porträt —
würde das kleine Leck ganz schliessen.

# Erledigt

## Was solide ist

Leak-freie Merkmale (nur Daten von *vor* dem Gang), zeitlicher statt
zufälliger Holdout, täglicher Lauf mit Abbruchbedingungen statt stillem
Commit schlechter Daten, Verlustquote unter 1 %, rund 260 Tests. Die
erledigten Befunde unten waren Mess-, Deutungs- und Datenfehler — keine
kaputte Pipeline.

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

## ✅ Seiten-Audit und Datenqualität (25.09.2026)

- **Namensvettern** wurden zu einer Person zusammengelegt, sobald nur einer
  ein Porträt hatte (Samuel Giger stand an fünf Tagen an zwei Festen
  gleichzeitig). `namensvettern.py` trennt über Klub/Jahrgang der Rangliste,
  nur bei durchmischten Auftritten. Sechs Personen getrennt; Giger Elo
  1970 → 2100; Test-Log-Loss 0.7495 → 0.7404.
- **Feste-Seite mit Rückblick** (Festsieger, Kränze, Teilnehmer je Saison);
  **Festsiege** im Schwinger-Profil statt eines „grössten Erfolgs" aus der
  Anlaufphase 2023. Überraschungs-Index erst nach der Einschwingphase.
- **Karte** über den Klub statt nur Porträts (2517 statt ~700 Schwinger),
  gezählt ab 5 Gängen.
- Anzeige: „Südwestschweiz" statt Datenschlüssel, Schwungnamen gross,
  einheitlich „Vorname Nachname", Zahlen mit Tausendertrennzeichen, veraltete
  Texte (Demodaten, Parsing-Warnungen) ersetzt.
- Aufgeräumt: ungenutzter Code entfernt (u. a. `schema.Gang` als Doppelung
  von `labels.GangResultat`), Anzeigetexte zentral in `web/lib/labels.ts`,
  Echte-Daten-Harness ins Repo (`pipeline/harness.py`), `CLAUDE.md` für
  KI-Assistenten.
