"use client";

// Bausteine der Analyse-Seite (neu gestaltet 26.09.2026): Kennzahlen oben,
// Rangliste der Ansätze, Schwierigkeit je Festtyp, Entwicklung des Modells
// als Meilensteine und die tägliche Überwachung. Alle Zahlen kommen aus den
// Artefakten (report.json, benchmark.json, report_verlauf.json, events.json).

import { useMemo } from "react";
import type { BenchmarkKandidat, PrognoseCheck, VergangenesFest } from "@/lib/types";
import { datumKurz, festtypName, modellStandText, prozent, zahl } from "@/lib/labels";
import { VerlaufDiagramm, type VerlaufLauf } from "@/components/VerlaufDiagramm";

// --- Kennzahlen -------------------------------------------------------------

export interface Kennzahl {
  zahl: string;
  label: string;
  sub?: string;
}

/** Die Antwort zuerst: vier grosse Zahlen mit je einem Satz Einordnung. */
export function Kennzahlen({ werte }: { werte: Kennzahl[] }) {
  return (
    <div className="kpi-grid">
      {werte.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="kpi-zahl">{k.zahl}</div>
          <div className="kpi-label">{k.label}</div>
          {k.sub && <div className="kpi-sub">{k.sub}</div>}
        </div>
      ))}
    </div>
  );
}

// --- Rangliste der Ansätze --------------------------------------------------

const ANSATZ_TEXT: Record<string, { name: string; was: string }> = {
  ml_komplett: {
    name: "Unser Modell",
    was: "Gradient Boosting mit allen Merkmalen (Produktion)",
  },
  lr_komplett: {
    name: "Lineares Modell",
    was: "Logistische Regression, gleiche Merkmale — bis 25.9.2026 im Einsatz",
  },
  elo_baseline: {
    name: "Elo-Rating",
    was: "nur die Rating-Differenz der beiden Schwinger",
  },
  ml_ohne_elo: {
    name: "Modell ohne Elo",
    was: "nur Physis, Stil und Verband — ohne Ergebnisse der Vergangenheit",
  },
  kranz_heuristik: {
    name: "Faustregel Kranzstatus",
    was: "wer den höheren Kranzstatus hat, gewinnt",
  },
};

/** Alle Ansätze auf denselben Testgängen, beste zuerst (nach Brier-Score).
 *  Ein Balken (Treffer) für die Intuition, der Brier-Score als Zahl für die
 *  Güte der Wahrscheinlichkeiten -- zwei Masse, keine zweite Achse. */
export function AnsatzRangliste({ kandidaten }: { kandidaten: BenchmarkKandidat[] }) {
  const sortiert = [...kandidaten].sort((a, b) => a.brier_score - b.brier_score);
  return (
    <div className="rang">
      <div className="rang-kopf muted small">
        <span>Ansatz</span>
        <span>Gänge richtig vorhergesagt</span>
        <span title="Mittlerer quadrierter Abstand der Wahrscheinlichkeiten zum Ergebnis; tiefer = besser">
          Brier
        </span>
      </div>
      {sortiert.map((k, i) => {
        const text = ANSATZ_TEXT[k.key] ?? { name: k.label, was: "" };
        const unser = k.key === "ml_komplett";
        return (
          <div className={`rang-zeile${unser ? " rang-unser" : ""}`} key={k.key}>
            <div>
              <div className="rang-name">
                <span className="rang-platz">{i + 1}.</span> {text.name}
              </div>
              {text.was && <div className="muted small">{text.was}</div>}
            </div>
            <div className="rang-balken">
              <div className="rang-track">
                <div className="rang-fill" style={{ width: `${k.accuracy * 100}%` }} />
              </div>
              <span className="rang-wert">{(k.accuracy * 100).toFixed(1)}%</span>
            </div>
            <div className="rang-brier">{k.brier_score.toFixed(3)}</div>
          </div>
        );
      })}
    </div>
  );
}

// --- Schwierigkeit je Festtyp ------------------------------------------------

interface TypZeile {
  typ: string;
  n: number;
  modell: number;
  elo: number | null;
}

/** Trefferquote je Festtyp aus dem Prognose-Check (events.json), nach Gängen
 *  gewichtet: Hantel von der reinen Elo-Prognose zum Modell. */
export function SchwierigkeitJeFesttyp({
  feste,
  saison,
}: {
  feste: VergangenesFest[];
  saison: string;
}) {
  const zeilen = useMemo<TypZeile[]>(() => {
    const summe = new Map<string, { n: number; t: number; e: number; ne: number }>();
    for (const f of feste) {
      const c: PrognoseCheck | undefined = f.prognose_check;
      if (!c || !f.datum.startsWith(saison)) continue;
      const z = summe.get(f.typ) ?? { n: 0, t: 0, e: 0, ne: 0 };
      z.n += c.n;
      z.t += c.treffer * c.n;
      if (c.treffer_elo !== null) {
        z.e += c.treffer_elo * c.n;
        z.ne += c.n;
      }
      summe.set(f.typ, z);
    }
    return [...summe.entries()]
      .map(([typ, z]) => ({
        typ,
        n: z.n,
        modell: z.t / z.n,
        elo: z.ne ? z.e / z.ne : null,
      }))
      .sort((a, b) => b.modell - a.modell);
  }, [feste, saison]);
  if (zeilen.length === 0) return null;

  const werte = zeilen.flatMap((z) => [z.modell, z.elo ?? z.modell]);
  const lo = Math.floor(Math.min(...werte) * 20) / 20;
  const hi = Math.ceil(Math.max(...werte) * 20) / 20;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const ticks: number[] = [];
  for (let t = lo; t <= hi + 1e-9; t += 0.05) ticks.push(t);

  return (
    <div className="hantel">
      <div className="hantel-zeile hantel-achse" aria-hidden>
        <span />
        <div className="hantel-track">
          {ticks.map((t) => (
            <span key={t} className="hantel-tick" style={{ left: x(t) }}>
              {Math.round(t * 100)}%
            </span>
          ))}
        </div>
        <span />
      </div>
      {zeilen.map((z) => (
        <div className="hantel-zeile" key={z.typ}>
          <div>
            <div className="hantel-name">{festtypName(z.typ)}</div>
            <div className="muted small">{zahl(z.n)} Gänge</div>
          </div>
          <div
            className="hantel-track"
            title={`${festtypName(z.typ)}: Modell ${prozent(z.modell)}${z.elo !== null ? `, Elo ${prozent(z.elo)}` : ""}`}
          >
            {ticks.map((t) => (
              <span key={t} className="hantel-gitter" style={{ left: x(t) }} />
            ))}
            {z.elo !== null && (
              <>
                <span
                  className="hantel-linie"
                  style={{
                    left: x(Math.min(z.elo, z.modell)),
                    width: `calc(${x(Math.max(z.elo, z.modell))} - ${x(Math.min(z.elo, z.modell))})`,
                  }}
                />
                <span className="hantel-punkt hantel-elo" style={{ left: x(z.elo) }} />
              </>
            )}
            <span className="hantel-punkt hantel-modell" style={{ left: x(z.modell) }} />
          </div>
          <div className="hantel-wert">
            <strong>{prozent(z.modell)}</strong>
            {z.elo !== null && <div className="muted small">Elo {prozent(z.elo)}</div>}
          </div>
        </div>
      ))}
      <div className="hantel-legende muted small">
        <span>
          <i className="hantel-punkt hantel-modell hantel-legende-punkt" /> unser Modell
        </span>
        <span>
          <i className="hantel-punkt hantel-elo hantel-legende-punkt" /> reine Elo-Prognose
        </span>
      </div>
    </div>
  );
}

// --- Entwicklung des Modells ------------------------------------------------

function stand(l: VerlaufLauf): string {
  return `${l.modell_typ}|${l.merkmal_version}`;
}

/** Je Modellstand der jüngste Lauf, in der Reihenfolge, in der die Stände
 *  eingeführt wurden. Der Balken zeigt den Vorsprung vor der reinen
 *  Elo-Prognose (Log-Loss-Differenz, länger = besser). */
export function ModellEntwicklung({ laeufe }: { laeufe: VerlaufLauf[] }) {
  const schritte = useMemo(() => {
    const erst = new Map<string, string>();
    const letzt = new Map<string, VerlaufLauf>();
    for (const l of laeufe) {
      if (!erst.has(stand(l))) erst.set(stand(l), l.datum);
      letzt.set(stand(l), l);
    }
    return [...letzt.entries()].map(([k, l]) => ({ ab: erst.get(k)!, l }));
  }, [laeufe]);
  if (schritte.length === 0) return null;
  const vorsprung = (l: VerlaufLauf) =>
    l.baseline_log_loss ? l.baseline_log_loss - l.log_loss : null;
  const max = Math.max(...schritte.map((s) => vorsprung(s.l) ?? 0), 1e-6);

  return (
    <ol className="meilensteine">
      {schritte.map(({ ab, l }, i) => {
        const text = modellStandText(l.modell_typ, l.merkmal_version);
        const v = vorsprung(l);
        const vorher = i > 0 ? schritte[i - 1].l.log_loss : null;
        const aktuell = i === schritte.length - 1;
        return (
          <li key={stand(l)} className={`meilenstein${aktuell ? " meilenstein-aktuell" : ""}`}>
            <div className="ms-kopf">
              <strong>{text.name}</strong>
              <span className="muted small">
                ab {datumKurz(ab)}
                {aktuell ? " · heute im Einsatz" : ""}
              </span>
            </div>
            <div className="muted small">{text.was}</div>
            <div className="ms-zeile">
              <div className="ms-track">
                {v !== null && <div className="ms-fill" style={{ width: `${(v / max) * 100}%` }} />}
              </div>
              <div className="ms-werte">
                <span>
                  Log-Loss <strong>{l.log_loss.toFixed(3)}</strong>
                  {vorher !== null && (
                    <span className="ms-delta">
                      {" "}
                      {(l.log_loss - vorher).toFixed(3).replace("-", "−")}
                    </span>
                  )}
                </span>
                <span className="muted">Treffer {(l.accuracy * 100).toFixed(1)}%</span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// --- Tägliche Überwachung ---------------------------------------------------

/** Nur Läufe des aktuellen Modellstands -- nur sie sind vergleichbar. Die
 *  Alarmgrenze ist die der Pipeline (export.verlauf_warnung): Median der
 *  letzten 14 vergleichbaren Läufe + 0.01. */
export function Ueberwachung({
  laeufe,
  warnung,
}: {
  laeufe: VerlaufLauf[];
  warnung: string | null | undefined;
}) {
  if (laeufe.length === 0) return null;
  const jetzt = laeufe[laeufe.length - 1];
  const vergleichbar = laeufe.filter(
    (l) => stand(l) === stand(jetzt) && l.holdout_jahr === jetzt.holdout_jahr
  );
  const frueher = vergleichbar
    .slice(0, -1)
    .slice(-14)
    .map((l) => l.log_loss)
    .sort((a, b) => a - b);
  const median = frueher.length ? frueher[Math.floor((frueher.length - 1) / 2)] : null;
  const grenze = frueher.length >= 3 && median !== null ? median + 0.01 : null;

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        {warnung ? (
          <span className="badge badge-warn">⚠ {warnung}</span>
        ) : (
          <span className="badge badge-ok">✓ keine Auffälligkeit</span>
        )}{" "}
        <span className="muted small">
          letzter Lauf {datumKurz(jetzt.datum)}: Log-Loss {jetzt.log_loss.toFixed(3)}, Treffer{" "}
          {(jetzt.accuracy * 100).toFixed(1)}%
        </span>
      </p>
      {vergleichbar.length >= 3 ? (
        <VerlaufDiagramm
          laeufe={vergleichbar}
          titel="Log-Loss je Lauf (tiefer = besser)"
          wert={(l) => l.log_loss}
          format={(v) => v.toFixed(3)}
          schwelle={grenze ?? undefined}
        />
      ) : (
        <p className="muted small">
          Dieser Modellstand läuft seit {datumKurz(vergleichbar[0].datum)}. Der Verlauf erscheint ab
          drei täglichen Läufen; die Alarmgrenze ab dann.
        </p>
      )}
    </div>
  );
}
