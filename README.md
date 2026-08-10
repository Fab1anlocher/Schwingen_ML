# Schwingen ML — Gang-Prognosetool

Datengetriebene, **erklärbare** Prognose für Schwingen-Gänge: für ein Schwinger-Paar
die Wahrscheinlichkeit von **Sieg A / Gestellt / Sieg B**, plus Fest-Vorschau,
Merkmalswichtigkeit und Schwinger-Profile. Prognosen sind **informativ, kein
Wettangebot**.

> Status: **Phase-1-MVP lauffähig** — komplette Pipeline (Labels → Elo-Baseline →
> Logistic Regression → JSON-Artefakte) und Next.js-Web-App mit clientseitiger
> Inferenz. Läuft end-to-end mit synthetischen Demodaten; der ESV-Scraper
> (esv.ch/ranglisten) ist implementiert und mechanisch getestet, offen ist nur
> die Kalibrierung gegen das reale HTML (siehe [Datenquelle](#datenquelle-esv-ranglisten-esvchranglisten)).

---

## Entscheidungen (Antworten auf §11 der Spec)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Stack / Sprache | **Next.js App Router + TypeScript** | Typsicherheit für Modell-Artefakte (JSON-Gewichte), Standard, gute Vercel-Integration. |
| 2 | MVP-Datensatz | **Offizielle ESV-Ranglisten** (esv.ch/ranglisten), aktive Feste zuerst | Offizielle Quelle, einheitliche Notation, über `?anlass=<id>` je Fest abrufbar. |
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
  scrape/esv.py           ESV-Ranglisten-Scraper (esv.ch/ranglisten) — höflich
  scrape/recon_esv.py     Kalibrierhilfe: echtes HTML abgreifen + Parser prüfen
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
| FR-2 | Fest-Vorschau + Quote | ✅ UI, wartet auf Agenda-Scraper |
| FR-6 | Automatische Datenpipeline | ✅ Workflow, Scraper-Parser offen |
| — | Gradient Boosting + ONNX, Kalibrierung, zwilch-Historie | ⬜ Phase 2 |

---

## Datenquelle: ESV-Ranglisten (esv.ch/ranglisten)

Primäre Quelle sind die **offiziellen ESV-Ranglisten**:

- Index:      `https://esv.ch/ranglisten/`
- Einzelfest: `https://esv.ch/ranglisten/?anlass=<ANLASS_ID>` (z. B. `?anlass=3694` = ESAF 2025)

Die Ranglisten nutzen die offizielle Schwingen-Notation (Symbol `+`/`-`/`o` + Note),
identisch zur Label-Logik (§4.3) — diese bleibt unverändert.

- `pipeline/scrape/esv.py` — Index + Rangliste laden und parsen → Roh-Gang-Einträge
- `pipeline/scrape/recon_esv.py` — Kalibrierhilfe (echtes HTML abgreifen + Parser prüfen)
- `pipeline/scrape/http.py` — höflicher Client: Rate-Limit, User-Agent, **robots.txt** (NFR-4)

**Kalibrierung (R-6):** Das exakte HTML-Layout ist gegen eine echte Seite zu
verifizieren. Da diese Sandbox esv.ch nicht erreicht (Egress-Sperre), läuft die
Kalibrierung dort, wo das Internet offen ist:

```bash
python -m pipeline.scrape.recon_esv --anlass 3694   # lädt HTML + zeigt Parser-Ergebnis
python -m pipeline.run_pipeline --source esv         # echter Lauf (nach Kalibrierung)
```

Bis zur Kalibrierung bleibt `--source synth` der lauffähige Default. Der
Parser ist mechanisch getestet (nachgebildete Ranglisten-Tabelle → korrekte
Dedup/Labels); offen ist nur die Anpassung an das reale Spaltenlayout.

**Recht/Fairness (NFR-4/5):** höfliches, rate-limitiertes Abrufen; keine
Voll-Replikation der Quell-DBs; Quellenattribution in der App; nur abgeleitete
Kennzahlen. Sensible Felder (Geburtsdatum, Zivilstand) werden nicht gespeichert/
angezeigt — fürs Modell nur **Alter**.

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
