"use client";

// Seite "Analyse": Modellgüte gegen die Elo-Baseline und im Verlauf, Benchmark,
// Konfusionsmatrix, Gestellt-Kalibrierung (report.json, benchmark.json),
// Merkmalswichtigkeit (feature_importance.json) sowie Physis/Schwünge gegen
// Elo (schwinger.json + ratings.json). Alle Zahlen stammen aus dem letzten
// Pipeline-Lauf; hier wird nichts neu geschätzt.

import { useEffect, useMemo, useState } from "react";
import { ladeFeatureImportance, ladeBenchmark, ladeSchwinger, ladeRatings, ladeVerlauf } from "@/lib/data";
import { VerlaufDiagramm, modellStand, type VerlaufLauf } from "@/components/VerlaufDiagramm";
import type { FeatureImportanceEntry, BenchmarkArtifact, Schwinger, RatingsArtifact } from "@/lib/types";
import {
  GestelltKalibrierung,
  Konfusionsmatrix,
  VergleichBalken,
  VierWegeBenchmark,
  type GestelltKalibrierungDaten,
} from "@/components/ModellGuete";
import { StreudiagrammMitTrend } from "@/components/StreudiagrammMitTrend";
import { SchwungVergleich, type SchwungStat } from "@/components/SchwungVergleich";
import { datumKurz, schwungName, zahl } from "@/lib/labels";

const MIN_SCHWINGER_PRO_SCHWUNG = 15;
// Ab so vielen Gängen gilt ein Elo als Messung (wie model.json
// config.min_gaenge_fuer_sicherheit): nach ein, zwei Gängen liegt es noch
// fast beim Startwert und zöge jede Trendlinie Richtung 1500.
const MIN_GAENGE_FUER_ELO = 5;

interface Report {
  lauf_id?: string;
  holdout_jahr: number;
  n_train: number;
  /** Trainingszeilen des ausgelieferten Modells (inkl. Holdout-Saison, s.
   *  pipeline/train.py); fehlt bei Reports vor dem 26.09.2026. */
  n_train_ausgeliefert?: number;
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
  /** "gbm" (zweistufiges Gradient Boosting) oder "lr"; ältere Reports ohne Angabe = LR. */
  modell_typ?: string;
  /** Bäume je Stufe (nur Boosting). */
  n_baeume?: { gestellt: number; sieg: number } | null;
  klassen?: string[];
  konfusionsmatrix?: number[][] | null;
  /** Ab Merkmalsversion 2 (P3); ältere Reports haben den Block nicht. */
  gestellt_kalibrierung?: GestelltKalibrierungDaten | null;
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
  const [fiArt, setFiArt] = useState<"koeffizient" | "permutation">("koeffizient");
  const [verlauf, setVerlauf] = useState<VerlaufLauf[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ladeFeatureImportance()
      .then(({ art, features }) => {
        setFi(features);
        setFiArt(art);
      })
      .catch((e) => setError(String(e)));
    ladeVerlauf().then(setVerlauf);
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
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.groesse_cm)
      .map((e) => ({ x: e.s.groesse_cm as number, y: e.r!.elo, label: e.s.name }));
  }, [schwinger, ratings]);

  const streuGewicht = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.gewicht_kg)
      .map((e) => ({ x: e.s.gewicht_kg as number, y: e.r!.elo, label: e.s.name }));
  }, [schwinger, ratings]);

  const streuAlter = useMemo(() => {
    if (!ratings) return [];
    const jahr = new Date().getFullYear();
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.jahrgang)
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
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && (e.s.bevorzugte_schwuenge?.length ?? 0) > 0);
    if (mitSchwung.length === 0) return { schwungStats: [], gesamtschnittElo: 0 };

    const summeGesamt = mitSchwung.reduce((acc, e) => acc + e.r!.elo, 0);
    const gesamtschnitt = summeGesamt / mitSchwung.length;

    const gruppen = new Map<string, { summe: number; n: number }>();
    for (const { s, r } of mitSchwung) {
      for (const roh of s.bevorzugte_schwuenge ?? []) {
        const name = schwungName(roh);
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
  const modellName = report?.modell_typ === "gbm" ? "Gradient Boosting" : "Logistic Regression";

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
                <th>Modell ({modellName})</th>
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
            modellName={modellName}
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
              <span className="badge" style={{ color: "var(--accent-2)", borderColor: "rgba(18,135,106,0.4)" }}>
                ✓ schlägt Baseline um {report.verbesserung_log_loss.toFixed(4)} Log-Loss
              </span>
            ) : (
              <span className="badge" style={{ color: "#b26a00" }}>
                ✗ schlägt Baseline (noch) nicht
              </span>
            )}
          </p>
          <p className="muted small">
            Datenbasis: {zahl(report.datenbasis.n_gaenge)} Gänge, {zahl(report.datenbasis.n_schwinger)}{" "}
            Schwinger · Training {zahl(report.n_train / 2)} Gänge (je aus beiden Sichten, A/B
            gespiegelt) · Test {zahl(report.n_test)} Gänge der Saison {report.holdout_jahr}, die
            das Modell nie gesehen hat
            {(report.n_train_ausgeliefert ?? 0) > report.n_train && (
              <>
                {" "}
                · Die Prognosen der App rechnet danach ein Modell mit denselben Einstellungen, das
                zusätzlich auf dieser Saison trainiert ist ({zahl(report.n_train_ausgeliefert! / 2)}{" "}
                Gänge) — die Kennzahlen hier stammen bewusst vom Modell ohne sie.
              </>
            )}
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
          <h2>Benchmark (Holdout {benchmark.holdout_jahr})</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Unabhängige Ansätze, ausgewertet auf denselben {zahl(benchmark.n_test)} echten
              Gängen der jüngsten Saison (keine gespiegelten Trainings-Duplikate): eine reine
              Kranz-Heuristik ohne Statistik, das klassische Elo-Rating, ein ML-Modell{" "}
              <em>ohne</em> Elo/Historie (nur Physis, Stil, Verband), die lineare Logistic
              Regression mit allen Merkmalen (das Modell bis 25.09.2026) und das
              Produktionsmodell. Beantwortet, ob Elo einen Mehrwert bringt, ob das Modell
              besser ist als reines Elo-Ranking — und was der Wechsel auf Gradient Boosting
              gebracht hat.
            </p>
            <VierWegeBenchmark kandidaten={benchmark.kandidaten} />
          </div>
        </>
      )}

      {verlauf.length >= 2 && (
        <>
          <h2>Modellgüte im Verlauf</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Ein Punkt je Tag mit Pipeline-Lauf, gemessen auf der jeweils jüngsten Saison, die
              das Modell nicht gesehen hat. Gestrichelt: Wechsel des Modells oder der Merkmale
              (wechselt es an einem Tag, stehen dort beide Punkte übereinander).
              Steigt der Log-Loss ohne solchen Wechsel deutlich, schlägt der tägliche Lauf Alarm
              (Datenqualitätsbericht).
            </p>
            <div className="grid-2">
              <VerlaufDiagramm
                laeufe={verlauf}
                titel="Log-Loss (tiefer = besser)"
                wert={(l) => l.log_loss}
                format={(v) => v.toFixed(3)}
              />
              <VerlaufDiagramm
                laeufe={verlauf}
                titel="Accuracy (höher = besser)"
                wert={(l) => l.accuracy}
                format={(v) => `${(v * 100).toFixed(1)}%`}
              />
            </div>
            <details style={{ marginTop: "0.6rem" }}>
              <summary className="muted small">Als Tabelle</summary>
              <div className="tabelle-wrap">
                <table style={{ minWidth: 420 }}>
                  <thead>
                    <tr>
                      <th>Datum</th>
                      <th>Modell</th>
                      <th>Log-Loss</th>
                      <th>Accuracy</th>
                      <th>Gänge</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...verlauf].reverse().map((l, i) => (
                      <tr key={`${l.datum}-${i}`}>
                        <td>{datumKurz(l.datum)}</td>
                        <td className="muted small">{modellStand(l)}</td>
                        <td>{l.log_loss.toFixed(4)}</td>
                        <td>{(l.accuracy * 100).toFixed(1)}%</td>
                        <td className="muted">{l.n_gaenge ? zahl(l.n_gaenge) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
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

      {report?.gestellt_kalibrierung?.stufen?.length ? (
        <>
          <h2>Stimmt die Gestellt-Chance? (Holdout {report.holdout_jahr})</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              „Gestellt“ ist nur selten der wahrscheinlichste Ausgang — Accuracy und
              Konfusionsmatrix sehen darum kaum, ob die angezeigte Gestellt-Chance stimmt. Hier
              sind die {report.gestellt_kalibrierung.n} Testgänge nach vorhergesagter
              Gestellt-Chance in zehn gleich grosse Stufen geteilt. Liegen die Punkte auf der
              Diagonalen, endet ein Gang so oft gestellt, wie das Modell sagt.
            </p>
            <GestelltKalibrierung daten={report.gestellt_kalibrierung} />
          </div>
        </>
      ) : null}

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
        {fiArt === "permutation"
          ? "Wichtigkeit = um so viel steigt der Log-Loss auf den Testgängen, wenn dieses Merkmal zufällig vertauscht wird (Permutation) — also wie viel schlechter das Modell ohne das Merkmal wäre."
          : "Wichtigkeit = mittlerer Betrag der standardisierten Koeffizienten über die drei Klassen."}{" "}
        „Fokus" markiert Merkmale, deren Beitrag die Spezifikation explizit prüfen
        will (Gewicht, Grösse, bevorzugte Schwünge — vgl. AK-4.2). Klein heisst hier nicht
        bedeutungslos: Physis und Stil sind nur für Schwinger mit Porträt erfasst, und ein Teil
        ihrer Wirkung steckt schon im Elo-Rating.
      </p>

      {(streuGroesse.length > 0 || streuGewicht.length > 0 || streuAlter.length > 0) && (
        <>
          <h2>Macht Grösse, Gewicht oder Alter einen Unterschied?</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "1rem" }}>
              Jeder Punkt ein Schwinger mit mindestens {MIN_GAENGE_FUER_ELO} erfassten Gängen (Elo
              also eine echte Messung, nicht mehr der Startwert). Die gestrichelte Linie ist die
              lineare Trendlinie; r zeigt, wie stark der Zusammenhang tatsächlich ist (0 = keiner,
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
              Ø Elo der Schwinger mit mindestens {MIN_GAENGE_FUER_ELO} Gängen, die diesen Schwung
              bevorzugen (nur Schwünge mit mindestens{" "}
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
