"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeRatings, ladeSchwinger } from "@/lib/data";
import type { RatingsArtifact, Schwinger } from "@/lib/types";

const KRANZ_LABEL: Record<string, string> = {
  kein: "—",
  kranzer: "Kranzer",
  eidgenosse: "Eidgenosse",
  koenig: "Schwingerkönig",
};

const TEILVERBAND_OPTIONEN = [
  "berner",
  "innerschweizer",
  "nordostschweizer",
  "nordwestschweizer",
  "suedwestschweizer",
];

export default function Rangliste() {
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [teilverband, setTeilverband] = useState("");
  const [minGaenge, setMinGaenge] = useState(5);

  useEffect(() => {
    ladeSchwinger().then(setSchwinger);
    ladeRatings().then(setRatings);
  }, []);

  const verfuegbareTeilverbaende = useMemo(() => {
    const gefunden = new Set(schwinger.map((s) => s.teilverband).filter(Boolean) as string[]);
    return TEILVERBAND_OPTIONEN.filter((t) => gefunden.has(t));
  }, [schwinger]);

  const rangliste = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({
        ...s,
        elo: ratings.ratings[s.id]?.elo ?? ratings.elo_start,
        n: ratings.ratings[s.id]?.n_gaenge ?? 0,
      }))
      .filter((s) => s.n >= minGaenge)
      .filter((s) => !teilverband || s.teilverband === teilverband)
      .sort((a, b) => b.elo - a.elo)
      .slice(0, 100);
  }, [schwinger, ratings, teilverband, minGaenge]);

  if (!ratings) return <p className="loading">Rangliste wird geladen …</p>;

  return (
    <div>
      <h1>🏆 Rangliste</h1>
      <p className="subtitle">
        Alle erfassten Schwinger nach Elo-Rating (Power-Rating), chronologisch aus den echten
        Gängen berechnet — kein offizielles ESV-Ranking, sondern die modellinterne Einstufung.
      </p>

      <div className="panel" style={{ marginBottom: "1.25rem" }}>
        <div className="grid-2">
          <div>
            <label className="field" htmlFor="tv">
              Teilverband
            </label>
            <select id="tv" value={teilverband} onChange={(e) => setTeilverband(e.target.value)}>
              <option value="">Alle</option>
              {verfuegbareTeilverbaende.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="ming">
              Mindestens erfasste Gänge
            </label>
            <select
              id="ming"
              value={minGaenge}
              onChange={(e) => setMinGaenge(Number(e.target.value))}
            >
              {[0, 5, 10, 20, 40].map((n) => (
                <option key={n} value={n}>
                  {n === 0 ? "Keine Mindestanzahl" : `≥ ${n} Gänge`}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="panel" style={{ padding: "0.5rem 1rem" }}>
        {rangliste.map((s, i) => {
          const platz = i + 1;
          const platzKlasse =
            platz === 1
              ? " rang-platz-top1"
              : platz === 2
              ? " rang-platz-top2"
              : platz === 3
              ? " rang-platz-top3"
              : "";
          return (
            <Link
              href={`/?a=${encodeURIComponent(s.id)}`}
              key={s.id}
              className="rang-zeile"
              style={{ color: "inherit" }}
              title="Als Schwinger A in der Paar-Prognose übernehmen"
            >
              <div className={`rang-platz${platzKlasse}`}>
                {platz === 1 ? "🥇" : platz === 2 ? "🥈" : platz === 3 ? "🥉" : platz}
              </div>
              <div>
                <div className="rang-name">
                  {s.name}
                  {s.jahrgang ? <span className="muted"> · {s.jahrgang}</span> : ""}
                </div>
                <div className="rang-meta">
                  {[s.schwingklub, s.teilverband].filter(Boolean).join(" · ") || "—"}
                </div>
              </div>
              <span className="badge">{KRANZ_LABEL[s.kranzstatus] ?? s.kranzstatus}</span>
              <span className="muted small">{s.n} Gänge</span>
              <span className="rang-elo">{Math.round(s.elo)}</span>
            </Link>
          );
        })}
        {rangliste.length === 0 && (
          <p className="muted small" style={{ padding: "1rem 0.5rem" }}>
            Keine Schwinger für diesen Filter.
          </p>
        )}
      </div>
      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        Top {rangliste.length} · Klick auf einen Schwinger übernimmt ihn direkt als Schwinger A
        in der Paar-Prognose.
      </p>
    </div>
  );
}
