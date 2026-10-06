# Modell im Detail

Wie die Prognose entsteht, was gemessen wurde und warum es so gebaut ist.
Kurzfassung im [README](../README.md#das-modell), Planung und offene Punkte in
der [ROADMAP](../ROADMAP.md). Die Zahlen stammen jeweils aus der Messung zum
genannten Zeitpunkt; aktuelle Werte stehen in `artifacts/report.json` und auf
der Analyse-Seite.

## Bausteine

**Stand 05.10.2026** (Merkmalsversion 3, Rating-Version 2, zweistufiges
Gradient Boosting, Test = Saison 2026, 37'747 Gänge, die das Modell nie
gesehen hat): Log-Loss **0.6829** (Logistic Regression: 0.6938, Elo-Formel
0.8006), Accuracy **70.4 %** (95 %-Bereich über die Feste 69.7–71.2 %, Elo
66.2 %), Gestellt 20.5 % vorhergesagt bei 21.0 % eingetreten,
Kalibrierungsfehler 0.7 Prozentpunkte. Die aktuellen Zahlen
stehen immer in `artifacts/report.json` und auf der Analyse-Seite, ihr
Verlauf in `artifacts/report_verlauf.json`.

* **Elo-Baseline** (`ratings.py`): chronologisch fortgeschrieben, K-Faktor nach
  Fest-Wichtigkeit gewichtet. Seit Rating-Version 2 (05.10.2026) K 56 statt
  24, und wer neu ist, bewegt sich am Anfang stärker (K x8 im ersten Gang,
  x1.6 nach 100 Gängen) — gemessen in beiden Jahren besser, Zahlen in
  `config.py`. Jedes komplexere Modell muss die Elo-Prognose schlagen.
* **Merkmale** (`features.py`): **leak-freie** A-minus-B-Merkmale —
  Rating-Vorsprung und -Nähe, Form, Kranzstatus, Alter, Gewicht/Grösse,
  Erfahrung, Verband, bevorzugte Schwünge, Kopf-an-Kopf-Bilanz, Gestellt-
  Neigung und -Bilanz, Niveau der Paarung und die Datenlage (`portraet_diff`,
  s. unten). Alle Merkmale nutzen nur Daten von **vor** dem Gang; Holdout ist
  die jüngste Saison, kein zufälliger Split. Trainiert wird mit Spiegelzeilen
  (jeder Gang zusätzlich als B-gegen-A); **bewertet wird ohne sie** — sonst
  stünde jeder Testgang doppelt drin. Die Elo-Baseline wird auf **genau
  denselben** Gängen gemessen wie das Modell.
* **Prognosemodell** (`modell.py`, s. unten „Gradient Boosting"): zwei
  Stufen — erst P(Gestellt), dann P(Sieg A | entschieden) —, beide als
  Gradient Boosting mit Monotonie-Vorgaben, gemittelt mit der gespiegelten
  Paarung. Die Logistic Regression bleibt als Rückfall
  (`config.MODELL_TYP = "lr"`) und als Benchmark-Kandidat.
* **Zwei Modelle je Lauf** (`train.trainiere`): das **Evaluationsmodell**
  sieht die jüngste Saison nicht und liefert alle Kennzahlen; **ausgeliefert**
  (`model.json`) wird danach eines mit denselben Einstellungen, das zusätzlich
  auf dieser Saison trainiert ist. Sonst lernte die App nie aus der laufenden
  Saison — rückwirkend kostet eine fehlende Saison 0.009 Log-Loss (Test 2026
  mit Training bis 2024: 0.7294, bis 2025: 0.7207).
* **Jüngere Gänge zählen mehr**: Stichprobengewicht mit Halbwertszeit 365
  Tage (`config.GBM_HALBWERTSZEIT_TAGE`). Validierung 0.7400 → 0.7390, Test
  0.7207 → 0.7203; 180 und 540 Tage waren je in einem Jahr schlechter.
* **5-Wege-Benchmark** (`benchmark.py`): Kranz-Heuristik / reine Elo / ML ohne
  Elo / Logistic Regression / Produktionsmodell auf demselben Holdout, mit
  Accuracy, Brier-Score sowie MAE und MSE (s. unten).
* **K-Means + KNN** (`clustering.py`): Cluster-Anzahl per Silhouette-Score.
* **Clientseitige Inferenz** (`web/lib/inference.ts`, `web/lib/kopfAnKopf.ts`)
  spiegelt `features.py` in TypeScript — eine Handkopie, die still
  auseinanderlaufen kann (ist schon einmal passiert). `verify_inference.py`
  prüft nur `model.json` gegen sklearn, mit dem **Python**-Vektor (beim
  Boosting prüft das schon der Export, `export.pruefe_modell_export`). Die
  TypeScript-Seite prüft **`pipeline/paritaet.py`**: Python erzeugt ~330
  Prüffälle aus den echten Artefakten (alle vier Porträt/Stub-Kombinationen,
  Kopf-an-Kopf in beiden Richtungen, fehlendes Rating), `npm run paritaet`
  rechnet sie mit den kompilierten TS-Modulen nach — Merkmale, Kopf-an-Kopf
  und Wahrscheinlichkeiten getrennt. Läuft in jedem PR (CI-Job
  `inferenz-paritaet`) und im täglichen Lauf **vor** dem Commit neuer
  Artefakte. Per Mutationstest belegt, dass er anschlägt: vertauschte
  Kopf-an-Kopf-Richtung, falsches Vorzeichen, falsche Skala, fehlendes
  Merkmal, fehlender Intercept — alle erkannt. Die Gruppe `modell-lr` prüft,
  dass die App ein LR-`model.json` (das vorige Prod-Modell) weiter richtig
  rechnet.

  Neue Merkmale **nur hinten** an `FEATURE_NAMES` anhängen: `model.json` ist
  positionsgebunden, und die App kürzt den Vektor auf die Merkmale, die das
  ausgelieferte Modell kennt. Ändert sich die **Definition** eines Merkmals,
  steigt `MERKMAL_VERSION` (`config.py`): sie steht in `model.json`, und App
  wie Python rechnen ein älteres ausgeliefertes Modell mit **dessen**
  Definition weiter. Die Paritätsprüfung testet das für jede ältere Version
  (Gruppen `modell-v1`, `modell-v2`).

## Merkmalsversion 2: Stand vor dem Fest, Gestellt-Neigung

Gemessen an echten Daten, Test 2026 (36'485 Gänge) und Validierung 2025
jeweils gleichsinnig:

| Schritt | Log-Loss Test | (Validierung) | Accuracy | AUC Gestellt |
|---|---:|---:|---:|---:|
| Version 1 | 0.8314 | (0.8537) | 63.9 % | 0.640 |
| + alle Gänge eines Fests sehen den Stand **vor** dem Fest | 0.8204 | (0.8415) | 64.5 % | 0.645 |
| + **Gestellt-Neigung** je Schwinger | 0.7923 | (0.8131) | 65.8 % | 0.722 |
| + Erfahrung **logarithmisch** | 0.7582 | (0.7876) | 67.8 % | 0.732 |
| + Elo-Abstand **pro Streuung** + **Einschwingphase** | **0.7503** | (**0.7771**) | **68.2 %** | **0.736** |

* **Stand vor dem Fest.** Vorher bekam jeder Gang den Stand nach den im selben
  Fest zuvor *verarbeiteten* Gängen, und die Verarbeitungsreihenfolge folgt der
  Statistik-PDF, also dem Schlussrang. Die App prognostiziert dagegen immer aus
  dem Stand vor einem Fest — Training und Betrieb passten nicht zusammen.
* **Gestellt-Neigung.** Wie oft ein Schwinger stellt, ist eine stabile
  Eigenschaft (erste gegen zweite Karrierehälfte r = 0.67, Spanne 0–63 %).
  Anteil gestellter Gänge, geschrumpft gegen den Durchschnitt (20 „Phantom-
  Gänge"); Merkmal = Mittel beider Schwinger minus Durchschnitt. Symmetrisch —
  bevorzugt niemanden, sagt nur, wie wahrscheinlich ein Gestellter ist.
* **Erfahrung logarithmisch.** Der Median an Gängen wächst von 15 (2023) auf
  126 (2026); als rohe Differenz verzerrt das jedes Jahr mehr.
* **Elo-Abstand pro Streuung.** Die Streuung der aktiven Ratings wächst,
  solange das System einschwingt (2023: 41, 2026: 126). Ohne Skalierung sagte
  das Modell 2026 18.3 % Gestellt voraus bei 21.1 % eingetreten; mit ihr 20.5 %.
* **Einschwingphase.** Das erste Datenjahr liefert Historie, geht aber nicht
  ins Training (Ratings noch nicht eingeschwungen, Gestellt-Quote 28.4 % statt
  ~21.5 % in jedem späteren Jahr und jedem Festtyp).

Verworfen, weil gemessen schlechter: `class_weight="balanced"` (Recall
Gestellt 21 % → 46 %, aber P(Gestellt) 30 % statt 21 %, Log-Loss 0.7503 →
0.7741 — die App zeigt Wahrscheinlichkeiten, keine Klassen) und andere
Regularisierung (C = 0.1 … 10 ohne Unterschied). `report.json` →
`gestellt_kalibrierung` misst jetzt eigens, ob P(Gestellt) stimmt; die
Analyse-Seite zeigt die Kalibrierungskurve.

## Merkmalsversion 3: Spitzenpaarungen und Gestellt-Bilanz des Paars

Anlass: Orlik gegen Staudenmann bekam 17 / 18 / 65 %, obwohl die beiden fünf
ihrer sechs Duelle gestellt haben. Die Nachmessung zeigte, dass das kein
Einzelfall war. Version 2 unterschätzte Gestellt genau bei den Paarungen, auf
die man schaut:

| Test 2026 — P(Gestellt) vorhergesagt / eingetreten | Version 2 | Version 3 |
|---|---:|---:|
| oberstes 1 % nach Stärke des Paars (306 Gänge) | 18.2 % / 29.7 % | **29.6 %** / 29.7 % |
| ≥ 2 frühere Duelle, davon ≥ die Hälfte gestellt (972) | 32.5 % / 42.1 % | **40.1 %** / 42.1 % |
| alle Testgänge | 20.5 % / 21.1 % | 20.6 % / 21.1 % |

Log-Loss Test 0.7503 → **0.7491** (Validierung 2025: 0.7771 → **0.7757**),
Accuracy 68.2 % → **68.5 %**, AUC Gestellt 0.736 → **0.738**.

* **Spitzen-Niveau** (`spitzen_niveau`): wie stark der *schwächere* der beiden
  ist, in Streuungen über dem Startwert, unten bei 0 abgeschnitten. Hoch nur,
  wenn beide stark sind. Spitzenschwinger schlagen das Feld und haben darum
  eine tiefe Gestellt-Neigung (Staudenmann 17 %). Treffen zwei aufeinander,
  wird aber viel öfter gestellt: 34 % ab 1 Streuung, 45–61 % ab 4. Version 2
  sagte mit steigendem Niveau sogar *weniger* Gestellte voraus.
* **Gestellt-Bilanz des Paars** (`paar_gestellt`): Anteil gestellter
  bisheriger Duelle, gegen die Erwartung aus beiden Einzelneigungen
  geschrumpft (4 „Phantom-Duelle", K = 2 … 16 gleichauf), minus diese
  Erwartung; ohne Duelle 0. Das bestehende Merkmal `kopf_an_kopf` zählt
  Gestellte als halben Sieg, also fast als „kein Signal".

Orlik gegen Staudenmann steht damit bei 11 / 54 / 36 %.

## Gradient Boosting statt Logistic Regression (26.09.2026)

Mit **denselben 16 Merkmalen**, gemessen mit `pipeline/harness.py`:

| Test 2026 (Validierung 2025) | Log-Loss | Accuracy | AUC Gestellt |
|---|---:|---:|---:|
| Logistic Regression | 0.7400 (0.7627) | 68.6 % | 0.741 |
| Gradient Boosting, drei Klassen | 0.7206 (0.7388) | 68.9 % | 0.751 |
| **Gradient Boosting, zweistufig mit Monotonie** | **0.7207 (0.7400)** | **69.0 %** | **0.751** |

Der Gewinn ist grösser als die Merkmalsversionen 2 → 3 zusammen. Er steckt
in Wechselwirkungen: die LR überschätzte Aussenseiter (19.4 % vorhergesagt,
15.7 % eingetreten) und unterschätzte Favoriten; nichtlineare Zusatzmerkmale
für die LR (d·|d|, d³, Elo-Trend) holten davon nur 0.001 zurück.

**Warum zweistufig.** Das Drei-Klassen-Boosting lernte in dünn besetzten
Ecken Unsinn: bei 7–8 % der Paare mit Vorgeschichte **senkte** eine hohe
Gestellt-Bilanz die Gestellt-Chance — ausgerechnet Orlik gegen Staudenmann
(5 von 6 Duellen gestellt) zeigte „Gestellt-Bilanz: −8.7 %-Pkt.". Monotonie-
Vorgaben kann sklearn nur für zwei Klassen. Darum zwei Stufen:

```
g = P(Gestellt)                 monoton: Gestellt-Bilanz ↑, Gestellt-Neigung ↑, Rating-Abstand ↓
s = P(Sieg A | entschieden)     monoton: Rating-Vorsprung ↑, Kopf-an-Kopf ↑
P = [(1 − g)·s,  g,  (1 − g)·(1 − s)]
```

Fehlrichtungen danach 0 %, Log-Loss praktisch gleich. Mehr Vorgaben (Form,
Kranz, Erfahrung) kosteten 0.005–0.007 — Erfahrung wirkt tatsächlich nicht
monoton. Die Gestellt-Kalibrierung stimmt über alle zehn Stufen, auch im
obersten Zehntel (51.7 % vorhergesagt, 51.7 % eingetreten).

* **Symmetrie erzwungen.** Bäume sind nicht von selbst paar-symmetrisch. Beide
  Stufen werden mit der gespiegelten Paarung x′ gemittelt:
  g = (g(x) + g(x′)) / 2, s = (s(x) + 1 − s(x′)) / 2. „Orlik gegen
  Staudenmann" ist so exakt „Staudenmann gegen Orlik" mit vertauschten Siegen.
* **Baumzahl zeitlich gewählt**, je Stufe auf den jüngsten 15 % der
  Trainingsdaten (sklearns eingebautes Early Stopping zieht zufällig — mit
  Spiegelzeilen und Gängen desselben Fests auf beiden Seiten zu optimistisch).
* **Export.** `model.json` enthält je Stufe Startwert und Bäume (innerer
  Knoten `[Merkmal, Schwelle, links, rechts]`, Blatt = Wert), kompakt rund
  0.26 MB (gzip ~90 kB). Der Export rechnet das JSON wie die App nach und
  bricht ab, wenn es mehr als 1e-5 vom trainierten Modell abweicht.
* **Kopf-an-Kopf bitgleich.** Bäume trennen an exakten Schwellen; darum ist
  `kopf_an_kopf` so formuliert, dass Python und TypeScript bitgleich rechnen
  und A/B-Tausch exakt das Vorzeichen dreht: (2·Punkte_A − n) / (n + K).
* **Erklärbalken** bleiben die Gegenprobe (Merkmal auf den Durchschnitt,
  neu rechnen). Bei Bäumen addieren sie sich nicht exakt zur Prognose; der
  Hilfetext sagt das.
* **Merkmalswichtigkeit** ist beim Boosting die Permutations-Wichtigkeit: um
  so viel steigt der Log-Loss auf den Testgängen, wenn das Merkmal zufällig
  vertauscht wird.

Orlik gegen Staudenmann steht jetzt bei 13 / 58 / 29 %.

## Schnelleres Rating und saubere Daten (05.10.2026)

Drei Schritte, jeder in Validierung 2025 **und** Test 2026 besser:

| Schritt | Test 2026: Log-Loss / Treffer |
|---|---:|
| Gradient Boosting (Stand 04.10.) | 0.7199 / 69.1 % |
| **Rating-Version 2**: K 56 statt 24, Neulings-Bonus (K x8 im ersten Gang) | 0.6947 / 70.0 % |
| **D4**: Niederlage „0" in den PDFs bis Anfang 2024 richtig gelesen | 0.6935 / 70.0 % |
| **D5**: Namensvettern über Klub, Wohnort und Punktetotal getrennt | **0.6829 / 70.4 %** |

* **Rating.** Die Ratings waren 2026 noch nicht eingeschwungen, die
  Elo-Formel zu zaghaft. Ein schnelleres K und ein Rating, das sich am
  Anfang stärker bewegt (der Kern von Glicko), holen das auf. Messreihe und
  verworfene Varianten in `config.py` bei `ELO_K`.
* **D4.** Die Statistik-PDFs bis Anfang 2024 schreiben die Niederlage als
  Ziffer 0; als Rang gelesen, verschob das 2023 fast alle Gänge. Einseitig
  belegte Gänge 15.7 % → 0.16 %, Gestellt-Quote 2023 28.5 % → 20.6 %.
* **D5.** 18 Personen getrennt, die unter einem Namen zusammengelegt waren
  (darunter sehr aktive wie Fankhauser, 82 Feste). Ihr gemischtes Rating
  verzerrte auch die Ratings ihrer Gegner. Details in
  [DATEN.md](DATEN.md#schwinger-identität-und-namensvettern) und der
  ROADMAP (D4, D5).

## Prognose-Check je Fest

Wie gut lag die Prognose an einem bestimmten Fest? `prognose_check.py`
rechnet jede auswertbare Saison mit dem Modell, das **vor** ihr galt (trainiert
auf allem davor), und dem Stand jedes Schwingers vor seinem Fest — also genau
die Prognose, die man damals hätte sehen können. Je Fest stehen in
`events.json`: Trefferquote (wahrscheinlichster Ausgang trat ein), dieselbe
für die reine Elo-Prognose, die mittlere Wahrscheinlichkeit für den
tatsächlichen Ausgang und Gestellt vorhergesagt/eingetreten; je Saison
`prognose_check_saisons`. Ausgewertet werden die Holdout-Saison und jede
frühere, vor der mindestens eine halbe eingeschwungene Saison liegt (heute
2025 und 2026).

| Saison | Gänge | Treffer | Elo | P(tatsächlicher Ausgang) |
|---|---:|---:|---:|---:|
| 2025 | 37'164 | 69.2 % | 65.1 % | 59.1 % |
| 2026 | 37'747 | 70.4 % | 66.2 % | 60.3 % |

Kantonal- und Teilverbandsfeste liegen meist bei 68–75 %, Bergfeste und das
Eidgenössische deutlich tiefer (58–62 %): dort treffen mehr Spitzenschwinger
aufeinander, und es wird öfter gestellt.

## Fest-Simulator (Monte Carlo)

`fest_simulation.py` (Python) und `web/lib/simulation.ts` (App) spielen ein
ganzes Fest tausendfach durch. Aus den Paar-Wahrscheinlichkeiten des Modells
entsteht, was ein Einzelgang nicht sagt: Festsieg-, Schlussgang- und
Kranzchance je Schwinger.

| Baustein | Regel | Herkunft |
|---|---|---|
| Einteilung Gang 1 | stärkste 20 % nach Elo gegeneinander, Rest gemischt | kalibriert an den echten Paarungen 2026 |
| Einteilung Gang 2.. | nach Punkten mit Ermessensspielraum (Punkte + 1.0 × Zufall), keine Wiederholung | Elo-Abstand der Gegner real 108 / simuliert 116; Gestellte real 22.1 % / simuliert 21.6 % (streng nach Punkten: 55 / 30 %) |
| Noten | Sieg 10.00 in 52 % (sonst 9.75), Gestellt 9.00 in 31 % (sonst 8.75), Niederlage 8.75 in 11 % (sonst 8.50); Schlussgang 10.00 / 8.75 | gemessen auf den Rohdaten (Messung `noten`) |
| Ausstich | Kranzfeste: nach Gang 4 schwingen 80 % weiter; ESAF: 82 % nach Gang 4, 55 % nach Gang 6 | Gangzahlen je Teilnehmer 2025/26 |
| Schlussgang / Festsieg | die zwei Punktbesten; bei gestelltem Schlussgang der Punktbeste | Reglement |
| Kränze | beste 16 % (ESAF 15 %), Punktgleichheit an der Grenze eingeschlossen | Kranzquote 15–18 % |

Plausibilität: die simulierte Kranzgrenze liegt an Kantonalfesten bei
Ø 56.6 Punkten (Richtwert 56.50), am ESAF mit 8 Gängen bei rund 75.
Python und TypeScript rechnen bei gleichem Startwert exakt dieselben
Zählungen (mulberry32, gleiche Reihenfolge der Zufallszahlen; geprüft in der
Paritätsprüfung).

**Rückblick** (`fest_simulation.backtest`, täglich im Pipeline-Lauf, Ergebnis
in `simulation_backtest.json`): jedes Kranzfest der Holdout-Saison wird mit
dem Modell von vor der Saison und dem Stand jedes Schwingers vor dem Fest
simuliert und mit der Schlussrangliste verglichen, dazu dieselbe Simulation
mit reinen Elo-Wahrscheinlichkeiten.

## Modellgüte im Verlauf

Jeder Lauf hängt eine Zeile an `artifacts/report_verlauf.json` (je Tag und
Modellstand, höchstens 730 Einträge; vor dem 26.09.2026 aus der Git-Historie
nachgetragen, `scripts/verlauf_aus_git.py`). Liegt der Log-Loss mehr als 0.01
über dem Median der letzten 14 vergleichbaren Läufe (gleiches Holdout-Jahr,
Modelltyp und Merkmalsversion), warnt der Datenqualitätsbericht. Die
Analyse-Seite zeigt Log-Loss und Accuracy als Verlauf.

## Erklärbalken: wem ein Merkmal nützt

Ein Balken zeigt, um wie viele Prozentpunkte die Siegchance des genannten
Schwingers durch dieses Merkmal höher ist. **Symmetrische** Merkmale —
Ausgeglichenheit, gleicher Verband, ähnlicher Stil, Gestellt-Neigung,
Gestellt-Bilanz des Paars, Niveau der Paarung — bleiben
beim Tausch von A und B gleich; das Modell hat für sie bei „Sieg A" und
„Sieg B" dasselbe Gewicht. Sie verschieben nur zwischen „einer gewinnt" und
„Gestellt" und erscheinen darum neutral als **„Gestellt ± X %-Pkt."**.
Früher wurden sie an P(Sieg A) gemessen und dem Gegner gutgeschrieben, sobald
diese sank: „Gleicher Verband: Moser +7 %-Pkt." bei Staudenmann gegen Moser,
obwohl auch Mosers Chance dadurch sank (Staudenmann −7.1, Gestellt +8.5,
Moser −1.5). Der Effekt selbst ist echt, aber klein: Duelle im gleichen
Verband enden in den Daten 30.5 % gestellt statt 28.8 %, in jedem Festtyp.

## Datenlage: Porträt oder Stub

76 % des Kaders haben kein schlussgang.ch-Porträt und damit weder Physis noch
Verband noch Schwünge noch Kranzstatus. schlussgang.ch porträtiert **nur
Kranzer und besser** (706 von 706 Porträts), Stubs haben immer `kein`. Und
Porträt-Schwinger schlagen Stubs deutlich:

| Konstellation | A siegt | B siegt |
|---|---:|---:|
| beide Stub | 39.0 % | 40.0 % |
| beide Porträt | 34.4 % | 35.6 % |
| A Stub, B Porträt | 12.6 % | **68.8 %** |
| A Porträt, B Stub | **67.0 %** | 13.5 % |

Ohne ein eigenes Merkmal dafür lernte das Modell diese Datenlücke über
Ersatzgrössen — vor allem über `kranz_diff`, das bei jedem Stub strukturell 0
ist — und die App begründete eine Prognose dann mit „Kranzstärke", wo in
Wahrheit „hat ein Profil" stand. Darum:

* **`portraet_diff`** (Porträt A − Porträt B) macht die Datenlage zu einem
  offenen Merkmal; die App zeigt es als „Datenlage".
* Merkmale, die für eine Paarung auf **fehlenden Daten** beruhen (Physis,
  Alter, Verband, Schwünge, Kranzstatus), erscheinen **nicht mehr als Grund**.
  Die Wahrscheinlichkeit ändert sich dadurch nicht, nur die Begründung.
* `report.json` → `nur_portraet` misst Modell **und** Elo-Baseline zusätzlich
  nur auf Porträt-gegen-Porträt-Gängen. Nur dort liegen die wrestlerischen
  Merkmale auf beiden Seiten vor.

Eine Folge davon: die Ergebnisverteilung (`sieg_a` rund 35 %, `sieg_b` rund
42 %) ist **kein Signal**. A und B werden alphabetisch per ID vergeben, und
Stub-IDs sortieren systematisch häufiger nach vorne (29'690 gemischte
Paarungen mit Stub vorne gegen 16'134 umgekehrt).

## MAE und MSE — Fehlermasse in der Einheit des Ergebnisses

Log-Loss und Brier-Score bewerten eine Wahrscheinlichkeitsverteilung, sind aber
nicht als "so weit daneben" lesbar. `metriken.py` ergänzt die beiden klassischen
Fehlermasse für numerische Vorhersagen:

    MAE = 1/n * sum |y - yhat|      alle Fehler zählen gleich, Einheit = Target
    MSE = 1/n * sum (y - yhat)^2    grosse Fehler zählen überproportional

Das Modell sagt allerdings keine Zahl vorher, sondern eine Verteilung über
`sieg_a / gestellt / sieg_b`. Als numerisches Target dient deshalb der
**Punktwert eines Gangs aus Sicht von Schwinger A** — genau die Konvention, die
die Elo-Stufe ohnehin schon benutzt (`ratings.py`: Sieg=1, Gestellt=0.5,
Niederlage=0):

    y    = 1.0 / 0.5 / 0.0  (tatsächlicher Ausgang)
    yhat = P(sieg_a)*1.0 + P(gestellt)*0.5 + P(sieg_b)*0.0

MAE ist damit direkt lesbar: "im Schnitt X Punktwert neben dem tatsächlichen
Ausgang". MSE steht im Quadrat dieser Einheit und ist nur im Vergleich
zwischen Kandidaten interessant.

**Nicht dasselbe wie der Brier-Score:** der misst die quadratische Abweichung
über den *ganzen* Wahrscheinlichkeitsvektor (inkl. Kalibrierung der
Gestellt-Klasse). MAE/MSE verdichten die Prognose vorher auf eine Zahl. Ein
Modell kann den erwarteten Punktwert gut treffen und trotzdem schlecht
kalibriert sein — 50/0/50 statt 0/100/0 ergibt denselben Punktwert 0.5, aber
einen deutlich schlechteren Brier-Score.

Genau deshalb stehen beide Masse nebeneinander — sie können Kandidaten
unterschiedlich reihen. Auf dem synthetischen Datensatz (`--source synth`,
offline reproduzierbar) sieht man das direkt:

| Kandidat        | Accuracy | Brier | MAE | MSE |
|-----------------|---------:|------:|----:|----:|
| kranz_heuristik |   0.6045 | 0.7911 | **0.2212** | 0.1341 |
| elo_baseline    |   0.7265 | 0.4647 | 0.3533 | 0.1471 |
| ml_ohne_elo     |   0.7019 | 0.4063 | 0.2685 | 0.1234 |
| ml_komplett     |   0.7312 | **0.3819** | 0.2396 | **0.1117** |

Die Kranz-Heuristik hat hier den **besten MAE** und zugleich den **schlechtesten
Brier-Score**: bei Kranz-Gleichstand sagt sie "gestellt" (= Punktwert 0.5) und
liegt damit selten weit daneben, ihre harten 1/0-Prognosen sind im Irrtum aber
maximal teuer — was erst das Quadrieren sichtbar macht. Nach MAE allein wäre
sie das beste Modell, was sie offensichtlich nicht ist. Die Zahlen auf den
echten Daten stehen in `artifacts/benchmark.json` und werden bei jedem Lauf neu
geschrieben.

## Warum der ältere Schwinger beim Alters-Merkmal im Vorteil ist

Gemessen noch mit der Logistic Regression (Merkmalsversion 1): `alter_diff`
(Alter A − Alter B) hatte für `sieg_a` einen **positiven** Koeffizienten
(+0.0197). Älter zu sein zählte im Modell also leicht **für**
einen Schwinger — was der Anschauung „Frische" widerspricht, aber genau das
ist, was in den Daten steht:

| A ist … | n | Sieg A | gestellt | Sieg B |
|---|---:|---:|---:|---:|
| älter | 17'074 | **40.0 %** | 29.6 % | 30.3 % |
| gleich alt | 2'135 | 33.9 % | 30.2 % | 36.0 % |
| jünger | 17'900 | 29.1 % | 30.1 % | **40.8 %** |

Der Zusammenhang ist über den ganzen Bereich monoton (bei −12 Jahren 23.2 %
Siegquote, bei +12 Jahren 45.4 %). Im Aktivschwinger-Feld heisst „älter" in
aller Regel „ausgereift", nicht „verbraucht"; die Jüngsten sind 18–21 und noch
im Aufbau. Das Merkmal ist mit Koeffizient 0.0197 gegenüber `rating_diff`
(0.747) allerdings rund 38-mal schwächer — Elo trägt den Löwenanteil, `alter_diff`
nur einen Rest, den Elo noch nicht eingepreist hat.

Die UI beschriftet das Merkmal deshalb neutral mit **„Alter"**. Der frühere
Titel „Frische" behauptete eine Richtung, die das Modell nie gelernt hat.

Fehlende Werte (z. B. Gewicht bei Schwingern ohne Porträt) werden in den
Differenz-Merkmalen als `0.0` imputiert — die Merkmale tragen für solche Paare
also kein Signal.
