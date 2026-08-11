# Schwingen ML

Datengetriebene, **erklärbare** Prognose für Schwingen-Gänge — trainiert auf echten
Resultaten von schlussgang.ch (2023–heute, 450+ Feste, 125'000+ Gänge). Für ein
Schwinger-Paar die Wahrscheinlichkeit von **Sieg A / Gestellt / Sieg B**, plus
Rangliste, Kopf-an-Kopf-Historie, eine Schweiz-Karte, echtes K-Means-Clustering
der Schwingertypen und eine 4-Wege-Modellevaluierung. Prognosen sind
**informativ, kein Wettangebot**.

**Live:** [schwingen-ml.vercel.app](https://schwingen-ml.vercel.app/)

---

## Was die App kann

| Seite | Was man sieht |
|---|---|
| **Prognose** | Zwei Schwinger wählen (Fuzzy-Suche) → Sieg-A/Gestellt/Sieg-B-Wahrscheinlichkeit mit Merkmalsbeiträgen ("warum diese Prognose"), Kopf-an-Kopf-Historie falls die beiden sich schon begegnet sind, teilbarer Link (`?a=...&b=...`). |
| **Schwinger** | Alle erfassten Schwinger, durchsuchbar, nach Elo sortiert, mit Rang/Medaillen. Profil-Aufklappen zeigt Überraschungs-Index (Elo-erwartete vs. tatsächliche Leistung) und per KNN berechnete ähnliche Schwinger. |
| **Feste** | Vergangene und kommende Feste inkl. Paarungs-Vorschau. |
| **Karte** | Choroplethen-Karte der Schweiz (Elo-Schnitt, Siegquote, Anteil Top-Schwinger, Kaderbreite) — Bern einzeln nach seinen 6 Gauverbänden statt als ein Kanton, mit echten Grenzen der BFS-Verwaltungskreise. |
| **Typen** | Echtes K-Means-Clustering über das volle Schwinger-Profil (Physis, Stil, Elo, Erfahrung, Alter, Kranzstatus) — Cluster-Anzahl per Silhouette-Score automatisch gewählt, mit PCA-Streudiagramm, typischen Vertretern und Teilverband-Schwerpunkten je Typ. |
| **Analyse** | Modellgüte vs. Elo-Baseline, Konfusionsmatrix, Merkmalswichtigkeit, 4-Wege-Benchmark (Kranz-Heuristik / Elo / ML ohne Elo / ML komplett) und Streudiagramme zu Grösse/Gewicht vs. Elo. |

---

## Wie das Modell funktioniert

- **Elo-Baseline** (`pipeline/ratings.py`): klassisches, chronologisch fortgeschriebenes
  Rating — jedes komplexere Modell muss das schlagen.
- **Logistic Regression** (`pipeline/train.py`) auf **leak-freien** A-minus-B-Merkmalen
  (`pipeline/features.py`): Rating-Vorsprung, Form, Kranzstatus, Alter, Gewicht/Grösse,
  Erfahrung, Verband, bevorzugte Schwünge, Kopf-an-Kopf-Bilanz. Alle Merkmale nutzen
  ausschliesslich Daten von **vor** dem jeweiligen Gang; zeitlicher Holdout (jüngste
  Saison) statt zufälligem Split.
- **4-Wege-Benchmark** (`pipeline/benchmark.py`): vergleicht Kranz-Heuristik,
  reine Elo-Baseline, ML ohne Elo/Historie und das komplette Modell auf demselben
  Holdout mit Accuracy und (multiklassigem) Brier-Score — beantwortet ehrlich, ob
  Elo wirklich einen Mehrwert bringt.
- **K-Means-Clustering + KNN** (`pipeline/clustering.py`): gruppiert Schwinger nach
  ihrem vollen Profil; Cluster-Anzahl wird per Silhouette-Score aus einem Bereich
  automatisch gewählt statt fest vorgegeben. Dieselbe KNN-Distanz treibt auch die
  "Ähnliche Schwinger"-Anzeige.
- **Client-seitige Inferenz** (`web/lib/inference.ts`): spiegelt `features.py` +
  die trainierten Gewichte exakt in TypeScript — die Prognose läuft im Browser,
  kein Server-Rechenaufwand. `pipeline/verify_inference.py` prüft bei jedem
  Pipeline-Lauf, dass beide Implementierungen identisch rechnen.

---

## Architektur

```
┌─────────────────────────────────────────────┐
│ GitHub Actions (öffentliches Repo, gratis)   │
│  scrape → parse → labels → features → train  │
│                    │                          │
│                    ▼                          │
│  artifacts/*.json  +  web/public/data/*.json  │  ← versioniert im Repo
└─────────────────────────────────────────────┘
                     │ Commit löst Deploy aus
                     ▼
┌─────────────────────────────────────────────┐
│ Vercel Hobby — Next.js (TypeScript)          │
│  lädt JSON, rechnet Inferenz CLIENTSEITIG    │  ← < 500 ms, kein Server-Compute
└─────────────────────────────────────────────┘
```

Trennung von **Pipeline / Training / Web-App**, alle Artefakte als JSON — keine
Datenbank nötig, komplett $0 Betriebskosten (öffentliches Repo + Vercel Hobby).

---

## Projektstruktur

```
pipeline/                 Python-Datenpipeline (GitHub Actions)
  config.py                Seeds, Pfade, Hyperparameter (reproduzierbar)
  schema.py                Kanonisches Schema + Schwinger-Identität
  labels.py                Symbol→Ergebnis, Dedup, Validierung
  ratings.py                Elo-Baseline, chronologisch/leak-frei
  features.py               A-minus-B-Merkmale, leak-frei, augmentiert
  train.py                  Logistic Regression + zeitliche Evaluation
  benchmark.py               4-Wege-Modellvergleich (Accuracy + Brier-Score)
  clustering.py              K-Means-Schwingertypen + KNN-Ähnlichkeit
  kantone.py                 Kantonal-/Gauverband → politischer Kanton
  export.py                  JSON-Artefakte schreiben
  fetch_raw.py               CLI zum Befüllen von artifacts/raw aus Webquellen
  synth.py                   Synthetischer Datensatz (Demo)
  run_pipeline.py            Orchestrator
  verify_inference.py        Cross-Check: JSON-Inferenz == sklearn-Modell
  scrape/                    Scraper (schlussgang.ch, esv.ch) — rate-limitiert, robots.txt
  tests/                     pytest (Pipeline-Logik, ~50 Tests)
artifacts/                 Generierte JSON-Artefakte (versioniert, ausser artifacts/raw/)
web/                        Next.js App Router + TypeScript
  lib/inference.ts           Clientseitige LR-Inferenz (spiegelt features.py)
  lib/clustering, choropleth, aehnlichkeit, regression  Client-Helfer für die ML-Ansichten
  app/                       Seiten: Prognose, Schwinger, Feste, Karte, Typen, Analyse
  components/                 Wiederverwendbare Chart-/UI-Komponenten
  public/data/                Artefakt-Kopie, die die App lädt
.github/workflows/          ci.yml (Tests+Build), update.yml (täglicher Datenlauf)
```

---

## Lokal ausführen

### Pipeline (Python)

```bash
pip install -r requirements-pipeline.txt
python -m pipeline.run_pipeline --source synth   # schnell, synthetische Demodaten
python -m pipeline.verify_inference               # prüft Inferenz-Konsistenz
python -m pytest pipeline/tests -q                # ~50 Tests
```

### Web-App (Next.js)

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

### Mit echten Daten

```bash
python -m pipeline.fetch_raw --sources schlussgang esv events --materialize-schwinger
python -m pipeline.run_pipeline --source scrape
python -m pipeline.verify_inference
```

`fetch_raw` holt Porträts, ESV-Statistiken und abgeschlossene Feste direkt von den
Webquellen nach `artifacts/raw/` (nicht versioniert, jederzeit reproduzierbar).
`--seit-datum`/`--event-limit` steuern den Zeitraum; ohne Angabe wird nur ein
kleines Zeitfenster geholt (siehe unten für den vollen Historien-Refetch).

---

## Automatische tägliche Updates

`.github/workflows/update.yml` läuft täglich per Cron, holt neue Resultate und
committet geänderte Artefakte (Vercel deployt danach automatisch). Damit der
Cron-Lauf nicht jeden Tag bei null anfängt, wird `artifacts/raw/` über
`actions/cache` zwischen Läufen persistiert — der tägliche Lauf holt dann nur
das kurze Zeitfenster seit dem letzten Mal und baut auf dem Cache auf.

Der Cache startet leer. Einmalig (oder falls er je zurückgesetzt werden muss)
über **Actions → Datenpipeline aktualisieren → Run workflow** mit Häkchen bei
**„Volle Historie neu laden"** die komplette Historie neu laden — dauert
15–20 Minuten, danach reichen die täglichen inkrementellen Läufe.

Ein eingebautes Sicherheitsnetz (`_pruefe_datenvolumen` in `run_pipeline.py`)
bricht einen Lauf hart ab, statt das produktive Modell mit einem auf einem
Bruchteil der Historie trainierten zu überschreiben, falls der Cache doch
einmal leer sein sollte.

---

## Datenquellen & Fairness

- `pipeline/scrape/schlussgang_resultate.py` — abgeschlossene Feste (JSON:API `node/event`)
- `pipeline/scrape/schlussgang_pdf.py` — Ranglisten-PDFs, spaltenbasiert geparst,
  Punktetotal-Kreuzcheck gegen die ausgewiesene Summe
- `pipeline/scrape/schlussgang_portraet.py` — Schwinger-Porträts (Gewicht, Grösse,
  Verband, bevorzugte Schwünge); physisch unplausible Werte werden beim Parsen
  verworfen statt blind übernommen
- `pipeline/scrape/agenda.py` — kommende Feste + Spitzenpaarungen
- `pipeline/scrape/http.py` — höflicher Client: Rate-Limit pro Host, echter
  User-Agent, robots.txt wird respektiert

Keine Voll-Replikation der Quell-Datenbanken, nur abgeleitete Kennzahlen,
Quellenattribution in der App. Sensible Felder (Geburtsdatum, Zivilstand)
werden nicht gespeichert — fürs Modell nur **Alter** (Jahrgang).

---

## Deployment

**Web-App auf Vercel (Hobby, gratis):** Root Directory = `web`, Next.js wird
automatisch erkannt, keine Env-Vars nötig (Daten sind statische JSON-Dateien).

**Pipeline auf GitHub Actions:** `.github/workflows/update.yml` (täglich) und
`ci.yml` (Tests + Build bei jedem Push). Öffentliches Repo = gesamte Rechenlast
gratis.

---

## Lizenz / Disclaimer

Nicht-kommerzielles Hobby-Projekt. Prognosen sind informativ und **kein
Wettangebot**. Betriebskosten: **$0** (öffentliches Repo + Vercel Hobby + GitHub
Actions, keine Datenbank).
