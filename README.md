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
| **Feste** | Vergangene Feste; kommende Feste inkl. Paarungs-Vorschau, sofern die Agenda welche ausweist. |
| **Karte** | Choroplethen-Karte (Elo-Schnitt, Siegquote, Anteil Top-Schwinger, Kaderbreite) — Bern nach seinen 6 Gauverbänden statt als ein Kanton. |
| **Typen** | K-Means-Clustering über das volle Schwinger-Profil, Cluster-Anzahl per Silhouette-Score gewählt, mit PCA-Streudiagramm. |
| **Analyse** | Modellgüte vs. Elo-Baseline, Konfusionsmatrix, Merkmalswichtigkeit, 4-Wege-Benchmark. |

---

## Woher die Daten kommen

Einzige Quelle ist **schlussgang.ch**. Es gibt keine manuell gepflegten
Datenbestände — alles ist jederzeit aus der Quelle reproduzierbar.

| Was | Woher | Modul |
|---|---|---|
| Abgeschlossene Feste | JSON:API `backend-api.schlussgang.ch/jsonapi/node/event` (gefiltert auf `field_event_state=finished`) | `scrape/schlussgang_resultate.py` |
| Gänge (Symbol + Note je Gang) | Statistik-PDF je Fest (`…/event-ranking-list/<nid>-statistic-final.pdf`) | `scrape/schlussgang_pdf.py` |
| Porträts (Gewicht, Grösse, Verband, Kranzstatus, Schwünge) | JSON:API `node/portrait` | `scrape/schlussgang_portraet.py` |
| Kommende Feste | JSON-LD der Agenda-Seite | `scrape/agenda.py` |

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
4. **`pipeline.verify_inference`** — prüft, dass die clientseitige
   TypeScript-Inferenz identisch rechnet wie das trainierte Modell.
5. **`pipeline.datenqualitaet`** — schreibt den Qualitätsbericht ins
   Job-Summary des Actions-Laufs.
6. **Artefakte committen** — Vercel deployt automatisch.

Der Lauf **bricht ab, statt schlechte Daten zu committen**, wenn

* mehr als 25 % der Roh-Einträge verworfen werden (Verarbeitung defekt), oder
* die Rohabdeckung gegenüber dem Vorlauf einbricht (Cache verloren), oder
* die abgeleiteten Gänge einbrechen, obwohl die Rohabdeckung stimmt.

Ist der Cache je verloren, einmalig **Actions → Datenpipeline aktualisieren →
Run workflow → „Volle Historie ab 2023 neu laden"** starten.

> **Laufzeit-Warnung:** Ein voller Refetch dauert **mehrere Stunden**, nicht die
> früher dokumentierten 15–20 Minuten. Der Grund ist die schiere Menge: pro Fest
> wird eine Statistik-PDF angefragt (2 s Rate-Limit, NFR-4), auch für Feste, die
> gar keine haben. Die alte Angabe stimmte nur, weil der Workflow ein hartes
> `--event-limit 1000` mitgab, das die Historie stillschweigend abschnitt.
> Der **tägliche inkrementelle Lauf ist davon nicht betroffen** — gemessen:
> 13 Feste in 72 Sekunden, kompletter Job inkl. Training unter 2 Minuten.

---

## Voraussetzungen

* **Python ≥ 3.11**
* **Node.js ≥ 20** (nur für die Web-App)
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
python -m pipeline.verify_inference              # Inferenz-Konsistenz
python -m pytest pipeline/tests -q               # ~97 Tests
```

> `--source synth` **überschreibt die Artefakte** mit Demodaten. Danach
> `git checkout -- artifacts/ web/public/data/ web/data/`, wenn die echten
> Artefakte erhalten bleiben sollen.

### Pipeline — echte Daten

```bash
# 1. Rohdaten holen (volle Historie; dauert MEHRERE STUNDEN, s. oben)
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
  benchmark.py               4-Wege-Modellvergleich (Accuracy + Brier)
  clustering.py              K-Means-Schwingertypen + KNN-Ähnlichkeit
  kantone.py                 Kantonal-/Gauverband → politischer Kanton
  export.py                  JSON-Artefakte schreiben
  fetch_raw.py               CLI: Webquellen → artifacts/raw
  run_pipeline.py            Orchestrator (8 Stufen)
  datenqualitaet.py          Qualitätsbericht aus report.json
  verify_inference.py        Cross-Check: TS-Inferenz == sklearn-Modell
  synth.py                   Synthetischer Datensatz (offline/CI)
  scrape/                    schlussgang.ch-Scraper + Rohdaten-Einlesen
  tests/                     pytest
artifacts/                 Generierte Artefakte (versioniert, ausser raw/)
web/                       Next.js App Router + TypeScript
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
  Gewicht/Grösse, Erfahrung, Verband, bevorzugte Schwünge, Kopf-an-Kopf-Bilanz.
  Alle Merkmale nutzen nur Daten von **vor** dem Gang; Holdout ist die jüngste
  Saison, kein zufälliger Split.
* **4-Wege-Benchmark** (`benchmark.py`): Kranz-Heuristik / reine Elo / ML ohne
  Elo / ML komplett auf demselben Holdout, mit Accuracy und Brier-Score.
* **K-Means + KNN** (`clustering.py`): Cluster-Anzahl per Silhouette-Score.
* **Clientseitige Inferenz** (`web/lib/inference.ts`) spiegelt `features.py` in
  TypeScript; `verify_inference.py` prüft bei jedem Lauf, dass beide identisch
  rechnen.

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

* **Kommende Feste sind leer** (`events.json` -> `kommende: []`). Der
  Agenda-Scraper (`scrape/agenda.py`) erwartet JSON-LD-`Event`-Blöcke auf
  `schlussgang.ch/agenda`; er liefert seit mindestens dem 23.07. nichts. Das
  betrifft nur die Paarungs-Vorschau auf der Feste-Seite, nicht Training oder
  Prognose. Ungeprüft, weil die Seite aus der Analyse-Umgebung nicht erreichbar
  war. Verifizieren: `python -c "from pipeline.scrape.agenda import scrape_agenda;
  print(len(scrape_agenda()))"` — liefert das 0, hat die Seite ihr Markup
  geändert und der Parser muss neu kalibriert werden.

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
