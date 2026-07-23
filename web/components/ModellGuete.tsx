"use client";

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
