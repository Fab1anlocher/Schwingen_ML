"use client";

export interface SchwungStat {
  schwung: string;
  n: number;
  eloAvg: number;
}

const W = 640;
const ZEILE_H = 34;
const PAD = { links: 130, rechts: 56, oben: 8, unten: 8 };

/** Cleveland-Dot-Plot statt Balken: Elo-Durchschnitte liegen alle in einer
 * engen Bandbreite (~1500-1900) -- ein Balken ab 0 würde die echten
 * Unterschiede fast unsichtbar machen (derselbe Fehler wie die frühere
 * Karten-Farbskala). Ein Punkt je Kategorie mit gemeinsamer Referenzlinie
 * (Gesamtschnitt) zeigt "über/unter Durchschnitt" ehrlich, ohne einen
 * Balken-Nullpunkt vorzutäuschen, der hier nicht aussagekräftig ist. */
export function SchwungVergleich({
  daten,
  gesamtschnitt,
}: {
  daten: SchwungStat[];
  gesamtschnitt: number;
}) {
  if (daten.length === 0) return null;
  const H = daten.length * ZEILE_H + PAD.oben + PAD.unten;

  const werte = daten.map((d) => d.eloAvg).concat(gesamtschnitt);
  const xMin = Math.min(...werte);
  const xMax = Math.max(...werte);
  const puffer = (xMax - xMin) * 0.15 || 20;
  const x0 = xMin - puffer;
  const x1 = xMax + puffer;
  const xScale = (v: number) => PAD.links + ((v - x0) / (x1 - x0)) * (W - PAD.links - PAD.rechts);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="schwung-svg" role="img" aria-label="Ø Elo je bevorzugtem Schwung">
        <line
          x1={xScale(gesamtschnitt)}
          x2={xScale(gesamtschnitt)}
          y1={0}
          y2={H}
          stroke="var(--muted)"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />
        <text x={xScale(gesamtschnitt)} y={11} textAnchor="middle" className="schwung-referenz">
          Ø {gesamtschnitt.toFixed(0)}
        </text>
        {daten.map((d, i) => {
          const y = PAD.oben + i * ZEILE_H + ZEILE_H / 2;
          const ueberdurchschnitt = d.eloAvg >= gesamtschnitt;
          return (
            <g key={d.schwung}>
              <text x={0} y={y + 4} className="schwung-label">
                {d.schwung}
              </text>
              <line
                x1={xScale(gesamtschnitt)}
                x2={xScale(d.eloAvg)}
                y1={y}
                y2={y}
                stroke={ueberdurchschnitt ? "var(--accent-2)" : "var(--muted-2)"}
                strokeWidth={2}
                opacity={0.5}
              />
              <circle
                cx={xScale(d.eloAvg)}
                cy={y}
                r={5.5}
                fill={ueberdurchschnitt ? "var(--accent-2)" : "var(--muted-2)"}
                stroke="var(--surface)"
                strokeWidth={1.5}
              >
                <title>
                  {d.schwung}: Ø {d.eloAvg.toFixed(0)} Elo ({d.n} Schwinger)
                </title>
              </circle>
              <text x={xScale(d.eloAvg)} y={y - 10} textAnchor="middle" className="schwung-wert">
                {d.eloAvg.toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="muted small" style={{ marginTop: "0.3rem" }}>
        Gestrichelte Linie = Ø Elo über alle abgebildeten Schwinger. Grün = überdurchschnittlich,
        Grau = unterdurchschnittlich. Nur Schwünge mit ausreichend vielen Schwingern (sonst zu
        verrauscht), Achse startet bewusst nicht bei 0 — die Unterschiede liegen in einer engen
        Elo-Bandbreite, ein Nullpunkt würde sie unsichtbar machen.
      </p>
    </div>
  );
}
