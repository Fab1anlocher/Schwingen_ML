"use client";

import { useState } from "react";
import type { BenchmarkKandidat } from "@/lib/types";

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

interface Metrik {
  key: string;
  label: string;
  modell: number;
  baseline: number;
  format: (v: number) => string;
}

/** Modell-vs-Baseline-Vergleich als horizontale Balken (ergänzt die Zahlentabelle). */
export function VergleichBalken({ metriken }: { metriken: Metrik[] }) {
  return (
    <div className="vergleich-balken">
      {metriken.map((m) => {
        const max = Math.max(m.modell, m.baseline, 1e-9);
        return (
          <div className="vb-zeile" key={m.key}>
            <div className="vb-label">{m.label}</div>
            <div className="vb-bar-row">
              <span className="vb-name">Modell</span>
              <div className="vb-track">
                <div
                  className="vb-fill vb-fill-modell"
                  style={{ width: `${(m.modell / max) * 100}%` }}
                />
              </div>
              <span className="vb-value">{m.format(m.modell)}</span>
            </div>
            <div className="vb-bar-row">
              <span className="vb-name">Baseline</span>
              <div className="vb-track">
                <div
                  className="vb-fill vb-fill-baseline"
                  style={{ width: `${(m.baseline / max) * 100}%` }}
                />
              </div>
              <span className="vb-value">{m.format(m.baseline)}</span>
            </div>
          </div>
        );
      })}
      <div className="vb-legend">
        <span>
          <i className="vb-swatch vb-swatch-modell" /> Modell (Logistic Regression)
        </span>
        <span>
          <i className="vb-swatch vb-swatch-baseline" /> Baseline (Elo)
        </span>
      </div>
    </div>
  );
}

const BENCHMARK_REIHENFOLGE = ["kranz_heuristik", "elo_baseline", "ml_ohne_elo", "ml_komplett"];
const CHAMPION_FARBE = "var(--accent-2)";
const VERGLEICH_FARBE = "#9b978c";

/** 4-Wege-Vergleich Kranz-Heuristik / Elo-Baseline / ML ohne Elo / ML komplett.
 * Champion (ML komplett, Produktionsmodell) ist immer gleich hervorgehoben
 * (Grün) — alle Vergleichskandidaten teilen dieselbe neutrale Vergleichsfarbe,
 * statt vier beliebiger kategorialer Farben (Farbe folgt hier der Rolle
 * "Champion vs. Vergleich", nicht einer willkürlichen Identität). */
export function VierWegeBenchmark({ kandidaten }: { kandidaten: BenchmarkKandidat[] }) {
  const sortiert = [...kandidaten].sort(
    (a, b) => BENCHMARK_REIHENFOLGE.indexOf(a.key) - BENCHMARK_REIHENFOLGE.indexOf(b.key)
  );
  const maxAcc = Math.max(...sortiert.map((k) => k.accuracy), 1e-9);
  const maxBrier = Math.max(...sortiert.map((k) => k.brier_score), 1e-9);
  // MAE/MSE erst anzeigen, wenn JEDER Kandidat sie mitbringt: ein älteres
  // benchmark.json (vor Einführung der Fehlermasse) hat die Felder nicht, und
  // ein halb gefüllter Vergleich wäre irreführender als gar keiner.
  const hatFehlermasse = sortiert.every(
    (k) => typeof k.mae === "number" && typeof k.mse === "number"
  );
  const maxMae = Math.max(...sortiert.map((k) => k.mae ?? 0), 1e-9);
  const maxMse = Math.max(...sortiert.map((k) => k.mse ?? 0), 1e-9);

  const Balken = (
    k: BenchmarkKandidat,
    wert: number,
    max: number,
    format: (v: number) => string,
    key: string
  ) => (
    <div className="vb-bar-row vwb-row" key={key}>
      <span className={`vb-name${k.key === "ml_komplett" ? " vwb-champion-label" : ""}`}>{k.label}</span>
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
          Accuracy <span className="muted small">(höher = besser)</span>
        </div>
        {sortiert.map((k) => Balken(k, k.accuracy, maxAcc, (v) => `${(v * 100).toFixed(1)}%`, `acc-${k.key}`))}
      </div>
      <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
        <div className="vwb-titel">
          Brier-Score <span className="muted small">(tiefer = besser, 0 = perfekt kalibriert)</span>
        </div>
        {sortiert.map((k) => Balken(k, k.brier_score, maxBrier, (v) => v.toFixed(3), `brier-${k.key}`))}
      </div>
      {hatFehlermasse && (
        <>
          <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
            <div className="vwb-titel">
              MAE{" "}
              <span className="muted small">
                (tiefer = besser; Punktwert des Gangs, Sieg=1 / Gestellt=0.5 / Niederlage=0 —
                „im Schnitt so weit daneben“)
              </span>
            </div>
            {sortiert.map((k) => Balken(k, k.mae!, maxMae, (v) => v.toFixed(3), `mae-${k.key}`))}
          </div>
          <div className="vwb-gruppe" style={{ marginTop: "1.1rem" }}>
            <div className="vwb-titel">
              MSE{" "}
              <span className="muted small">
                (tiefer = besser; quadriert, gewichtet grosse Fehlprognosen also stärker als MAE)
              </span>
            </div>
            {sortiert.map((k) => Balken(k, k.mse!, maxMse, (v) => v.toFixed(3), `mse-${k.key}`))}
          </div>
        </>
      )}
      <div className="vb-legend" style={{ marginTop: "0.7rem" }}>
        <span>
          <i className="vb-swatch" style={{ background: CHAMPION_FARBE }} /> ML komplett (Champion, Produktionsmodell)
        </span>
        <span>
          <i className="vb-swatch" style={{ background: VERGLEICH_FARBE }} /> Vergleichskandidaten
        </span>
      </div>
    </div>
  );
}

/** Konfusionsmatrix als Heatmap: Zeile = tatsächliche Klasse, Spalte = vorhergesagte Klasse. */
export function Konfusionsmatrix({
  klassen,
  matrix,
}: {
  klassen: string[];
  matrix: number[][];
}) {
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
                    {summe} Gänge
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
                      style={{ background: `rgba(18, 135, 106, ${0.06 + anteil * 0.6})` }}
                      title={`${wert} von ${summe} tatsächlichen "${LABELS[klassen[i]] ?? klassen[i]}"-Gängen als "${
                        LABELS[klassen[j]] ?? klassen[j]
                      }" vorhergesagt (${(anteilZeile * 100).toFixed(0)}%)`}
                    >
                      <div className="km-count">{wert}</div>
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
        Zeile = tatsächliches Ergebnis, Spalte = Modell-Vorhersage. Dunklere Zellen = mehr
        Gänge; die Diagonale (hervorgehoben) sind die richtig klassifizierten Gänge.
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

const KW = 420;
const KH = 300;
const KPAD = { links: 44, rechts: 14, oben: 12, unten: 34 };

/** Kalibrierung der Gestellt-Klasse: Testgänge nach vorhergesagter
 *  P(Gestellt) in gleich grosse Stufen geteilt; je Stufe vorhergesagt gegen
 *  tatsächlich eingetreten. Auf der Diagonalen = so oft gestellt wie
 *  vorhergesagt. "Gestellt" ist fast nie die wahrscheinlichste Klasse --
 *  Accuracy und Konfusionsmatrix sehen darum nicht, ob diese Zahl stimmt. */
export function GestelltKalibrierung({ daten }: { daten: GestelltKalibrierungDaten }) {
  const [hover, setHover] = useState<number | null>(null);
  const hoechster = Math.max(...daten.stufen.flatMap((s) => [s.vorhergesagt, s.eingetreten]), 0.1);
  const max = Math.min(1, Math.ceil(hoechster * 10 + 0.5) / 10);
  const x = (v: number) => KPAD.links + (v / max) * (KW - KPAD.links - KPAD.rechts);
  const y = (v: number) => KH - KPAD.unten - (v / max) * (KH - KPAD.oben - KPAD.unten);
  const ticks = Array.from({ length: Math.round(max * 10) + 1 }, (_, i) => i / 10);
  const pct = (v: number) => `${(v * 100).toFixed(1)} %`;
  const aktiv = hover !== null ? daten.stufen[hover] : null;

  return (
    <div className="kal-wrap">
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
      <svg
        viewBox={`0 0 ${KW} ${KH}`}
        className="kal-svg"
        role="img"
        aria-label={`Gestellt-Kalibrierung: vorhergesagt ${pct(daten.vorhergesagt)}, eingetreten ${pct(daten.eingetreten)}`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(max)} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} />
            <text x={x(0) - 8} y={y(t) + 4} textAnchor="end" className="streu-achsentext">
              {Math.round(t * 100)}%
            </text>
            <text x={x(t)} y={KH - 14} textAnchor="middle" className="streu-achsentext">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        <line
          x1={x(0)} y1={y(0)} x2={x(max)} y2={y(max)}
          stroke="var(--muted-2)" strokeWidth={1.5} strokeDasharray="5 4"
        />
        <text x={x(max) - 4} y={y(max) + 14} textAnchor="end" className="streu-achsentext">
          perfekt kalibriert
        </text>
        <polyline
          points={daten.stufen.map((s) => `${x(s.vorhergesagt)},${y(s.eingetreten)}`).join(" ")}
          fill="none" stroke="var(--accent-2)" strokeWidth={2}
        />
        {daten.stufen.map((s, i) => (
          <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover((h) => (h === i ? null : h))}>
            <circle cx={x(s.vorhergesagt)} cy={y(s.eingetreten)} r={12} fill="transparent" style={{ cursor: "pointer" }} />
            <circle
              cx={x(s.vorhergesagt)} cy={y(s.eingetreten)} r={hover === i ? 6 : 4.5}
              fill="var(--accent-2)" stroke="var(--surface, #fff)" strokeWidth={2}
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
      <details className="small" style={{ marginTop: "0.6rem" }}>
        <summary className="muted">Als Tabelle</summary>
        <table>
          <thead>
            <tr><th>Stufe</th><th>Gänge</th><th>vorhergesagt</th><th>eingetreten</th></tr>
          </thead>
          <tbody>
            {daten.stufen.map((s, i) => (
              <tr key={i}>
                <td>{i + 1}</td><td>{s.n}</td><td>{pct(s.vorhergesagt)}</td><td>{pct(s.eingetreten)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
