"use client";

// Streudiagramm mit linearer Trendlinie und Korrelation r (lib/regression.ts).

import { useMemo, useState } from "react";
import { korrelationsBereich, korrelationsStaerke, linearRegression } from "@/lib/regression";
import { useBreite } from "@/lib/useBreite";

interface Punkt {
  x: number;
  y: number;
  label: string;
}

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
  const [ref, W] = useBreite(320);
  const H = Math.round(Math.min(320, Math.max(200, W * 0.62)));

  const regression = useMemo(() => linearRegression(punkte), [punkte]);

  // Achse mit etwas Rand; beschriftet werden aber die echten Extremwerte (der
  // Rand allein zeigte etwa ein Alter von 14, das es nicht gibt).
  const { xMin, xMax, yMin, yMax, daten } = useMemo(() => {
    const xs = punkte.map((p) => p.x);
    const ys = punkte.map((p) => p.y);
    const d = {
      x0: Math.min(...xs),
      x1: Math.max(...xs),
      y0: Math.min(...ys),
      y1: Math.max(...ys),
    };
    const [x0, x1] = nizeRange(d.x0, d.x1);
    const [y0, y1] = nizeRange(d.y0, d.y1);
    return { xMin: x0, xMax: x1, yMin: y0, yMax: y1, daten: d };
  }, [punkte]);

  const px0 = PAD.links;
  const px1 = W - PAD.rechts;
  const py0 = PAD.oben;
  const py1 = H - PAD.unten;
  const xScale = (v: number) => px0 + ((v - xMin) / (xMax - xMin)) * (px1 - px0);
  const yScale = (v: number) => py1 - ((v - yMin) / (yMax - yMin)) * (py1 - py0);

  if (punkte.length < 5 || !regression) {
    return <p className="muted small">Zu wenig Daten für {titel}.</p>;
  }

  const trendX0 = xMin;
  const trendX1 = xMax;
  const trendY0 = regression.steigung * trendX0 + regression.achsenabschnitt;
  const trendY1 = regression.steigung * trendX1 + regression.achsenabschnitt;

  const rQuadrat = regression.r * regression.r;
  const bereich = korrelationsBereich(regression.r, punkte.length);

  return (
    <div className="streu-wrap" ref={ref}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <strong>{titel}</strong>
        <span className="muted small">
          r = {regression.r.toFixed(2)} (R² = {(rQuadrat * 100).toFixed(0)}%) —{" "}
          {korrelationsStaerke(regression.r)}
        </span>
      </div>
      <div className="muted small">
        {punkte.length} Schwinger
        {bereich &&
          ` · 95 %-Bereich für r: ${bereich[0].toFixed(2)} bis ${bereich[1].toFixed(2)}${
            bereich[0] < 0 && bereich[1] > 0 ? " — kein gesicherter Zusammenhang" : ""
          }`}
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

        <text x={xScale(daten.x0)} y={H - 10} textAnchor="start" className="streu-achsentext">
          {formatX(daten.x0)}
        </text>
        <text x={xScale(daten.x1)} y={H - 10} textAnchor="end" className="streu-achsentext">
          {formatX(daten.x1)}
        </text>
        <text x={px0 - 8} y={yScale(daten.y1) + 4} textAnchor="end" className="streu-achsentext">
          {Math.round(daten.y1)}
        </text>
        <text x={px0 - 8} y={yScale(daten.y0) + 4} textAnchor="end" className="streu-achsentext">
          {Math.round(daten.y0)}
        </text>
      </svg>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="muted small">{achseXLabel} →</span>
        <span className="muted small">↑ Elo-Rating</span>
      </div>
    </div>
  );
}
