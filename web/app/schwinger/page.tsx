"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeCluster, ladeRatings, ladeSchwinger } from "@/lib/data";
import type { ClusterArtifact, RatingsArtifact, Schwinger } from "@/lib/types";
import { gruende, hatProfildaten } from "@/lib/aehnlichkeit";

const KRANZ_LABEL: Record<string, string> = {
  kein: "—",
  kranzer: "Kranzer",
  eidgenosse: "Eidgenosse",
  koenig: "Schwingerkönig",
};

// Echte Werte aus schwinger.json (nicht "Berner"/"innerschweizer" o.ä. --
// das Feld war bisher fälschlich gegen erfundene Strings gefiltert, das
// Dropdown dadurch faktisch immer leer/wirkungslos).
const TEILVERBAND_OPTIONEN = [
  "Bern",
  "Innerschweiz",
  "Nordostschweiz",
  "Nordwestschweiz",
  "Suedwestschweiz",
];

// Ohne aktive Suche/Filter würde die volle Liste (auch tausende Schwinger
// ohne erfasste Gänge) die Seite unübersichtlich machen — daher Deckel,
// solange nicht gezielt gesucht wird (dann sollen auch Ränge >100 auffindbar
// sein, s. Suche-Verbesserung weiter unten in der Historie).
const MAX_OHNE_SUCHE = 150;

export default function SchwingerListe() {
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [cluster, setCluster] = useState<ClusterArtifact | null>(null);
  const [q, setQ] = useState("");
  const [teilverband, setTeilverband] = useState("");
  const [minGaenge, setMinGaenge] = useState(0);
  const [zeigeInaktive, setZeigeInaktive] = useState(false);
  const [offen, setOffen] = useState<string | null>(null);

  useEffect(() => {
    ladeSchwinger().then(setSchwinger);
    ladeRatings().then(setRatings);
    ladeCluster().then(setCluster).catch(() => {});
  }, []);

  const verfuegbareTeilverbaende = useMemo(() => {
    const gefunden = new Set(schwinger.map((s) => s.teilverband).filter(Boolean) as string[]);
    return TEILVERBAND_OPTIONEN.filter((t) => gefunden.has(t));
  }, [schwinger]);

  const gefiltert = useMemo(() => {
    const nadel = q.trim().toLowerCase();
    const mit = schwinger.map((s) => ({
      ...s,
      elo: ratings?.ratings[s.id]?.elo ?? ratings?.elo_start ?? 1500,
      n: ratings?.ratings[s.id]?.n_gaenge ?? 0,
    }));
    const arr = mit
      .filter((s) => {
        if (!nadel) return true;
        // Nicht nur der Name -- auch Teilverband/Kanton/Klub sollen über die
        // freie Suche auffindbar sein, nicht nur über das Teilverband-Dropdown.
        const heuhaufen = `${s.name} ${s.teilverband ?? ""} ${s.kanton ?? ""} ${
          s.schwingklub ?? ""
        }`.toLowerCase();
        return heuhaufen.includes(nadel);
      })
      .filter((s) => !teilverband || s.teilverband === teilverband)
      .filter((s) => s.n >= minGaenge)
      .filter((s) => zeigeInaktive || s.aktiv)
      .sort((a, b) => b.elo - a.elo);
    return nadel ? arr : arr.slice(0, MAX_OHNE_SUCHE);
  }, [schwinger, ratings, q, teilverband, minGaenge, zeigeInaktive]);

  return (
    <div>
      <h1>Schwinger</h1>
      <p className="subtitle">
        {schwinger.length} erfasste Schwinger, nach Elo-Rating (Power-Rating) sortiert — kein
        offizielles ESV-Ranking, sondern die modellinterne Einstufung. Suchen, filtern oder
        auf einen Namen klicken für Profildetails.
      </p>

      <div className="panel" style={{ marginBottom: "1.25rem" }}>
        <input
          placeholder="Name suchen …"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ marginBottom: "0.85rem", maxWidth: 360 }}
          aria-label="Schwinger suchen"
        />
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
        <label className="row" style={{ marginTop: "0.85rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={zeigeInaktive}
            onChange={(e) => setZeigeInaktive(e.target.checked)}
            style={{ width: "auto" }}
          />
          <span className="small muted">
            Auch inaktive anzeigen (kein Gang in der laufenden Saison)
          </span>
        </label>
      </div>

      <div className="panel tabelle-wrap" style={{ padding: 0 }}>
        <table style={{ minWidth: 600 }}>
          <thead>
            <tr>
              <th style={{ width: "3rem" }}>#</th>
              <th>Name</th>
              <th>Jg.</th>
              <th title="Höchste je erreichte Kranzstufe">Kranz</th>
              <th>Elo</th>
              <th title="Anzahl Feste mit Kranz">Kränze</th>
              <th>Form</th>
            </tr>
          </thead>
          <tbody>
            {gefiltert.map((s, i) => {
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
                <Fragment key={s.id}>
                  <tr
                    onClick={() => setOffen(offen === s.id ? null : s.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td className={`rang-platz${platzKlasse}`} style={{ textAlign: "center" }}>
                      {platz === 1 ? "🥇" : platz === 2 ? "🥈" : platz === 3 ? "🥉" : platz}
                    </td>
                    <td>
                      {s.name}
                      {!s.aktiv && (
                        <span className="badge" style={{ marginLeft: 6 }}>
                          inaktiv
                        </span>
                      )}
                    </td>
                    <td className="muted">{s.jahrgang ?? "—"}</td>
                    <td>{KRANZ_LABEL[s.kranzstatus] ?? s.kranzstatus}</td>
                    <td>
                      <strong>{Math.round(s.elo)}</strong>
                    </td>
                    <td>{s.anzahl_kraenze}</td>
                    <td className="muted">{(s.form * 100).toFixed(0)}%</td>
                  </tr>
                  {offen === s.id && (
                    <tr>
                      <td colSpan={7} style={{ background: "var(--panel-2)" }}>
                        <SchwingerDetail schwinger={s} alle={schwinger} cluster={cluster} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {gefiltert.length === 0 && (
        <p className="muted" style={{ marginTop: "1rem" }}>
          Keine Treffer für diesen Filter.
        </p>
      )}
      {!q && gefiltert.length === MAX_OHNE_SUCHE && (
        <p className="muted small" style={{ marginTop: "0.75rem" }}>
          Zeigt die Top {MAX_OHNE_SUCHE} nach Elo. Für weitere Schwinger gezielt nach Namen suchen.
        </p>
      )}
    </div>
  );
}

function SchwingerDetail({
  schwinger: s,
  alle,
  cluster,
}: {
  schwinger: Schwinger;
  alle: Schwinger[];
  cluster: ClusterArtifact | null;
}) {
  const byId = useMemo(() => Object.fromEntries(alle.map((sw) => [sw.id, sw])), [alle]);
  const aehnliche = useMemo(() => {
    const treffer = cluster?.aehnlichste[s.id] ?? [];
    return treffer
      .map((t) => ({ schwinger: byId[t.schwinger_id], score: t.score }))
      .filter((t): t is { schwinger: Schwinger; score: number } => t.schwinger !== undefined);
  }, [cluster, s.id, byId]);
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
        ) : !cluster ? (
          <span className="muted">wird geladen …</span>
        ) : aehnliche.length === 0 ? (
          <span className="muted">keine vergleichbaren Profile gefunden.</span>
        ) : (
          <div className="row" style={{ marginTop: "0.3rem", gap: "0.4rem" }}>
            {aehnliche.map((t) => (
              <Link
                key={t.schwinger.id}
                href={`/?a=${encodeURIComponent(t.schwinger.id)}&b=${encodeURIComponent(s.id)}`}
                className="badge"
                title={gruende(s, t.schwinger).join(", ") || "ähnliches Profil (K-Means/KNN)"}
                style={{ color: "var(--text)" }}
              >
                {t.schwinger.name} · {(t.score * 100).toFixed(0)}%
              </Link>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginTop: "0.6rem" }}>
        <Link href={`/?a=${encodeURIComponent(s.id)}`} className="badge" style={{ color: "var(--text)" }}>
          Als Schwinger A in der Paar-Prognose übernehmen →
        </Link>
      </div>
    </div>
  );
}
