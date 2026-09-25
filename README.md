# Schwingen ML

Datengetriebene, **erklärbare** Prognose für Schwingen-Gänge — trainiert auf
echten Resultaten von [schlussgang.ch](https://www.schlussgang.ch). Für ein
Schwinger-Paar die Wahrscheinlichkeit von **Sieg A / Gestellt / Sieg B**, plus
Rangliste, Kopf-an-Kopf-Historie, Schweiz-Karte, K-Means-Clustering der
Schwingertypen und eine 4-Wege-Modellevaluierung.

Prognosen sind **informativ, kein Wettangebot**.

**Live:** [schwingen-ml.vercel.app](https://schwingen-ml.vercel.app/)

---

## Zweck

Die Frage ist nicht nur „wer gewinnt", sondern **warum**. Jede Prognose weist
ihre Merkmalsbeiträge aus, und jedes Modell muss sich gegen eine ehrliche
Elo-Baseline behaupten — ein Modell, das die Baseline nicht schlägt, ist keine
Verbesserung, egal wie aufwendig es ist.

---

## Was die App kann

| Seite | Was man sieht |
|---|---|
| **Prognose** | Zwei Schwinger wählen → Sieg-A/Gestellt/Sieg-B-Wahrscheinlichkeit mit Merkmalsbeiträgen, Kopf-an-Kopf-Historie, teilbarer Link (`?a=…&b=…`). |
| **Schwinger** | Alle erfassten Schwinger, durchsuchbar, nach Elo sortiert. Profil zeigt Überraschungs-Index (Elo-erwartete vs. tatsächliche Leistung) und per KNN ähnliche Schwinger. |
| **Feste** | Vergangene Feste; kommende Feste der nächsten 60 Tage. Je veröffentlichter Paarung Prognose + informative Quote; ohne Startliste keine Prognose, sondern nur die belegten Angaben zum Fest. |
| **Karte** | Choroplethen-Karte (Elo-Schnitt, Siegquote, Anteil Top-Schwinger, Kaderbreite) — Bern nach seinen 6 Gauverbänden statt als ein Kanton. |
| **Typen** | K-Means-Clustering über das volle Schwinger-Profil, Cluster-Anzahl per Silhouette-Score gewählt, mit PCA-Streudiagramm. |
| **Analyse** | Modellgüte vs. Elo-Baseline, Konfusionsmatrix, Kalibrierung der Gestellt-Chance, Merkmalswichtigkeit, 4-Wege-Benchmark. |

---

## Woher die Daten kommen

Einzige Quelle ist **schlussgang.ch**. Es gibt keine manuell gepflegten
Datenbestände — alles ist jederzeit aus der Quelle reproduzierbar.

| Was | Woher | Modul |
|---|---|---|
| Abgeschlossene Feste | JSON:API `backend-api.schlussgang.ch/jsonapi/node/event` (gefiltert auf `field_event_state=finished`) | `scrape/schlussgang_resultate.py` |
| Gänge (Symbol + Note je Gang) | Statistik-PDF je Fest (`…/event-ranking-list/<nid>-statistic-final.pdf`) | `scrape/schlussgang_pdf.py` |
| Porträts (Gewicht, Grösse, Verband, Kranzstatus, Schwünge) | JSON:API `node/portrait` | `scrape/schlussgang_portraet.py` |
| Kommende Feste | JSON:API `node/event`, ab heute (Agenda-HTML als Fallback) | `scrape/agenda.py` |

`scrape/http.py` ist ein höflicher Client: Rate-Limit pro Host, echter
User-Agent, `robots.txt` wird respektiert.

### Wie ein Gang gelesen wird

Die Statistik-PDFs nutzen die offizielle Schwingen-Notation. Pro Schwinger ein
Block, pro Gang eine Zeile mit Symbol, Gegnername und Note:

| Symbol | Bedeutung | Note |
|:--:|---|---|
| `+` | Sieg | 9.75 – 10.00 |
| `-` | Gestellt | 8.75 – 9.00 |
| `o` | Niederlage | ≤ 8.75 |

Jeder Gang steht **zweimal** im PDF (einmal je Perspektive). `labels.py` führt
beide zusammen und prüft sie gegeneinander: `+` muss `o` gegenüberstehen, `-`
muss `-` gegenüberstehen. Widersprüchliche Paare werden verworfen und gezählt,
nicht stillschweigend übernommen.

### Schwinger-Identität

schlussgang.ch schreibt denselben Schwinger unterschiedlich: Porträts als
`Vorname Nachname`, Statistik-PDFs als `Nachname Vorname`. `identity.py` löst
das über einen **reihenfolgeunabhängigen Schlüssel** aus der sortierten
Token-Menge des Namens. Ist ein Name mehrdeutig (zwei echte Namensvettern),
wird er als unauflösbar gemeldet statt geraten — lieber ein sichtbar fehlender
Gang als ein falsch zugeordneter.

Teilnehmer ohne Porträt werden als „Stub" geführt: ihre Gänge zählen voll,
Physis/Alter/Verband fehlen. Das betrifft die Mehrheit des Kaders, weil
schlussgang.ch nicht für jeden Schwinger ein Porträt führt.

---

## Datenworkflow

```
schlussgang.ch
   │  JSON:API + Statistik-PDFs
   ▼
pipeline.fetch_raw ──────────►  artifacts/raw/     (nicht versioniert, gecacht)
   │                              events.json · gaenge.json
   │                              schlussgang_portraits.json · schwinger.json
   ▼
pipeline.run_pipeline
   Labels → Elo → Merkmale → Training → Benchmark → Clustering
   ▼
artifacts/*.json  +  web/public/data/*.json        (versioniert)
   │  Commit löst Vercel-Deploy aus
   ▼
Next.js — lädt JSON, rechnet die Prognose CLIENTSEITIG
```

`artifacts/raw/` ist bewusst nicht im Repo (`gaenge.json` allein > 50 MB und
würde bei täglichem Lauf unbegrenzt wachsen). Versioniert werden nur die
kompakten, abgeleiteten Artefakte.

### Automatischer täglicher Download

`.github/workflows/update.yml` läuft täglich um 04:00 UTC:

1. **Rohdaten-Cache laden** (`actions/cache`) — trägt die Historie über Läufe.
2. **`pipeline.fetch_raw --seit-datum auto`** — holt Feste ab dem jüngsten
   bereits bekannten Fest minus 14 Tage Überlappung (fängt nachgetragene
   Resultate ein). Der Kader wird danach **komplett neu** aus Porträts +
   PDF-Namen gebaut, nie inkrementell fortgeschrieben.
3. **`pipeline.run_pipeline --source scrape`** — trainiert und exportiert.
4. **`pipeline.verify_inference`** — prüft, dass die exportierten Gewichte in
   `model.json` dieselben Wahrscheinlichkeiten liefern wie das sklearn-Modell.
5. **`pipeline.paritaet`** + **`npm run paritaet`** — rechnet echte Fälle mit
   der App-Logik (TypeScript) nach und bricht bei jeder Abweichung ab, **bevor**
   die neuen Artefakte auf Prod gehen (s. unten).
6. **`pipeline.datenqualitaet`** — schreibt den Qualitätsbericht ins
   Job-Summary des Actions-Laufs.
7. **Artefakte committen** — Vercel deployt automatisch.

Der Lauf **bricht ab, statt schlechte Daten zu committen**, wenn

* mehr als 25 % der Roh-Einträge verworfen werden (Verarbeitung defekt), oder
* die Rohabdeckung gegenüber dem Vorlauf einbricht (Cache verloren), oder
* die abgeleiteten Gänge einbrechen, obwohl die Rohabdeckung stimmt.

Ist der Cache je verloren, einmalig **Actions → Datenpipeline aktualisieren →
Run workflow → „Volle Historie ab 2023 neu laden"** starten.

> **Laufzeit:** Ein voller Refetch dauert rund **20 Minuten** — gemessen am Lauf
> vom 22.09.2026: 481 Feste, kompletter Job inkl. Training in 20 min. Die Dauer
> ergibt sich im Wesentlichen aus dem Rate-Limit (2 s je Statistik-PDF, NFR-4),
> also ~16 min reine Wartezeit. Die frühere Warnung „mehrere Stunden" stammte
> aus einem Lauf mit der defekten Blätterschleife der Fest-API, die dieselben
> Seiten endlos neu holte; seit deren Begrenzung stimmt sie nicht mehr.
> Der **tägliche inkrementelle Lauf** braucht rund 2 Minuten.

---

## Voraussetzungen

* **Python ≥ 3.11**
* **Node.js ≥ 20** (nur für die Web-App; Next 15 verlangt ≥ 18.18, Vercel baut mit 24.x)

**Abhängigkeiten der Web-App.** Next 15.5 statt 14: Next 14 bekommt keine
Sicherheitsfixes mehr — selbst die letzte 14er (14.2.35) hat 23 offene
Advisories, darunter Remote Code Execution in der Image-Optimierung und XSS im
App Router. `package.json` erzwingt per `overrides` zudem `postcss ≥ 8.5.28`,
weil auch Next 15.5 intern `postcss 8.4.31` pinnt (4 offene Advisories).
`npm audit --omit=dev` meldet damit 0 Befunde; die CI prüft das in jedem PR
(Job `abhaengigkeiten-audit`), Dependabot schlägt wöchentlich Updates vor
(`.github/dependabot.yml`).
* Netzzugriff auf `schlussgang.ch` / `backend-api.schlussgang.ch` (nur für
  echte Daten; der synthetische Modus läuft offline)

Python-Abhängigkeiten (`requirements-pipeline.txt`): `numpy`, `scikit-learn`,
`pdfplumber` (PDF-Parsing), `pytest`.

---

## Lokal ausführen

### Pipeline — synthetisch (offline, schnell)

```bash
pip install -r requirements-pipeline.txt
python -m pipeline.run_pipeline --source synth   # erzeugt alle Artefakte
python -m pipeline.verify_inference              # model.json == sklearn
python -m pipeline.paritaet && (cd web && npm run paritaet)   # App == Pipeline
python -m pytest pipeline/tests -q               # 190 Tests
```

> `--source synth` **überschreibt die Artefakte** mit Demodaten. Danach
> `git checkout -- artifacts/ web/public/data/ web/data/`, wenn die echten
> Artefakte erhalten bleiben sollen.

### Pipeline — echte Daten

```bash
# 1. Rohdaten holen (volle Historie; rund 20 Minuten, s. oben)
python -m pipeline.fetch_raw --seit-datum 2023-01-01

#    …oder nur nachführen, was seit dem letzten Lauf dazukam:
python -m pipeline.fetch_raw --seit-datum auto

# 2. Trainieren + Artefakte schreiben
python -m pipeline.run_pipeline --source scrape

# 3. Prüfen
python -m pipeline.verify_inference
python -m pipeline.datenqualitaet        # Datenqualitätsbericht
```

Beim ersten vollen Aufbau (kein Vorlauf zum Vergleich):
`python -m pipeline.run_pipeline --source scrape --ohne-volumenpruefung`.

### Web-App

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

Die App liest ausschliesslich die JSON-Dateien in `web/public/data/`. Ohne
vorherigen Pipeline-Lauf zeigt sie die im Repo eingecheckten Artefakte.

---

## Projektstruktur

```
pipeline/                  Python-Datenpipeline
  config.py                  Seeds, Pfade, Hyperparameter (reproduzierbar)
  schema.py                  Kanonisches Schema (Schwinger, Event, Gang)
  identity.py                Namensauflösung Porträt <-> PDF  ← kritisch
  roster.py                  Kader aus Porträts + PDF-Namen (zustandslos)
  labels.py                  Symbol → Ergebnis, Dedup, Konsistenzprüfung
  ratings.py                 Elo-Baseline, chronologisch/leak-frei
  features.py                A-minus-B-Merkmale, leak-frei
  train.py                   Logistic Regression + zeitliche Evaluation
  benchmark.py               4-Wege-Modellvergleich (Accuracy/Brier/MAE/MSE)
  metriken.py                MAE + MSE auf dem Punktwert des Gangs
  clustering.py              K-Means-Schwingertypen + KNN-Ähnlichkeit
  kantone.py                 Kantonal-/Gauverband → politischer Kanton
  export.py                  JSON-Artefakte schreiben
  fetch_raw.py               CLI: Webquellen → artifacts/raw
  run_pipeline.py            Orchestrator (8 Stufen)
  datenqualitaet.py          Qualitätsbericht aus report.json
  diagnose_agenda.py         CLI: warum die Vorschau "kommende Feste" leer ist
  diagnose_kranz.py          CLI: Gegenprobe zur Bedeutung des PDF-Sterns
  verify_inference.py        Cross-Check: model.json == sklearn-Modell
  paritaet.py                Cross-Check: App (TypeScript) == Pipeline (Python)
  synth.py                   Synthetischer Datensatz (offline/CI)
  scrape/                    schlussgang.ch-Scraper + Rohdaten-Einlesen
  tests/                     pytest
artifacts/                 Generierte Artefakte (versioniert, ausser raw/)
web/                       Next.js 15 (App Router) + React 19 + TypeScript
  lib/inference.ts           Clientseitige Inferenz (spiegelt features.py)
  app/                       Seiten
  public/data/               Artefakt-Kopie, die die App lädt
.github/workflows/         ci.yml (Tests + Build), update.yml (täglicher Lauf)
```

**Besonders wichtig:** `identity.py` und `roster.py` entscheiden, welche Gänge
überhaupt im Training landen; `labels.py` entscheidet, ob sie richtig gelabelt
sind. Fehler dort sind teuer und fallen ohne den Datenqualitätsbericht nicht
auf.

---

## Wie das Modell funktioniert

* **Elo-Baseline** (`ratings.py`): chronologisch fortgeschrieben, K-Faktor nach
  Fest-Wichtigkeit gewichtet. Jedes komplexere Modell muss sie schlagen.
* **Logistic Regression** (`train.py`) auf **leak-freien** A-minus-B-Merkmalen
  (`features.py`): Rating-Vorsprung und -Nähe, Form, Kranzstatus, Alter,
  Gewicht/Grösse, Erfahrung, Verband, bevorzugte Schwünge, Kopf-an-Kopf-Bilanz
  und die Datenlage (`portraet_diff`, s. unten). Alle Merkmale nutzen nur Daten
  von **vor** dem Gang; Holdout ist die jüngste Saison, kein zufälliger Split.
  Trainiert wird mit Spiegelzeilen (jeder Gang zusätzlich als B-gegen-A), damit
  das Modell paar-symmetrisch ist; **bewertet wird ohne sie** — sonst stünde
  jeder Testgang doppelt drin. Die Elo-Baseline wird auf **genau denselben**
  Gängen gemessen wie das Modell.
* **4-Wege-Benchmark** (`benchmark.py`): Kranz-Heuristik / reine Elo / ML ohne
  Elo / ML komplett auf demselben Holdout, mit Accuracy, Brier-Score sowie
  MAE und MSE (s. unten).
* **K-Means + KNN** (`clustering.py`): Cluster-Anzahl per Silhouette-Score.
* **Clientseitige Inferenz** (`web/lib/inference.ts`, `web/lib/kopfAnKopf.ts`)
  spiegelt `features.py` in TypeScript — eine Handkopie, die still
  auseinanderlaufen kann (ist schon einmal passiert). `verify_inference.py`
  prüft nur `model.json` gegen sklearn, mit dem **Python**-Vektor. Die
  TypeScript-Seite prüft **`pipeline/paritaet.py`**: Python erzeugt ~240
  Prüffälle aus den echten Artefakten (alle vier Porträt/Stub-Kombinationen,
  Kopf-an-Kopf in beiden Richtungen, fehlendes Rating), `npm run paritaet`
  rechnet sie mit den kompilierten TS-Modulen nach — Merkmale, Kopf-an-Kopf
  und Wahrscheinlichkeiten getrennt. Läuft in jedem PR (CI-Job
  `inferenz-paritaet`) und im täglichen Lauf **vor** dem Commit neuer
  Artefakte. Per Mutationstest belegt, dass er anschlägt: vertauschte
  Kopf-an-Kopf-Richtung, falsches Vorzeichen, falsche Skala, fehlendes
  Merkmal, fehlender Intercept — alle erkannt.

  Neue Merkmale **nur hinten** an `FEATURE_NAMES` anhängen: `model.json` ist
  positionsgebunden, und die App kürzt den Vektor auf die Merkmale, die das
  ausgelieferte Modell kennt. Ändert sich die **Definition** eines Merkmals,
  steigt `MERKMAL_VERSION` (`config.py`): sie steht in `model.json`, und App
  wie Python rechnen ein älteres ausgeliefertes Modell mit **dessen**
  Definition weiter. Die Paritätsprüfung testet beide Fälle (Gruppe
  `modell-v1`).

### Merkmalsversion 2: Stand vor dem Fest, Gestellt-Neigung

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

### Erklärbalken: wem ein Merkmal nützt

Ein Balken zeigt, um wie viele Prozentpunkte die Siegchance des genannten
Schwingers durch dieses Merkmal höher ist. **Symmetrische** Merkmale —
Ausgeglichenheit, gleicher Verband, ähnlicher Stil, Gestellt-Neigung — bleiben
beim Tausch von A und B gleich; das Modell hat für sie bei „Sieg A" und
„Sieg B" dasselbe Gewicht. Sie verschieben nur zwischen „einer gewinnt" und
„Gestellt" und erscheinen darum neutral als **„Gestellt ± X %-Pkt."**.
Früher wurden sie an P(Sieg A) gemessen und dem Gegner gutgeschrieben, sobald
diese sank: „Gleicher Verband: Moser +7 %-Pkt." bei Staudenmann gegen Moser,
obwohl auch Mosers Chance dadurch sank (Staudenmann −7.1, Gestellt +8.5,
Moser −1.5). Der Effekt selbst ist echt, aber klein: Duelle im gleichen
Verband enden in den Daten 30.5 % gestellt statt 28.8 %, in jedem Festtyp.

### Datenlage: Porträt oder Stub

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

**Offizielle Schlussranglisten** (`scrape/schlussgang_rangliste.py`,
`ranglisten.py`): schlussgang.ch veröffentlicht zu jedem Fest die
Schlussrangliste des ESV (Fusszeile „Quelle: ESV", 480 von 481 Festen seit
2023). esv.ch selbst sperrt Rechenzentrums-IPs per Firewall (schon
`robots.txt` antwortet 403), über schlussgang.ch kommt dieselbe Liste auf
erlaubtem Weg. Sie führt **jeden** Teilnehmer mit Schwingklub, Wohnort,
Senn/Turner, Kranzabzeichen und dem Status an diesem Fest. Daraus:

* **Kränze seit 2023** je Schwinger. Der Kranz geht an alle ab einer
  Punkteschwelle — vermessen an allen Kranzfesten der Stichprobe: jeder
  Markierte hatte mehr Punkte als jeder Unmarkierte. Das ESAF markiert nur
  Neueidgenossen; über dieselbe Schwelle zählen die bisherigen Eidgenossen
  mit (ESAF 2025: 17 + 23 = 40 von 269, 14.9 %). Kranzquote an Kranzfesten
  14–18 %, wie erwartet.
* **Schwingklub, Senn/Turner, Kranzstatus** auch für Schwinger ohne Porträt
  (z.B. Fritz Ramseier: Eidgenosse, ohne Porträt bisher als „kein" geführt).
* **Teilverband und Gauverband über den Klub**: jeder Klub gehört genau einem
  Verband an, gelernt aus den Porträts (136 Klubs, kein Widerspruch), geprüft
  per Leave-one-out an den Porträt-Schwingern (99.75 % in der Stichprobe).

Alles nur für Anzeige und Suche; das Modell bleibt bei seinen gemessenen
Merkmalen. Selbstprüfungen je Lauf stehen in `report.json` →
`datenqualitaet.ranglisten`.

**Teilverband ohne Porträt und ohne bekannten Klub** (`verbandsschaetzung.py`): aus den besuchten
Festen geschätzt — an Kantonal-, Teilverbands- und Regionalfesten startet fast
nur, wer dem Verband angehört. Validiert an den Porträt-Schwingern
(Leave-one-out) mit 99.8 % Treffern; die Prüfung läuft bei jedem Lauf erneut
und steht in `report.json` → `datenqualitaet.datenabdeckung`. Nur für Anzeige
und Suche (eigenes Feld `teilverband_geschaetzt`, in der App als „geschätzt"
markiert) — im Modell verschlechterte sie den Log-Loss und bleibt draussen.

Eine Folge davon: die Ergebnisverteilung (`sieg_a` rund 35 %, `sieg_b` rund
42 %) ist **kein Signal**. A und B werden alphabetisch per ID vergeben, und
Stub-IDs sortieren systematisch häufiger nach vorne (29'690 gemischte
Paarungen mit Stub vorne gegen 16'134 umgekehrt).

### MAE und MSE — Fehlermasse in der Einheit des Ergebnisses

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

### Warum der ältere Schwinger beim Alters-Merkmal im Vorteil ist

`alter_diff` (Alter A − Alter B) hat für `sieg_a` einen **positiven**
Koeffizienten (+0.0197). Älter zu sein zählt im Modell also leicht **für**
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

---

## Deployment

**Web-App auf Vercel (Hobby):** Root Directory = `web`, Next.js wird erkannt,
keine Env-Vars nötig (Daten sind statische JSON-Dateien).

**Pipeline auf GitHub Actions:** `update.yml` (täglich) und `ci.yml` (Tests +
Build bei jedem Push). Öffentliches Repo = Rechenlast gratis.

---

## Datennutzung / Disclaimer

Keine Voll-Replikation der Quell-Datenbank, nur abgeleitete Kennzahlen, mit
Quellenattribution in der App. Sensible Felder (Geburtsdatum, Zivilstand)
werden nicht gespeichert — fürs Modell nur der **Jahrgang**.

Nicht-kommerzielles Hobby-Projekt. Prognosen sind informativ und **kein
Wettangebot**. Betriebskosten: **$0**.

---

## Offene Punkte / bekannte Unsicherheiten

* **Kommende Feste kamen aus der falschen Quelle** (behoben, aber noch nicht
  gegen die echte Quelle verifiziert). Der Scraper las ausschliesslich
  JSON-LD-`Event`-Blöcke aus dem HTML von `schlussgang.ch/agenda` und lieferte
  dauerhaft `kommende: []`. Primärquelle ist jetzt dieselbe JSON:API, aus der
  auch die 466 abgeschlossenen Feste kommen — nur ohne `finished`-Filter und ab
  heute. Das HTML bleibt als Fallback. Beide Pfade werden protokolliert und im
  Datenqualitätsbericht ausgewiesen.

  Verifizieren (braucht Netzzugriff auf schlussgang.ch):

  ```bash
  python -m pipeline.diagnose_agenda
  ```

  Das prüft robots.txt, JSON:API und Agenda-HTML einzeln und sagt, welche Stufe
  klemmt. Bleibt der Kalender mitten in der Saison leer, steht der Grund seither
  auch im Job-Summary des Actions-Laufs statt nur in einer weggedruckten
  Ausnahme.

* **Die Kranz-Zahlen waren falsch — die Ursache ist geklärt, die Zahl ist
  entfallen.** Der Stern in der Kopfzeile der Statistik-PDF ist das
  **Statusabzeichen des Schwingers** (Kranzer/Eidgenosse), kein Kranzgewinn an
  diesem Fest. Dieselbe Bedeutung wie `field_portrait_wreath_status` im
  Porträt, wo `*`/`**`/`***` den Status bezeichnet.

  Belegt an den Artefakten, nicht an einer Annahme: über neun Feste, die seit
  dem Parser-Fix frisch geladen wurden, stimmt die Zahl der markierten
  Teilnehmer fast exakt mit der Zahl derer überein, die laut Porträt einen
  Kranzstatus tragen — **256 erwartet, 251 gefunden**.

  | Fest | Typ | Teiln. | mit Kranzstatus | markiert |
  |---|---|---:|---:|---:|
  | Kilchberger Schwinget | eidgenössisch | 59 | 59 (100 %) | 59 |
  | Kemmeriboden-Schwinget | regional | 148 | 47 (32 %) | ~45 |
  | Engstlenalp-Schwinget | regional | 106 | 37 (35 %) | ~37 |
  | Klubschwinget SK Tavannes | regional | 30 | 6 (20 %) | 6 |

  Der Kilchberger Schwinget entscheidet es: ein Einladungsfest, zu dem
  praktisch nur Eidgenossen antreten — 59 von 59 markiert. Ein Kranzgewinn
  ginge an rund 15 % der Teilnehmer. Und Regional- wie Klubfeste, an denen
  **überhaupt kein Kranz vergeben wird**, tragen Markierungen im selben
  Verhältnis.

  `_anzahl_kraenze` zählte damit faktisch „Feste, an denen ein Kranzer
  angetreten ist" und verkaufte das als Kranzgewinne. Deshalb stand Armon
  Orlik als Schwingerkönig bei 3 — gleich viel wie ein beliebiger Kranzer.

  **Konsequenz:** die Kranz-Zahl ist ersatzlos entfallen. Eine belastbare
  Kranzzahl geben diese Quellen nicht her — wo die Kranzgrenze liegt, legt
  jedes Fest selbst fest, und die PDF weist sie nicht aus; ein geschätzter
  Schwellenwert wäre geraten, nicht gemessen. Die Artefakte führen stattdessen
  `anzahl_feste` (besuchte Feste, direkt aus den Daten), und die App zeigt die
  höchste erreichte Kranzstufe aus dem Porträt — eine gemessene Angabe. Die
  Markierung heisst im Code jetzt `status_abzeichen`.

* **Der Selbsttest mass das Falsche und blieb folgenlos.** Die alte Prüfung
  verglich die „Kranzquote je Kranzfest" mit einem geratenen Band von 8–25 %.
  Sie stand wochenlang auf `plausibel: false`, Median `0.0`, **141 von 149
  Kranzfesten ohne einen einzigen Treffer** — ohne dass daraus etwas folgte.

  Neu prüft `_abzeichen_plausibilitaet` Soll gegen Ist: das Abzeichen hängt am
  Schwinger, also müssen an *jedem* Fest genau die markiert sein, die laut
  Porträt einen Kranzstatus tragen. Ein Fest ohne jeden Treffer ist damit ein
  harter Befund statt einer Quote am Rand eines Bandes.

  Diese 141 Feste sind **Altbestand in `artifacts/raw`**: eingelesen vor dem
  Parser-Fix und seither nie neu geparst, weil der tägliche Lauf nur ein
  kurzes Zeitfenster holt. Jedes seither frisch geladene Fest trägt die
  Abzeichen. Behebt sich nur über **Actions → Datenpipeline aktualisieren →
  Run workflow → „Volle Historie ab 2023 neu laden"** (rund 20 Minuten), weil
  `artifacts/raw/gaenge.json` die geparsten Einträge hält und die PDFs selbst
  nicht gecacht sind. Für `anzahl_feste` ist der Refetch **nicht** nötig —
  diese Zahl hängt nicht am Abzeichen.

* **`_status_counts` erfand Zahlen.** Die Funktion leitete aus dem Statustext
  („Eidgenosse"/„Kranzer") eine Tabelle `{"Kränze": 1, "ESAF": 0, …}` ab und
  gab sie als Zählung aus. Das waren keine Daten aus der Quelle, sondern eine
  aus einem Kategorienamen erfundene Eins. Entfernt.

* **Feste ohne Statistik-PDF** werden bei jedem vollen Refetch erneut
  angefragt (2 s Rate-Limit je Versuch). Ein „hat keine PDF"-Vermerk in
  `events.json` würde den vollen Refetch deutlich verkürzen. Der tägliche
  inkrementelle Lauf ist nicht betroffen (13 Feste in 72 s gemessen).
* **Drei echte Namensvettern** (Roman Bucher 2002/2003, Christian Zemp
  2000/2004, Jonas Wüthrich 2001/2003) lassen sich aus den Statistik-PDFs nicht
  auseinanderhalten — die nennen nur den Namen, keinen Jahrgang. Ihre Gänge
  werden bewusst verworfen und im Datenqualitätsbericht ausgewiesen, statt
  geraten.
* **Fehlende Physis ist nicht zufällig verteilt — und das Modell nutzt das
  nicht.** Nur Schwinger mit Porträt haben Gewicht/Grösse/Verband, und
  schlussgang.ch porträtiert vor allem die Spitze. Gemessen an den aktuellen
  Daten (129'990 Gänge):

  | Paarung | A gewinnt | gestellt | B gewinnt | n |
  |---|---:|---:|---:|---:|
  | Porträt vs. Porträt | 34.4 % | 29.9 % | 35.7 % | 37'109 |
  | Porträt vs. Stub | **67.2 %** | 19.5 % | 13.4 % | 15'967 |
  | Stub vs. Porträt | 12.5 % | 18.6 % | **68.8 %** | 28'784 |
  | Stub vs. Stub | 38.9 % | 21.1 % | 40.1 % | 48'130 |

  Gleiche Kategorien sind sauber symmetrisch (kein Zuordnungsfehler), aber ein
  Schwinger mit Porträt gewinnt gegen einen ohne rund 68 % seiner Gänge. „Hat
  ein Porträt" ist damit selbst ein starker Stärke-Indikator.

  `features._diff_oder_null` imputiert bei fehlendem Wert eine Differenz von
  `0.0` — also „beide gleich schwer/gross/alt". Damit wird ein informativer
  Unterschied als Gleichstand kodiert. Elo fängt den grössten Teil davon ohnehin
  ein; wer die Physis-Merkmale ernst nehmen will, sollte statt der Null-Imputation
  ein explizites „Wert fehlt"-Merkmal je Seite ergänzen und den Effekt gegen den
  Holdout messen.

* **Die aggregierte Ergebnisverteilung ist deshalb nicht 50/50** (35.2 % sieg_a
  vs. 41.9 % sieg_b). Das ist ein Nebeneffekt obiger Selektion in Kombination
  damit, wie die kanonische A-Seite bestimmt wird (lexikographisch kleinere ID),
  kein Label-Fehler: das Training augmentiert jeden Gang gespiegelt und ist
  dadurch paar-symmetrisch.
