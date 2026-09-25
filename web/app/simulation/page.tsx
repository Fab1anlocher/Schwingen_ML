"use client";

// Seite "Simulator": ein ganzes Schwingfest tausendfach durchspielen
// (web/lib/simulation.ts, gespiegelt aus pipeline/fest_simulation.py).
// Startfeld = alle, die an einem gewählten Fest geschwungen haben
// (/api/fest-feld); Paar-Wahrscheinlichkeiten aus dem Modell mit dem
// HEUTIGEN Stand jedes Schwingers. Unten der ehrliche Rückblick
// (simulation_backtest.json): dieselbe Simulation mit dem Modell von vor der
// Saison gegen die echten Ranglisten.

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ladeEvents,
  ladeModel,
  ladeRatings,
  ladeSchwinger,
  ladeSimulationBacktest,
} from "@/lib/data";
import { paarWahrscheinlichkeiten } from "@/lib/inference";
import { paarHistorie, trefferAusSichtVonA, type H2HTreffer } from "@/lib/kopfAnKopf";
import { REGELN_JE_TYP, simuliere, type Regeln } from "@/lib/simulation";
import { datumKurz, festtypName, prozent, zahl } from "@/lib/labels";
import type {
  EventsArtifact,
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
  SimulationBacktest,
  VergangenesFest,
} from "@/lib/types";

const FESTTYPEN = new Set(["kantonal", "teilverband", "berg", "eidgenoessisch"]);
// Beschriftung fest statt zahl(): beim Vorrendern auf dem Server formatiert
// Node "1'000", der Browser "1’000" -- das gäbe einen Hydration-Fehler.
const SIMULATIONEN = [
  { wert: 1000, label: "1’000" },
  { wert: 5000, label: "5’000" },
];
const SEED = 1;
const ZEIGEN = 30;

/** Regeln für ein Fest. Kilchberg und Unspunnen zählen als "eidgenössisch",
 *  haben aber nur ~60-120 Teilnehmer, 6 Gänge und keine Kränze. */
function regelnFuer(typ: string, n: number): Regeln {
  const r = REGELN_JE_TYP[typ] ?? REGELN_JE_TYP.kantonal;
  if (typ === "eidgenoessisch" && n < 150) {
    return { ...REGELN_JE_TYP.kantonal, kranzquote: 0 };
  }
  return r;
}

interface Zeile {
  s: Schwinger;
  elo: number;
  festsieg: number;
  schlussgang: number;
  kranz: number;
  punkte: number;
}

interface Resultat {
  zeilen: Zeile[];
  kranzgrenze: number | null;
  regeln: Regeln;
  nSim: number;
  dauerMs: number;
}

// Rechenarbeit in Häppchen, damit die Seite während der Paarungen reagiert.
const pause = () => new Promise((r) => setTimeout(r, 0));

export default function Simulator() {
  const [events, setEvents] = useState<EventsArtifact | null>(null);
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [backtest, setBacktest] = useState<SimulationBacktest | null>(null);
  const [festId, setFestId] = useState("");
  const [nSim, setNSim] = useState(SIMULATIONEN[0].wert);
  const [status, setStatus] = useState<string | null>(null);
  const [resultat, setResultat] = useState<Resultat | null>(null);
  const [alle, setAlle] = useState(false);

  useEffect(() => {
    Promise.all([ladeEvents(), ladeModel(), ladeRatings(), ladeSchwinger()]).then(
      ([e, m, r, s]) => {
        setEvents(e);
        setModel(m);
        setRatings(r);
        setSchwinger(s);
      }
    );
    ladeSimulationBacktest().then(setBacktest);
  }, []);

  const feste = useMemo(
    () =>
      (events?.vergangene ?? [])
        .filter((f) => FESTTYPEN.has(f.typ) && (f.n_teilnehmer ?? 0) >= 20)
        .sort((a, b) => b.datum.localeCompare(a.datum)),
    [events]
  );
  // Voreinstellung: das jüngste Fest mit Kränzen (Kilchberg und Unspunnen
  // vergeben keine -- dort wäre die halbe Auswertung leer).
  const fest: VergangenesFest | undefined =
    feste.find((f) => f.id === festId) ?? feste.find((f) => (f.n_kraenze ?? 0) > 0) ?? feste[0];
  const byId = useMemo(() => Object.fromEntries(schwinger.map((s) => [s.id, s])), [schwinger]);

  async function starte() {
    if (!fest || !model || !ratings) return;
    const start = performance.now();
    setResultat(null);
    setStatus("Teilnehmerfeld laden …");
    const antwort = await fetch(`/api/fest-feld?event=${encodeURIComponent(fest.id)}`);
    const feld: { teilnehmer: string[]; paare: { a: string; b: string; treffer: H2HTreffer[] }[] } =
      await antwort.json();
    const rating = (id: string) => ratings.ratings[id] ?? { elo: ratings.elo_start, n_gaenge: 0 };
    // Setzreihenfolge wie in der Pipeline: stärkster zuerst (Elo, dann ID).
    const teil = feld.teilnehmer
      .filter((id) => byId[id])
      .sort((a, b) => rating(b).elo - rating(a).elo || (a < b ? -1 : a > b ? 1 : 0));
    const historie = new Map(feld.paare.map((p) => [`${p.a}\u0000${p.b}`, p.treffer]));
    const n = teil.length;
    const pSieg = Array.from({ length: n }, () => new Array<number>(n).fill(0));
    const pGestellt = Array.from({ length: n }, () => new Array<number>(n).fill(0));
    for (let i = 0; i < n; i++) {
      if (i % 12 === 0) {
        setStatus(`Paarungen berechnen … ${Math.round((i / n) * 100)} %`);
        await pause();
      }
      for (let j = i + 1; j < n; j++) {
        const [x, y] = [teil[i], teil[j]];
        const kanonisch = historie.get(x < y ? `${x}\u0000${y}` : `${y}\u0000${x}`) ?? [];
        const [pa, pg, pb] = paarWahrscheinlichkeiten(
          model,
          byId[x],
          byId[y],
          rating(x).elo,
          rating(y).elo,
          rating(x).n_gaenge,
          rating(y).n_gaenge,
          paarHistorie(trefferAusSichtVonA(kanonisch, x, y))
        );
        pSieg[i][j] = pa;
        pSieg[j][i] = pb;
        pGestellt[i][j] = pGestellt[j][i] = pg;
      }
    }
    setStatus(`${zahl(nSim)} Feste simulieren …`);
    await pause();
    const regeln = regelnFuer(fest.typ, n);
    const e = simuliere(pSieg, pGestellt, regeln, nSim, SEED);
    const zeilen = teil
      .map((id, k) => ({
        s: byId[id],
        elo: rating(id).elo,
        festsieg: e.festsieg[k] / nSim,
        schlussgang: e.schlussgang[k] / nSim,
        kranz: e.kranz[k] / nSim,
        punkte: e.punkteSumme[k] / nSim,
      }))
      .sort((a, b) => b.festsieg - a.festsieg || b.kranz - a.kranz || b.punkte - a.punkte);
    setResultat({
      zeilen,
      kranzgrenze: regeln.kranzquote > 0 ? e.kranzgrenzeSumme / nSim : null,
      regeln,
      nSim,
      dauerMs: performance.now() - start,
    });
    setStatus(null);
  }

  // Beim ersten Laden und bei jedem Wechsel automatisch rechnen.
  useEffect(() => {
    if (fest && model && ratings && schwinger.length) starte();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fest?.id, nSim, model, ratings, schwinger.length]);

  const top = resultat?.zeilen.slice(0, 10) ?? [];
  const maxSieg = Math.max(...top.map((z) => z.festsieg), 1e-9);
  const sichtbar = resultat ? (alle ? resultat.zeilen : resultat.zeilen.slice(0, ZEIGEN)) : [];

  return (
    <div>
      <div className="eyebrow">Monte-Carlo-Simulation</div>
      <h1>Fest-Simulator</h1>
      <p className="subtitle">
        Wer gewinnt, wer steht im Schlussgang, wer holt einen Kranz? Das Modell schwingt ein ganzes
        Fest tausendfach durch — Einteilung, Gänge, Noten, Ausstich, Schlussgang, Kranzvergabe.
      </p>

      <div className="panel" style={{ marginBottom: "1rem" }}>
        <div className="row" style={{ gap: "1rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ flex: "1 1 320px" }}>
            <label className="field" htmlFor="fest">
              Teilnehmerfeld von
            </label>
            <select id="fest" value={fest?.id ?? ""} onChange={(e) => setFestId(e.target.value)}>
              {feste.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} · {festtypName(f.typ)} · {datumKurz(f.datum)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="nsim">
              Durchgänge
            </label>
            <select id="nsim" value={nSim} onChange={(e) => setNSim(Number(e.target.value))}>
              {SIMULATIONEN.map((k) => (
                <option key={k.wert} value={k.wert}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          Simuliert wird das Feld dieses Fests mit dem <strong>heutigen</strong> Stand jedes
          Schwingers — „wie ginge es aus, wenn dieses Feld heute anträte?“. Wie gut die Simulation
          wirklich liegt, zeigt unten der Rückblick mit dem Modell von vor der Saison.
        </p>
      </div>

      {status && <p className="loading">{status}</p>}

      {resultat && fest && (
        <>
          <div className="kpi-grid">
            <div className="kpi">
              <div className="kpi-zahl">{prozent(resultat.zeilen[0].festsieg)}</div>
              <div className="kpi-label">Festsieg {resultat.zeilen[0].s.name}</div>
              <div className="kpi-sub">
                der Favorit; im Schlussgang in {prozent(resultat.zeilen[0].schlussgang)} der Feste
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-zahl">
                {resultat.kranzgrenze !== null ? resultat.kranzgrenze.toFixed(2) : "–"}
              </div>
              <div className="kpi-label">Punkte für einen Kranz</div>
              <div className="kpi-sub">
                {resultat.kranzgrenze !== null
                  ? `Ø simulierte Kranzgrenze bei ${prozent(resultat.regeln.kranzquote)} Kränzen`
                  : "dieses Fest vergibt keine Kränze"}
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-zahl">{zahl(resultat.zeilen.length)}</div>
              <div className="kpi-label">Schwinger im Feld</div>
              <div className="kpi-sub">
                {resultat.regeln.gaenge} Gänge
                {resultat.regeln.ausstiche.length
                  ? `, Ausstich nach Gang ${resultat.regeln.ausstiche.map(([g]) => g).join(" und ")}`
                  : ""}
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-zahl">{zahl(resultat.nSim)}</div>
              <div className="kpi-label">simulierte Feste</div>
              <div className="kpi-sub">
                in {(resultat.dauerMs / 1000).toFixed(1)} s im Browser gerechnet
              </div>
            </div>
          </div>

          <h2>Wer das Fest gewinnt</h2>
          <div className="panel">
            {top.map((z) => (
              <div
                className="rang-zeile"
                key={z.s.id}
                style={{ gridTemplateColumns: "minmax(0,1.2fr) minmax(0,1.5fr)" }}
              >
                <div>
                  <Link
                    href={`/?a=${encodeURIComponent(z.s.id)}`}
                    className="rang-name"
                    style={{ color: "var(--text)" }}
                  >
                    {z.s.name}
                  </Link>
                  <div className="muted small">
                    Elo {Math.round(z.elo)} · Schlussgang {prozent(z.schlussgang)}
                    {resultat.kranzgrenze !== null && ` · Kranz ${prozent(z.kranz)}`}
                  </div>
                </div>
                <div className="rang-balken">
                  <div className="rang-track">
                    <div
                      className="rang-fill"
                      style={{
                        width: `${(z.festsieg / maxSieg) * 100}%`,
                        background: "var(--accent)",
                      }}
                    />
                  </div>
                  <span className="rang-wert">{prozent(z.festsieg)}</span>
                </div>
              </div>
            ))}
            {fest.sieger && fest.sieger.length > 0 && (
              <p className="muted small" style={{ marginBottom: 0 }}>
                Tatsächlich gewann {fest.sieger.map((s) => s.name).join(" und ")}
                {fest.n_kraenze
                  ? `; ${zahl(fest.n_kraenze)} Kränze bei ${zahl(fest.n_teilnehmer ?? 0)} Teilnehmern`
                  : ""}
                . Zum Vergleich nur bedingt: das heutige Modell kennt dieses Fest schon.
              </p>
            )}
          </div>

          <h2>Alle Schwinger</h2>
          <div className="panel tabelle-wrap" style={{ padding: 0 }}>
            <table style={{ minWidth: 560 }}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Schwinger</th>
                  <th>Elo</th>
                  <th title="Anteil der Durchgänge, in denen er das Fest gewann">Festsieg</th>
                  <th title="Anteil der Durchgänge im Schlussgang">Schlussgang</th>
                  <th title="Anteil der Durchgänge mit Kranz">Kranz</th>
                  <th title="Mittlere Punktzahl über alle Durchgänge">Ø Punkte</th>
                </tr>
              </thead>
              <tbody>
                {sichtbar.map((z, i) => (
                  <tr key={z.s.id}>
                    <td className="muted">{i + 1}</td>
                    <td>{z.s.name}</td>
                    <td className="muted">{Math.round(z.elo)}</td>
                    <td>{z.festsieg >= 0.0005 ? `${(z.festsieg * 100).toFixed(1)}%` : "–"}</td>
                    <td>
                      {z.schlussgang >= 0.0005 ? `${(z.schlussgang * 100).toFixed(1)}%` : "–"}
                    </td>
                    <td>
                      {resultat.kranzgrenze !== null ? `${(z.kranz * 100).toFixed(0)}%` : "–"}
                    </td>
                    <td className="muted">{z.punkte.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resultat.zeilen.length > ZEIGEN && (
            <button
              className="teilen-btn"
              style={{ marginTop: "0.7rem" }}
              onClick={() => setAlle((a) => !a)}
            >
              {alle ? `Nur die ersten ${ZEIGEN}` : `Alle ${resultat.zeilen.length} anzeigen`}
            </button>
          )}
        </>
      )}

      <h2>So wird simuliert</h2>
      <div className="panel">
        <ol className="small" style={{ lineHeight: 1.65, paddingLeft: "1.2rem", margin: 0 }}>
          <li>
            <strong>Paarungen.</strong> Für jedes mögliche Paar im Feld rechnet das Modell Sieg,
            Gestellt und Niederlage — wie auf der Prognose-Seite, mit Elo, Form, Kranzstatus,
            direkten Duellen usw.
          </li>
          <li>
            <strong>Einteilung</strong> wie beim Einteilungskampfgericht: im ersten Gang die
            stärksten 20 % gegeneinander, das übrige Feld gemischt; danach nach Punkten mit
            Ermessensspielraum, ohne Wiederholungen. Kalibriert an den echten Paarungen 2026:
            mittlerer Elo-Abstand der Gegner real 108, simuliert 116; Gestellte real 22 %, simuliert
            22 %.
          </li>
          <li>
            <strong>Noten</strong> nach der Notengebung, Anteile gemessen an allen Gängen seit 2023:
            Sieg 10.00 (Plattwurf) in 52 %, sonst 9.75; Gestellt 9.00 in 31 %, sonst 8.75;
            Niederlage 8.75 in 11 %, sonst 8.50. Im Schlussgang 10.00 / 8.75.
          </li>
          <li>
            <strong>Ausstich</strong> nach Gang 4 (an Kranzfesten schwingen rund 80 % weiter; am
            Eidgenössischen nach Gang 4 und 6), <strong>Schlussgang</strong> der zwei Punktbesten,
            Festsieger ist dessen Sieger — bei gestelltem Schlussgang, wer am meisten Punkte hat.
          </li>
          <li>
            <strong>Kränze</strong> für die besten 16 % (am Eidgenössischen 15 %), bei
            Punktgleichheit an der Grenze alle. Die simulierte Kranzgrenze liegt an Kantonalfesten
            um 56.5 Punkte — wie in der Wirklichkeit.
          </li>
        </ol>
      </div>

      {backtest && (
        <>
          <h2>Wie gut liegt der Simulator?</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Rückblick auf {backtest.n_feste} Kranzfeste der Saison {backtest.saison}: jedes mit
              dem Modell simuliert, das <strong>vor</strong> der Saison galt, und dem Stand jedes
              Schwingers vor dem Fest — dann mit der Schlussrangliste verglichen. Zum Vergleich
              dieselbe Simulation mit reinen Elo-Wahrscheinlichkeiten.
            </p>
            <div className="tabelle-wrap">
              <table style={{ minWidth: 420 }}>
                <thead>
                  <tr>
                    <th />
                    <th>Modell</th>
                    <th>nur Elo</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.festsieg.p_sieger_modell !== null && (
                    <tr>
                      <td>Wahrscheinlichkeit, die der tatsächliche Festsieger bekam (Ø)</td>
                      <td>
                        <strong>{prozent(backtest.festsieg.p_sieger_modell)}</strong>
                      </td>
                      <td>{prozent(backtest.festsieg.p_sieger_elo ?? 0)}</td>
                    </tr>
                  )}
                  {backtest.festsieg.favorit_modell !== null && (
                    <tr>
                      <td>Der Favorit gewann das Fest</td>
                      <td>
                        <strong>{prozent(backtest.festsieg.favorit_modell)}</strong>
                      </td>
                      <td>{prozent(backtest.festsieg.favorit_elo ?? 0)}</td>
                    </tr>
                  )}
                  {backtest.festsieg.top3_modell !== null && (
                    <tr>
                      <td>Sieger unter den drei Favoriten</td>
                      <td>
                        <strong>{prozent(backtest.festsieg.top3_modell)}</strong>
                      </td>
                      <td>{prozent(backtest.festsieg.top3_elo ?? 0)}</td>
                    </tr>
                  )}
                  <tr>
                    <td>
                      Kranz: Brier-Score (tiefer = besser; ohne Wissen über die Schwinger{" "}
                      {backtest.kranz.brier_konstant.toFixed(3)})
                    </td>
                    <td>
                      <strong>{backtest.kranz.brier_modell.toFixed(3)}</strong>
                    </td>
                    <td>{backtest.kranz.brier_elo.toFixed(3)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <h3 style={{ marginTop: "1.2rem" }}>Stimmen die Kranzchancen?</h3>
            <div className="tabelle-wrap">
              <table style={{ minWidth: 380 }}>
                <thead>
                  <tr>
                    <th>simulierte Kranzchance</th>
                    <th>Schwinger</th>
                    <th>Ø vorhergesagt</th>
                    <th>tatsächlich Kranz</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.kranz.kalibrierung.map((k) => (
                    <tr key={k.von}>
                      <td>
                        {Math.round(k.von * 100)}–{Math.round(k.bis * 100)}%
                      </td>
                      <td className="muted">{zahl(k.n)}</td>
                      <td>{prozent(k.vorhergesagt)}</td>
                      <td>
                        <strong>{prozent(k.eingetreten)}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small" style={{ marginBottom: 0 }}>
              {zahl(backtest.n_teilnahmen)} Teilnahmen, je Fest {zahl(backtest.n_simulationen)}{" "}
              Durchgänge; mittlere Feldgrösse {backtest.festsieg.mittlere_feldgroesse ?? "–"}. Die
              Zahl der Kränze ist dabei die tatsächliche des Fests — gemessen wird, wer sie holt.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
