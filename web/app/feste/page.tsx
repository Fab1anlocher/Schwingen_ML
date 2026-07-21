"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import type {
  EventsArtifact,
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
  KommendesFest,
} from "@/lib/types";

const TYP_LABEL: Record<string, string> = {
  eidgenoessisch: "Eidgenössisches",
  berg: "Bergfest",
  kantonal: "Kantonales",
  teilverband: "Teilverband",
  regional: "Regional",
};

export default function Feste() {
  const [events, setEvents] = useState<EventsArtifact | null>(null);
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);

  useEffect(() => {
    Promise.all([ladeEvents(), ladeModel(), ladeRatings(), ladeSchwinger()]).then(
      ([e, m, r, s]) => {
        setEvents(e);
        setModel(m);
        setRatings(r);
        setSchwinger(s);
      }
    );
  }, []);

  const byId = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );

  if (!events) return <p className="loading">Feste werden geladen …</p>;
  const kommende = events.kommende ?? [];

  return (
    <div>
      <h1>Bevorstehende Feste</h1>
      <p className="subtitle">
        Pro veröffentlichter Paarung Prognose und informative Quote. Quoten sind{" "}
        <strong>kein Wettangebot</strong>.
      </p>

      {kommende.length === 0 ? (
        <div className="panel">
          <p>
            Aktuell sind keine bevorstehenden Feste erfasst. Sobald der Agenda-Scraper
            (schlussgang.ch/agenda) aktiv ist, erscheinen hier kommende Feste samt
            veröffentlichter Spitzenpaarungen.
          </p>
          <p className="muted small">
            Bis dahin lässt sich jedes Paar direkt über die{" "}
            <a href="/" style={{ color: "var(--accent-2)" }}>
              Paar-Prognose
            </a>{" "}
            durchspielen.
          </p>
        </div>
      ) : (
        <div className="card-list">
          {kommende.map((fest) => (
            <FestCard
              key={fest.id}
              fest={fest}
              model={model}
              ratings={ratings}
              byId={byId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FestCard({
  fest,
  model,
  ratings,
  byId,
}: {
  fest: KommendesFest;
  model: ModelArtifact | null;
  ratings: RatingsArtifact | null;
  byId: Record<string, Schwinger>;
}) {
  const hatPaarungen = fest.paarungen && fest.paarungen.length > 0;
  const favoriten =
    !hatPaarungen && model && ratings ? baueFavoriten(fest, model, ratings, byId) : [];
  return (
    <div className="fest-card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h3>{fest.name}</h3>
          <span className="muted small">
            {fest.datum}
            {fest.ort ? ` · ${fest.ort}` : ""}
          </span>
        </div>
        <span className="badge">{TYP_LABEL[fest.typ] ?? fest.typ}</span>
      </div>

      {!hatPaarungen && (
        <>
          <p className="muted small" style={{ marginTop: "0.75rem" }}>
            <span className="badge" style={{ marginRight: 6 }}>
              Paarungen noch offen
            </span>
            Favoriten-/Kranz-Prognose (rating-basiert, informativ).
          </p>
          {favoriten.length > 0 && (
            <table style={{ marginTop: "0.5rem" }}>
              <thead>
                <tr>
                  <th>Favorit</th>
                  <th>Rating</th>
                  <th>Kranz</th>
                  <th>Index</th>
                </tr>
              </thead>
              <tbody>
                {favoriten.map((f) => (
                  <tr key={f.id}>
                    <td>{f.name}</td>
                    <td>{Math.round(f.elo)}</td>
                    <td>{f.kranz}</td>
                    <td>{f.index.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {hatPaarungen && model && ratings && (
        <table style={{ marginTop: "0.85rem" }}>
          <thead>
            <tr>
              <th>Paarung</th>
              <th>Sieg A</th>
              <th>Gestellt</th>
              <th>Sieg B</th>
            </tr>
          </thead>
          <tbody>
            {fest.paarungen!.map((pg, i) => {
              const a = byId[pg.a_id];
              const b = byId[pg.b_id];
              if (!a || !b) return null;
              const ra = ratings.ratings[pg.a_id] ?? { elo: ratings.elo_start, n_gaenge: 0 };
              const rb = ratings.ratings[pg.b_id] ?? { elo: ratings.elo_start, n_gaenge: 0 };
              const pr = prognostiziere(model, a, b, ra.elo, rb.elo, ra.n_gaenge, rb.n_gaenge);
              const cell = (v: number) => (
                <>
                  {(v * 100).toFixed(0)}%
                  <span className="muted small"> · {(1 / Math.max(v, 1e-6)).toFixed(2)}</span>
                </>
              );
              return (
                <tr key={i}>
                  <td>
                    {a.name} <span className="muted">vs</span> {b.name}
                  </td>
                  <td>{cell(pr.p.sieg_a)}</td>
                  <td>{cell(pr.p.gestellt)}</td>
                  <td>{cell(pr.p.sieg_b)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function baueFavoriten(
  fest: KommendesFest,
  model: ModelArtifact,
  ratings: RatingsArtifact,
  byId: Record<string, Schwinger>
) {
  const ord = model.config.kranzstatus_ordinal;
  const bonus = fest.typ === "berg" ? 12 : fest.typ === "eidgenoessisch" ? 18 : 0;
  return Object.entries(ratings.ratings)
    .map(([id, r]) => {
      const s = byId[id];
      if (!s) return null;
      const kranz = ord[s.kranzstatus] ?? 0;
      const index = r.elo + kranz * 25 + bonus;
      return { id, name: s.name, elo: r.elo, kranz: s.kranzstatus, index };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null)
    .sort((a, b) => b.index - a.index)
    .slice(0, 6);
}
