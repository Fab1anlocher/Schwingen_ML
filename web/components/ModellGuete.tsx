"use client";

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
                      style={{ background: `rgba(61, 139, 110, ${0.08 + anteil * 0.72})` }}
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
