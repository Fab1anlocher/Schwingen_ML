"use client";

// Seite "Rückblick": was eine Saison ausgemacht hat -- Festsieger, Kränze,
// Aufsteiger (Elo-Gewinn), die grössten Überraschungen und die Kranzfeste.
// Aufsteiger, Kränze je Saison und Überraschungen kommen aus
// saison_rueckblick.json (pipeline/saison_rueckblick.py), Festsiege aus
// schwinger.json, Feste und Prognose-Check aus events.json.

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeSaisonRueckblick, ladeSchwinger } from "@/lib/data";
import type {
  EventsArtifact,
  SaisonEloEintrag,
  SaisonRueckblickArtifact,
  Schwinger,
} from "@/lib/types";
import { datumKurz, festtypName, prozent, prozent1, zahl } from "@/lib/labels";

const KRANZFESTE = new Set(["kantonal", "teilverband", "berg", "eidgenoessisch"]);
// Für "beste/schwächste Prognose": nur Feste mit genug Gängen.
const MIN_GAENGE_FEST = 100;
// Wie saison_rueckblick.MIN_GAENGE_AUFSTEIGER (nur für den Text).
const MIN_GAENGE = 15;

/** Aufsteiger (Balken = Gewinn) oder Neue (Balken = Elo am Saisonende). */
function EloListe({ liste, wert }: { liste: SaisonEloEintrag[]; wert: "gewinn" | "elo_nachher" }) {
  const werte = liste.map((a) => a[wert]);
  // Neue: Balken ab dem kleinsten gezeigten Wert, sonst wären alle fast gleich lang.
  const boden = wert === "gewinn" ? 0 : Math.min(...werte) - 50;
  const max = Math.max(...werte.map((v) => v - boden), 1);
  return (
    <table>
      <tbody>
        {liste.map((a) => (
          <tr key={a.id}>
            <td style={{ width: "40%" }}>{a.name}</td>
            <td style={{ width: "28%" }}>
              <div
                className="fi-bar"
                style={{ width: `${(Math.max(0, a[wert] - boden) / max) * 100}%` }}
              />
            </td>
            <td className="small" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              {wert === "gewinn" ? (
                <>
                  <strong>
                    {a.gewinn >= 0 ? "+" : "−"}
                    {Math.abs(Math.round(a.gewinn))}
                  </strong>{" "}
                  <span className="muted">
                    ({Math.round(a.elo_vorher)} → {Math.round(a.elo_nachher)})
                  </span>
                </>
              ) : (
                <>
                  <strong>{Math.round(a.elo_nachher)}</strong>{" "}
                  <span className="muted">({a.gaenge} Gänge)</span>
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Rueckblick() {
  const [daten, setDaten] = useState<SaisonRueckblickArtifact | null>(null);
  const [events, setEvents] = useState<EventsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [saison, setSaison] = useState<string>("");

  useEffect(() => {
    ladeSaisonRueckblick()
      .then((d) => {
        setDaten(d);
        const jahre = Object.keys(d?.saisons ?? {}).sort();
        setSaison((s) => s || jahre[jahre.length - 1] || "");
      })
      .catch((e) => setFehler(String(e)));
    ladeEvents()
      .then(setEvents)
      .catch(() => {});
    ladeSchwinger()
      .then(setSchwinger)
      .catch(() => {});
  }, []);

  const s = daten?.saisons[saison];
  const check = events?.prognose_check_saisons?.[saison];

  const feste = useMemo(
    () => (events?.vergangene ?? []).filter((f) => f.datum.startsWith(saison)),
    [events, saison]
  );
  const festName = useMemo(() => new Map(feste.map((f) => [f.id, f.name])), [feste]);

  // Festsiege der Saison je Schwinger (geteilte Siege zählen für alle).
  const festsieger = useMemo(() => {
    return schwinger
      .map((x) => ({
        x,
        siege: (x.festsiege ?? []).filter((f) => f.datum.startsWith(saison)),
      }))
      .filter((e) => e.siege.length > 0)
      .sort(
        (a, b) =>
          b.siege.length - a.siege.length ||
          b.siege.filter((f) => KRANZFESTE.has(f.typ)).length -
            a.siege.filter((f) => KRANZFESTE.has(f.typ)).length ||
          a.x.name.localeCompare(b.x.name)
      )
      .slice(0, 10);
  }, [schwinger, saison]);

  const kranzfeste = useMemo(
    () => feste.filter((f) => KRANZFESTE.has(f.typ)).sort((a, b) => a.datum.localeCompare(b.datum)),
    [feste]
  );
  const mitCheck = useMemo(
    () =>
      feste
        .filter((f) => f.prognose_check && f.prognose_check.n >= MIN_GAENGE_FEST)
        .sort((a, b) => b.prognose_check!.treffer - a.prognose_check!.treffer),
    [feste]
  );

  if (fehler) return <p className="warn">Fehler: {fehler}</p>;
  if (!daten) return <p className="muted">Lade …</p>;
  const jahre = Object.keys(daten.saisons).sort().reverse();
  if (!s) return <p className="muted">Noch keine Saison ausgewertet.</p>;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>Saisonrückblick {saison}</h1>
        {jahre.length > 1 && (
          <select
            aria-label="Saison"
            value={saison}
            onChange={(e) => setSaison(e.target.value)}
            style={{ maxWidth: "8rem" }}
          >
            {jahre.map((j) => (
              <option key={j} value={j}>
                {j}
              </option>
            ))}
          </select>
        )}
      </div>
      <p className="subtitle">
        {s.n_feste} Feste vom {datumKurz(s.von)} bis {datumKurz(s.bis)}: wer gewann, wer aufstieg,
        und wo das Unerwartete geschah.
      </p>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-zahl">{s.n_feste}</div>
          <div className="kpi-label">Feste</div>
          <div className="kpi-sub">davon {kranzfeste.length} Kranzfeste</div>
        </div>
        <div className="kpi">
          <div className="kpi-zahl">{zahl(s.n_gaenge)}</div>
          <div className="kpi-label">Gänge</div>
          <div className="kpi-sub">
            {s.anteil_gestellt !== null && `${prozent(s.anteil_gestellt)} gestellt`}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-zahl">{zahl(s.n_schwinger)}</div>
          <div className="kpi-label">Schwinger im Einsatz</div>
        </div>
        {check && (
          <div className="kpi">
            <div className="kpi-zahl">{prozent1(check.treffer)}</div>
            <div className="kpi-label">der Gänge richtig vorhergesagt</div>
            <div className="kpi-sub">
              Modell von vor der Saison · nur Elo{" "}
              {check.treffer_elo !== null ? prozent1(check.treffer_elo) : "–"}
            </div>
          </div>
        )}
      </div>

      <div className="grid-2" style={{ marginTop: "1.2rem" }}>
        <div>
          <h2>Die Festsieger</h2>
          <div className="panel">
            {festsieger.length === 0 ? (
              <p className="muted small">Keine Schlussranglisten für diese Saison.</p>
            ) : (
              <table>
                <tbody>
                  {festsieger.map(({ x, siege }) => (
                    <tr key={x.id}>
                      <td>
                        <strong>{x.name}</strong>
                        <div className="muted small">
                          {siege
                            .slice()
                            .sort((a, b) => a.datum.localeCompare(b.datum))
                            .map((f) => f.name)
                            .join(" · ")}
                        </div>
                      </td>
                      <td style={{ textAlign: "right", verticalAlign: "top" }}>
                        <strong>{siege.length}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div>
          <h2>Die meisten Kränze</h2>
          <div className="panel">
            {s.kraenze.length === 0 ? (
              <p className="muted small">Keine Schlussranglisten für diese Saison.</p>
            ) : (
              <table>
                <tbody>
                  {s.kraenze.map((k) => (
                    <tr key={k.id}>
                      <td>{k.name}</td>
                      <td style={{ textAlign: "right" }}>
                        <strong>{k.kraenze}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: "1.2rem" }}>
        <div>
          <h2>Die Aufsteiger</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Grösster Elo-Gewinn von vor dem ersten bis nach dem letzten Gang der Saison — wer schon
              vorher in den Daten war und mindestens {MIN_GAENGE} Gänge bestritt.
            </p>
            <EloListe liste={s.aufsteiger} wert="gewinn" />
          </div>
        </div>
        {s.neue && s.neue.length > 0 && (
          <div>
            <h2>Die stärksten Neuen</h2>
            <div className="panel">
              <p className="muted small" style={{ marginTop: 0 }}>
                Zum ersten Mal in den Daten (ab {MIN_GAENGE} Gängen), nach dem Elo am Saisonende. Ihr
                Gewinn wäre vor allem der Weg vom Startwert {Math.round(s.neue[0].elo_vorher)} zur
                eigenen Stärke.
              </p>
              <EloListe liste={s.neue} wert="elo_nachher" />
            </div>
          </div>
        )}
      </div>

      {s.ueberraschungen.length > 0 && (
        <>
          <h2>Die grössten Überraschungen</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Siege, die das Modell von vor der Saison am wenigsten erwartet hatte — mit dem Stand
              beider Schwinger vor dem jeweiligen Fest.
            </p>
            <table>
              <tbody>
                {s.ueberraschungen.map((u) => (
                  <tr key={`${u.event_id}-${u.sieger}-${u.verlierer}`}>
                    <td>
                      <strong>{u.sieger_name}</strong> schlug {u.verlierer_name}
                      <div className="muted small">
                        {festName.get(u.event_id) ?? u.event_id}, {datumKurz(u.datum)} ·{" "}
                        <Link
                          href={`/?a=${encodeURIComponent(u.sieger)}&b=${encodeURIComponent(u.verlierer)}`}
                        >
                          Paarung heute
                        </Link>
                      </div>
                    </td>
                    <td style={{ textAlign: "right", verticalAlign: "top", whiteSpace: "nowrap" }}>
                      <strong>{prozent1(u.p_sieger)}</strong>
                      <div className="muted small">Siegchance</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {kranzfeste.length > 0 && (
        <>
          <h2>Die Kranzfeste</h2>
          <div className="panel tabelle-wrap">
            <table style={{ minWidth: 560 }}>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Fest</th>
                  <th>Sieger</th>
                  <th style={{ textAlign: "right" }}>Kränze</th>
                  <th style={{ textAlign: "right" }}>Prognose</th>
                </tr>
              </thead>
              <tbody>
                {kranzfeste.map((f) => (
                  <tr key={f.id}>
                    <td className="muted small">{datumKurz(f.datum)}</td>
                    <td>
                      {f.name}
                      <div className="muted small">{festtypName(f.typ)}</div>
                    </td>
                    <td>{(f.sieger ?? []).map((x) => x.name).join(", ") || "–"}</td>
                    <td style={{ textAlign: "right" }}>{f.n_kraenze ?? "–"}</td>
                    <td style={{ textAlign: "right" }}>
                      {f.prognose_check ? prozent(f.prognose_check.treffer) : "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {mitCheck.length >= 6 && (
        <>
          <h2>Wo die Prognose am besten und am schlechtesten lag</h2>
          <div className="panel">
            <p className="muted small" style={{ marginTop: 0 }}>
              Anteil richtig vorhergesagter Gänge je Fest (nur Feste mit mindestens{" "}
              {MIN_GAENGE_FEST} Gängen), mit dem Modell von vor der Saison. Alle Feste stehen im{" "}
              <Link href="/feste">Rückblick der Feste</Link>.
            </p>
            <div className="grid-2">
              {[
                { titel: "Am besten", liste: mitCheck.slice(0, 3) },
                { titel: "Am schlechtesten", liste: mitCheck.slice(-3).reverse() },
              ].map(({ titel, liste }) => (
                <div key={titel}>
                  <strong>{titel}</strong>
                  <table>
                    <tbody>
                      {liste.map((f) => (
                        <tr key={f.id}>
                          <td>
                            {f.name}
                            <div className="muted small">
                              {festtypName(f.typ)} · {zahl(f.prognose_check!.n)} Gänge
                            </div>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <strong>{prozent(f.prognose_check!.treffer)}</strong>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
