"use client";

import type { H2HTreffer } from "@/lib/kopfAnKopf";

const ERGEBNIS_TEXT: Record<string, (a: string, b: string) => string> = {
  sieg_a: (a, b) => `${a} gewinnt`,
  sieg_b: (a, b) => `${b} gewinnt`,
  gestellt: () => "Gestellt",
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
        Diese beiden sind sich in den erfassten echten Gängen (2023–2026) noch nie begegnet.
      </p>
    );

  const datumVon = (t: H2HTreffer) => eventInfo[t.event_id]?.datum ?? "";
  const sortiert = [...treffer].sort((x, y) => (datumVon(x) < datumVon(y) ? 1 : -1));

  return (
    <div>
      <p className="muted small" style={{ marginBottom: "0.5rem" }}>
        {treffer.length} bisherige{treffer.length === 1 ? "r" : ""} Gang
        {treffer.length === 1 ? "" : "e"} in den echten Daten — fliesst auch in die Prognose ein:
      </p>
      {sortiert.map((t, i) => (
        <div className="kak-zeile" key={i}>
          <span>{ERGEBNIS_TEXT[t.ergebnis](nameA, nameB)}</span>
          <span className="muted">
            {eventInfo[t.event_id]?.name ?? t.event_id}
            {eventInfo[t.event_id]?.datum ? ` · ${eventInfo[t.event_id].datum}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}
