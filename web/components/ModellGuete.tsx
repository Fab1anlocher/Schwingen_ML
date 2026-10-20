"use client";

// Diagramme der Analyse-Seite: alle Masse der Ansätze, Treffer und Fehler
// (Konfusionsmatrix für Laien) und Kalibrierungskurve der Gestellt-Chance.

import { useState } from "react";
import type { BenchmarkKandidat } from "@/lib/types";
import { ansatzName, zahl } from "@/lib/labels";
import { useBreite } from "@/lib/useBreite";

const LABELS: Record<string, string> = {
  sieg_a: "Sieg A",
  gestellt: "Gestellt",
  sieg_b: "Sieg B",
};

const BENCHMARK_REIHENFOLGE = [
  "kranz_heuristik",
  "elo_baseline",
  "elo_angepasst",
  "ml_ohne_elo",
  "lr_komplett",
  "ml_komplett",
];
const CHAMPION_FARBE = "var(--accent-2)";
const VERGLEICH_FARBE = "#9b978c";

/** Alle Masse aller Ansätze (Treffer, Log-Loss, Brier, MSE). Das Modell im
 * Einsatz ist hervorgehoben (Grün), alle anderen teilen eine neutrale Farbe --
 * Farbe folgt der Rolle, nicht einer willkürlichen Identität.
 * Kein MAE: er belohnt übertriebene Sicherheit (die Kranz-Faustregel hätte
 * einen besseren MAE als Elo, s. pipeline/benchmark.py). */
export function VierWegeBenchmark({ kandidaten }: { kandidaten: BenchmarkKandidat[] }) {
  const sortiert = [...kandidaten].sort(
    (a, b) => BENCHMARK_REIHENFOLGE.indexOf(a.key) - BENCHMARK_REIHENFOLGE.indexOf(b.key)
  );
  const maxAcc = Math.max(...sortiert.map((k) => k.accuracy), 1e-9);
  const maxBrier = Math.max(...sortiert.map((k) => k.brier_score), 1e-9);
  // MAE/MSE erst anzeigen, wenn JEDER Kandidat sie mitbringt: ein älteres
  // benchmark.json (vor Einführung der Fehlermasse) hat die Felder nicht, und
  // ein halb gefüllter Vergleich wäre irreführender als gar keiner.
  const hatMse = sortiert.every((k) => typeof k.mse === "number");
  const maxMse = Math.max(...sortiert.map((k) => k.mse ?? 0), 1e-9);
  // Log-Loss: ab dem Audit vom 25.09.2026 im Artefakt; die 0/1-Faustregel hat keinen.
  const mitLogLoss = sortiert.filter((k) => typeof k.log_loss === "number");
  const maxLl = Math.max(...mitLogLoss.map((k) => k.log_loss as number), 1e-9);

  const Balken = (
    k: BenchmarkKandidat,
    wert: number,
    max: number,
    format: (v: number) => string,
    key: string
  ) => (
    <div className="vb-bar-row vwb-row" key={key}>
      <span className={`vb-name${k.key === "ml_komplett" ? " vwb-champion-label" : ""}`}>
        {ansatzName(k.key, k.label)}
      </span>
      <div className="vb-track">
        <div
          className="vb-fill"
          style={{
            width: `${(wert / max) * 100}%`,
            background: k.key === "ml_komplett" ? CHAMPION_FARBE : VERGLEICH_FARBE,
          }}
        />
      </div>
      <span className="vb-value">{format(wert)}</span>
    </div>
  );

  return (
    <div className="vwb-wrap">
      <div className="vwb-gruppe">
        <div className="vwb-titel">
          Treffer <span className="muted small">(höher = besser)</span>
        </div>
        {sortiert.map((k) =>
          Balken(k, k.accuracy, maxAcc, (v) => `${(v * 100).toFixed(1)}%`, `acc-${k.key}`)
        )}
      </div>
      {mitLogLoss.length > 0 && (
        <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
          <div className="vwb-titel">
            Log-Loss{" "}
            <span className="muted small">
              (tiefer = besser; bestraft sichere Fehlprognosen stark — für die Faustregel, die immer
              „sicher“ ist, nicht definiert)
            </span>
          </div>
          {mitLogLoss.map((k) =>
            Balken(k, k.log_loss as number, maxLl, (v) => v.toFixed(3), `ll-${k.key}`)
          )}
        </div>
      )}
      <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
        <div className="vwb-titel">
          Brier-Score{" "}
          <span className="muted small">
            (tiefer = besser; 0 = jede Prognose sicher und richtig)
          </span>
        </div>
        {sortiert.map((k) =>
          Balken(k, k.brier_score, maxBrier, (v) => v.toFixed(3), `brier-${k.key}`)
        )}
      </div>
      {hatMse && (
        <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
          <div className="vwb-titel">
            MSE{" "}
            <span className="muted small">
              (tiefer = besser; quadrierter Abstand der erwarteten zur tatsächlichen Punktzahl des
              Gangs, Sieg = 1 / Gestellt = 0.5 / Niederlage = 0)
            </span>
          </div>
          {sortiert.map((k) => Balken(k, k.mse!, maxMse, (v) => v.toFixed(3), `mse-${k.key}`))}
        </div>
      )}
      <div className="vb-legend" style={{ marginTop: "0.7rem" }}>
        <span>
          <i className="vb-swatch" style={{ background: CHAMPION_FARBE }} /> Modell im Einsatz
        </span>
        <span>
          <i className="vb-swatch" style={{ background: VERGLEICH_FARBE }} /> Vergleichskandidaten
        </span>
      </div>
    </div>
  );
}

/** Art eines Felds der Konfusionsmatrix. Treffer: die Diagonale. Knapp
 *  daneben: einen Sieger getippt und der Gang endete gestellt, oder
 *  umgekehrt. Falscher Sieger: der andere hat gewonnen. Farbe = Bewertung
 *  (grün, gelb, rot; Farbcheck dataviz bestanden, Rot gegen Grün für
 *  Farbenblinde knapp), darum immer mit Zeichen und Text, nie Farbe allein. */
type TrefferArt = "treffer" | "knapp" | "falsch";

const TREFFER_ART: Record<TrefferArt, { zeichen: string; name: string; text: string }> = {
  treffer: { zeichen: "✓", name: "Treffer", text: "Ausgang richtig getippt" },
  knapp: {
    zeichen: "≈",
    name: "knapp daneben",
    text: "einen Sieger getippt, aber gestellt – oder umgekehrt",
  },
  falsch: { zeichen: "✗", name: "falscher Sieger", text: "der andere hat gewonnen" },
};
const ARTEN: TrefferArt[] = ["treffer", "knapp", "falsch"];

function artVon(klassen: string[], tatsaechlich: number, tipp: number): TrefferArt {
  if (tatsaechlich === tipp) return "treffer";
  return klassen[tatsaechlich] === "gestellt" || klassen[tipp] === "gestellt" ? "knapp" : "falsch";
}

/** Kurztext im Feld: welcher Fehler genau. */
function feldText(klassen: string[], tatsaechlich: number, tipp: number): string {
  const art = artVon(klassen, tatsaechlich, tipp);
  if (art !== "knapp") return TREFFER_ART[art].name;
  return klassen[tatsaechlich] === "gestellt" ? "gestellt statt Sieg" : "Sieg statt gestellt";
}

/** Anteile auf ganze Kästchen von 100 runden, Summe genau 100 (grösster Rest). */
function aufHundert(werte: number[]): number[] {
  const summe = werte.reduce((a, b) => a + b, 0);
  if (!summe) return werte.map(() => 0);
  const roh = werte.map((w) => (w * 100) / summe);
  const ganz = roh.map(Math.floor);
  let rest = 100 - ganz.reduce((a, b) => a + b, 0);
  const nachRest = roh.map((r, i) => [r - ganz[i], i]).sort((x, y) => y[0] - x[0]);
  for (const [, i] of nachRest) {
    if (rest <= 0) break;
    ganz[i] += 1;
    rest -= 1;
  }
  return ganz;
}

// Mit geschütztem Leerzeichen, damit „%" nicht allein auf die nächste Zeile rutscht.
const pz = (anteil: number) => `${Math.round(anteil * 100)}\u00a0%`;
const pz1 = (anteil: number) => `${(anteil * 100).toFixed(1)}\u00a0%`;

/** Konfusionsmatrix für Laien: zuerst „von 100 Gängen“ (Treffer, knapp
 *  daneben, falscher Sieger), dann die ganze Tabelle mit denselben Farben,
 *  Zeile = tatsächlicher Ausgang, Spalte = Tipp des Modells (sein
 *  wahrscheinlichster Ausgang); rechts je Ausgang, wie viele das Modell
 *  erkannt hat, unten je Tipp, wie oft er stimmte. */
export function Konfusionsmatrix({ klassen, matrix }: { klassen: string[]; matrix: number[][] }) {
  const [aktiv, setAktiv] = useState<TrefferArt | null>(null);
  const n = matrix.flat().reduce((a, b) => a + b, 0);
  const zeilenSumme = matrix.map((z) => z.reduce((a, b) => a + b, 0));
  const spaltenSumme = klassen.map((_, j) => matrix.reduce((a, z) => a + z[j], 0));
  const jeArt: Record<TrefferArt, number> = { treffer: 0, knapp: 0, falsch: 0 };
  matrix.forEach((z, i) => z.forEach((w, j) => (jeArt[artVon(klassen, i, j)] += w)));
  const kaestchen = aufHundert(ARTEN.map((a) => jeArt[a]));
  const felder = ARTEN.flatMap((a, k) => Array.from({ length: kaestchen[k] }, () => a));
  const g = klassen.indexOf("gestellt");
  const gestelltErkannt = g >= 0 && zeilenSumme[g] > 0 ? matrix[g][g] / zeilenSumme[g] : null;
  if (!n) return null;

  return (
    <div className="km">
      <p className="km-lead">
        Von 100 Gängen trifft das Modell <strong>{kaestchen[0]}</strong>.
      </p>
      <div className="km-hundert">
        <div
          className="km-waffel"
          role="img"
          aria-label={`Von 100 Gängen: ${kaestchen[0]} Treffer, ${kaestchen[1]} knapp daneben, ${kaestchen[2]} falscher Sieger`}
        >
          {felder.map((art, i) => (
            <span
              key={i}
              className={`km-feld km-${art}${aktiv && aktiv !== art ? " km-gedimmt" : ""}`}
              title={`${TREFFER_ART[art].name}: ${kaestchen[ARTEN.indexOf(art)]} von 100 Gängen`}
            />
          ))}
        </div>
        <ul className="km-legende">
          {ARTEN.map((art, k) => (
            <li
              key={art}
              tabIndex={0}
              className={aktiv && aktiv !== art ? "km-gedimmt" : undefined}
              onMouseEnter={() => setAktiv(art)}
              onMouseLeave={() => setAktiv(null)}
              onFocus={() => setAktiv(art)}
              onBlur={() => setAktiv(null)}
            >
              <span className={`km-marke km-${art}`} aria-hidden="true">
                {TREFFER_ART[art].zeichen}
              </span>
              <span className="km-legende-zahl">{kaestchen[k]}</span>
              <span>
                <strong>{TREFFER_ART[art].name}</strong>: {TREFFER_ART[art].text}
                <span className="muted small km-legende-genau">
                  {zahl(jeArt[art])} von {zahl(n)} Gängen ({pz1(jeArt[art] / n)})
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <p className="muted small">
        Klar daneben, also der andere gewinnt, liegt das Modell nur bei {pz1(jeArt.falsch / n)}{" "}
        der Gänge. Die meisten Fehler betreffen Gestellte: Das Modell tippt nur auf Gestellt, wenn
        das wahrscheinlicher ist als jeder Sieg, und das ist selten.
        {gestelltErkannt !== null &&
          ` Von den ${zahl(zeilenSumme[g])} gestellten Gängen hat es darum nur ${pz(gestelltErkannt)} als wahrscheinlichsten Ausgang getippt.`}{" "}
        Ob die angezeigte Gestellt-Chance trotzdem stimmt, zeigt der Abschnitt{" "}
        <a href="#gestellt-chance">„Stimmt die Gestellt-Chance?“</a>.
      </p>

      <h3 className="km-titel">Die ganze Tabelle (Konfusionsmatrix)</h3>
      <div className="km-wrap">
        <table className="km-table">
          <caption className="sr-only">
            Konfusionsmatrix: Zeile = tatsächlicher Ausgang, Spalte = Tipp des Modells
          </caption>
          <thead>
            <tr>
              <th />
              <th colSpan={klassen.length} className="km-achse">
                Das Modell tippte auf …
              </th>
              <th />
            </tr>
            <tr>
              <th className="km-achse km-ecke">So endete der Gang ↓</th>
              {klassen.map((k) => (
                <th key={k} scope="col">
                  {LABELS[k] ?? k}
                </th>
              ))}
              <th scope="col" className="km-rand">
                richtig erkannt
              </th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((zeile, i) => (
              <tr key={klassen[i]}>
                <th scope="row">
                  {LABELS[klassen[i]] ?? klassen[i]}
                  <div className="muted small km-unter">{zahl(zeilenSumme[i])} Gänge</div>
                </th>
                {zeile.map((wert, j) => {
                  const art = artVon(klassen, i, j);
                  return (
                    <td
                      key={j}
                      className={`km-cell km-${art}-feld`}
                      title={`${zahl(wert)} von ${zahl(zeilenSumme[i])} Gängen mit Ausgang „${LABELS[klassen[i]] ?? klassen[i]}“ tippte das Modell auf „${LABELS[klassen[j]] ?? klassen[j]}“ (${pz(zeilenSumme[i] ? wert / zeilenSumme[i] : 0)})`}
                    >
                      <div className="km-count">{zahl(wert)}</div>
                      <div className="km-art">
                        <span aria-hidden="true">{TREFFER_ART[art].zeichen}</span>
                        <span className="km-art-text"> {feldText(klassen, i, j)}</span>
                      </div>
                    </td>
                  );
                })}
                <td className="km-rand">
                  <div className="km-count">
                    {pz(zeilenSumme[i] ? matrix[i][i] / zeilenSumme[i] : 0)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="km-rand">
                Tipp stimmte
              </th>
              {klassen.map((k, j) => (
                <td key={k} className="km-rand">
                  <div className="km-count">
                    {pz(spaltenSumme[j] ? matrix[j][j] / spaltenSumme[j] : 0)}
                  </div>
                  <div className="muted small km-unter">von {zahl(spaltenSumme[j])}</div>
                </td>
              ))}
              <td className="km-rand km-gesamt">
                <div className="km-count">{pz1(jeArt.treffer / n)}</div>
                <div className="muted small km-unter">insgesamt</div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <ul className="muted small km-lesehilfe">
        <li>
          Jede <strong>Zeile</strong> ist ein tatsächlicher Ausgang, jede <strong>Spalte</strong> der
          Tipp des Modells, also sein wahrscheinlichster Ausgang. Oben links stehen zum Beispiel die{" "}
          {zahl(matrix[0][0])} Gänge, die {LABELS[klassen[0]] ?? klassen[0]} endeten und für die das
          Modell genau das tippte.
        </li>
        <li>
          <strong>Richtig erkannt</strong> (rechts): welcher Anteil eines Ausgangs richtig getippt
          wurde. <strong>Tipp stimmte</strong> (unten): wie oft ein Tipp eintraf.
        </li>
        <li>
          A ist der alphabetisch erste der beiden Schwinger, eine reine Ordnung ohne Heim- oder
          Favoritenrolle. Dass Sieg A und Sieg B verschieden häufig sind, sagt darum nichts.
        </li>
      </ul>
    </div>
  );
}

export interface GestelltKalibrierungDaten {
  n: number;
  vorhergesagt: number;
  eingetreten: number;
  ece: number;
  auc: number | null;
  stufen: { n: number; vorhergesagt: number; eingetreten: number }[];
}

const KPAD = { links: 44, rechts: 14, oben: 12, unten: 34 };

/** Kalibrierung der Gestellt-Klasse: Testgänge nach vorhergesagter
 *  P(Gestellt) in gleich grosse Stufen geteilt; je Stufe vorhergesagt gegen
 *  tatsächlich eingetreten. Auf der Diagonalen = so oft gestellt wie
 *  vorhergesagt. "Gestellt" ist nur selten die wahrscheinlichste Klasse --
 *  Accuracy und Konfusionsmatrix sehen darum nicht, ob diese Zahl stimmt. */
export function GestelltKalibrierung({
  daten,
  erklaerung,
}: {
  daten: GestelltKalibrierungDaten;
  /** Text rechts neben dem Diagramm (auf dem Handy darunter). */
  erklaerung?: React.ReactNode;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [ref, KW] = useBreite(420);
  const KH = Math.round(Math.min(320, Math.max(220, KW * 0.72)));
  const hoechster = Math.max(...daten.stufen.flatMap((s) => [s.vorhergesagt, s.eingetreten]), 0.1);
  const max = Math.min(1, Math.ceil(hoechster * 10 + 0.5) / 10);
  const x = (v: number) => KPAD.links + (v / max) * (KW - KPAD.links - KPAD.rechts);
  const y = (v: number) => KH - KPAD.unten - (v / max) * (KH - KPAD.oben - KPAD.unten);
  const ticks = Array.from({ length: Math.round(max * 10) + 1 }, (_, i) => i / 10);
  const pct = (v: number) => `${(v * 100).toFixed(1)} %`;
  const aktiv = hover !== null ? daten.stufen[hover] : null;

  const kennzahlen = (
    <div className="kal-kennzahlen">
      <div>
        <div className="muted small">Gestellt vorhergesagt</div>
        <strong>{pct(daten.vorhergesagt)}</strong>
      </div>
      <div>
        <div className="muted small">tatsächlich eingetreten</div>
        <strong>{pct(daten.eingetreten)}</strong>
      </div>
      <div>
        <div className="muted small">Kalibrierungsfehler (ECE)</div>
        <strong>{(daten.ece * 100).toFixed(1)} %-Pkt.</strong>
      </div>
      {daten.auc !== null && (
        <div>
          <div className="muted small">Trennschärfe (AUC)</div>
          <strong>{daten.auc.toFixed(2)}</strong>
        </div>
      )}
    </div>
  );

  return (
    <div className="kal-layout">
      <div className="kal-wrap" ref={ref}>
        <svg
          viewBox={`0 0 ${KW} ${KH}`}
          className="kal-svg"
          role="img"
          aria-label={`Gestellt-Kalibrierung: vorhergesagt ${pct(daten.vorhergesagt)}, eingetreten ${pct(daten.eingetreten)}`}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(0)}
                x2={x(max)}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--border)"
                strokeWidth={1}
              />
              <text x={x(0) - 8} y={y(t) + 4} textAnchor="end" className="streu-achsentext">
                {Math.round(t * 100)}%
              </text>
              <text x={x(t)} y={KH - 14} textAnchor="middle" className="streu-achsentext">
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          <line
            x1={x(0)}
            y1={y(0)}
            x2={x(max)}
            y2={y(max)}
            stroke="var(--muted-2)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
          />
          <text x={x(max) - 4} y={y(max) + 14} textAnchor="end" className="streu-achsentext">
            perfekt kalibriert
          </text>
          <polyline
            points={daten.stufen.map((s) => `${x(s.vorhergesagt)},${y(s.eingetreten)}`).join(" ")}
            fill="none"
            stroke="var(--accent-2)"
            strokeWidth={2}
          />
          {daten.stufen.map((s, i) => (
            <g
              key={i}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((h) => (h === i ? null : h))}
            >
              <circle
                cx={x(s.vorhergesagt)}
                cy={y(s.eingetreten)}
                r={12}
                fill="transparent"
                style={{ cursor: "pointer" }}
              />
              <circle
                cx={x(s.vorhergesagt)}
                cy={y(s.eingetreten)}
                r={hover === i ? 6 : 4.5}
                fill="var(--accent-2)"
                stroke="var(--surface, #fff)"
                strokeWidth={2}
              />
            </g>
          ))}
        </svg>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="muted small">vorhergesagte Gestellt-Chance →</span>
          <span className="muted small">
            {aktiv
              ? `Stufe ${hover! + 1}: vorhergesagt ${pct(aktiv.vorhergesagt)}, eingetreten ${pct(aktiv.eingetreten)} (${aktiv.n} Gänge)`
              : "↑ tatsächlich gestellt"}
          </span>
        </div>
      </div>
      <div>
        {kennzahlen}
        {erklaerung}
        <details className="small" style={{ marginTop: "0.6rem" }}>
          <summary className="muted">Als Tabelle</summary>
          <div className="tabelle-wrap">
            <table>
              <thead>
                <tr>
                  <th>Stufe</th>
                  <th>Gänge</th>
                  <th>vorhergesagt</th>
                  <th>eingetreten</th>
                </tr>
              </thead>
              <tbody>
                {daten.stufen.map((s, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>{s.n}</td>
                    <td>{pct(s.vorhergesagt)}</td>
                    <td>{pct(s.eingetreten)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </div>
  );
}
