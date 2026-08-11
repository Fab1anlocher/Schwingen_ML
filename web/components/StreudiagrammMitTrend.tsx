"use client";

import { useMemo, useState } from "react";
import { linearRegression, korrelationsStaerke } from "@/lib/regression";

interface Punkt {
  x: number;
  y: number;
  label: string;
}

const W = 640;
const H = 320;
const PAD = { links: 48, rechts: 16, oben: 12, unten: 34 };

function nizeRange(min: number, max: number): [number, number] {
  const puffer = (max - min) * 0.06 || 1;
  return [min - puffer, max + puffer];
}

/** Streudiagramm mit linearer Trendlinie + Pearson-r (Analyse-Seite: hängt
 * Elo mit einem physischen Merkmal zusammen, und wie stark?). */
export function StreudiagrammMitTrend({
  titel,
  achseXLabel,
  punkte,
  formatX,
}: {
  titel: string;
  achseXLabel: string;
  punkte: Punkt[];
  formatX: (v: number) => string;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const regression = useMemo(() => linearRegression(punkte), [punkte]);

  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    const xs = punkte.map((p) => p.x);
    const ys = punkte.map((p) => p.y);
    const [x0, x1] = nizeRange(Math.min(...xs), Math.max(...xs));
    const [y0, y1] = nizeRange(Math.min(...ys), Math.max(...ys));
    return { xMin: x0, xMax: x1, yMin: y0, yMax: y1 };
  }, [punkte]);

  const px0 = PAD.links;
  const px1 = W - PAD.rechts;
  const py0 = PAD.oben;
  const py1 = H - PAD.unten;
  const xScale = (v: number) => px0 + ((v - xMin) / (xMax - xMin)) * (px1 - px0);
  const yScale = (v: number) => py1 - ((v - yMin) / (yMax - yMin)) * (py1 - py0);

  if (punkte.length < 5 || !regression) {
    return (
      <p className="muted small">Zu wenig Daten für {titel}.</p>
    );
  }

  const trendX0 = xMin;
  const trendX1 = xMax;
  const trendY0 = regression.steigung * trendX0 + regression.achsenabschnitt;
  const trendY1 = regression.steigung * trendX1 + regression.achsenabschnitt;

  const rQuadrat = regression.r * regression.r;

  return (
    <div className="streu-wrap">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <strong>{titel}</strong>
        <span className="muted small">
          r = {regression.r.toFixed(2)} (R² = {(rQuadrat * 100).toFixed(0)}%) —{" "}
          {korrelationsStaerke(regression.r)}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="streu-svg"
        role="img"
        aria-label={`${titel}: r=${regression.r.toFixed(2)}`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={px0}
            x2={px1}
            y1={py0 + f * (py1 - py0)}
            y2={py0 + f * (py1 - py0)}
            stroke="var(--border)"
            strokeWidth={1}
          />
        ))}

        {punkte.map((p, i) => (
          <circle
            key={i}
            cx={xScale(p.x)}
            cy={yScale(p.y)}
            r={hoverIdx === i ? 4.5 : 3}
            fill="var(--accent)"
            opacity={hoverIdx === null || hoverIdx === i ? 0.55 : 0.2}
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx((h) => (h === i ? null : h))}
            style={{ cursor: "pointer", transition: "r 0.1s ease" }}
          >
            <title>
              {p.label}: {achseXLabel} {formatX(p.x)}, Elo {Math.round(p.y)}
            </title>
          </circle>
        ))}

        <line
          x1={xScale(trendX0)}
          y1={yScale(trendY0)}
          x2={xScale(trendX1)}
          y2={yScale(trendY1)}
          stroke="var(--text)"
          strokeWidth={2}
          strokeDasharray="6 4"
        />

        <text x={px0} y={H - 10} textAnchor="start" className="streu-achsentext">
          {formatX(xMin)}
        </text>
        <text x={px1} y={H - 10} textAnchor="end" className="streu-achsentext">
          {formatX(xMax)}
        </text>
        <text x={px0 - 8} y={py0 + 4} textAnchor="end" className="streu-achsentext">
          {Math.round(yMax)}
        </text>
        <text x={px0 - 8} y={py1 + 4} textAnchor="end" className="streu-achsentext">
          {Math.round(yMin)}
        </text>
      </svg>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="muted small">{achseXLabel} →</span>
        <span className="muted small">↑ Elo-Rating</span>
      </div>
    </div>
  );
}
