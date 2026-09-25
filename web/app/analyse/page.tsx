"use client";

// Seite "Analyse": die Antwort zuerst (Kennzahlen), dann Vergleich der
// Ansätze, Schwierigkeit je Festtyp (Prognose-Check, events.json),
// Gestellt-Kalibrierung, Entwicklung des Modells und tägliche Überwachung
// (report_verlauf.json), Merkmalswichtigkeit, Exkurse zu Physis/Schwüngen
// und zuletzt Details für Fachleute (Methodik, Konfusionsmatrix, alle
// Fehlermasse, alle Läufe). Alle Zahlen stammen aus dem letzten
// Pipeline-Lauf; hier wird nichts neu geschätzt.

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ladeBenchmark,
  ladeEvents,
  ladeFeatureImportance,
  ladeRatings,
  ladeSchwinger,
  ladeVerlauf,
} from "@/lib/data";
import { modellStand, type VerlaufLauf } from "@/components/VerlaufDiagramm";
import type {
  BenchmarkArtifact,
  EventsArtifact,
  FeatureImportanceEntry,
  RatingsArtifact,
  Schwinger,
} from "@/lib/types";
import {
  GestelltKalibrierung,
  Konfusionsmatrix,
  VierWegeBenchmark,
  type GestelltKalibrierungDaten,
} from "@/components/ModellGuete";
import {
  AnsatzRangliste,
  Kennzahlen,
  ModellEntwicklung,
  SchwierigkeitJeFesttyp,
  Ueberwachung,
  type Kennzahl,
} from "@/components/AnalyseTeile";
import { StreudiagrammMitTrend } from "@/components/StreudiagrammMitTrend";
import { SchwungVergleich, type SchwungStat } from "@/components/SchwungVergleich";
import { datumKurz, prozent, schwungName, zahl } from "@/lib/labels";

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
  /** T1: Stand des Verlaufs und Warnung des jüngsten Laufs (export.ergaenze_verlauf). */
  modell_verlauf?: { n_laeufe: number; warnung: string | null } | null;
}

// Merkmale, die die Spec explizit beleuchten will (AK-4.2).
const FOKUS = new Set(["gewicht_diff", "groesse_diff", "schwung_overlap", "schwung_count_diff"]);

export default function Analyse() {
  const [fi, setFi] = useState<FeatureImportanceEntry[]>([]);
  const [fiArt, setFiArt] = useState<"koeffizient" | "permutation">("koeffizient");
  const [verlauf, setVerlauf] = useState<VerlaufLauf[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [events, setEvents] = useState<EventsArtifact | null>(null);
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
    ladeBenchmark()
      .then(setBenchmark)
      .catch(() => {});
    ladeSchwinger()
      .then(setSchwinger)
      .catch(() => {});
    ladeRatings()
      .then(setRatings)
      .catch(() => {});
    ladeEvents()
      .then(setEvents)
      .catch(() => {});
  }, []);

  // Nur Schwinger mit tatsächlich erfassten Gängen (nicht der Elo-Startwert
  // ohne jede Messung) und erfasstem Körperwert -- sonst würde die Nulllinie
  // Rauschen ins Streudiagramm bringen statt eine echte Elo-Messung.
  const streuGroesse = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.groesse_cm)
      .map((e) => ({
        x: e.s.groesse_cm as number,
        y: e.r!.elo,
        label: e.s.name,
      }));
  }, [schwinger, ratings]);

  const streuGewicht = useMemo(() => {
    if (!ratings) return [];
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.gewicht_kg)
      .map((e) => ({
        x: e.s.gewicht_kg as number,
        y: e.r!.elo,
        label: e.s.name,
      }));
  }, [schwinger, ratings]);

  const streuAlter = useMemo(() => {
    if (!ratings) return [];
    const jahr = new Date().getFullYear();
    return schwinger
      .map((s) => ({ s, r: ratings.ratings[s.id] }))
      .filter((e) => e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && e.s.jahrgang)
      .map((e) => ({
        x: jahr - (e.s.jahrgang as number),
        y: e.r!.elo,
        label: e.s.name,
      }));
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
      .filter(
        (e) =>
          e.r && e.r.n_gaenge >= MIN_GAENGE_FUER_ELO && (e.s.bevorzugte_schwuenge?.length ?? 0) > 0
      );
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
  const haupt = fi.slice(0, 8);
  const rest = fi.slice(8);
  const saison = report ? String(report.holdout_jahr) : "";
  const check = events?.prognose_check_saisons?.[saison];
  const kal = report?.gestellt_kalibrierung;
  const lr = benchmark?.kandidaten.find((k) => k.key === "lr_komplett");

  const kennzahlen: Kennzahl[] = report
    ? [
        {
          zahl: prozent(report.modell.accuracy),
          label: "der Gänge richtig vorhergesagt",
          sub: `reine Elo-Prognose: ${prozent(report.baseline_elo.accuracy)}`,
        },
        check
          ? {
              zahl: prozent(check.p_eingetreten),
              label: "gab das Modell im Schnitt dem tatsächlichen Ausgang",
              sub: `Log-Loss ${report.modell.log_loss.toFixed(3)} · Elo ${report.baseline_elo.log_loss.toFixed(3)}`,
            }
          : {
              zahl: report.modell.log_loss.toFixed(3),
              label: "Log-Loss (tiefer = besser)",
              sub: `reine Elo-Prognose: ${report.baseline_elo.log_loss.toFixed(3)}`,
            },
        kal
          ? {
              zahl: `${prozent(kal.vorhergesagt)} / ${prozent(kal.eingetreten)}`,
              label: "Gestellt vorhergesagt / eingetreten",
              sub: `im Schnitt ${(kal.ece * 100).toFixed(1)} Prozentpunkte daneben`,
            }
          : { zahl: "–", label: "Gestellt-Kalibrierung", sub: "noch nicht gemessen" },
        {
          zahl: zahl(report.n_test),
          label: `Testgänge der Saison ${report.holdout_jahr}`,
          sub: "beim Training unbekannt",
        },
      ]
    : [];

  return (
    <div>
      <h1>Wie gut sind die Prognosen?</h1>
      <p className="subtitle">
        Gemessen an der ganzen Saison {saison || "…"}: jeder Gang so vorhergesagt, als hätte er noch
        nicht stattgefunden — und verglichen mit dem, was dann geschah.
      </p>

      {report && <Kennzahlen werte={kennzahlen} />}

      {benchmark && (
        <>
          <h2>Im Vergleich</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Fünf Ansätze auf denselben {zahl(benchmark.n_test)} Gängen, bester zuerst. Der Balken
              zeigt, wie oft der wahrscheinlichste Ausgang eintrat; der Brier-Score misst
              zusätzlich, ob die Wahrscheinlichkeiten stimmen (tiefer = besser).
              {lr &&
                ` Der Wechsel vom linearen Modell auf Gradient Boosting brachte ${(
                  (benchmark.kandidaten.find((k) => k.key === "ml_komplett")!.accuracy -
                    lr.accuracy) *
                  100
                ).toFixed(
                  1
                )} Prozentpunkte mehr Treffer und deutlich bessere Wahrscheinlichkeiten.`}
            </p>
            <AnsatzRangliste kandidaten={benchmark.kandidaten} />
          </div>
        </>
      )}

      {events && check && (
        <>
          <h2>Wo Schwingen schwer vorherzusagen ist</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Treffer je Festtyp in der Saison {saison}, gerechnet mit dem Modell, das vor der
              Saison galt. An Bergfesten und am Eidgenössischen treffen mehr Spitzenschwinger
              aufeinander, und es wird öfter gestellt — dort liegt jede Prognose seltener richtig.
              Je Fest steht die Trefferquote im <Link href="/feste">Rückblick der Feste</Link>.
            </p>
            <SchwierigkeitJeFesttyp feste={events.vergangene} saison={saison} />
          </div>
        </>
      )}

      {kal?.stufen?.length ? (
        <>
          <h2>Stimmt die Gestellt-Chance?</h2>
          <div className="panel">
            <GestelltKalibrierung
              daten={kal}
              erklaerung={
                <p className="muted small">
                  „Gestellt“ ist selten der wahrscheinlichste Ausgang — die Trefferquote sieht darum
                  kaum, ob die angezeigte Gestellt-Chance stimmt. Hier sind die {zahl(kal.n)}{" "}
                  Testgänge nach vorhergesagter Gestellt-Chance in zehn gleich grosse Gruppen
                  geteilt. Liegen die Punkte auf der Diagonalen, endet ein Gang genau so oft
                  gestellt, wie das Modell sagt.
                </p>
              }
            />
          </div>
        </>
      ) : null}

      {verlauf.length > 0 && (
        <>
          <h2>Wie das Modell besser wurde</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Jeder Schritt wurde an der Saison {saison} gemessen und nur übernommen, wenn er auch
              auf der Saison davor besser war. Der Balken zeigt den Vorsprung vor der reinen
              Elo-Prognose (länger = besser); daneben der Log-Loss und seine Änderung zum vorherigen
              Schritt.
            </p>
            <ModellEntwicklung laeufe={verlauf} />
          </div>

          <h3 style={{ marginTop: "1.6rem" }}>Tägliche Überwachung</h3>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Jeder tägliche Lauf misst neu. Steigt der Log-Loss mehr als 0.01 über den Median der
              letzten 14 vergleichbaren Läufe, meldet der Datenqualitätsbericht Alarm — etwa wenn
              neue Daten fehlerhaft eingelesen wurden.
            </p>
            <Ueberwachung laeufe={verlauf} warnung={report?.modell_verlauf?.warnung} />
          </div>
        </>
      )}

      {/* Erst mit den Daten zeigen: vorher stünde der Text der falschen Methode da. */}
      {fi.length > 0 && (
        <>
          <h2>Was die Prognose treibt</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              {fiArt === "permutation"
                ? "Um so viel verschlechtert sich die Prognose (Log-Loss), wenn man ein Merkmal zufällig unter den Testgängen vertauscht — also wie viel das Modell ohne dieses Merkmal verlöre."
                : "Mittlerer Betrag der standardisierten Koeffizienten über die drei Ausgänge."}
            </p>
            <FiTabelle eintraege={haupt} max={max} />
            {rest.length > 0 && (
              <details style={{ marginTop: "0.4rem" }}>
                <summary className="muted small">
                  Weitere {rest.length} Merkmale mit kleinem Beitrag
                </summary>
                <FiTabelle eintraege={rest} max={max} />
              </details>
            )}
            <p className="muted small" style={{ marginBottom: 0 }}>
              „Fokus“ markiert die Merkmale, deren Beitrag die Spezifikation eigens prüfen will
              (Gewicht, Grösse, bevorzugte Schwünge, AK-4.2). Klein heisst nicht bedeutungslos:
              Physis und Stil sind nur für Schwinger mit Porträt erfasst, und ein Teil ihrer Wirkung
              steckt schon im Elo-Rating — der Exkurs unten zeigt die Zusammenhänge direkt.
            </p>
          </div>
        </>
      )}

      {(streuGroesse.length > 0 || streuGewicht.length > 0 || streuAlter.length > 0) && (
        <>
          <h2>Exkurs: Macht Grösse, Gewicht oder Alter einen Unterschied?</h2>
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
          <h2>Exkurs: Macht der bevorzugte Schwung einen Unterschied?</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0, marginBottom: "0.5rem" }}>
              Ø Elo der Schwinger mit mindestens {MIN_GAENGE_FUER_ELO} Gängen, die diesen Schwung
              bevorzugen (nur Schwünge mit mindestens {MIN_SCHWINGER_PRO_SCHWUNG} Schwingern, sonst
              zu verrauscht — ein Schwinger kann mehrere bevorzugte Schwünge haben und zählt dann
              bei mehreren mit).
            </p>
            <SchwungVergleich daten={schwungStats} gesamtschnitt={gesamtschnittElo} />
          </div>
        </>
      )}

      {report && (
        <>
          <h2>Für Fachleute</h2>
          <div className="panel fachleute">
            <details>
              <summary>Methodik und Datenbasis</summary>
              <ul className="small" style={{ lineHeight: 1.6 }}>
                <li>
                  Datenbasis: {zahl(report.datenbasis.n_gaenge)} Gänge,{" "}
                  {zahl(report.datenbasis.n_schwinger)} Schwinger. Training{" "}
                  {zahl(report.n_train / 2)} Gänge vor der Saison {report.holdout_jahr} (je aus
                  beiden Sichten, A/B gespiegelt), Test {zahl(report.n_test)} Gänge der Saison{" "}
                  {report.holdout_jahr} — zeitlich getrennt, kein Zufallssplit.
                </li>
                <li>
                  Modell:{" "}
                  {report.modell_typ === "gbm"
                    ? "zweistufiges Gradient Boosting"
                    : "Logistic Regression"}
                  {report.n_baeume &&
                    ` (${report.n_baeume.gestellt} Bäume für Gestellt, ${report.n_baeume.sieg} für den Sieger)`}
                  , Merkmale Stand vor dem jeweiligen Fest.
                </li>
                {(report.n_train_ausgeliefert ?? 0) > report.n_train && (
                  <li>
                    Die App rechnet mit einem Modell derselben Einstellungen, das zusätzlich auf der
                    Saison {report.holdout_jahr} trainiert ist (
                    {zahl(report.n_train_ausgeliefert! / 2)} Gänge). Alle Kennzahlen hier stammen
                    bewusst vom Modell ohne sie.
                  </li>
                )}
                <li>
                  Log-Loss {report.modell.log_loss.toFixed(4)} gegen Elo{" "}
                  {report.baseline_elo.log_loss.toFixed(4)} (Differenz{" "}
                  {report.verbesserung_log_loss.toFixed(4)}); Treffer{" "}
                  {(report.modell.accuracy * 100).toFixed(1)}% gegen{" "}
                  {(report.baseline_elo.accuracy * 100).toFixed(1)}%.
                </li>
              </ul>
            </details>
            {report.konfusionsmatrix && report.klassen && (
              <details>
                <summary>Konfusionsmatrix</summary>
                <Konfusionsmatrix klassen={report.klassen} matrix={report.konfusionsmatrix} />
              </details>
            )}
            {benchmark && (
              <details>
                <summary>Alle Fehlermasse der Ansätze (Accuracy, Brier, MAE, MSE)</summary>
                <VierWegeBenchmark kandidaten={benchmark.kandidaten} />
              </details>
            )}
            {verlauf.length > 0 && (
              <details>
                <summary>Alle Läufe seit {datumKurz(verlauf[0].datum)}</summary>
                <div className="tabelle-wrap">
                  <table style={{ minWidth: 420 }}>
                    <thead>
                      <tr>
                        <th>Datum</th>
                        <th>Modell</th>
                        <th>Log-Loss</th>
                        <th>Treffer</th>
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
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** Merkmalswichtigkeit als Balkentabelle (s. oben: Haupt- und Restteil). */
function FiTabelle({ eintraege, max }: { eintraege: FeatureImportanceEntry[]; max: number }) {
  return (
    <table>
      <tbody>
        {eintraege.map((f) => (
          <tr key={f.feature}>
            <td style={{ width: "40%" }}>
              {f.label}
              {FOKUS.has(f.feature) && (
                <span className="badge" style={{ marginLeft: 6, fontSize: "0.7rem" }}>
                  Fokus
                </span>
              )}
            </td>
            <td style={{ width: "48%" }}>
              <div className="fi-bar" style={{ width: `${(f.wichtigkeit / max) * 100}%` }} />
            </td>
            <td className="muted small" style={{ textAlign: "right" }}>
              {f.wichtigkeit.toFixed(3)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
