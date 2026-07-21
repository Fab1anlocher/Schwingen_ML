"use client";

import { useEffect, useState } from "react";
import { ladeFeatureImportance } from "@/lib/data";
import type { FeatureImportanceEntry } from "@/lib/types";
import { Konfusionsmatrix, VergleichBalken } from "@/components/ModellGuete";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ladeFeatureImportance().then(setFi).catch((e) => setError(String(e)));
    fetch("/data/report.json", { cache: "no-store" })
      .then((r) => r.json())
      .then(setReport)
      .catch(() => {});
  }, []);

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
    </div>
  );
}
