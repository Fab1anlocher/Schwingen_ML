"use client";

import type { KantonStatistik } from "@/lib/types";

const FARBE = "var(--accent)";

function siegquote(g: KantonStatistik): number {
  const n = g.n_siege + g.n_gestellt + g.n_niederlagen;
  return n > 0 ? g.n_siege / n : 0;
}

/** Vergleicht mehrere Kantonal-/Gauverbände einzeln (z.B. Berns 6 Regionen),
 * die auf der Schweiz-Karte zu einem Kanton zusammengefasst sind, weil dafür
 * keine passenden Kartengrenzen existieren (s. pipeline/kantone.py). */
export function GauverbandVergleich({
  titel,
  gauverbaende,
  namen,
}: {
  titel: string;
  gauverbaende: KantonStatistik[];
  namen: string[];
}) {
  const gefiltert = gauverbaende
    .filter((g) => namen.includes(g.kanton) && g.n_schwinger > 0)
    .sort((a, b) => (b.elo_avg ?? 0) - (a.elo_avg ?? 0));

  if (gefiltert.length === 0) return null;

  const maxElo = Math.max(...gefiltert.map((g) => g.elo_avg ?? 0), 1);
  const maxSieg = Math.max(...gefiltert.map(siegquote), 0.01);

  return (
    <div className="vergleich-balken">
      <strong>{titel}</strong>
      <p className="muted small" style={{ marginTop: "0.3rem", marginBottom: "0.9rem" }}>
        Die Karte oben fasst diese {gefiltert.length} Gauverbände zu einem Kanton zusammen (keine
        eigenen Kartengrenzen verfügbar) — hier einzeln im Vergleich.
      </p>
      {gefiltert.map((g) => (
        <div className="vb-zeile" key={g.kanton}>
          <div className="vb-label">
            {g.kanton} <span className="muted">· {g.n_schwinger} Schwinger</span>
          </div>
          <div className="vb-bar-row">
            <span className="vb-name">Elo</span>
            <div className="vb-track">
              <div
                className="vb-fill"
                style={{ width: `${((g.elo_avg ?? 0) / maxElo) * 100}%`, background: FARBE }}
              />
            </div>
            <span className="vb-value">{Math.round(g.elo_avg ?? 0)}</span>
          </div>
          <div className="vb-bar-row">
            <span className="vb-name">Siege</span>
            <div className="vb-track">
              <div
                className="vb-fill"
                style={{ width: `${(siegquote(g) / maxSieg) * 100}%`, background: FARBE }}
              />
            </div>
            <span className="vb-value">{(siegquote(g) * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}
