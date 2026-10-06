"use client";

// Choroplethen-Karte der Schweiz (SVG-Pfade aus lib/schweiz-kantone.ts, Bern
// nach Gauverbänden aus lib/bern-gauverbaende.ts), Klassen per Quantilen.

import { useMemo, useState } from "react";
import { KANTON_PFADE, KANTON_VIEWBOX } from "@/lib/schweiz-kantone";
import { BERN_GAUVERBAND_PFADE } from "@/lib/bern-gauverbaende";
import { KLASSEN_FARBEN, quantilGrenzen, klasseFuer } from "@/lib/choropleth";
import type { KantonStatistik } from "@/lib/types";
import { kantonName } from "@/lib/labels";

type MetrikKey = "elo_avg" | "eidgenossen" | "siegquote" | "top_schwinger_quote" | "n_schwinger";

const METRIKEN: { key: MetrikKey; label: string; format: (v: number) => string }[] = [
  { key: "elo_avg", label: "Ø Elo-Rating", format: (v) => v.toFixed(0) },
  // Eidgenossen (inkl. Könige): fast alle haben ein Porträt oder Sterne in der
  // Rangliste, die Auswahlverzerrung unten trifft sie darum kaum.
  { key: "eidgenossen", label: "Eidgenossen (inkl. Schwingerkönige)", format: (v) => v.toFixed(0) },
  { key: "siegquote", label: "Siegquote (echte Gänge)", format: (v) => `${(v * 100).toFixed(0)}%` },
  { key: "top_schwinger_quote", label: "Anteil Top-Schwinger (oberste 10% Elo)", format: (v) => `${(v * 100).toFixed(0)}%` },
  { key: "n_schwinger", label: "Anzahl erfasste Schwinger", format: (v) => v.toFixed(0) },
  // Bewusst KEINE "Kranz-Quote": schlussgang.ch legt ein Porträt (und damit
  // einen Kantonal-/Gauverband) fast ausschliesslich für Schwinger an, die
  // bereits einen Kranz haben. Schwinger ohne Porträt (~75% der Datenbasis)
  // haben keinen erfassten Verband und fallen aus JEDER Kanton-Statistik
  // heraus -- die Quote läge dadurch überall bei ~100%, unabhängig von der
  // tatsächlichen regionalen Kranz-Quote. Kein Anzeige-Bug, sondern eine
  // Auswahlverzerrung der Datenquelle, die sich ohne zusätzliche
  // Verbandsdaten für die "kein"-Schwinger nicht sauber beheben lässt.
];

// Bern hat als einziger Kanton eigene Gauverband-Geometrie (s.
// lib/bern-gauverbaende.ts, aus den 10 echten BFS-Verwaltungskreisen
// gebaut) -- wird deshalb NICHT als ein Kanton-Pfad gezeichnet, sondern
// direkt als seine 6 Gauverbände, jeder einzeln eingefärbt/hoverbar wie
// jeder andere Kanton auch. Für alle anderen zusammengeführten Fälle
// (Appenzell -> AI+AR, Ob-/Nidwalden) gibt es das nicht: die Rohdaten
// unterscheiden dort gar nicht, welcher Schwinger zu welcher Hälfte gehört,
// eine eigene Geometrie würde also nichts Echtes zeigen.
const BERN_ERSETZT = "Bern";

/** Fläche des umschliessenden Rechtecks eines SVG-Pfads (nur für die Reihenfolge). */
function rechteckFlaeche(d: string): number {
  const z = d.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
  const xs = z.filter((_, i) => i % 2 === 0);
  const ys = z.filter((_, i) => i % 2 === 1);
  return (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
}

// Grosse Flächen zuerst, kleine obenauf: St. Gallen ist eine Fläche ohne Loch
// und umschliesst beide Appenzell. In alphabetischer Reihenfolge deckte es
// sie zu -- Appenzell war nie sichtbar und nicht anwählbar.
const KANTONE_GEORDNET = Object.entries(KANTON_PFADE)
  .filter(([name]) => name !== BERN_ERSETZT) // s. BERN_GAUVERBAND_PFADE
  .sort((a, b) => rechteckFlaeche(b[1]) - rechteckFlaeche(a[1]));

function wertVon(k: KantonStatistik, metrik: MetrikKey): number | null {
  if (metrik === "siegquote") {
    const n = k.n_siege + k.n_gestellt + k.n_niederlagen;
    return n > 0 ? k.n_siege / n : null;
  }
  if (metrik === "eidgenossen") return k.n_eidgenosse + k.n_koenig;
  if (metrik === "top_schwinger_quote") {
    return k.n_schwinger > 0 ? k.n_top_schwinger / k.n_schwinger : null;
  }
  const v = k[metrik];
  return v === null || v === undefined ? null : v;
}

export function SchweizKarte({
  kantone,
  gauverbaende,
  ausgewaehlt = null,
  onWaehle,
  meister = {},
}: {
  kantone: KantonStatistik[];
  gauverbaende?: KantonStatistik[];
  /** Ausgewählte Fläche (Kanton bzw. Berner Gauverband), hervorgehoben. */
  ausgewaehlt?: string | null;
  onWaehle?: (flaeche: string) => void;
  /** Fläche -> Name des Kantonsmeisters (Hover-Text). */
  meister?: Record<string, string>;
}) {
  const [metrikKey, setMetrikKey] = useState<MetrikKey>("elo_avg");
  const metrik = METRIKEN.find((m) => m.key === metrikKey)!;
  const [hover, setHover] = useState<string | null>(null);

  const byName = useMemo(
    () => Object.fromEntries(kantone.map((k) => [k.kanton, k])),
    [kantone]
  );
  const gauverbandByName = useMemo(
    () => Object.fromEntries((gauverbaende ?? []).map((g) => [g.kanton, g])),
    [gauverbaende]
  );

  // Farbskala über alle TATSÄCHLICH gezeichneten Flächen: politische Kantone
  // ausser Bern (das stattdessen durch seine 6 Gauverbände ersetzt wird) +
  // diese 6 Gauverbände selbst -- sonst würde Berns politischer Mittelwert
  // in die Skala einfliessen, obwohl er auf der Karte gar nicht mehr auftaucht.
  const gezeichneteFlaechen = useMemo(() => {
    const politisch = kantone.filter((k) => k.kanton !== BERN_ERSETZT);
    const bernVerbaende = Object.keys(BERN_GAUVERBAND_PFADE)
      .map((name) => gauverbandByName[name])
      .filter((g): g is KantonStatistik => g !== undefined);
    return [...politisch, ...bernVerbaende];
  }, [kantone, gauverbandByName]);

  // Quantil-Klassen statt stufenloser Farbe: jede Klasse enthält ungefähr
  // gleich viele Kantone/Gauverbände, robust auch bei schiefen Verteilungen
  // (z.B. viele Kantone mit 0 Top-Schwingern) -- s. lib/choropleth.ts.
  const grenzen = useMemo(() => {
    const werte = gezeichneteFlaechen
      .map((k) => wertVon(k, metrikKey))
      .filter((v): v is number => v !== null);
    return quantilGrenzen(werte, KLASSEN_FARBEN.length);
  }, [gezeichneteFlaechen, metrikKey]);

  const farbeFuer = (stat: KantonStatistik | undefined) => {
    const wert = stat ? wertVon(stat, metrikKey) : null;
    if (wert === null || grenzen.length < 2) return "#e0ddd2"; // keine Daten
    return KLASSEN_FARBEN[klasseFuer(wert, grenzen)];
  };

  const angezeigt = hover ? byName[hover] ?? gauverbandByName[hover] : null;

  // Eine Fläche: Farbe, Hervorhebung (Hover/Auswahl), Klick/Tipp/Tastatur.
  const flaeche = (name: string, d: string, stat: KantonStatistik | undefined) => {
    const aktiv = hover === name || ausgewaehlt === name;
    const wert = stat ? wertVon(stat, metrikKey) : null;
    return (
      <path
        key={name}
        d={d}
        fill={farbeFuer(stat)}
        stroke={aktiv ? "var(--text)" : "var(--border)"}
        strokeWidth={ausgewaehlt === name ? 2.4 : aktiv ? 1.6 : 0.8}
        onMouseEnter={() => setHover(name)}
        onMouseLeave={() => setHover((h) => (h === name ? null : h))}
        onClick={() => onWaehle?.(name)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onWaehle?.(name);
          }
        }}
        role={onWaehle ? "button" : undefined}
        tabIndex={onWaehle ? 0 : undefined}
        aria-label={kantonName(name)}
        className="karte-flaeche"
        style={{ cursor: "pointer", transition: "fill 0.15s ease" }}
      >
        <title>
          {kantonName(name)}
          {wert !== null ? `: ${metrik.format(wert)}` : ": keine Daten"}
          {meister[name] ? ` · Kantonsmeister ${meister[name]}` : ""}
        </title>
      </path>
    );
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.75rem" }}>
        <label className="field" htmlFor="karte-metrik" style={{ marginBottom: 0 }}>
          Kennzahl
        </label>
        <select
          id="karte-metrik"
          style={{ width: "auto", minWidth: 280 }}
          value={metrikKey}
          onChange={(e) => setMetrikKey(e.target.value as MetrikKey)}
        >
          {METRIKEN.map((m) => (
            <option key={m.key} value={m.key}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <div className="karte-status muted small">
        {angezeigt
          ? `${kantonName(angezeigt.kanton)}: ${
              wertVon(angezeigt, metrikKey) !== null
                ? metrik.format(wertVon(angezeigt, metrikKey)!)
                : "keine Daten"
            } · ${angezeigt.n_schwinger} erfasste Schwinger${
              meister[angezeigt.kanton] ? ` · 👑 ${meister[angezeigt.kanton]}` : ""
            }`
          : "Tippe auf einen Kanton: wer ist dort der Beste?"}
      </div>

      <svg
        viewBox={KANTON_VIEWBOX}
        className="karte-svg"
        role={onWaehle ? "group" : "img"}
        aria-label="Schweizer Kantone"
      >
        {KANTONE_GEORDNET.map(([name, d]) => flaeche(name, d, byName[name]))}
        {Object.entries(BERN_GAUVERBAND_PFADE).map(([name, d]) =>
          flaeche(name, d, gauverbandByName[name])
        )}
      </svg>

      <div className="karte-legende">
        {grenzen.slice(0, -1).map((untergrenze, i) => (
          <div className="karte-legende-klasse" key={i}>
            <i className="karte-legende-swatch" style={{ background: KLASSEN_FARBEN[i] }} />
            <span className="muted small">
              {metrik.format(untergrenze)}
              {i < grenzen.length - 2 ? `–${metrik.format(grenzen[i + 1])}` : "+"}
            </span>
          </div>
        ))}
        <div className="karte-legende-klasse">
          <i className="karte-legende-swatch" style={{ background: "#e0ddd2" }} />
          <span className="muted small">keine Daten</span>
        </div>
      </div>
      <details className="muted small" style={{ marginTop: "0.5rem" }}>
        <summary>Wie die Karte zählt</summary>
        Kantonszuordnung basiert auf dem Kantonal-/Gauverband der Schwinger. Bern wird als
        einziger Kanton in seine 6 Gauverbände einzeln aufgeteilt (Oberland, Emmental,
        Mittelland, Oberaargau, Seeland, Berner-Jura) — anhand der echten Grenzen der 10
        offiziellen BFS-Verwaltungskreise, zu den Gauverbänden nach Namen gruppiert; eine
        plausible, aber nicht vom Schwingerverband selbst bestätigte Annäherung. Für andere
        zusammengeführte Verbände (z.B. Appenzell, Ob-/Nidwalden) gibt es das nicht — die
        Rohdaten unterscheiden dort gar nicht, welcher Schwinger zu welcher Hälfte gehört.
        Graue Flächen: keine erfassten Schwinger. Der Kantonal-/Gauverband stammt aus dem
        Porträt, sonst aus dem Schwingklub laut offizieller Schlussrangliste (jeder Klub gehört
        genau einem Verband an). Früher zählten nur Schwinger mit Porträt — rund ein Viertel
        des Kaders, fast nur die Erfolgreicheren.
      </details>
    </div>
  );
}
