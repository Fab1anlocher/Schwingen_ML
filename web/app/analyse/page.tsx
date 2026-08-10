"use client";

import { useEffect, useState } from "react";
import { ladeFeatureImportance } from "@/lib/data";
import type { FeatureImportanceEntry } from "@/lib/types";

interface ModellBlock {
  log_loss: number | null;
  accuracy: number | null;
  brier: number | null;
  cv_log_loss: number | null;
  params?: Record<string, number>;
}
interface Report {
  holdout_jahr: number;
  n_train: number;
  n_test: number;
  bestes_modell: "lr" | "gbm";
  logistic_regression: ModellBlock;
  gradient_boosting: ModellBlock;
  baseline_elo: { log_loss: number; accuracy: number };
  schlaegt_baseline: boolean;
  verbesserung_log_loss: number;
  datenbasis: { n_gaenge: number; n_schwinger: number };
  n_parsing_warnungen: number;
}

const FOKUS = new Set(["gewicht_diff", "groesse_diff"]);
const fmt = (v: number | null, d = 3) => (v === null || v === undefined ? "—" : v.toFixed(d));
const pct = (v: number | null) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);

export default function Analyse() {
  const [fi, setFi] = useState<{ lr: FeatureImportanceEntry[]; gbm: FeatureImportanceEntry[] }>({
    lr: [],
    gbm: [],
  });
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ladeFeatureImportance()
      .then((r) => setFi(r))
      .catch((e) => setError(String(e)));
    fetch("/data/report.json", { cache: "no-store" })
      .then((r) => r.json())
      .then(setReport)
      .catch(() => {});
  }, []);

  if (error) return <p className="warn">Fehler: {error}</p>;
  const maxLr = Math.max(...fi.lr.map((f) => f.wichtigkeit), 1e-6);
  const maxGbm = Math.max(...fi.gbm.map((f) => f.wichtigkeit), 1e-6);

  return (
    <div>
      <h1>Analyse &amp; Modellgüte</h1>
      <p className="subtitle">
        Modellvergleich auf zeitlich abgetrenntem Holdout und welche Merkmale die
        Prognose treiben.
      </p>

      {report && (
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Modellvergleich (Holdout {report.holdout_jahr})</h2>
          <table>
            <thead>
              <tr>
                <th>Modell</th>
                <th>Log-Loss ↓</th>
                <th>Accuracy ↑</th>
                <th>Brier ↓</th>
                <th>CV Log-Loss</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Elo-Baseline</td>
                <td>{fmt(report.baseline_elo.log_loss, 4)}</td>
                <td>{pct(report.baseline_elo.accuracy)}</td>
                <td className="muted">—</td>
                <td className="muted">—</td>
              </tr>
              <tr style={{ background: report.bestes_modell === "lr" ? "rgba(61,139,110,0.12)" : undefined }}>
                <td>Logistic Regression{report.bestes_modell === "lr" && " ★"}</td>
                <td>{fmt(report.logistic_regression.log_loss, 4)}</td>
                <td>{pct(report.logistic_regression.accuracy)}</td>
                <td>{fmt(report.logistic_regression.brier)}</td>
                <td>{fmt(report.logistic_regression.cv_log_loss, 4)}</td>
              </tr>
              <tr style={{ background: report.bestes_modell === "gbm" ? "rgba(61,139,110,0.12)" : undefined }}>
                <td>Gradient Boosting{report.bestes_modell === "gbm" && " ★"}</td>
                <td>
                  <strong>{fmt(report.gradient_boosting.log_loss, 4)}</strong>
                </td>
                <td>
                  <strong>{pct(report.gradient_boosting.accuracy)}</strong>
                </td>
                <td>{fmt(report.gradient_boosting.brier)}</td>
                <td>{fmt(report.gradient_boosting.cv_log_loss, 4)}</td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: "0.9rem" }}>
            {report.schlaegt_baseline ? (
              <span className="badge" style={{ color: "#7fd6a8", borderColor: "#3d8b6e" }}>
                ✓ bestes Modell schlägt Baseline um {report.verbesserung_log_loss.toFixed(4)} Log-Loss
              </span>
            ) : (
              <span className="badge" style={{ color: "#f0c675" }}>
                ✗ schlägt Baseline (noch) nicht
              </span>
            )}{" "}
            <span className="badge">
              deployt: {report.bestes_modell === "gbm" ? "Gradient Boosting" : "Logistic Regression"}
            </span>
          </p>
          <p className="muted small">
            ★ = für die Web-App deploytes Modell. „Brier" und „CV Log-Loss" messen
            Kalibrierung bzw. Robustheit (zeitbasierte Cross-Validation). Datenbasis:{" "}
            {report.datenbasis.n_gaenge} Gänge, {report.datenbasis.n_schwinger} Schwinger ·
            Train {report.n_train} / Test {report.n_test}.
          </p>
        </div>
      )}

      <h2>Merkmalswichtigkeit — Logistic Regression</h2>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th style={{ width: "35%" }}>Merkmal</th>
              <th style={{ width: "45%" }}>Wichtigkeit (|Koeffizient|)</th>
              <th>Wert</th>
            </tr>
          </thead>
          <tbody>
            {fi.lr.map((f) => (
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
                  <div className="fi-bar" style={{ width: `${(f.wichtigkeit / maxLr) * 100}%` }} />
                </td>
                <td className="muted small">{f.wichtigkeit.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {fi.gbm.length > 0 && (
        <>
          <h2>Merkmalswichtigkeit — Gradient Boosting</h2>
          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th style={{ width: "35%" }}>Merkmal</th>
                  <th style={{ width: "45%" }}>Importance</th>
                  <th>Wert</th>
                </tr>
              </thead>
              <tbody>
                {fi.gbm.map((f) => (
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
                        style={{
                          width: `${(f.wichtigkeit / maxGbm) * 100}%`,
                          background: "var(--a)",
                        }}
                      />
                    </td>
                    <td className="muted small">{f.wichtigkeit.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        „Fokus" markiert Merkmale, deren Beitrag die Spezifikation explizit prüfen will
        (Gewicht, Grösse — AK-4.2). Bei synthetischen Demodaten sind die Werte illustrativ;
        mit echten Gang-Daten wird der tatsächliche Beitrag sichtbar.
      </p>
    </div>
  );
}
