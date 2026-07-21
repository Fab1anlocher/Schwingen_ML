"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeRatings, ladeSchwinger } from "@/lib/data";
import type { RatingsArtifact, Schwinger } from "@/lib/types";
import { findeAehnliche, hatProfildaten } from "@/lib/aehnlichkeit";

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
                      <SchwingerDetail schwinger={s} alle={schwinger} />
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

function SchwingerDetail({ schwinger: s, alle }: { schwinger: Schwinger; alle: Schwinger[] }) {
  const aehnliche = useMemo(() => findeAehnliche(s, alle, 5), [s, alle]);
  const index = s.ueberraschungsindex;

  return (
    <div className="small" style={{ padding: "0.6rem 0" }}>
      <div>
        <strong>Teilverband:</strong> {s.teilverband ?? "?"} ·{" "}
        <strong>Kantonal-/Gauverband:</strong> {s.kanton ?? "?"} · <strong>Klub:</strong>{" "}
        {s.schwingklub ?? "?"}
      </div>
      <div>
        <strong>Grösse:</strong> {s.groesse_cm ? `${s.groesse_cm} cm` : "?"} ·{" "}
        <strong>Gewicht:</strong> {s.gewicht_kg ? `${s.gewicht_kg} kg` : "?"}
      </div>
      <div>
        <strong>Bevorzugte Schwünge:</strong>{" "}
        {s.bevorzugte_schwuenge.length ? s.bevorzugte_schwuenge.join(", ") : "—"}
      </div>

      {index !== null && s.n_bewertete_gaenge > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          <strong>Überraschungs-Index:</strong>{" "}
          <span style={{ color: index >= 0 ? "#7fd6a8" : "#f0c675" }}>
            {index >= 0 ? "+" : ""}
            {(index * 100).toFixed(1)}%
          </span>{" "}
          <span className="muted">
            ({s.n_bewertete_gaenge} Gänge · {index >= 0 ? "übertrifft" : "verfehlt"} die
            Elo-Erwartung im Schnitt)
          </span>
          {s.groesster_erfolg && (
            <div className="muted">
              Grösster Erfolg: schlug <strong>{s.groesster_erfolg.gegner_name}</strong> (
              {Math.round(s.groesster_erfolg.gegner_elo - s.groesster_erfolg.eigenes_elo)} Elo-Punkte
              Unterschied) am {s.groesster_erfolg.datum}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: "0.6rem" }}>
        <strong>Ähnliche Schwinger:</strong>{" "}
        {!hatProfildaten(s) ? (
          <span className="muted">kein Porträt erfasst — kein sinnvoller Vergleich möglich.</span>
        ) : aehnliche.length === 0 ? (
          <span className="muted">keine vergleichbaren Profile gefunden.</span>
        ) : (
          <div className="row" style={{ marginTop: "0.3rem", gap: "0.4rem" }}>
            {aehnliche.map((t) => (
              <Link
                key={t.schwinger.id}
                href={`/?a=${encodeURIComponent(t.schwinger.id)}&b=${encodeURIComponent(s.id)}`}
                className="badge"
                title={t.gruende.join(", ") || "ähnliches Profil"}
                style={{ color: "var(--text)" }}
              >
                {t.schwinger.name} · {(t.score * 100).toFixed(0)}%
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
