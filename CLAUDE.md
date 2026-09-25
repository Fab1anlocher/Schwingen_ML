# CLAUDE.md — Orientierung für KI-Assistenten

Kurzfassung für jede KI, die an diesem Repo arbeitet. Ausführlich: `README.md`.
Sprache im Projekt: **Deutsch** (Bezeichner, Kommentare, Commits, UI).

## Was das ist

Prognose für Schwingen-Gänge (Sieg A / Gestellt / Sieg B) mit Erklärung, dazu
Schwinger-Übersicht, Feste, Karte, Typen und Modellgüte. Modell: zweistufiges
Gradient Boosting (`pipeline/modell.py`; P(Gestellt), dann P(Sieg A |
entschieden)), die Logistic Regression bleibt als Rückfall und Benchmark.
Je Lauf zwei Modelle (`train.trainiere`): das Evaluationsmodell ohne die
jüngste Saison liefert die Kennzahlen, ausgeliefert wird eines inklusive.
**Pipeline** in Python (`pipeline/`) → JSON-Artefakte → **Web-App** in
Next.js 16 (`web/`). Die App rechnet jede Prognose selbst im Browser
(`web/lib/inference.ts`). Live: schwingen-ml.vercel.app, deployt von `main`.

## Datenfluss

```
schlussgang.ch  ──fetch_raw──►  artifacts/raw/         (NICHT im Repo, nur Actions-Cache)
  Porträts, Feste, Statistik-PDFs (Gänge), Schlussranglisten-PDFs (Klub, Kranz, Rang)
                 ──run_pipeline──►  artifacts/*.json + web/public/data/*.json + web/data/
                                    (im Repo, vom Bot committet; Vercel deployt)
```

`run_pipeline` in 8 Stufen: Rohdaten einlesen (inkl. Namensauflösung und
Namensvettern) → Labels/Dedup → Elo → Merkmale → Training/Evaluation →
Benchmark → Clustering → Export.

## Wo was liegt

| Thema | Python | TypeScript (App) |
|---|---|---|
| Merkmale (Modell-Eingabe) | `features.py` (`_feature_vektor`, einzige Definition) | `lib/inference.ts` (`baueFeatures`, Spiegel) |
| Modell (Training, Symmetrie, Monotonie) | `modell.py`, Hyperparameter in `config.py` | `lib/inference.ts` (`wahrscheinlichkeiten`) |
| model.json (Bäume je Stufe) | `export.modell_json`, Prüfung `pruefe_modell_export` | Typ `ModelArtifact` in `lib/types.ts` |
| Modellgüte je Lauf | `export.ergaenze_verlauf` → `report_verlauf.json` | `components/VerlaufDiagramm.tsx` |
| Prognose-Check je Fest | `prognose_check.py` → `events.json` | `app/feste/page.tsx` (Rückblick) |
| Kopf-an-Kopf / Paar-Historie | `features._kopf_an_kopf_vorteil`, `paar_gestellt` | `lib/kopfAnKopf.ts` |
| Konstanten der Merkmale | `config.py` (`MERKMAL_VERSION`, `PAAR_GESTELLT_K`, …) | `inference.ts` (gleiche Werte) |
| Namen → Schwinger-ID | `identity.py`, `roster.py`, `namensvettern.py` | – |
| Ranglisten (Kränze, Klub, Festsiege) | `scrape/schlussgang_rangliste.py`, `ranglisten.py` | – |
| Teilverband | Porträt → Klub (`ranglisten.verband_ueber_klub`) → Schätzung (`verbandsschaetzung.py`) | `lib/teilverband.ts` (`verbandVon`) |
| Anzeigetexte (Verband, Festtyp, Kranz, Schwung, Zahlen) | `schema.anzeigename` | `lib/labels.ts` — **nur hier** |
| Export der Artefakte | `export.py` | Typen in `lib/types.ts` |

## Invarianten — nicht brechen

1. **Merkmale nur hinten anhängen** (`FEATURE_NAMES`). `model.json` ist
   positionsgebunden. Ändert sich eine Definition oder kommt ein Merkmal dazu:
   `MERKMAL_VERSION` erhöhen, `MERKMALE_JE_VERSION` ergänzen, in
   `inference.ts` den Versionszweig ergänzen. Die App muss ältere
   `model.json` weiter nach **deren** Version rechnen (der Bot-Lauf kann dem
   Code hinterherhinken).
2. **Python und TypeScript rechnen identisch** — bitgleich, weil Bäume an
   exakten Schwellen trennen (deshalb die Form von `_kopf_an_kopf_vorteil`).
   Jede Änderung an `features.py`, `kopfAnKopf`, der Baumauswertung,
   Konstanten oder Normalisierungen (`clustering._normiert` ⇄
   `labels.schwungName`) auf beiden Seiten. Prüfen:
   `python -m pipeline.paritaet && (cd web && npm run paritaet)`.
   **Paar-Symmetrie:** „A gegen B" = „B gegen A" mit vertauschten Siegen.
   Das Boosting erzwingt das durch Mitteln mit der gespiegelten Paarung
   (`modell.spiegle`, `SYMMETRISCH`). Ein neues Merkmal muss dort als
   symmetrisch oder als Differenz eingetragen sein (auch in `inference.ts`).
3. **Leak-frei.** Alle Gänge eines Fests sehen den Stand **vor** dem Fest
   (Form, Kopf-an-Kopf, Neigung, Elo-Snapshots). Holdout = jüngste Saison,
   kein Zufallssplit. Training mit Spiegelzeilen (B-gegen-A), Test **ohne**.
4. **Artefakte nie von Hand ändern.** Sie entstehen im Workflow `update.yml`.
   `run_pipeline --source synth` überschreibt sie mit Demodaten → danach
   `git checkout -- artifacts web/public/data web/data`.
5. **Datenwerte sind ASCII-Schlüssel** (`Suedwestschweiz`, `eidgenoessisch`,
   `koenig`). Angezeigt wird nur über `lib/labels.ts`.
6. **Gemessen statt geschätzt kennzeichnen.** Geschätzte Werte haben eigene
   Felder (`teilverband_geschaetzt`) und erscheinen in der App als „geschätzt".
7. **esv.ch nicht umgehen.** Die Firewall sperrt Rechenzentrums-IPs; dieselben
   Ranglisten kommen legitim über schlussgang.ch. Rate-Limit und `robots.txt`
   einhalten (`scrape/http.py`).

## Prüfen, bevor etwas gepusht wird

```bash
python -m pytest pipeline/tests -q                      # ~260 Tests
python -m pipeline.run_pipeline --source synth && python -m pipeline.verify_inference
git checkout -- artifacts web/public/data web/data      # Demodaten verwerfen!
python -m pipeline.paritaet && (cd web && npm run paritaet)
cd web && npx tsc --noEmit -p . && npm run build
```

Die CI (`.github/workflows/ci.yml`) führt dasselbe aus, plus `npm audit`.

## Modelländerungen messen

Ohne Rohdaten, an den committeten Artefakten: `pipeline/harness.py`
(`lade()` → `bewerte()` liefert Validierung 2025 und Test 2026, `typ="lr"`
für die LR). Eine Änderung wird nur übernommen, wenn **beide** Jahre besser
werden. Ausnahme: Vorgaben gegen Unsinn (Monotonie) bei Güte im Rauschen.
Neben der Güte die Plausibilität prüfen: Erklärbalken einiger
Spitzenpaarungen (Orlik–Staudenmann) und Monotonie der Gestellt-Merkmale. Kennzahlen und die
Begründung gehören als Kommentar an die Stelle im Code (Muster: siehe
`config.py` bei `MERKMAL_VERSION`).

## Echte Artefakte erzeugen (Pipeline-Änderung)

Die Rohdaten liegen nur im Actions-Cache. Workflow **„Datenpipeline
aktualisieren"** (`update.yml`) per `workflow_dispatch` auf dem eigenen Branch
starten. Er rechnet mit dem Branch-Code, prüft Parität und Inferenz,
committet die Artefakte auf den Branch und startet danach die CI selbst.
Bot-Pushes lösen sonst keine CI aus. Messungen, die die Rohdaten brauchen
(z.B. Noten je Gang), laufen im Workflow **„Messung auf Rohdaten"**
(`messung.yml`, Modul `pipeline/messung.py`), Ergebnis im Job-Summary. Die
Ergebnisse des Pipeline-Laufs stehen in
`artifacts/report.json` → `datenqualitaet`, der Verlauf in
`artifacts/report_verlauf.json`.

## Fachwissen Schwingen (für Plausibilitätsprüfungen)

- **Kranzquote:** An einem Kranzfest (Kantonal, Teilverband, Berg,
  Eidgenössisch) gewinnen 15–18 % der Teilnehmer einen Kranz, in der Regel ab
  56.50 Punkten; wenige Teilnehmer, wenige Kränze. Kilchberg, Unspunnen und
  Jubiläumsfeste vergeben keine Kränze. Geprüft in
  `ranglisten.kranzquote_ausreisser` (12–21 % mit Spielraum).
- **Noten je Gang:** Plattwurf-Sieg 10.00, Sieg 9.75, Gestellt 8.75 (technisch
  hochstehend bis 9.00), Niederlage 8.50 (offensiv 8.75). Im **Schlussgang**
  sind 10.00/8.75 vorgeschrieben — dort sagen Noten nichts über den Gang.
  Details und Merkmalsideen: `ROADMAP.md` → D1.
- **Symbole der Statistik-PDF:** `+` Sieg, `-` Gestellt, `o` Niederlage; der
  Stern ist ein Statusabzeichen, kein Kranz (s. unten).

## Fallstricke (real passiert)

- **Namensvettern:** Ein Porträt pro Name heisst nicht eine Person.
  `namensvettern.py` trennt über Klub/Jahrgang der Rangliste, aber nur bei
  durchmischten Auftritten. Ein Klubwechsel bleibt eine Person.
- **Der Stern in der Statistik-PDF** ist das Statusabzeichen, kein Kranzgewinn.
  Kränze kommen ausschliesslich aus den Schlussranglisten.
- **Next 16 / LightningCSS** fasst `-webkit-backdrop-filter` und
  `backdrop-filter` zusammen und behält die **letzte** Angabe. Deshalb steht der
  Standard zuletzt.
- **`next dev`** schreibt `web/AGENTS.md` und `web/CLAUDE.md` (gitignored, kein
  Projektinhalt).
- **Lockfile:** CI nutzt npm 11. Lokales npm 10 entfernt `libc`-Felder, diese
  Änderung nicht committen.
- **A/B ist nicht zufällig:** A = kanonisch kleinere ID (alphabetisch). Die
  Ergebnisverteilung A/B ist darum kein Signal.
- **Boosting in dünnen Ecken:** Ohne Monotonie-Vorgaben senkte eine hohe
  Gestellt-Bilanz bei 7–8 % der Paare die Gestellt-Chance. Neue Merkmale mit
  sachlich klarer Richtung gehören in `MONOTON_GESTELLT`/`MONOTON_SIEG`.
- **`pkill -f "next start"`** trifft auch die eigene Shell (das Muster steht
  in ihrer Kommandozeile). `pkill -f "[n]ext-server"` nehmen.
