"use client";

import { useEffect, useState } from "react";

interface Treffer {
  event_id: string;
  ergebnis: "sieg_a" | "gestellt" | "sieg_b";
}

const ERGEBNIS_TEXT: Record<string, (a: string, b: string) => string> = {
  sieg_a: (a, b) => `${a} gewinnt`,
  sieg_b: (a, b) => `${b} gewinnt`,
  gestellt: () => "Gestellt",
};

/** Zeigt echte, bereits gefochtene Gänge zwischen den zwei gewählten Schwingern. */
export function KopfAnKopf({
  aId,
  bId,
  nameA,
  nameB,
  eventInfo,
}: {
  aId: string;
  bId: string;
  nameA: string;
  nameB: string;
  eventInfo: Record<string, { name: string; datum: string }>;
}) {
  const [treffer, setTreffer] = useState<Treffer[] | null>(null);

  useEffect(() => {
    let aktuell = true;
    setTreffer(null);
    fetch(`/api/kopf-an-kopf?a=${encodeURIComponent(aId)}&b=${encodeURIComponent(bId)}`)
      .then((r) => r.json())
      .then((d) => {
        if (aktuell) setTreffer(d.treffer ?? []);
      })
      .catch(() => aktuell && setTreffer([]));
    return () => {
      aktuell = false;
    };
  }, [aId, bId]);

  if (treffer === null) return <p className="muted small">Kopf-an-Kopf wird geladen …</p>;
  if (treffer.length === 0)
    return (
      <p className="muted small">
        Diese beiden sind sich in den erfassten echten Gängen (2023–2026) noch nie begegnet.
      </p>
    );

  // ergebnis ist relativ zur kanonischen (alphabetisch kleineren) Schwinger-ID gespeichert,
  // nicht zwingend zur UI-Reihenfolge A/B — hier auf die aktuelle Auswahl zurückspiegeln.
  const aIstKanonischKleiner = aId < bId;
  const datumVon = (t: Treffer) => eventInfo[t.event_id]?.datum ?? "";
  const sortiert = [...treffer].sort((x, y) => (datumVon(x) < datumVon(y) ? 1 : -1));

  return (
    <div>
      <p className="muted small" style={{ marginBottom: "0.5rem" }}>
        {treffer.length} bisherige{treffer.length === 1 ? "r" : ""} Gang
        {treffer.length === 1 ? "" : "e"} in den echten Daten:
      </p>
      {sortiert.map((t, i) => {
        const ergebnis = aIstKanonischKleiner
          ? t.ergebnis
          : t.ergebnis === "sieg_a"
          ? "sieg_b"
          : t.ergebnis === "sieg_b"
          ? "sieg_a"
          : "gestellt";
        return (
          <div className="kak-zeile" key={i}>
            <span>{ERGEBNIS_TEXT[ergebnis](nameA, nameB)}</span>
            <span className="muted">
              {eventInfo[t.event_id]?.name ?? t.event_id}
              {eventInfo[t.event_id]?.datum ? ` · ${eventInfo[t.event_id].datum}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}
