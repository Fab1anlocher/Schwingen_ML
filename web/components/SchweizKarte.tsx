"use client";

import { useMemo, useState } from "react";
import { KANTON_PFADE, KANTON_VIEWBOX } from "@/lib/schweiz-kantone";
import type { KantonStatistik } from "@/lib/types";
import { GauverbandVergleich } from "@/components/GauverbandVergleich";

type MetrikKey = "elo_avg" | "siegquote" | "top_schwinger_quote" | "n_schwinger";

const METRIKEN: { key: MetrikKey; label: string; format: (v: number) => string }[] = [
  { key: "elo_avg", label: "Ø Elo-Rating", format: (v) => v.toFixed(0) },
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

// Politische Kantone, für die die Rohdaten mehrere eigene Kantonal-/
// Gauverbände unterscheiden (s. pipeline/kantone.py) -- nur für diese lohnt
// sich ein Klick-Aufklapp mit Detailvergleich. Andere zusammengeführte Fälle
// (Appenzell -> AI+AR, Ob-/Nidwalden) haben in den Rohdaten nur EINEN
// gemeinsamen Verbandsnamen, es gibt dort schlicht nichts aufzuschlüsseln.
const GAUVERBAND_AUFSCHLUESSELUNG: Record<string, string[]> = {
  Bern: ["Berner-Jura", "Emmental", "Mittelland", "Oberaargau", "Oberland", "Seeland"],
};

// Absolute Zaehl-Metriken (Siege, Top-Schwinger) skalieren trivial mit der
// Anzahl erfasster Schwinger pro Kanton -- ein Kanton mit mehr Schwingern
// "gewinnt" dann fast automatisch, unabhaengig davon wie erfolgreich die
// einzelnen Schwinger tatsaechlich sind. Deshalb hier als Quote (durch
// Bevoelkerung normiert), damit Kantone unterschiedlicher Groesse fair
// vergleichbar sind.
function wertVon(k: KantonStatistik, metrik: MetrikKey): number | null {
  if (metrik === "siegquote") {
    const n = k.n_siege + k.n_gestellt + k.n_niederlagen;
    return n > 0 ? k.n_siege / n : null;
  }
  if (metrik === "top_schwinger_quote") {
    return k.n_schwinger > 0 ? k.n_top_schwinger / k.n_schwinger : null;
  }
  const v = k[metrik];
  return v === null || v === undefined ? null : v;
}

export function SchweizKarte({
  kantone,
  gauverbaende,
}: {
  kantone: KantonStatistik[];
  gauverbaende?: KantonStatistik[];
}) {
  const [metrikKey, setMetrikKey] = useState<MetrikKey>("elo_avg");
  const metrik = METRIKEN.find((m) => m.key === metrikKey)!;
  const [hover, setHover] = useState<string | null>(null);
  const [ausgewaehlt, setAusgewaehlt] = useState<string | null>(null);

  const byName = useMemo(
    () => Object.fromEntries(kantone.map((k) => [k.kanton, k])),
    [kantone]
  );

  const { min, max } = useMemo(() => {
    const werte = kantone
      .map((k) => wertVon(k, metrikKey))
      .filter((v): v is number => v !== null);
    // Bei Zähl-Metriken ist 0 ein echter, aussagekräftiger Boden ("keine
    // Siege"). Beim Elo-Schnitt würde ein 0-Boden die tatsächliche Spanne
    // (hier z.B. 1477-1776) auf ein paar Farbnuancen stauchen — dort zählt
    // die tatsächliche Min/Max-Spanne der Kantone.
    const nullBoden = metrikKey !== "elo_avg";
    return {
      min: nullBoden ? Math.min(...werte, 0) : Math.min(...werte),
      max: Math.max(...werte, nullBoden ? 1 : 0),
    };
  }, [kantone, metrikKey]);

  const farbeFuer = (name: string) => {
    const k = byName[name];
    const wert = k ? wertVon(k, metrikKey) : null;
    if (wert === null) return "#232b35"; // keine Daten
    const anteil = max > min ? (wert - min) / (max - min) : 0.5;
    return `rgba(69, 161, 127, ${0.12 + anteil * 0.8})`;
  };

  const angezeigt = (hover ? byName[hover] : null) ?? (ausgewaehlt ? byName[ausgewaehlt] : null);
  const gauverbandNamen = ausgewaehlt ? GAUVERBAND_AUFSCHLUESSELUNG[ausgewaehlt] : null;

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
          ? `${angezeigt.kanton}: ${
              wertVon(angezeigt, metrikKey) !== null
                ? metrik.format(wertVon(angezeigt, metrikKey)!)
                : "keine Daten"
            } · ${angezeigt.n_schwinger} erfasste Schwinger`
          : "Kanton anklicken für Details, oder mit der Maus über die Karte fahren"}
        {angezeigt && GAUVERBAND_AUFSCHLUESSELUNG[angezeigt.kanton] && (
          <span>
            {" "}
            · gliedert sich in {GAUVERBAND_AUFSCHLUESSELUNG[angezeigt.kanton].length} Gauverbände
            {ausgewaehlt === angezeigt.kanton ? " (unten)" : " — anklicken für Details"}
          </span>
        )}
      </div>

      <svg viewBox={KANTON_VIEWBOX} className="karte-svg" role="img" aria-label="Schweizer Kantone">
        {Object.entries(KANTON_PFADE).map(([name, d]) => (
          <path
            key={name}
            d={d}
            fill={farbeFuer(name)}
            stroke={ausgewaehlt === name ? "var(--accent)" : hover === name ? "var(--text)" : "var(--border)"}
            strokeWidth={ausgewaehlt === name ? 2.2 : hover === name ? 1.6 : 0.8}
            onMouseEnter={() => setHover(name)}
            onMouseLeave={() => setHover((h) => (h === name ? null : h))}
            onClick={() => setAusgewaehlt((a) => (a === name ? null : name))}
            style={{ cursor: "pointer", transition: "fill 0.15s ease" }}
          >
            <title>
              {name}
              {byName[name] && wertVon(byName[name], metrikKey) !== null
                ? `: ${metrik.format(wertVon(byName[name], metrikKey)!)}`
                : ": keine Daten"}
            </title>
          </path>
        ))}
      </svg>

      <div className="karte-legende">
        <span className="muted small">{metrik.format(min)}</span>
        <div className="karte-legende-balken" />
        <span className="muted small">{metrik.format(max)}</span>
      </div>
      <p className="muted small" style={{ marginTop: "0.5rem" }}>
        Kantonszuordnung basiert auf dem Kantonal-/Gauverband der Schwinger; grosse Verbände
        (z.B. Bern: Oberland, Emmental, Mittelland, Oberaargau, Seeland, Berner-Jura) werden zum
        politischen Kanton zusammengeführt. Graue Kantone: keine erfassten Schwinger. Der
        Kantonal-/Gauverband ist nur für Schwinger mit eigenem Porträt bekannt — alle Zahlen
        hier beziehen sich nur auf diesen Teil der Datenbasis, tendenziell die erfolgreicheren
        Schwinger.
      </p>

      {gauverbandNamen && gauverbaende && (
        <div className="karte-gauverband-panel">
          <GauverbandVergleich
            titel={`${ausgewaehlt} nach Gauverband`}
            gauverbaende={gauverbaende}
            namen={gauverbandNamen}
          />
        </div>
      )}
    </div>
  );
}
