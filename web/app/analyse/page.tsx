"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeFeatureImportance, ladeBenchmark, ladeSchwinger, ladeRatings } from "@/lib/data";
import type { FeatureImportanceEntry, BenchmarkArtifact, Schwinger, RatingsArtifact } from "@/lib/types";
import { Konfusionsmatrix, VergleichBalken, VierWegeBenchmark } from "@/components/ModellGuete";
import { StreudiagrammMitTrend } from "@/components/StreudiagrammMitTrend";
import { SchwungVergleich, type SchwungStat } from "@/components/SchwungVergleich";

// Rohdaten schreiben denselben Schwung uneinheitlich gross/klein
// ("innerer Haken" vs. "Innerer Haken") -- sonst zwei Zeilen fürs Gleiche.
// Gleiche Normalisierung wie pipeline/clustering.py:_normiert.
function normiertesSchwung(name: string): string {
  const t = name.trim();
  return t ? t[0].toLowerCase() + t.slice(1) : t;
}
const MIN_SCHWINGER_PRO_SCHWUNG = 15;

interface Report {
  lauf_id?: string;
  holdout_jahr: number;
  n_train: number;
  n_test: number;
  modell: { log_loss: number; accuracy: number };
  baseline_elo: { log_loss: number; accuracy: number };
  schlaegt_baseline: boolean;
  verbesserung_log_loss: number;
  accuracy_gg_baseline?: number;
  erfolgskriterien?: {
    log_loss_besser_als_baseline: boolean;
    accuracy_mindestens_baseline: boolean;
    gesamt_erfuellt: boolean;
  };
  datenbasis: { n_gaenge: number; n_schwinger: number };
  n_parsing_warnungen: number;
  klassen?: string[];
  konfusionsmatrix?: number[][] | null;
}

// Merkmale, die die Spec explizit beleuchten will (AK-4.2).
const FOKUS = new Set([
  "gewicht_diff",
  "groesse_diff",
  "schwung_overlap",
  "schwung_count_diff",
]);

export default function Analyse() {
  const [fi, setFi] = useState<FeatureImportanceEntry[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ladeFeatureImportance().then(setFi).catch((e) => setError(String(e)));
    fetch("/data/report.json", { cache: "no-store" })
      .then((r) => r.json())
      .then(setReport)
      .catch(() => {});
    ladeBenchmark().then(setBenchmark).catch(() => {});
    ladeSchwinger().then(setSchwinger).catch(() => {});
    ladeRatings().then(setRatings).catch(() => {});
  }, []);

  // Nur Schwinger mit tatsächlich erfassten Gängen (nicht der Elo-Startwert
  // ohne jede Messung) und erfasstem Körperwert -- sonst würde die Nulllinie
  // Rauschen ins Streudiagramm bringen statt eine echte Elo-Messung.
  const streuGroesse = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge > 0 && e.s.groesse_cm)
      .map((e) => ({ x: e.s.groesse_cm as number, y: e.r!.elo, label: e.s.name }));
  }, [schwinger, ratings]);

  const streuGewicht = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge > 0 && e.s.gewicht_kg)
      .map((e) => ({ x: e.s.gewicht_kg as number, y: e.r!.elo, label: e.s.name }));
  }, [schwinger, ratings]);

  const streuAlter = useMemo(() => {
    if (!ratings) return [];
    const jahr = new Date().getFullYear();
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge > 0 && e.s.jahrgang)
      .map((e) => ({ x: jahr - (e.s.jahrgang as number), y: e.r!.elo, label: e.s.name }));
  }, [schwinger, ratings]);

  // Kategorial statt kontinuierlich: Ø Elo je bevorzugtem Schwung (nur wo
  // genug Schwinger dafür vorliegen, sonst zu verrauscht).
  const { schwungStats, gesamtschnittElo } = useMemo(() => {
    if (!ratings) return { schwungStats: [] as SchwungStat[], gesamtschnittElo: 0 };
    // Referenzlinie NUR über Schwinger mit erfasstem Schwung berechnen, nicht
    // über alle n_gaenge>0 -- sonst zieht die riesige Masse an Stub-Schwingern
    // (kein Porträt, kaum gespielt, Elo noch nah am Startwert 1500) den
    // Gesamtschnitt künstlich runter und der Vergleich wird unfair (dieselbe
    // Auswahlverzerrung wie bei der Kranzquote auf der Karte).
    const mitSchwung = schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge > 0 && (e.s.bevorzugte_schwuenge?.length ?? 0) > 0);
    if (mitSchwung.length === 0) return { schwungStats: [], gesamtschnittElo: 0 };

    const summeGesamt = mitSchwung.reduce((acc, e) => acc + e.r!.elo, 0);
    const gesamtschnitt = summeGesamt / mitSchwung.length;

    const gruppen = new Map<string, { summe: number; n: number }>();
    for (const { s, r } of mitSchwung) {
      for (const roh of s.bevorzugte_schwuenge ?? []) {
        const name = normiertesSchwung(roh);
        const g = gruppen.get(name) ?? { summe: 0, n: 0 };
        g.summe += r!.elo;
        g.n += 1;
        gruppen.set(name, g);
      }
    }
    const stats = [...gruppen.entries()]
      .filter(([, g]) => g.n >= MIN_SCHWINGER_PRO_SCHWUNG)
      .map(([schwung, g]) => ({ schwung, n: g.n, eloAvg: g.summe / g.n }))
      .sort((a, b) => b.eloAvg - a.eloAvg);
    return { schwungStats: stats, gesamtschnittElo: gesamtschnitt };
  }, [schwinger, ratings]);

  if (error) return <p className="warn">Fehler: {error}</p>;
  const max = Math.max(...fi.map((f) => f.wichtigkeit), 1e-6);

  return (
    <div>
      <h1>Analyse &amp; Modellgüte</h1>
      <p className="subtitle">
        Welche Merkmale treiben die Prognose — und schlägt das Modell die Elo-Baseline?
      </p>

      {report && (
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Modellgüte (Holdout {report.holdout_jahr})</h2>
          <table>
            <thead>
              <tr>
                <th>Metrik</th>
                <th>Modell (Logistic Regression)</th>
                <th>Baseline (Elo)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Log-Loss (tiefer = besser)</td>
                <td>
                  <strong>{report.modell.log_loss.toFixed(4)}</strong>
                </td>
                <td>{report.baseline_elo.log_loss.toFixed(4)}</td>
              </tr>
              <tr>
                <td>Accuracy</td>
                <td>
                  <strong>{(report.modell.accuracy * 100).toFixed(1)}%</strong>
                </td>
                <td>{(report.baseline_elo.accuracy * 100).toFixed(1)}%</td>
              </tr>
            </tbody>
          </table>
          <VergleichBalken
            metriken={[
              {
                key: "log_loss",
                label: "Log-Loss (tiefer = besser)",
                modell: report.modell.log_loss,
                baseline: report.baseline_elo.log_loss,
                format: (v) => v.toFixed(4),
              },
              {
                key: "accuracy",
                label: "Accuracy (höher = besser)",
                modell: report.modell.accuracy,
                baseline: report.baseline_elo.accuracy,
                format: (v) => `${(v * 100).toFixed(1)}%`,
              },
            ]}
          />
          <p style={{ marginTop: "0.9rem" }}>
            {report.schlaegt_baseline ? (
              <span className="badge" style={{ color: "#7fd6a8", borderColor: "#3d8b6e" }}>
                ✓ schlägt Baseline um {report.verbesserung_log_loss.toFixed(4)} Log-Loss
              </span>
            ) : (
              <span className="badge" style={{ color: "#f0c675" }}>
                ✗ schlägt Baseline (noch) nicht
              </span>
            )}
          </p>
          <p className="muted small">
            Datenbasis: {report.datenbasis.n_gaenge} Gänge, {report.datenbasis.n_schwinger}{" "}
            Schwinger · Train {report.n_train} / Test {report.n_test} · Parsing-Warnungen:{" "}
            {report.n_parsing_warnungen}
          </p>
          {report.erfolgskriterien && (
            <p className="muted small">
              Kriterium Log-Loss:{" "}
              {report.erfolgskriterien.log_loss_besser_als_baseline ? "erfüllt" : "offen"} ·
              Kriterium Accuracy:{" "}
              {report.erfolgskriterien.accuracy_mindestens_baseline ? "erfüllt" : "offen"}
              {typeof report.accuracy_gg_baseline === "number" &&
                ` (Δ ${(report.accuracy_gg_baseline * 100).toFixed(1)}%-Pkt)`}
            </p>
          )}
        </div>
      )}

      {benchmark && (
        <>
          <h2>4-Wege-Benchmark (Holdout {benchmark.holdout_jahr})</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Vier unabhängige Ansätze, ausgewertet auf denselben {benchmark.n_test} echten
              Gängen der jüngsten Saison (keine gespiegelten Trainings-Duplikate): eine reine
              Kranz-Heuristik ohne Statistik, das klassische Elo-Rating, ein ML-Modell{" "}
              <em>ohne</em> Elo/Historie (nur Physis, Stil, Verband) und das komplette
              Produktionsmodell. Beantwortet die Frage, ob Elo wirklich einen Mehrwert bringt —
              und ob unser Modell besser ist als reines Elo-Ranking.
            </p>
            <VierWegeBenchmark kandidaten={benchmark.kandidaten} />
          </div>
        </>
      )}

      {report?.konfusionsmatrix && report.klassen && (
        <>
          <h2>Konfusionsmatrix (Holdout {report.holdout_jahr})</h2>
          <div className="panel">
            <Konfusionsmatrix klassen={report.klassen} matrix={report.konfusionsmatrix} />
          </div>
        </>
      )}

      <h2>Merkmalswichtigkeit</h2>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th style={{ width: "35%" }}>Merkmal</th>
              <th style={{ width: "45%" }}>Wichtigkeit</th>
              <th>Wert</th>
            </tr>
          </thead>
          <tbody>
            {fi.map((f) => (
              <tr key={f.feature}>
                <td>
                  {f.label}
                  {FOKUS.has(f.feature) && (
                    <span className="badge" style={{ marginLeft: 6 }}>
                      Fokus
                    </span>
                  )}
                </td>
                <td>
                  <div
                    className="fi-bar"
                    style={{ width: `${(f.wichtigkeit / max) * 100}%` }}
                  />
                </td>
                <td className="muted small">{f.wichtigkeit.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        Wichtigkeit = mittlerer Betrag der standardisierten Koeffizienten über die drei
        Klassen. „Fokus" markiert Merkmale, deren Beitrag die Spezifikation explizit prüfen
        will (Gewicht, Grösse, bevorzugte Schwünge — vgl. AK-4.2). Bei synthetischen
        Demodaten sind diese Werte illustrativ; mit echten Gang-Daten wird ihr
        tatsächlicher Beitrag sichtbar.
      </p>

      {(streuGroesse.length > 0 || streuGewicht.length > 0 || streuAlter.length > 0) && (
        <>
          <h2>Macht Grösse, Gewicht oder Alter einen Unterschied?</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Jeder Punkt ein Schwinger mit mindestens einem erfassten Gang (Elo also eine
              echte Messung, kein Startwert). Die gestrichelte Linie ist die lineare
              Trendlinie; r zeigt, wie stark der Zusammenhang tatsächlich ist (0 = keiner,
              ±1 = perfekt).
            </p>
            <div className="grid-3">
              <StreudiagrammMitTrend
                titel="Grösse vs. Elo"
                achseXLabel="Grösse (cm)"
                punkte={streuGroesse}
                formatX={(v) => `${v.toFixed(0)} cm`}
              />
              <StreudiagrammMitTrend
                titel="Gewicht vs. Elo"
                achseXLabel="Gewicht (kg)"
                punkte={streuGewicht}
                formatX={(v) => `${v.toFixed(0)} kg`}
              />
              <StreudiagrammMitTrend
                titel="Alter vs. Elo"
                achseXLabel="Alter (Jahre)"
                punkte={streuAlter}
                formatX={(v) => `${v.toFixed(0)}`}
              />
            </div>
          </div>
        </>
      )}

      {schwungStats.length > 0 && (
        <>
          <h2>Macht der bevorzugte Schwung einen Unterschied?</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "0.5rem" }}>
              Ø Elo der Schwinger, die diesen Schwung bevorzugen (nur Schwünge mit mindestens{" "}
              {MIN_SCHWINGER_PRO_SCHWUNG} Schwingern, sonst zu verrauscht — ein Schwinger kann
              mehrere bevorzugte Schwünge haben und zählt dann bei mehreren mit).
            </p>
            <SchwungVergleich daten={schwungStats} gesamtschnitt={gesamtschnittElo} />
          </div>
        </>
      )}
    </div>
  );
}
