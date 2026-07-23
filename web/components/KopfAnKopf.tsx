"use client";

import type { H2HTreffer } from "@/lib/kopfAnKopf";

const ERGEBNIS_TEXT: Record<string, (a: string, b: string) => string> = {
  sieg_a: (a) => `Sieg ${a}`,
  sieg_b: (a, b) => `Sieg ${b}`,
  gestellt: () => "Gestellt",
};

const ERGEBNIS_KLASSE: Record<string, string> = {
  sieg_a: "erg-pill-a",
  sieg_b: "erg-pill-b",
  gestellt: "erg-pill-draw",
};

/** Zeigt echte, bereits gefochtene Gänge zwischen den zwei gewählten Schwingern.
 * `treffer` kommt vom Aufrufer (bereits auf die A/B-Reihenfolge gespiegelt via
 * lib/kopfAnKopf.ladeKopfAnKopf) — dieselben Daten fliessen dort auch als
 * Modell-Merkmal ein, daher hier keine eigene Fetch-Logik mehr. */
export function KopfAnKopf({
  treffer,
  nameA,
  nameB,
  eventInfo,
}: {
  treffer: H2HTreffer[] | null;
  nameA: string;
  nameB: string;
  eventInfo: Record<string, { name: string; datum: string }>;
}) {
  if (treffer === null) return <p className="muted small">Kopf-an-Kopf wird geladen …</p>;
  if (treffer.length === 0)
    return (
      <p className="muted small">
        Diese beiden sind sich in den erfassten echten Gängen (seit 2023) noch nie begegnet.
      </p>
    );

  const datumVon = (t: H2HTreffer) => eventInfo[t.event_id]?.datum ?? "";
  const sortiert = [...treffer].sort((x, y) => (datumVon(x) < datumVon(y) ? 1 : -1));

  const siegeA = treffer.filter((t) => t.ergebnis === "sieg_a").length;
  const gestellt = treffer.filter((t) => t.ergebnis === "gestellt").length;
  const siegeB = treffer.filter((t) => t.ergebnis === "sieg_b").length;

  return (
    <div>
      <div className="kak-stats">
        <div className="kak-stat kak-stat-a">
          <div className="kak-stat-zahl">{siegeA}</div>
          <div className="kak-stat-label">Siege {nameA}</div>
        </div>
        <div className="kak-stat">
          <div className="kak-stat-zahl">{gestellt}</div>
          <div className="kak-stat-label">Gestellt</div>
        </div>
        <div className="kak-stat kak-stat-b">
          <div className="kak-stat-zahl">{siegeB}</div>
          <div className="kak-stat-label">Siege {nameB}</div>
        </div>
      </div>

      <div className="tabelle-wrap">
        <table style={{ minWidth: 420 }}>
          <thead>
            <tr>
              <th>Fest</th>
              <th>Datum</th>
              <th style={{ textAlign: "right" }}>Resultat</th>
            </tr>
          </thead>
          <tbody>
            {sortiert.map((t, i) => (
              <tr key={i}>
                <td>{eventInfo[t.event_id]?.name ?? t.event_id}</td>
                <td className="muted">{eventInfo[t.event_id]?.datum ?? "—"}</td>
                <td style={{ textAlign: "right" }}>
                  <span className={`erg-pill ${ERGEBNIS_KLASSE[t.ergebnis]}`}>
                    {ERGEBNIS_TEXT[t.ergebnis](nameA, nameB)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
