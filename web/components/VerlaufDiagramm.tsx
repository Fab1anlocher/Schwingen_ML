"use client";

// Verlauf einer Kennzahl über die Pipeline-Läufe (report_verlauf.json, Roadmap
// T1): eine Linie je Diagramm, Modellwechsel als senkrechte Markierung, Wert
// beim Überfahren. Bewusst zwei getrennte Diagramme (Log-Loss, Accuracy) statt
// einer zweiten y-Achse -- zwei Skalen in einem Bild lesen sich falsch.
//
// Der Verlauf hat einen Eintrag je Tag UND Modellstand: wechselt das Modell
// an einem Tag, stehen dort mehrere Punkte übereinander (senkrechter Sprung).

import { useMemo, useState } from "react";
import { datumKurz } from "@/lib/labels";
import { useBreite } from "@/lib/useBreite";

export interface VerlaufLauf {
  datum: string;
  modell_typ: string;
  merkmal_version: number;
  holdout_jahr: number | null;
  log_loss: number;
  accuracy: number;
  n_gaenge: number | null;
  /** Log-Loss der reinen Elo-Prognose auf denselben Testgängen. */
  baseline_log_loss?: number | null;
}

// Breite = gemessene Breite des Containers (1 SVG-Einheit = 1 px), damit die
// Achsenschrift auf dem Handy nicht mitschrumpft. 640 bis zur ersten Messung.
const W_START = 640;
const H = 220;
const PAD = { links: 52, rechts: 16, oben: 22, unten: 28 };

/** Kurzname eines Modellstands für Markierung und Tooltip. */
export function modellStand(l: VerlaufLauf): string {
  return `${l.modell_typ === "gbm" ? "Boosting" : "LR"} · Merkmale v${l.merkmal_version}`;
}

const tag = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / 86_400_000;

export function VerlaufDiagramm({
  laeufe,
  titel,
  wert,
  format,
  schwelle,
}: {
  laeufe: VerlaufLauf[];
  titel: string;
  wert: (l: VerlaufLauf) => number;
  format: (v: number) => string;
  /** Optionale waagrechte Alarmgrenze (gestrichelt, beschriftet). */
  schwelle?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [wrapRef, W] = useBreite(W_START, 280);

  const skala = useMemo(() => {
    const xs = laeufe.map((l) => tag(l.datum));
    const ys = [...laeufe.map(wert), ...(schwelle !== undefined ? [schwelle] : [])];
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const puffer = (y1 - y0) * 0.12 || Math.abs(y0) * 0.01 || 0.01;
    return {
      x0,
      x1: x1 === x0 ? x0 + 1 : x1,
      y0: y0 - puffer,
      y1: y1 + puffer,
    };
  }, [laeufe, wert, schwelle]);

  if (laeufe.length < 2) return null;

  const px = (l: VerlaufLauf) =>
    PAD.links + ((tag(l.datum) - skala.x0) / (skala.x1 - skala.x0)) * (W - PAD.links - PAD.rechts);
  const py = (v: number) =>
    H - PAD.unten - ((v - skala.y0) / (skala.y1 - skala.y0)) * (H - PAD.oben - PAD.unten);

  // Wo sich Modelltyp oder Merkmalsversion ändert: senkrechte Markierung,
  // je Tag nur eine (beschriftet mit dem Stand, der danach gilt).
  const wechselJeTag = new Map<string, VerlaufLauf>();
  laeufe.forEach((l, i) => {
    if (i > 0 && modellStand(l) !== modellStand(laeufe[i - 1])) wechselJeTag.set(l.datum, l);
  });
  const wechsel = [...wechselJeTag.values()];

  const pfad = laeufe
    .map((l, i) => `${i ? "L" : "M"}${px(l).toFixed(1)},${py(wert(l)).toFixed(1)}`)
    .join(" ");
  const aktiv = hover !== null ? laeufe[hover] : null;
  const ticks = [0, 0.5, 1].map((f) => skala.y0 + f * (skala.y1 - skala.y0));

  // Nächster Lauf zur Mausposition (Trefferfläche = ganze Fläche, nicht nur
  // der Punkt). Abstand vor allem waagrecht; senkrecht nur, um zwischen
  // Punkten desselben Tags (Modellwechsel) zu wählen.
  function beiMaus(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const y = ((e.clientY - rect.top) / rect.height) * H;
    const abstand = (l: VerlaufLauf) => Math.abs(px(l) - x) * 1000 + Math.abs(py(wert(l)) - y);
    let best = 0;
    laeufe.forEach((l, i) => {
      if (abstand(l) < abstand(laeufe[best])) best = i;
    });
    setHover(best);
  }

  return (
    <div className="verlauf-wrap" ref={wrapRef}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <strong>{titel}</strong>
        <span className="muted small">
          {aktiv
            ? `${datumKurz(aktiv.datum)}: ${format(wert(aktiv))} · ${modellStand(aktiv)}`
            : `zuletzt ${format(wert(laeufe[laeufe.length - 1]))}`}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="verlauf-svg"
        role="img"
        aria-label={`${titel} im Verlauf`}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.links} x2={W - PAD.rechts} y1={py(v)} y2={py(v)} stroke="var(--border)" />
            <text x={PAD.links - 6} y={py(v) + 4} textAnchor="end" className="streu-achsentext">
              {format(v)}
            </text>
          </g>
        ))}
        {wechsel.map((l) => (
          <g key={l.datum}>
            <line
              x1={px(l)}
              x2={px(l)}
              y1={PAD.oben - 6}
              y2={H - PAD.unten}
              stroke="var(--muted-2)"
              strokeDasharray="3 3"
            />
            <text x={px(l) - 4} y={PAD.oben - 10} textAnchor="end" className="streu-achsentext">
              {modellStand(l)}
            </text>
          </g>
        ))}
        {schwelle !== undefined && (
          <g>
            <line
              x1={PAD.links}
              x2={W - PAD.rechts}
              y1={py(schwelle)}
              y2={py(schwelle)}
              stroke="var(--accent)"
              strokeDasharray="5 4"
              strokeWidth={1.5}
            />
            <text
              x={W - PAD.rechts}
              y={py(schwelle) - 5}
              textAnchor="end"
              className="streu-achsentext"
            >
              Alarmgrenze {format(schwelle)}
            </text>
          </g>
        )}
        <path
          d={pfad}
          fill="none"
          stroke="var(--accent-2)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {laeufe.map((l, i) => (
          <circle
            key={`${l.datum}-${i}`}
            cx={px(l)}
            cy={py(wert(l))}
            r={hover === i ? 5 : 3}
            fill="var(--accent-2)"
            stroke="var(--surface)"
            strokeWidth={hover === i ? 2 : 0}
          />
        ))}
        {aktiv && (
          <line
            x1={px(aktiv)}
            x2={px(aktiv)}
            y1={PAD.oben}
            y2={H - PAD.unten}
            stroke="var(--text)"
            strokeOpacity={0.25}
          />
        )}
        <text x={PAD.links} y={H - 8} className="streu-achsentext">
          {datumKurz(laeufe[0].datum)}
        </text>
        <text x={W - PAD.rechts} y={H - 8} textAnchor="end" className="streu-achsentext">
          {datumKurz(laeufe[laeufe.length - 1].datum)}
        </text>
        <rect
          x={PAD.links}
          y={0}
          width={W - PAD.links - PAD.rechts}
          height={H}
          fill="transparent"
          onMouseMove={beiMaus}
          onMouseLeave={() => setHover(null)}
        />
      </svg>
    </div>
  );
}
