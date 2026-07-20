# Schwingen ML — Gang-Prognosetool

Datengetriebene, **erklärbare** Prognose für Schwingen-Gänge: für ein Schwinger-Paar
die Wahrscheinlichkeit von **Sieg A / Gestellt / Sieg B**, plus Fest-Vorschau,
Merkmalswichtigkeit und Schwinger-Profile. Prognosen sind **informativ, kein
Wettangebot**.

> Status: **MVP lauffähig** — komplette Pipeline (Labels → Elo-Baseline →
> Logistic Regression → JSON-Artefakte) und Next.js-Web-App mit clientseitiger
> Inferenz. Läuft end-to-end mit synthetischen Demodaten; produktive Läufe sind
> über `--source scrape` mit lokalen Raw-Daten (`artifacts/raw`) vorbereitet.

---

## Entscheidungen (Antworten auf §11 der Spec)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Stack / Sprache | **Next.js App Router + TypeScript** | Typsicherheit für Modell-Artefakte (JSON-Gewichte), Standard, gute Vercel-Integration. |
| 2 | MVP-Datensatz | **Aktive Elite, letzte ~2–3 Saisons** aus schlussgang.ch-PDFs zuerst | Sauberste, maschinenlesbare Quelle. zwilch.ch-Historie kommt in Phase 2 dazu. |
| 3 | Metrik-Schwelle | **Log-Loss < Elo-Baseline** auf zeitlichem Holdout | „Gut genug" = schlägt Baseline messbar. Aktuell (synthetisch): 0.76 vs. 0.85. |
| 4 | Betrieb / Datastore | **Öffentliches Repo + Vercel Hobby, KEIN Supabase** | Siehe unten. |

### Warum kein Supabase (für ein Gratis-Heim-Projekt am besten)

Für den MVP genügen **im Repo versionierte JSON-Artefakte**, die die Web-App
clientseitig lädt. Das ist die einfachste, wirklich wartungsfreie **$0**-Lösung:

- **Keine Datenbank, kein Account, keine Inaktivitäts-Pause** (Supabase Free pausiert
  Projekte nach ~1 Woche Inaktivität — für ein Hobby-Projekt lästig).
- **GitHub Actions** (öffentliches Repo = gratis, ohne Minutenlimit) macht das
  Rechnen: scrapen, trainieren, Artefakte committen.
- **Vercel Hobby** hostet die statische App und rechnet die Prognose im Browser.
- Neue Artefakte → Commit → Vercel deployt automatisch.

Eine DB (Supabase o. Ä.) lohnt sich erst, wenn die **volle zwilch.ch-Historie**
(~1,48 Mio. Paarungen) durchsuchbar gemacht werden soll. Selbst dann sind
vorberechnete JSON-Artefakte für die Inferenz weiterhin die richtige Wahl.

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

Trennung von **Pipeline / Training / Web-App** (NFR-6). Alle Artefakte als JSON.

---

## Projektstruktur

```
pipeline/                 Python-Datenpipeline (GitHub Actions)
  config.py               Seeds, Pfade, Hyperparameter (reproduzierbar, NFR-3)
  schema.py               Kanonisches Schema + Schwinger-Identität (§4.2, R-5)
  labels.py               Symbol→Ergebnis, Dedup, Validierung (§4.3, KRITISCH)
  ratings.py              Elo-Baseline, chronologisch/leak-frei (ML-2, ML-5)
  features.py             A-minus-B-Merkmale, leak-frei, augmentiert (ML-4/5)
  train.py                Logistic Regression + zeitliche Evaluation (ML-3/6)
  export.py               JSON-Artefakte schreiben (§7)
  synth.py                Synthetischer Datensatz (Demo, bis Scraper aktiv)
  run_pipeline.py         Orchestrator (FR-6)
  verify_inference.py     Cross-Check: JSON-Inferenz == sklearn-Modell
  scrape/                 Echte Scraper-Gerüste (schlussgang.ch, agenda) — höflich
  tests/                  pytest für die Label-Logik
artifacts/                Generierte JSON-Artefakte (versioniert)
web/                      Next.js App Router + TypeScript
  lib/inference.ts        Clientseitige LR-Inferenz (spiegelt features.py)
  app/                    Seiten: Paar-Prognose, Feste, Schwinger, Analyse
  public/data/            Artefakt-Kopie, die die App lädt
.github/workflows/        CI (Tests+Build) und geplanter Update-Lauf
```

---

## Lokal ausführen

### Pipeline (Python)

```bash
pip install -r requirements-pipeline.txt
python -m pipeline.run_pipeline --source synth   # erzeugt artifacts/ + web/public/data/
python -m pipeline.verify_inference               # prüft Inferenz-Konsistenz
python -m pytest pipeline/tests -q                # Label-Logik-Tests
```

### Web-App (Next.js)

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

---

## Tutorial: von Demo-/Synth-Daten zu echtem Training

Die Web-App zeigt immer die Daten aus `web/public/data/`. Diese Dateien werden
von der Pipeline erzeugt und aus `artifacts/` dorthin kopiert.

### 1) Demo-Training prüfen (aktueller Standard)

```bash
python -m pipeline.run_pipeline --source synth
python -m pipeline.verify_inference
```

Danach zeigt die Web-App weiterhin synthetische Daten — das ist korrekt.

### 2) Echte Rohdaten vorbereiten

Lege den Ordner `artifacts/raw/` an und erstelle drei Dateien:

- `artifacts/raw/schwinger.json`
- `artifacts/raw/events.json`
- `artifacts/raw/gaenge.json`

Minimalbeispiel:

`artifacts/raw/schwinger.json`

```json
{
  "schwinger": [
    {
      "id": "max-muster",
      "name": "Max Muster",
      "jahrgang": 1998,
      "kranzstatus": "kein"
    },
    {
      "id": "peter-beispiel",
      "name": "Peter Beispiel",
      "jahrgang": 1997,
      "kranzstatus": "kein"
    }
  ]
}
```

`artifacts/raw/events.json`

```json
{
  "events": [
    {
      "id": "ev-2026-test",
      "name": "Testschwinget",
      "datum": "2026-07-20",
      "typ": "kantonal"
    }
  ]
}
```

`artifacts/raw/gaenge.json`

```json
{
  "gaenge": [
    {
      "event_id": "ev-2026-test",
      "datum": "2026-07-20",
      "fest_typ": "kantonal",
      "schwinger_id": "max-muster",
      "gegner_id": "peter-beispiel",
      "symbol": "+",
      "note": 10.0
    },
    {
      "event_id": "ev-2026-test",
      "datum": "2026-07-20",
      "fest_typ": "kantonal",
      "schwinger_id": "peter-beispiel",
      "gegner_id": "max-muster",
      "symbol": "o",
      "note": 8.75
    }
  ]
}
```

Hinweise:
- Für Schwinger ist `name` Pflicht; `id` ist optional (wird sonst abgeleitet).
- Für Events sind `id`, `datum`, `name` Pflicht.
- Für Gänge sind `event_id`, `datum`, `symbol` (`+`, `-`, `o`) und beide
  Schwinger (per ID oder Name) nötig.

### 3) Echtes Training starten

```bash
python -m pipeline.run_pipeline --source scrape
python -m pipeline.verify_inference
```

Wenn `--source scrape` erfolgreich läuft, sind `artifacts/*.json` und
`web/public/data/*.json` auf echten Rohdaten basiert.

### 4) Web-App mit neuen Artefakten prüfen

```bash
cd web
npm run dev
```

Browser neu laden; Prognosen und Listen kommen jetzt aus den neu erzeugten
Artefakten statt aus Synth-Daten.

### 5) Optional: automatische tägliche Updates

Der Workflow `.github/workflows/update.yml` führt die Pipeline täglich aus
(Standard `source=scrape`) und committet geänderte Artefakte. Dafür müssen
die Raw-Daten in `artifacts/raw/` verfügbar sein.

---

## Features (Umsetzungsstand)

| Anf. | Feature | Status |
|---|---|---|
| FR-1 | Paar-Prognose (Sieg A / Gestellt / Sieg B) | ✅ |
| FR-3 | Erklärbarkeit (Top-Merkmalsbeiträge) | ✅ |
| FR-4 | Feature-Wichtigkeit / Analyse-Sicht | ✅ |
| FR-5 | Schwinger-Suche & Profil | ✅ |
| ML-2 | Elo-Baseline | ✅ |
| ML-3 | Logistic Regression (schlägt Baseline) | ✅ |
| ML-5 | Kein Data Leakage (zeitliche Trennung) | ✅ |
| ML-6 | Log-Loss / Accuracy-Report | ✅ |
| FR-2 | Fest-Vorschau + Quote | ✅ inkl. Fallback-Favoriten bei offenen Paarungen |
| FR-6 | Automatische Datenpipeline | ✅ Workflow täglich, default `source=scrape` |
| — | Gradient Boosting + ONNX, Kalibrierung, zwilch-Historie | ⬜ Phase 2 |

---

## Datenquellen

Der MVP läuft weiterhin mit **synthetischen** Daten (`pipeline/synth.py`) für
eine sofort lauffähige Demo. Für produktive Läufe unterstützt die Pipeline
`--source scrape` mit lokalen Raw-Daten in `artifacts/raw/`:

- `schwinger.json` (`{"schwinger":[...]}`)
- `events.json` (`{"events":[...]}`)
- `gaenge.json` (`{"gaenge":[...]}`)

Zusätzlich liest `pipeline/scrape/agenda.py` kommende Feste von
`schlussgang.ch/agenda` (JSON-LD) und extrahiert optionale Paarungen.
Der PDF-Parser enthält eine kalibrierbare Text-Extraktion:

- `pipeline/scrape/schlussgang_pdf.py` — Ranglisten-PDF (`<eventId>-statistic-final.pdf`)
- `pipeline/scrape/agenda.py` — kommende Feste + Spitzenpaarungen (FR-2)
- `pipeline/scrape/http.py` — höflicher Client: Rate-Limit, User-Agent, **robots.txt** (NFR-4)

**Recht/Fairness (NFR-4/5):** höfliches, rate-limitiertes Abrufen; keine
Voll-Replikation der Quell-DBs; Quellenattribution in der App; nur abgeleitete
Kennzahlen. Sensible Felder (Geburtsdatum, Zivilstand) werden nicht gespeichert/
angezeigt — fürs Modell nur **Alter**.

---

## Deployment

**Web-App auf Vercel (Hobby, gratis, nicht-kommerziell):**
- Neues Vercel-Projekt, **Root Directory = `web`**.
- Framework Next.js wird automatisch erkannt. Kein Env-Var nötig (Daten sind statisch).

**Pipeline auf GitHub Actions:**
- `.github/workflows/update.yml` läuft täglich (Cron) oder manuell, erzeugt neue
  Artefakte und committet sie → Vercel deployt automatisch.
- **Repo öffentlich halten** = gesamte Rechenlast gratis (§8).

Kosten: als persönliches, nicht-kommerzielles Projekt **komplett $0**.
