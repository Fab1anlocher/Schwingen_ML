"use client";

import { useMemo, useRef, useState } from "react";
import { prognostiziere } from "@/lib/inference";
import type { ModelArtifact, Schwinger, Klasse } from "@/lib/types";

type AchseKey = "rating" | "gewicht" | "groesse" | "form";

const KLASSE_FARBE: Record<Klasse, string> = {
  sieg_a: "var(--a)",
  gestellt: "var(--draw)",
  sieg_b: "var(--b)",
};
const KLASSE_LABEL: Record<Klasse, string> = {
  sieg_a: "Sieg A",
  gestellt: "Gestellt",
  sieg_b: "Sieg B",
};

const N_PUNKTE = 25;
function linspace(min: number, max: number, n: number): number[] {
  if (n <= 1) return [min];
  const schritt = (max - min) / (n - 1);
  return Array.from({ length: n }, (_, i) => min + i * schritt);
}

const ACHSEN: {
  key: AchseKey;
  label: string;
  bereich: [number, number];
  formatX: (v: number) => string;
  verfuegbar: (a: Schwinger, b: Schwinger) => boolean;
  aktuellerWert: (a: Schwinger, eloA: number, eloB: number) => number | null;
}[] = [
  {
    key: "rating",
    label: "Rating-Vorsprung A gegenüber B (Elo)",
    bereich: [-400, 400],
    formatX: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}`,
    verfuegbar: () => true,
    aktuellerWert: (_a, eloA, eloB) => eloA - eloB,
  },
  {
    key: "gewicht",
    label: "Gewicht Schwinger A",
    bereich: [60, 140],
    formatX: (v) => `${v.toFixed(0)} kg`,
    verfuegbar: (a, b) => a.gewicht_kg != null && b.gewicht_kg != null,
    aktuellerWert: (a) => a.gewicht_kg,
  },
  {
    key: "groesse",
    label: "Grösse Schwinger A",
    bereich: [160, 205],
    formatX: (v) => `${v.toFixed(0)} cm`,
    verfuegbar: (a, b) => a.groesse_cm != null && b.groesse_cm != null,
    aktuellerWert: (a) => a.groesse_cm,
  },
  {
    key: "form",
    label: "Form Schwinger A (Siegquote letzte Gänge)",
    bereich: [0, 1],
    formatX: (v) => `${(v * 100).toFixed(0)}%`,
    verfuegbar: () => true,
    aktuellerWert: (a) => a.form,
  },
];

function W() {
  return 640;
}
const H = 240;
const PAD = { links: 42, rechts: 12, oben: 10, unten: 28 };

export function WasWaereWenn({
  model,
  a,
  b,
  eloA,
  eloB,
  nA,
  nB,
  festTyp,
}: {
  model: ModelArtifact;
  a: Schwinger;
  b: Schwinger;
  eloA: number;
  eloB: number;
  nA: number;
  nB: number;
  festTyp: string;
}) {
  const verfuegbareAchsen = useMemo(
    () => ACHSEN.filter((ax) => ax.verfuegbar(a, b)),
    [a, b]
  );
  const [achseKey, setAchseKey] = useState<AchseKey>("rating");
  const achse = verfuegbareAchsen.find((ax) => ax.key === achseKey) ?? verfuegbareAchsen[0];
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const punkte = useMemo(() => {
    const [min, max] = achse.bereich;
    return linspace(min, max, N_PUNKTE).map((v) => {
      let a2 = a;
      let eloA2 = eloA;
      if (achse.key === "gewicht") a2 = { ...a, gewicht_kg: v };
      else if (achse.key === "groesse") a2 = { ...a, groesse_cm: v };
      else if (achse.key === "form") a2 = { ...a, form: v };
      else eloA2 = eloB + v;
      const { p } = prognostiziere(model, a2, b, eloA2, eloB, nA, nB, festTyp);
      return { x: v, p };
    });
  }, [achse, a, b, eloA, eloB, nA, nB, festTyp, model]);

  const px0 = PAD.links;
  const px1 = W() - PAD.rechts;
  const py0 = PAD.oben;
  const py1 = H - PAD.unten;
  const [min, max] = achse.bereich;
  const xScale = (v: number) => px0 + ((v - min) / (max - min)) * (px1 - px0);
  const yScale = (p: number) => py1 - p * (py1 - py0);

  const linie = (klasse: Klasse) =>
    punkte.map((pt) => `${xScale(pt.x).toFixed(1)},${yScale(pt.p[klasse]).toFixed(1)}`).join(" ");

  const aktuellerX = achse.aktuellerWert(a, eloA, eloB);

  const beiMausbewegung = (clientX: number) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const vx = frac * W();
    const idx = Math.round(((vx - px0) / (px1 - px0)) * (N_PUNKTE - 1));
    setHoverIdx(Math.min(N_PUNKTE - 1, Math.max(0, idx)));
  };

  const angezeigtIdx =
    hoverIdx ??
    (aktuellerX != null
      ? Math.round(((aktuellerX - min) / (max - min)) * (N_PUNKTE - 1))
      : Math.floor(N_PUNKTE / 2));
  const angezeigtPunkt = punkte[Math.min(N_PUNKTE - 1, Math.max(0, angezeigtIdx))];

  if (!achse) return null;

  return (
    <div className="www-wrap">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.75rem" }}>
        <label className="field" htmlFor="www-achse" style={{ marginBottom: 0 }}>
          Merkmal variieren
        </label>
        <select
          id="www-achse"
          style={{ width: "auto", minWidth: 260 }}
          value={achse.key}
          onChange={(e) => setAchseKey(e.target.value as AchseKey)}
        >
          {verfuegbareAchsen.map((ax) => (
            <option key={ax.key} value={ax.key}>
              {ax.label}
            </option>
          ))}
        </select>
      </div>

      <div className="www-status muted small">
        Bei {achse.formatX(angezeigtPunkt.x)}
        {hoverIdx === null && aktuellerX != null ? " (aktueller Wert)" : ""}:{" "}
        {(["sieg_a", "gestellt", "sieg_b"] as Klasse[])
          .map((k) => `${KLASSE_LABEL[k]} ${(angezeigtPunkt.p[k] * 100).toFixed(0)}%`)
          .join(" · ")}
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W()} ${H}`}
        className="www-svg"
        role="img"
        aria-label={`Wahrscheinlichkeit nach ${achse.label}`}
        onMouseMove={(e) => beiMausbewegung(e.clientX)}
        onMouseLeave={() => setHoverIdx(null)}
        onTouchMove={(e) => e.touches[0] && beiMausbewegung(e.touches[0].clientX)}
        onTouchEnd={() => setHoverIdx(null)}
      >
        {/* y-Gitter + Ticks 0/50/100% */}
        {[0, 0.5, 1].map((p) => (
          <g key={p}>
            <line
              x1={px0}
              x2={px1}
              y1={yScale(p)}
              y2={yScale(p)}
              stroke="var(--border)"
              strokeWidth={1}
            />
            <text x={px0 - 8} y={yScale(p) + 4} textAnchor="end" className="www-achsentext">
              {(p * 100).toFixed(0)}%
            </text>
          </g>
        ))}
        {/* x-Ticks: min / aktueller Wert / max */}
        <text x={px0} y={H - 8} textAnchor="start" className="www-achsentext">
          {achse.formatX(min)}
        </text>
        <text x={px1} y={H - 8} textAnchor="end" className="www-achsentext">
          {achse.formatX(max)}
        </text>

        {(["sieg_a", "gestellt", "sieg_b"] as Klasse[]).map((k) => (
          <polyline
            key={k}
            points={linie(k)}
            fill="none"
            stroke={KLASSE_FARBE[k]}
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* aktueller Wert: gestrichelte Markierung */}
        {aktuellerX != null && aktuellerX >= min && aktuellerX <= max && (
          <line
            x1={xScale(aktuellerX)}
            x2={xScale(aktuellerX)}
            y1={py0}
            y2={py1}
            stroke="var(--muted)"
            strokeWidth={1.5}
            strokeDasharray="3 3"
          />
        )}

        {/* Hover-Crosshair */}
        {hoverIdx !== null && (
          <g>
            <line
              x1={xScale(punkte[hoverIdx].x)}
              x2={xScale(punkte[hoverIdx].x)}
              y1={py0}
              y2={py1}
              stroke="var(--text)"
              strokeWidth={1}
              opacity={0.35}
            />
            {(["sieg_a", "gestellt", "sieg_b"] as Klasse[]).map((k) => (
              <circle
                key={k}
                cx={xScale(punkte[hoverIdx].x)}
                cy={yScale(punkte[hoverIdx].p[k])}
                r={3.5}
                fill={KLASSE_FARBE[k]}
                stroke="var(--panel)"
                strokeWidth={1.5}
              />
            ))}
          </g>
        )}
      </svg>

      <div className="www-legend">
        {(["sieg_a", "gestellt", "sieg_b"] as Klasse[]).map((k) => (
          <span key={k}>
            <i className="vb-swatch" style={{ background: KLASSE_FARBE[k] }} />
            {KLASSE_LABEL[k]}
          </span>
        ))}
      </div>
      <p className="muted small" style={{ marginTop: "0.5rem" }}>
        Alle anderen Merkmale bleiben auf dem tatsächlichen Wert fixiert — die Kurve zeigt
        ausschliesslich den Effekt von „{achse.label}", isoliert vom Rest.
      </p>
    </div>
  );
}
