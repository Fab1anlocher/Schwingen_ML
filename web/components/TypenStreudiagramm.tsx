"use client";

import { useMemo, useState } from "react";
import type { ClusterPunkt, Schwinger } from "@/lib/types";

const W = 760;
const H = 480;
const PAD = 16;

// Feste, nicht rotierende Farbzuordnung je Cluster-Index (Farbe = Identität,
// nie neu vergeben wenn sich die Punktzahl ändert) — erste zwei sind die
// bestehenden Marken-Akzentfarben, Rest ergänzt für bis zu 8 Cluster.
export const CLUSTER_FARBEN = [
  "#d1502f", "#1f8a63", "#b5801a", "#356fbf",
  "#8148c9", "#c94f8b", "#1f97a8", "#7c8526",
];

export function TypenStreudiagramm({
  punkte,
  schwingerById,
  hoverCluster,
}: {
  punkte: ClusterPunkt[];
  schwingerById: Record<string, Schwinger>;
  hoverCluster: number | null;
}) {
  const [hoverId, setHoverId] = useState<string | null>(null);

  const { xScale, yScale } = useMemo(() => {
    const xs = punkte.map((p) => p.pca_x);
    const ys = punkte.map((p) => p.pca_y);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const px = (v: number) => PAD + ((v - xMin) / (xMax - xMin || 1)) * (W - 2 * PAD);
    const py = (v: number) => H - PAD - ((v - yMin) / (yMax - yMin || 1)) * (H - 2 * PAD);
    return { xScale: px, yScale: py };
  }, [punkte]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="typen-svg" role="img" aria-label="Schwingertypen (PCA-Projektion)">
      {punkte.map((p) => {
        const name = schwingerById[p.schwinger_id]?.name ?? p.schwinger_id;
        const gedimmt = hoverCluster !== null && hoverCluster !== p.cluster;
        return (
          <circle
            key={p.schwinger_id}
            cx={xScale(p.pca_x)}
            cy={yScale(p.pca_y)}
            r={hoverId === p.schwinger_id ? 5 : 3}
            fill={CLUSTER_FARBEN[p.cluster % CLUSTER_FARBEN.length]}
            opacity={gedimmt ? 0.12 : hoverId === p.schwinger_id ? 1 : 0.7}
            onMouseEnter={() => setHoverId(p.schwinger_id)}
            onMouseLeave={() => setHoverId((h) => (h === p.schwinger_id ? null : h))}
            style={{ cursor: "pointer", transition: "opacity 0.15s ease, r 0.1s ease" }}
          >
            <title>{name}</title>
          </circle>
        );
      })}
    </svg>
  );
}
