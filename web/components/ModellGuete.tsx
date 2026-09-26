"use client";

// Diagramme der Analyse-Seite: alle Masse der Ansätze, Konfusionsmatrix und
// Kalibrierungskurve der Gestellt-Chance.

import { useState } from "react";
import type { BenchmarkKandidat } from "@/lib/types";
import { ansatzName, zahl } from "@/lib/labels";
import { useBreite } from "@/lib/useBreite";

const LABELS: Record<string, string> = {
  sieg_a: "Sieg A",
  gestellt: "Gestellt",
  sieg_b: "Sieg B",
};

const KLASSE_FARBE: Record<string, string> = {
  sieg_a: "var(--a)",
  gestellt: "var(--draw)",
  sieg_b: "var(--b)",
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

/** Konfusionsmatrix als Heatmap: Zeile = tatsächliche Klasse, Spalte = vorhergesagte Klasse. */
export function Konfusionsmatrix({ klassen, matrix }: { klassen: string[]; matrix: number[][] }) {
  const max = Math.max(...matrix.flat(), 1);
  const zeilenSumme = matrix.map((z) => z.reduce((a, b) => a + b, 0));

  return (
    <div className="km-wrap">
      <table className="km-table" role="img" aria-label="Konfusionsmatrix">
        <thead>
          <tr>
            <th className="km-corner">
              <span className="muted small">Tatsächlich ↓ / Vorhergesagt →</span>
            </th>
            {klassen.map((k) => (
              <th key={k} style={{ color: KLASSE_FARBE[k] }}>
                {LABELS[k] ?? k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((zeile, i) => {
            const summe = zeilenSumme[i] || 0;
            return (
              <tr key={klassen[i]}>
                <th style={{ color: KLASSE_FARBE[klassen[i]] }}>
                  {LABELS[klassen[i]] ?? klassen[i]}
                  <div className="muted small" style={{ fontWeight: 400 }}>
                    {zahl(summe)} Gänge
                  </div>
                </th>
                {zeile.map((wert, j) => {
                  const anteil = max > 0 ? wert / max : 0;
                  const anteilZeile = summe > 0 ? wert / summe : 0;
                  const richtig = i === j;
                  return (
                    <td
                      key={j}
                      className={`km-cell${richtig ? " km-cell-diag" : ""}`}
                      style={{
                        background: `rgba(18, 135, 106, ${0.06 + anteil * 0.6})`,
                      }}
                      title={`${wert} von ${summe} tatsächlichen "${LABELS[klassen[i]] ?? klassen[i]}"-Gängen als "${
                        LABELS[klassen[j]] ?? klassen[j]
                      }" vorhergesagt (${(anteilZeile * 100).toFixed(0)}%)`}
                    >
                      <div className="km-count">{zahl(wert)}</div>
                      {summe > 0 && <div className="km-pct">{(anteilZeile * 100).toFixed(0)}%</div>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted small" style={{ marginTop: "0.6rem" }}>
        Zeile = tatsächliches Ergebnis, Spalte = Modell-Vorhersage. Dunklere Zellen = mehr Gänge;
        die Diagonale (hervorgehoben) sind die richtig vorhergesagten Gänge. A ist der alphabetisch
        erste der beiden Schwinger — eine reine Ordnung, keine Heim- oder Favoritenrolle.
      </p>
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
