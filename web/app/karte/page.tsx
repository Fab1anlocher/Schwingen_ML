"use client";

// Seite "Karte": Kennzahlen je Kanton bzw. Berner Gauverband (kantone.json,
// gauverbaende.json aus pipeline/export.py exportiere_kantone).

import { useEffect, useState } from "react";
import { ladeKantone, ladeGauverbaende } from "@/lib/data";
import type { KantoneArtifact, GauverbaendeArtifact } from "@/lib/types";
import { SchweizKarte } from "@/components/SchweizKarte";

export default function Karte() {
  const [daten, setDaten] = useState<KantoneArtifact | null>(null);
  const [gauverbaende, setGauverbaende] = useState<GauverbaendeArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ladeKantone()
      .then(setDaten)
      .catch((e) => setError(String(e)));
    ladeGauverbaende()
      .then(setGauverbaende)
      .catch(() => {});
  }, []);

  if (error) return <p className="warn">Fehler beim Laden: {error}</p>;
  if (!daten) return <p className="loading">Karte wird geladen …</p>;

  return (
    <div>
      <h1>Schweiz-Karte</h1>
      <p className="subtitle">
        Regionale Verteilung von Rating, Erfolgen und Kadertiefe — pro Kanton bzw. Berner
        Gauverband, aus allen erfassten Festen seit 2023.
      </p>

      <div className="panel">
        <SchweizKarte kantone={daten.kantone} gauverbaende={gauverbaende?.gauverbaende} />
      </div>

      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        „Top-Schwinger" = oberste 10 % der gezählten Schwinger nach Elo-Rating (Schwelle{" "}
        {Math.round(daten.top_schwelle_elo)}). Gezählt wird, wer mindestens{" "}
        {daten.min_gaenge ?? 5} Gänge hat — vorher liegt das Elo noch fast beim Startwert.
      </p>
    </div>
  );
}
