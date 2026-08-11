"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeCluster, ladeSchwinger } from "@/lib/data";
import type { ClusterArtifact, Schwinger } from "@/lib/types";
import { TypenStreudiagramm, CLUSTER_FARBEN } from "@/components/TypenStreudiagramm";

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

  const sortiert = [...cluster.cluster_zusammenfassung].sort((a, b) => b.n - a.n);

  return (
    <div>
      <span className="eyebrow">Cluster-Analyse</span>
      <h1>Schwingertypen</h1>
      <p className="subtitle">
        {cluster.punkte.length} aktive Schwinger, per K-Means über das volle Profil gruppiert:
        Körperbau, Stil, Elo-Rating, Erfahrung, Alter und Kranzstatus — das Verfahren findet die
        Struktur selbst, ohne dass wir Merkmale vorher wegkuratieren.
      </p>

      <hr className="rule" />

      <div className="panel">
        <TypenStreudiagramm
          punkte={cluster.punkte}
          schwingerById={schwingerById}
          hoverCluster={hoverCluster}
        />
        <p className="muted small" style={{ marginTop: "0.6rem", textAlign: "center" }}>
          Jeder Punkt ist ein Schwinger (Nähe = ähnliches Profil), Farbe = Typ. Auf einen Punkt
          klicken öffnet ihn in der Prognose.
        </p>
      </div>

      <div className="typen-karten">
        {sortiert.map((c) => (
          <div
            key={c.cluster}
            className="typen-karte"
            onMouseEnter={() => setHoverCluster(c.cluster)}
            onMouseLeave={() => setHoverCluster((h) => (h === c.cluster ? null : h))}
            style={{ borderLeftColor: CLUSTER_FARBEN[c.cluster % CLUSTER_FARBEN.length] }}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
              <strong>
                <i
                  className="vb-swatch"
                  style={{ background: CLUSTER_FARBEN[c.cluster % CLUSTER_FARBEN.length] }}
                />
                {c.n} Schwinger
              </strong>
              {c.teilverband_schwerpunkt && (
                <span className="badge" title="Deutlich überrepräsentiert in diesem Cluster">
                  📍 {c.teilverband_schwerpunkt}
                </span>
              )}
            </div>
            <p className="typen-auszeichnung">{c.auszeichnung}</p>
            <p className="muted small" style={{ margin: "0.2rem 0" }}>
              Ø {c.gewicht_avg.toFixed(0)} kg · {c.groesse_avg.toFixed(0)} cm · Kompaktheit{" "}
              {c.kompaktheit_avg.toFixed(1)} · Elo {c.elo_avg.toFixed(0)} · {c.alter_avg.toFixed(0)}{" "}
              Jahre · {c.erfahrung_avg.toFixed(0)} Gänge Ø
              {c.top_schwuenge.length > 0 && <> · bevorzugt: {c.top_schwuenge.join(", ")}</>}
            </p>
            {c.typische_vertreter.length > 0 && (
              <div className="row" style={{ marginTop: "0.4rem", gap: "0.4rem", flexWrap: "wrap" }}>
                <span className="muted small">Typische Vertreter:</span>
                {c.typische_vertreter.map((sid) => {
                  const s = schwingerById[sid];
                  if (!s) return null;
                  return (
                    <Link
                      key={sid}
                      href={`/?a=${encodeURIComponent(sid)}`}
                      className="badge"
                      style={{ color: "var(--text)" }}
                    >
                      {s.name}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        k={cluster.k} Cluster automatisch per Silhouette-Score gewählt (aus 3–8 getestet,
        Silhouette={cluster.silhouette.toFixed(2)} — Mass für Clustergüte, 0 = keine Struktur,
        1 = perfekt getrennt). Merkmale: Gewicht, Grösse, Kompaktheits-Index (Gewicht/Grösse²),
        Elo-Rating, Erfahrung (Anzahl Gänge), Alter, Kranzstatus und bevorzugte Schwünge
        (One-Hot der häufigsten, Schwelle statt fixer Liste). „Schwerpunkt" markiert einen
        Teilverband, der in diesem Cluster gegenüber der Gesamtverteilung deutlich
        überrepräsentiert ist — rein beschreibend, fliesst nicht ins Clustering ein. Nur Schwinger
        mit eigenem Porträt haben diese Werte erfasst. Für namentlichen Vergleich:{" "}
        <Link href="/schwinger">Schwinger-Übersicht</Link>.
      </p>
    </div>
  );
}
