"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeCluster, ladeSchwinger } from "@/lib/data";
import type { ClusterArtifact, Schwinger } from "@/lib/types";
import { TypenStreudiagramm } from "@/components/TypenStreudiagramm";

const CLUSTER_FARBEN = [
  "#d1502f", "#45a17f", "#e3ab45", "#5599e6",
  "#a45de3", "#e35d9c", "#5ec8d8", "#c2c94a",
];

export default function Typen() {
  const [cluster, setCluster] = useState<ClusterArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hoverCluster, setHoverCluster] = useState<number | null>(null);

  useEffect(() => {
    ladeCluster()
      .then(setCluster)
      .catch((e) => setError(String(e)));
    ladeSchwinger().then(setSchwinger).catch(() => {});
  }, []);

  const schwingerById = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );

  if (error) return <p className="warn">Fehler beim Laden: {error}</p>;
  if (!cluster) return <p className="loading">Schwingertypen werden geladen …</p>;

  return (
    <div>
      <h1>🧬 Schwingertypen</h1>
      <p className="subtitle">
        {cluster.punkte.length} Schwinger mit erfasster Grösse und Gewicht, per K-Means über
        Körperbau und bevorzugte Schwünge gruppiert — bewusst ohne Elo oder Erfolg, „Typ" meint
        hier reinen Körperbau/Stil, nicht Stärke.
      </p>

      <div className="panel">
        <TypenStreudiagramm
          punkte={cluster.punkte}
          schwingerById={schwingerById}
          hoverCluster={hoverCluster}
        />

        <div className="typen-legende">
          {cluster.cluster_zusammenfassung.map((c) => (
            <div
              key={c.cluster}
              className="typen-legende-zeile"
              onMouseEnter={() => setHoverCluster(c.cluster)}
              onMouseLeave={() => setHoverCluster((h) => (h === c.cluster ? null : h))}
            >
              <i
                className="vb-swatch"
                style={{ background: CLUSTER_FARBEN[c.cluster % CLUSTER_FARBEN.length] }}
              />
              <span>
                <strong>{c.n} Schwinger</strong> · Ø {c.gewicht_avg.toFixed(0)} kg,{" "}
                {c.groesse_avg.toFixed(0)} cm
                {c.top_schwuenge.length > 0 && (
                  <span className="muted"> · bevorzugt: {c.top_schwuenge.join(", ")}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        k={cluster.k} Cluster automatisch per Silhouette-Score gewählt (aus 3–8 getestet,
        Silhouette={cluster.silhouette.toFixed(2)} — Mass für Clustergüte, 0 = keine Struktur,
        1 = perfekt getrennt). Merkmale: Gewicht, Grösse, bevorzugte Schwünge (One-Hot der
        häufigsten). Nur Schwinger mit eigenem Porträt haben diese Werte erfasst. Für
        namentlichen Vergleich: <Link href="/schwinger">Schwinger-Übersicht</Link>.
      </p>
    </div>
  );
}
