# Roadmap

Stand: Gesamtanalyse vom 24.09.2026. Jeder Punkt beruht auf einer Messung an
den echten Artefakten, nicht auf einer Vermutung — die Zahlen stehen dabei.

Die Reihenfolge folgt den Abhängigkeiten: erst muss die **Messung** stimmen
(P1), sonst lässt sich keine spätere Modelländerung bewerten; erst muss das
Modell **ehrlich** erklären (P2), bevor es besser rechnen soll (P3).

## Was solide ist

Leak-freie Merkmale (nur Daten von *vor* dem Gang), zeitlicher statt
zufälliger Holdout, täglicher Lauf mit Abbruchbedingungen statt stillem
Commit schlechter Daten, Verlustquote unter 1 %, 185 Tests. Die Befunde unten
sind Mess- und Deutungsfehler — keine kaputte Pipeline.

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

**Nach dem ersten echten Lauf prüfen:** Wie viel Gewicht bekommt
`portraet_diff`, und verliert `kranz_diff` dafür an Wichtigkeit? Wie gross ist
der Vorsprung auf `nur_portraet` — das ist die ehrliche Messung der
wrestlerischen Merkmale.

---

## P3 — „Gestellt" wird praktisch nie vorhergesagt

**Priorität hoch · Aufwand mittel**

| Klasse | tatsächlich | prognostiziert | Recall |
|---|---:|---:|---:|
| sieg_a | 39.5 % | 48.8 % | 79.7 % |
| **gestellt** | **21.1 %** | **2.3 %** | **4.6 %** |
| sieg_b | 39.5 % | 48.8 % | 79.7 % |

(Zahlen noch auf dem Testset mit Spiegelzeilen erhoben; die Grössenordnung
ändert P1 nicht.) Jeder fünfte Gang endet gestellt, das Modell sagt es in 2 %
der Fälle. Die App zeigt prominent eine Gestellt-Wahrscheinlichkeit samt Quote
— die ist systematisch zu tief.

- `class_weight="balanced"` gegen den Ist-Zustand messen (Log-Loss **und**
  Recall je Klasse — Balancing kann den Log-Loss verschlechtern).
- Kalibrierung prüfen: Reliability-Diagramm je Klasse.
- Per-Klassen-Metriken in `report.json`; die Gesamt-Accuracy verdeckt heute,
  dass eine von drei Klassen faktisch ausfällt.

## P4 — Sicherheitslücken im Web-Stack

**Priorität hoch · Aufwand klein**

`npm audit`: 3 Schwachstellen, davon 2 hoch und 1 kritisch (PostCSS, über
`next`). `next` ist exakt auf `14.2.5` gepinnt; Fix wäre `14.2.35`.

- `next` aktualisieren, `npm audit --audit-level=high` in die CI.
- Dependabot oder Renovate aktivieren.

## P5 — Parität TypeScript ↔ Python automatisch prüfen

**Priorität mittel · Aufwand klein bis mittel**

`verify_inference` prüft nur `model.json` gegen sklearn, und zwar mit dem
**Python**-Merkmalsvektor. Ein Fehler in `web/lib/inference.ts → baueFeatures`
fiele nirgends auf und erzeugte still falsche Live-Prognosen. Für
`portraet_diff` wurde die Parität von Hand geprüft (100 echte Paare,
Abweichung 0).

- Einen Paritätstest in die CI: `inference.ts` kompilieren, auf einer festen
  Auswahl echter Paare gegen `feature_vektor_fuer_prognose` vergleichen.
  Braucht einen Job mit Node **und** Python.

## P6 — Datenabdeckung erhöhen

**Priorität mittel · Aufwand gross — behebt P2 an der Wurzel**

Nur 706 von 2904 Schwingern haben ein Porträt. P2 macht die Lücke sichtbar,
schliesst sie aber nicht. Eine zweite Quelle für Physis und Verband der übrigen
76 % — z.B. die ESV-Ranglisten — würde P2 und P3 zugleich verbessern. Nicht als
Ersatz für schlussgang.ch, sondern als Ergänzung.

Vorher klären: Erlaubt die Quelle das Abrufen (robots.txt, Nutzungsbedingungen)?
Ein früherer ESV-Teilbaum wurde entfernt, weil der Host CI-Runner mit 403
sperrte.

## P7 — Kleinkram

- `diagnose_agenda` ungetestet.
- ✅ A/B-Zuteilung per Alphabet ist die Ursache der schiefen
  Ergebnisverteilung (35 % / 42 %): im README erklärt und im Qualitätsbericht
  als Artefakt gekennzeichnet.
- `benchmark.py → ml_ohne_elo` enthält `kranz_diff` — misst damit teilweise
  ebenfalls die Datenlage statt „Physis, Stil, Verband".
