# Schwingen ML

[![CI](https://github.com/Fab1anlocher/Schwingen_ML/actions/workflows/ci.yml/badge.svg)](https://github.com/Fab1anlocher/Schwingen_ML/actions/workflows/ci.yml)
[![Daten](https://github.com/Fab1anlocher/Schwingen_ML/actions/workflows/update.yml/badge.svg)](https://github.com/Fab1anlocher/Schwingen_ML/actions/workflows/update.yml)

**Erklärbare** Prognosen für Schwingen-Gänge, trainiert auf den Resultaten von
[schlussgang.ch](https://www.schlussgang.ch) und den offiziellen
Schlussranglisten. Für jedes Schwinger-Paar zeigt die App die
Wahrscheinlichkeit für **Sieg A / Gestellt / Sieg B** und begründet sie.
Jedes Modell muss sich dabei gegen eine ehrliche Elo-Prognose behaupten.

**Live:** [schwingen-ml.vercel.app](https://schwingen-ml.vercel.app/) ·
Prognosen sind informativ, **kein Wettangebot**.

| Dokument | Inhalt |
|---|---|
| [docs/MODELL.md](docs/MODELL.md) | Merkmale, Messungen, Entscheidungen zum Modell, Simulator |
| [docs/DATEN.md](docs/DATEN.md) | Quellen, Lesen der PDFs, Namensvettern, täglicher Lauf |
| [ROADMAP.md](ROADMAP.md) | Erledigtes und Offenes, mit Messwerten |
| [CLAUDE.md](CLAUDE.md) | Kurzfassung für KI-Assistenten: Architektur, Invarianten, Prüfschritte |

---

## Was die App kann

| Seite | Inhalt |
|---|---|
| **Prognose** | Zwei Schwinger wählen: Wahrscheinlichkeiten mit Begründung je Merkmal, Kopf-an-Kopf-Bilanz, teilbarer Link. |
| **Feste** | Kommende Feste mit Prognose je veröffentlichter Paarung; Rückblick je Saison mit Festsiegern, Kränzen und dem Prognose-Check (wie oft das Modell richtig lag). |
| **Simulator** | Ein ganzes Fest tausendfach durchgespielt: Festsieg-, Schlussgang- und Kranzchance je Schwinger. |
| **Rückblick** | Die Saison auf einen Blick: Festsieger, meiste Kränze, Aufsteiger, stärkste Neue, Überraschungen. |
| **Schwinger** | Alle erfassten Schwinger nach Elo, mit Profil, Festsiegen und ähnlichen Schwingern. |
| **Typen** | Wie einer seine Gänge entscheidet: Werfer, Bollwerk, Bodenarbeiter und Co., gemessen an Plattwurf und Gestellt gegenüber der Erwartung. |
| **Karte** | Kantone und Berner Gauverbände im Vergleich; Steckbrief mit Kantonsmeister und das Kantönligeist-Duell (die sechs Besten zweier Kantone gegeneinander). |
| **Analyse** | Wie gut das Modell ist, gegen welche Alternativen es antritt, wie es sich entwickelt hat, und der Härtetest am eingefrorenen Modell. |

---

## Das Modell

**Stand Oktober 2026**, gemessen an der Saison 2026 (37'747 Gänge, die das
Modell beim Training nicht gesehen hat):

| | Log-Loss | Treffer |
|---|---:|---:|
| **Gradient Boosting (ausgeliefert)** | **0.683** | **70.3 %** |
| Logistic Regression, gleiche Merkmale | 0.694 | 69.9 % |
| Elo, auf die Daten angepasst | 0.773 | 66.1 % |
| Elo-Formel | 0.801 | 66.2 % |

Gestellt sagt es mit 20.5 % voraus, eingetreten sind 21.0 %. Aktuelle Zahlen
stehen in `artifacts/report.json` und auf der Analyse-Seite.

**So funktioniert es:**

* **Zwei Stufen Gradient Boosting** (`pipeline/modell.py`): erst
  P(Gestellt), dann P(Sieg A | entschieden). Monotonie-Vorgaben verhindern
  Unsinn in dünn besetzten Ecken (eine hohe Gestellt-Bilanz kann die
  Gestellt-Chance nicht senken).
* **Merkmale** (`pipeline/features.py`): Elo-Vorsprung und -Nähe, Form,
  Kranzstatus, Physis, Erfahrung, Verband, Stil, Kopf-an-Kopf- und
  Gestellt-Bilanz, Niveau der Paarung. Alle Gänge eines Fests sehen nur den
  Stand **vor** dem Fest.
* **Ehrlich gemessen:** Getestet wird an der jüngsten Saison, nicht an einem
  Zufallssplit. Übernommen wird eine Änderung nur, wenn Validierung **und**
  Test besser werden.
* **Symmetrisch:** „A gegen B" ergibt exakt „B gegen A" mit vertauschten
  Siegen.
* **Im Browser gerechnet:** Die App rechnet jede Prognose selbst
  (`web/lib/inference.ts`). Eine Paritätsprüfung stellt in jedem PR sicher,
  dass Python und TypeScript bitgleich rechnen.

**Wie es dazu kam** (Test 2026, jeweils mit den Daten von damals):

| Schritt | Log-Loss | Treffer |
|---|---:|---:|
| Logistic Regression, erste Merkmale | 0.831 | 63.9 % |
| + Stand vor dem Fest, Gestellt-Neigung | 0.751 | 68.2 % |
| + Spitzenpaarungen, Gestellt-Bilanz des Paars | 0.740 | 68.6 % |
| Gradient Boosting, zweistufig | 0.720 | 69.1 % |
| + schnelleres Rating mit Neulings-Bonus | 0.695 | 70.0 % |
| + Datenkorrekturen (Niederlage „0", Namensvettern, Ränge „15aa") | 0.683 | 70.3 % |

Was sonst geprüft und warum es verworfen wurde, steht in
[docs/MODELL.md](docs/MODELL.md).

**Härtetest:** Das Modell für die Saison 2027 ist eingefroren
(`artifacts/haertetest_modell.json`, mit Prüfsumme). Die Analyse-Seite misst
es laufend an Gängen, die es nie gesehen haben kann.

---

## Daten

Einzige Quelle ist **schlussgang.ch**, nichts wird von Hand gepflegt.

| Was | Woher |
|---|---|
| Gänge (Symbol und Note je Gang) | Statistik-PDF je Fest |
| Schlussranglisten (Rang, Punkte, Klub, Wohnort, Kranz) | Ranglisten-PDF je Fest |
| Porträts (Physis, Verband, Kranzstatus, Schwünge) | JSON:API |
| Feste, vergangene und kommende | JSON:API |

* Jeder Gang steht zweimal in der PDF (einmal je Schwinger). Beide Seiten
  werden gegeneinander geprüft (`+` gegen `o`, `-` gegen `-`); was nicht
  passt, wird verworfen und gezählt.
* Namen werden über einen reihenfolgeunabhängigen Schlüssel zu Personen.
  **Namensvettern** trennt `pipeline/namensvettern.py` über Teilverband,
  Jahrgang, Klub und Wohnort, aber nur mit Beleg (selbes Fest oder selber
  Tag).
* Kränze, Festsiege und Klubs kommen ausschliesslich aus den
  Schlussranglisten.
* Der Scraper hält ein Rate-Limit ein und respektiert `robots.txt`.

Details: [docs/DATEN.md](docs/DATEN.md).

---

## Ablauf

```
schlussgang.ch ──fetch_raw──► artifacts/raw/           (nicht im Repo, Actions-Cache)
               ──run_pipeline──► artifacts/*.json
                                 web/public/data/*.json   (im Repo, vom Bot committet)
                                 └──► Vercel baut die App von main
```

Der Workflow **„Datenpipeline aktualisieren"** (`update.yml`) läuft täglich:
neue Feste holen, trainieren, Parität App ⇄ Pipeline prüfen, Artefakte
committen. Er bricht ab, statt schlechte Daten zu committen (zu viele
verworfene Einträge, eingebrochene Abdeckung). Weitere Workflows: `ci.yml`
(Tests, Parität, Build, `npm audit`), `messung.yml` (Messungen auf den
Rohdaten), `sicherheit.yml` (tägliches Sicherheits-Audit).

---

## Lokal ausführen

Voraussetzungen: Python ≥ 3.11, Node.js ≥ 20.9.

```bash
pip install -r requirements-pipeline.txt
python -m pytest pipeline/tests -q                          # rund 300 Tests

# End-to-End mit Demodaten (offline), danach echte Artefakte zurückholen
python -m pipeline.run_pipeline --source synth && python -m pipeline.verify_inference
git checkout -- artifacts web/public/data web/data

# Parität App ⇄ Pipeline
python -m pipeline.paritaet && (cd web && npm ci && npm run paritaet)

# Modelländerung an den echten Artefakten messen (Validierung 2025, Test 2026)
python -m pipeline.harness

# Web-App
cd web && npm run dev                                       # http://localhost:3000
```

Echte Rohdaten holt `python -m pipeline.fetch_raw --seit-datum auto`
(volle Historie: `--seit-datum 2023-01-01`, rund 20 Minuten), danach
`python -m pipeline.run_pipeline --source scrape`.

---

## Projektstruktur

```
pipeline/          Python: Einlesen, Rating, Merkmale, Training, Export
  scrape/            Abruf von schlussgang.ch und Einlesen der Rohdaten
  tests/             pytest
web/               Next.js 16, React 19, TypeScript
  app/               Seiten
  components/        Diagramme, Karte, Prognose-Ansicht
  lib/               Inferenz, Simulation, Anzeigetexte, Typen
  public/data/       Artefakte, die die App lädt
artifacts/         Erzeugte Artefakte (nie von Hand ändern)
docs/              Ausführliche Dokumentation
scripts/           Hilfsskripte der Workflows
.github/workflows/ CI, täglicher Datenlauf, Messungen, Sicherheits-Audit
```

Wo welche Logik liegt (Python und ihr TypeScript-Spiegel), zeigt die Tabelle
in [CLAUDE.md](CLAUDE.md#wo-was-liegt).

---

## Bekannte Grenzen

* **Physis, Stil und Kranzstatus nur mit Porträt.** schlussgang.ch porträtiert
  nur Kranzer und besser, rund drei Viertel des Kaders haben keines. Das
  Merkmal `portraet_diff` macht diese Datenlage offen sichtbar.
* **Kranzstatus und Porträt sind der heutige Stand**, nicht der vor dem Fest.
* **Namensvettern ohne Beleg** (gleicher Name, gleicher Teilverband, nie am
  selben Fest) bleiben zusammengelegt. Rund 17 Verdachtsfälle zeigt die
  Messung `vettern` (Workflow „Messung auf Rohdaten").
* **Kommende Paarungen** gibt es nur, wenn ein Fest seine Einteilung
  veröffentlicht.
* **Die Verteilung Sieg A / Sieg B ist kein Signal:** A ist die alphabetisch
  kleinere ID.

---

## Datennutzung

Nicht-kommerzielles Hobby-Projekt, Betriebskosten $0 (Vercel Hobby, GitHub
Actions). Gespeichert werden nur abgeleitete Kennzahlen mit Quellenangabe,
keine Kopie der Quelldatenbank. Sensible Felder (Geburtsdatum, Zivilstand)
werden nicht gespeichert, fürs Modell nur der Jahrgang.
