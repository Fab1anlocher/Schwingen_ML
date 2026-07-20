"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { ladeRatings, ladeSchwinger } from "@/lib/data";
import type { RatingsArtifact, Schwinger } from "@/lib/types";

const KRANZ_LABEL: Record<string, string> = {
  kein: "—",
  kranzer: "Kranzer",
  eidgenosse: "Eidgenosse",
  koenig: "Schwingerkönig",
};

export default function SchwingerListe() {
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [q, setQ] = useState("");
  const [offen, setOffen] = useState<string | null>(null);

  useEffect(() => {
    ladeSchwinger().then(setSchwinger);
    ladeRatings().then(setRatings);
  }, []);

  const gefiltert = useMemo(() => {
    const nadel = q.trim().toLowerCase();
    const mit = schwinger.map((s) => ({
      ...s,
      elo: ratings?.ratings[s.id]?.elo ?? null,
      n: ratings?.ratings[s.id]?.n_gaenge ?? 0,
    }));
    const arr = nadel
      ? mit.filter((s) => s.name.toLowerCase().includes(nadel))
      : mit;
    return arr.sort((a, b) => (b.elo ?? 0) - (a.elo ?? 0));
  }, [schwinger, ratings, q]);

  return (
    <div>
      <h1>Schwinger</h1>
      <p className="subtitle">
        {schwinger.length} erfasste Schwinger, nach Elo-Rating sortiert. Nach Namen suchen.
      </p>

      <input
        placeholder="Name suchen …"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: "1.25rem", maxWidth: 360 }}
        aria-label="Schwinger suchen"
      />

      <div className="panel" style={{ padding: 0, overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Jg.</th>
              <th>Kranz</th>
              <th>Elo</th>
              <th>Gänge</th>
              <th>Form</th>
            </tr>
          </thead>
          <tbody>
            {gefiltert.map((s) => (
              <Fragment key={s.id}>
                <tr
                  onClick={() => setOffen(offen === s.id ? null : s.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{s.name}</td>
                  <td className="muted">{s.jahrgang ?? "—"}</td>
                  <td>{KRANZ_LABEL[s.kranzstatus] ?? s.kranzstatus}</td>
                  <td>
                    <strong>{s.elo !== null ? Math.round(s.elo) : "—"}</strong>
                  </td>
                  <td className="muted">{s.n}</td>
                  <td className="muted">{(s.form * 100).toFixed(0)}%</td>
                </tr>
                {offen === s.id && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--panel-2)" }}>
                      <div className="small" style={{ padding: "0.35rem 0" }}>
                        <div>
                          <strong>Verband:</strong> {s.teilverband ?? "?"} ·{" "}
                          <strong>Kanton:</strong> {s.kanton ?? "?"} ·{" "}
                          <strong>Klub:</strong> {s.schwingklub ?? "?"}
                        </div>
                        <div>
                          <strong>Grösse:</strong>{" "}
                          {s.groesse_cm ? `${s.groesse_cm} cm` : "?"} ·{" "}
                          <strong>Gewicht:</strong>{" "}
                          {s.gewicht_kg ? `${s.gewicht_kg} kg` : "?"}
                        </div>
                        <div>
                          <strong>Bevorzugte Schwünge:</strong>{" "}
                          {s.bevorzugte_schwuenge.length
                            ? s.bevorzugte_schwuenge.join(", ")
                            : "—"}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {gefiltert.length === 0 && (
        <p className="muted" style={{ marginTop: "1rem" }}>
          Keine Treffer für „{q}".
        </p>
      )}
    </div>
  );
}
