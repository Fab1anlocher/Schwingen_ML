"use client";

// Stil-Landkarte (Seite "Typen", stiltypen.json aus pipeline/stiltypen.py):
// x = gestellt gegenüber der Erwartung, y = Plattwurf gegenüber der Erwartung,
// beides in Prozentpunkten. Der Typ folgt aus der Lage; die Zonen sind darum
// direkt beschriftet und die Punkte einfarbig -- sechs Farben wären in einer
// Punktwolke nicht auseinanderzuhalten, und die Lage sagt schon alles.

import { useMemo, useState } from "react";
import type { Schwinger, StilPunkt, StilTypenArtifact } from "@/lib/types";
import { stilTypName } from "@/lib/labels";
import { useBreite } from "@/lib/useBreite";

const PAD = { links: 14, rechts: 14, oben: 14, unten: 14 };
const TREFFER_RADIUS = 16; // px: so nah muss der Zeiger an einem Punkt sein

export function StilLandkarte({
  daten,
  schwingerById,
  markiert,
  hervorTyp,
  onWaehle,
}: {
  daten: StilTypenArtifact;
  schwingerById: Record<string, Schwinger>;
  markiert: string | null;
  hervorTyp: string | null;
  onWaehle: (sid: string) => void;
}) {
  const [ref, W] = useBreite(720);
  const H = Math.round(Math.min(540, Math.max(320, W * 0.72)));
  const [hover, setHover] = useState<StilPunkt | null>(null);

  // Achsen symmetrisch um 0 (= so wie erwartet), damit oben/unten und
  // links/rechts direkt "mehr/weniger als erwartet" heissen.
  const { xMax, yMax } = useMemo(() => {
    const xs = daten.punkte.map((p) => Math.abs(p.gestellt));
    const ys = daten.punkte.map((p) => Math.abs(p.plattwurf));
    return { xMax: Math.max(...xs, daten.schwelle_gestellt * 2) * 1.08,
             yMax: Math.max(...ys, daten.schwelle_plattwurf * 2) * 1.08 };
  }, [daten]);

  const px0 = PAD.links, px1 = W - PAD.rechts, py0 = PAD.oben, py1 = H - PAD.unten;
  const x = (v: number) => px0 + ((v + xMax) / (2 * xMax)) * (px1 - px0);
  const y = (v: number) => py1 - ((v + yMax) / (2 * yMax)) * (py1 - py0);
  const tg = daten.schwelle_gestellt, tp = daten.schwelle_plattwurf;

  const ausgepraegt = useMemo(
    () => new Set(daten.typen.map((t) => t.ausgepraegteste)),
    [daten]
  );

  function naechster(ev: React.PointerEvent<SVGSVGElement>): StilPunkt | null {
    const box = ev.currentTarget.getBoundingClientRect();
    const mx = ((ev.clientX - box.left) / box.width) * W;
    const my = ((ev.clientY - box.top) / box.height) * H;
    let bester: StilPunkt | null = null;
    let d2 = TREFFER_RADIUS * TREFFER_RADIUS;
    for (const p of daten.punkte) {
      const dx = x(p.gestellt) - mx, dy = y(p.plattwurf) - my;
      const d = dx * dx + dy * dy;
      if (d < d2) { d2 = d; bester = p; }
    }
    return bester;
  }

  // Zonen-Beschriftung in den Ecken (die Mitte ist dicht besetzt).
  const zonen: { typ: string; x: number; y: number; anker: "start" | "middle" | "end" }[] = [
    { typ: "werfer", x: px0 + 6, y: py0 + 16, anker: "start" },
    { typ: "lauerer", x: px1 - 6, y: py0 + 16, anker: "end" },
    { typ: "bollwerk", x: px1 - 6, y: py1 - 8, anker: "end" },
    { typ: "bodenarbeiter", x: px0 + 6, y: py1 - 8, anker: "start" },
    { typ: "entscheider", x: px0 + 6, y: y(0) + 4, anker: "start" },
    { typ: "allrounder", x: x(0), y: y(tp) + 15, anker: "middle" },
  ];

  const tooltipPunkt = hover;
  const tipLinks = tooltipPunkt ? x(tooltipPunkt.gestellt) / W : 0;

  return (
    <div className="stil-wrap" ref={ref}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="stil-svg"
        role="img"
        aria-label={`Stil-Landkarte: ${daten.n_schwinger} Schwinger nach Plattwurf und Gestellt gegenüber der Erwartung`}
        onPointerMove={(ev) => setHover(naechster(ev))}
        onPointerLeave={() => setHover(null)}
        onPointerDown={(ev) => {
          const p = naechster(ev);
          setHover(p);
          if (p) onWaehle(p.schwinger_id);
        }}
      >
        {/* Nulllinien = genau wie erwartet */}
        <line x1={x(0)} x2={x(0)} y1={py0} y2={py1} className="stil-null" />
        <line x1={px0} x2={px1} y1={y(0)} y2={y(0)} className="stil-null" />
        {/* Grenzen der Typen */}
        <line x1={px0} x2={px1} y1={y(tp)} y2={y(tp)} className="stil-grenze" />
        <line x1={px0} x2={x(tg)} y1={y(-tp)} y2={y(-tp)} className="stil-grenze" />
        <line x1={x(tg)} x2={x(tg)} y1={py0} y2={py1} className="stil-grenze" />
        <line x1={x(-tg)} x2={x(-tg)} y1={y(tp)} y2={y(-tp)} className="stil-grenze" />

        {daten.punkte.map((p) => {
          const gedimmt = hervorTyp !== null && p.typ !== hervorTyp;
          if (p.schwinger_id === markiert) return null;
          return (
            <circle
              key={p.schwinger_id}
              cx={x(p.gestellt)}
              cy={y(p.plattwurf)}
              r={ausgepraegt.has(p.schwinger_id) ? 4 : 2.6}
              className={ausgepraegt.has(p.schwinger_id) ? "stil-punkt stil-punkt-ausgepraegt" : "stil-punkt"}
              opacity={gedimmt ? 0.07 : undefined}
            />
          );
        })}

        {zonen.map((z) => (
          <text key={z.typ} x={z.x} y={z.y} textAnchor={z.anker}
                className={`stil-zone${hervorTyp === z.typ ? " stil-zone-aktiv" : ""}`}>
            {stilTypName(z.typ)}
          </text>
        ))}

        {/* Namen der ausgeprägtesten Vertreter je Typ */}
        {daten.typen.map((t) => {
          const p = daten.punkte.find((q) => q.schwinger_id === t.ausgepraegteste);
          if (!p || p.schwinger_id === markiert) return null;
          const cx = x(p.gestellt);
          const rechts = cx > W * 0.62;
          return (
            <text key={t.typ} x={cx + (rechts ? -7 : 7)} y={y(p.plattwurf) + 4}
                  textAnchor={rechts ? "end" : "start"} className="stil-name">
              {schwingerById[p.schwinger_id]?.name ?? p.schwinger_id}
            </text>
          );
        })}

        {hover && hover.schwinger_id !== markiert && (
          <circle cx={x(hover.gestellt)} cy={y(hover.plattwurf)} r={5.5} className="stil-hover" />
        )}

        {markiert && (() => {
          const p = daten.punkte.find((q) => q.schwinger_id === markiert);
          if (!p) return null;
          const cx = x(p.gestellt), cy = y(p.plattwurf);
          const rechts = cx > W * 0.62;
          return (
            <g>
              <circle cx={cx} cy={cy} r={7} className="stil-markiert" />
              <text x={cx + (rechts ? -11 : 11)} y={cy + 5} textAnchor={rechts ? "end" : "start"}
                    className="stil-name stil-name-markiert">
                {schwingerById[p.schwinger_id]?.name ?? p.schwinger_id}
              </text>
            </g>
          );
        })()}
      </svg>

      {tooltipPunkt && (
        <div
          className="stil-tooltip"
          style={{
            left: `${Math.min(Math.max(tipLinks * 100, 18), 82)}%`,
            top: `${(y(tooltipPunkt.plattwurf) / H) * 100}%`,
            transform: `translate(-50%, ${y(tooltipPunkt.plattwurf) < H * 0.35 ? "14px" : "calc(-100% - 14px)"})`,
          }}
        >
          <strong>{schwingerById[tooltipPunkt.schwinger_id]?.name ?? tooltipPunkt.schwinger_id}</strong>
          <span className="stil-tooltip-typ">{stilTypName(tooltipPunkt.typ)}</span>
          <span>
            Plattwurf {Math.round(tooltipPunkt.plattwurf_quote * 100)}% der Siege, erwartet{" "}
            {Math.round(tooltipPunkt.plattwurf_erwartet * 100)}%
          </span>
          <span>
            Gestellt {Math.round(tooltipPunkt.gestellt_quote * 100)}% der Gänge, erwartet{" "}
            {Math.round(tooltipPunkt.gestellt_erwartet * 100)}%
          </span>
          <span className="muted">
            Elo {Math.round(tooltipPunkt.elo)} · {tooltipPunkt.n_gaenge} Gänge
          </span>
        </div>
      )}

      <div className="stil-achsen">
        <span>← stellt seltener</span>
        <span className="stil-achse-mitte">Gestellt gegenüber der Erwartung</span>
        <span>stellt öfter →</span>
      </div>
      <p className="muted small stil-achse-y">
        ↑ oben: gewinnt öfter mit dem Plattwurf als erwartet · ↓ unten: seltener. Die
        gestrichelten Linien sind die Grenzen der Typen.
      </p>
    </div>
  );
}
