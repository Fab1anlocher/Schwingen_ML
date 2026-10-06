# Daten im Detail

Woher die Daten kommen, wie ein Gang gelesen wird, wie Namen zu Personen
werden und wie der tägliche Lauf sie aktualisiert. Kurzfassung im
[README](../README.md#daten).

## Quellen

Einzige Quelle ist **schlussgang.ch**. Es gibt keine manuell gepflegten
Datenbestände — alles ist jederzeit aus der Quelle reproduzierbar.

| Was | Woher | Modul |
|---|---|---|
| Abgeschlossene Feste | JSON:API `node/event` (`field_event_state=finished`) | `scrape/schlussgang_resultate.py` |
| Gänge (Symbol + Note je Gang) | Statistik-PDF je Fest | `scrape/schlussgang_pdf.py` |
| Schlussranglisten (Rang, Punkte, Klub, Wohnort, Senn/Turner, Kranz) | Ranglisten-PDF je Fest (`field_final_ranking_pdf`, „Quelle: ESV") | `scrape/schlussgang_rangliste.py` |
| Porträts (Gewicht, Grösse, Verband, Kranzstatus, Schwünge) | JSON:API `node/portrait` | `scrape/schlussgang_portraet.py` |
| Kommende Feste | JSON:API `node/event` ab heute (Agenda-HTML als Fallback) | `scrape/agenda.py` |

`scrape/http.py` ist ein höflicher Client: Rate-Limit pro Host, echter
User-Agent, `robots.txt` wird respektiert. esv.ch selbst sperrt
Rechenzentrums-IPs per Firewall; dieselben Ranglisten kommen über
schlussgang.ch auf erlaubtem Weg.

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
nicht stillschweigend übernommen. Der Stern in der Kopfzeile der Statistik-PDF
ist das **Statusabzeichen** des Schwingers, kein Kranzgewinn — Kränze kommen
ausschliesslich aus den Schlussranglisten.

### Schwinger-Identität und Namensvettern

schlussgang.ch schreibt denselben Schwinger unterschiedlich: Porträts als
`Vorname Nachname`, Statistik-PDFs als `Nachname Vorname`. `identity.py` löst
das über einen **reihenfolgeunabhängigen Schlüssel** aus der sortierten
Token-Menge des Namens. Gibt es zu einem Namen mehrere Porträts, rät der
Index nicht; welcher gemeint ist, entscheidet je Fest die Schlussrangliste
(Jahrgang-Zusatz oder Verband des Klubs, s. unten). Nur wo auch sie es offen
lässt, wird der Gang verworfen und gezählt.

Teilnehmer ohne Porträt werden als „Stub" geführt: ihre Gänge zählen voll,
Physis/Alter fehlen. Das betrifft rund drei Viertel des Kaders. Angezeigt
werden sie einheitlich als `Vorname Nachname` (`schema.anzeigename`, nur bei
eindeutig zweiteiligen Namen umgedreht).

**Namensvettern** (`namensvettern.py`): gibt es zu einem Namen nur **ein**
Porträt, landeten früher auch die Gänge und Kränze eines gleichnamigen
Schwingers ohne Porträt dort — Samuel Giger (Thurgau) stand an fünf Tagen an
zwei Festen gleichzeitig im Sägemehl. Getrennt wird über die
Schlussrangliste: ein abweichender Jahrgang-Zusatz, oder Auftritte für Klubs
zweier Teilverbände, die sich zeitlich ständig abwechseln (echte
Namensvettern: 20–38 Wechsel und Feste am selben Tag; Klubwechsler: 2–5
Wechsel, nie am selben Tag — die bleiben eine Person). Getrennt wurden sechs
Personen (Gasser, Ulrich, Giger, Odermatt, Schmid, Bucher). Samuel Giger
stieg dadurch von Elo 1970 auf 2100, und das ganze Modell wurde besser
(Test-Log-Loss 0.7495 → 0.7404).

Die zweite Stufe (ROADMAP D5) trennt Gleichnamige im **selben** Teilverband
über die Herkunft laut Rangliste (Klub, Wohnort), aber nur mit Beleg: beide
am selben Fest oder am selben Tag, oder ständiges Abwechseln bei
verschiedenen Wohnorten. Ein Klubwechsel ohne Beleg bleibt eine Person. Am
selben Fest ordnet das Punktetotal den PDF-Block der richtigen
Ranglisten-Zeile zu. So wurden 18 weitere Personen getrennt; in der App
heissen sie „Name (Klub)". Jede Trennung steht mit Beleg im
Datenqualitätsbericht (`datenqualitaet.namensvettern.herkunft`).

### Was die Schlussranglisten liefern

`ranglisten.py` wertet jede Rangliste aus (480 von 481 Festen seit 2023):

* **Kränze seit 2023** je Schwinger: der Kranz geht an alle ab der
  Punkteschwelle des niedrigsten Markierten (das ESAF markiert nur
  Neueidgenossen; die bisherigen zählen über dieselbe Schwelle mit).
  Kranzquote an Kranzfesten im Median 15.6–16.0 %.
* **Festsiege** (Rang 1, auch geteilt) je Schwinger und je Fest Sieger,
  Teilnehmer und Kränze — für Profil und Rückblick.
* **Schwingklub, Senn/Turner, Kranzstatus** auch ohne Porträt.
* **Teilverband und Kantonal-/Gauverband über den Klub**: jeder Klub gehört
  genau einem Verband an, gelernt aus den Porträts, geprüft per
  Leave-one-out (99.1 % richtig).

Wo auch der Klub fehlt, wird der Teilverband aus den besuchten Festen
geschätzt (`verbandsschaetzung.py`, 99.8 % Treffer an den Porträts) und in
der App als „geschätzt" markiert. Alles davon dient Anzeige und Suche; das
Modell nutzt nur die gemessenen Porträt-Merkmale. Selbstprüfungen je Lauf
stehen in `report.json` → `datenqualitaet`.


## Datenworkflow

```
schlussgang.ch
   │  JSON:API + Statistik-PDFs + Ranglisten-PDFs
   ▼
pipeline.fetch_raw ──────────►  artifacts/raw/     (nicht versioniert, Actions-Cache)
   │                              events.json · gaenge.json · ranglisten.json
   │                              schlussgang_portraits.json · schwinger.json
   ▼
pipeline.run_pipeline
   Einlesen (Namen, Namensvettern) → Labels → Elo → Merkmale → Training
   → Benchmark → Clustering → Export
   ▼
artifacts/*.json  +  web/public/data/*.json  +  web/data/  (versioniert)
   │  Commit auf main löst Vercel-Deploy aus
   ▼
Next.js — lädt JSON, rechnet die Prognose CLIENTSEITIG
```

`artifacts/raw/` ist bewusst nicht im Repo (`gaenge.json` allein > 50 MB).
Versioniert werden nur die kompakten, abgeleiteten Artefakte.

### Automatischer täglicher Lauf

`.github/workflows/update.yml` läuft täglich um 04:00 UTC (und per
`workflow_dispatch` auf jedem Branch; der Schalter `haertetest_einfrieren`
friert das ausgelieferte Modell für den Härtetest der nächsten Saison ein,
neu einfrieren nur, solange diese Saison noch keinen Gang hat, s.
`pipeline/haertetest.py`):

1. **Rohdaten-Cache laden** (`actions/cache`) — trägt die Historie über Läufe.
2. **`pipeline.fetch_raw --seit-datum auto`** — holt Feste ab dem jüngsten
   bekannten Fest minus 14 Tage Überlappung. Der Kader wird danach
   **komplett neu** aus Porträts + PDF-Namen gebaut, nie inkrementell.
3. **`pipeline.run_pipeline --source scrape`** — trainiert und exportiert.
4. **`pipeline.verify_inference`** — `model.json` == sklearn-Modell.
5. **`pipeline.paritaet`** + **`npm run paritaet`** — die App (TypeScript)
   rechnet echte Fälle identisch zur Pipeline, **bevor** Artefakte auf Prod
   gehen.
6. **`pipeline.datenqualitaet`** — Qualitätsbericht ins Job-Summary.
7. **Artefakte committen** und die CI per `workflow_dispatch` starten
   (Pushes mit dem `GITHUB_TOKEN` lösen sonst keine CI aus).

Der Lauf **bricht ab, statt schlechte Daten zu committen**, wenn mehr als
25 % der Roh-Einträge verworfen werden, die Rohabdeckung gegenüber dem Vorlauf
einbricht (Cache verloren) oder die abgeleiteten Gänge einbrechen. Ist der
Cache verloren: **Actions → Datenpipeline aktualisieren → Run workflow →
„Volle Historie ab 2023 neu laden"** (rund 20 Minuten; der tägliche Lauf
braucht rund 2 Minuten).

**Rohdaten-Sicherung** (Roadmap D3): Der Actions-Cache ist die einzige Kopie
der Rohdaten. Sonntags (und per Option „Rohdaten zusätzlich sichern") lädt
der Lauf `artifacts/raw` zusätzlich als Workflow-Artefakt hoch, 90 Tage
aufbewahrt (Actions → Lauf → Artifacts).

Weitere Workflows: `ci.yml` (Tests, synthetischer End-to-End-Lauf, Parität,
Build, `npm audit` in jedem PR), `sicherheit.yml` (tägliches
Sicherheits-Audit npm + pip, meldet Befunde als Issue), `messung.yml`
(„Messung auf Rohdaten": rechnet `python -m pipeline.messung <name>` auf dem
Rohdaten-Cache, Ergebnis im Job-Summary — für alles, was nicht in den
committeten Artefakten steht, etwa die Noten je Gang), Dependabot
(`.github/dependabot.yml`).

## Bekannte Lücken

* **Freiburger Kantonalfest 2023:** Die Rangliste führt keine
  Status-Einträge, dessen Kränze fehlen in der Zählung (im Bericht als
  „Kranzfest ohne Kranz").
* **Feste ohne Statistik-PDF** werden bei jedem vollen Refetch erneut
  angefragt (2 s Rate-Limit je Versuch); der tägliche Lauf ist nicht
  betroffen.
* **Mehrere Porträts gleichen Namens:** aufgelöst je Fest über die
  Rangliste; wo Jahrgang und Klub-Verband fehlen, werden die Gänge
  verworfen und gezählt.
