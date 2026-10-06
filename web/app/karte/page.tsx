"use client";

// Seite "Karte": Kennzahlen je Kanton bzw. Berner Gauverband (kantone.json,
// gauverbaende.json aus pipeline/export.py exportiere_kantone), dazu für
// Gelegenheitsbesucher: Tipp auf einen Kanton -> Steckbrief mit
// Kantonsmeister, und das Kantönligeist-Duell zweier Mannschaften.

import { useEffect, useMemo, useRef, useState } from "react";
import { ladeGauverbaende, ladeKantone, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import type {
  GauverbaendeArtifact,
  KantoneArtifact,
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
} from "@/lib/types";
import { SchweizKarte } from "@/components/SchweizKarte";
import { KantonsSteckbrief } from "@/components/KantonsSteckbrief";
import { KantonsDuell } from "@/components/KantonsDuell";
import { KANTON_PFADE } from "@/lib/schweiz-kantone";
import { BERN_GAUVERBAND_PFADE } from "@/lib/bern-gauverbaende";
import { kantonalverbandVon, verbaendeAuf } from "@/lib/kantone";
import { staerkste } from "@/lib/kantonsduell";

export default function Karte() {
  const [daten, setDaten] = useState<KantoneArtifact | null>(null);
  const [gauverbaende, setGauverbaende] = useState<GauverbaendeArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[] | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ausgewaehlt, setAusgewaehlt] = useState<string | null>(null);
  const [duellStart, setDuellStart] = useState<{ key: string; nr: number } | null>(null);
  const steckbriefRef = useRef<HTMLDivElement>(null);
  const duellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ladeKantone()
      .then(setDaten)
      .catch((e) => setError(String(e)));
    ladeGauverbaende()
      .then(setGauverbaende)
      .catch(() => {});
    Promise.all([ladeSchwinger(), ladeRatings(), ladeModel()])
      .then(([s, r, m]) => {
        setSchwinger(s);
        setRatings(r);
        setModel(m);
      })
      .catch(() => {});
  }, []);

  // Kantonsmeister je Fläche (für den Hover-Text der Karte).
  const meister = useMemo(() => {
    if (!schwinger || !ratings) return {};
    const flaechen = [
      ...Object.keys(KANTON_PFADE).filter((k) => k !== "Bern"),
      ...Object.keys(BERN_GAUVERBAND_PFADE),
    ];
    const aus: Record<string, string> = {};
    for (const f of flaechen) {
      const verbaende = verbaendeAuf(f);
      const besten = staerkste(
        schwinger.filter((s) => verbaende.includes(kantonalverbandVon(s) ?? "")),
        ratings.ratings,
        1
      );
      if (besten[0]) aus[f] = besten[0].s.name;
    }
    return aus;
  }, [schwinger, ratings]);

  // Laufende Saison: das jüngste Jahr mit einem Festsieg.
  const saison = useMemo(() => {
    let max = "";
    for (const s of schwinger ?? []) for (const f of s.festsiege ?? []) if (f.datum > max) max = f.datum;
    return max.slice(0, 4);
  }, [schwinger]);

  const waehle = (flaeche: string) => {
    setAusgewaehlt((a) => (a === flaeche ? null : flaeche));
    // Am Handy liegt der Steckbrief unter der Karte: sichtbar machen.
    requestAnimationFrame(() => {
      const el = steckbriefRef.current;
      if (el && el.getBoundingClientRect().top > window.innerHeight * 0.75) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  };

  const starteDuell = (verband: string) => {
    setDuellStart({ key: `v:${verband}`, nr: Date.now() });
    requestAnimationFrame(() => duellRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  if (error) return <p className="warn">Fehler beim Laden: {error}</p>;
  if (!daten) return <p className="loading">Karte wird geladen …</p>;

  return (
    <div>
      <h1>Schweiz-Karte</h1>
      <p className="subtitle">
        Wo wird am stärksten geschwungen? Tippe auf deinen Kanton: Wer ist dort der Beste, was
        ist der Lieblingsschwung — und wie ginge ein Duell gegen die Nachbarn aus?
      </p>

      <div className="panel">
        <SchweizKarte
          kantone={daten.kantone}
          gauverbaende={gauverbaende?.gauverbaende}
          ausgewaehlt={ausgewaehlt}
          onWaehle={waehle}
          meister={meister}
        />
      </div>

      <div ref={steckbriefRef} style={{ scrollMarginTop: "4.5rem", marginTop: "1rem" }}>
        {ausgewaehlt && schwinger && ratings && (
          <KantonsSteckbrief
            flaeche={ausgewaehlt}
            schwinger={schwinger}
            ratings={ratings.ratings}
            saison={saison}
            onDuell={starteDuell}
          />
        )}
      </div>

      <div ref={duellRef} style={{ scrollMarginTop: "4.5rem" }}>
        <h2>Kantönligeist-Duell</h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          Sechs gegen sechs: Welcher Kanton hätte im Sägemehl die Nase vorn?
        </p>
        {schwinger && ratings && model ? (
          <KantonsDuell schwinger={schwinger} ratings={ratings.ratings} model={model} start={duellStart} />
        ) : (
          <p className="loading">Mannschaften werden aufgestellt …</p>
        )}
      </div>

      <p className="muted small" style={{ marginTop: "1.25rem" }}>
        „Top-Schwinger" = oberste 10 % der gezählten Schwinger nach Elo-Rating (Schwelle{" "}
        {Math.round(daten.top_schwelle_elo)}). Gezählt wird, wer mindestens{" "}
        {daten.min_gaenge ?? 5} Gänge hat — vorher liegt das Elo noch fast beim Startwert.
        Kantonsmeister und Duell-Mannschaften: aktive Schwinger mit mindestens 10 Gängen.
      </p>
    </div>
  );
}
