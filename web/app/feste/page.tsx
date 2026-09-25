"use client";

// Seite "Feste": kommende Feste (events.json -> kommende, mit Prognose je
// veröffentlichter Paarung) und Rückblick auf vergangene Feste (Festsieger,
// Kränze, Teilnehmer laut Schlussrangliste, events.json -> vergangene).

import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import { ladeKopfAnKopf, paarHistorie, KEINE_HISTORIE } from "@/lib/kopfAnKopf";
import Link from "next/link";
import { teilverbandFuerFest } from "@/lib/teilverband";
import { datumKurz, festtypName, prozent, teilverbandName, zahl } from "@/lib/labels";
import type {
  EventsArtifact,
  ModelArtifact,
  PrognoseCheck,
  RatingsArtifact,
  Schwinger,
  KommendesFest,
  VergangenesFest,
} from "@/lib/types";

// Spiegelt pipeline/scrape/agenda.HORIZONT_TAGE — wie weit die Vorschau reicht.
const HORIZONT_TAGE = 60;

// Festtypen, an denen Kränze vergeben werden -- die Voreinstellung im
// Rückblick. Regionalfeste (rund 70 % aller Feste) nur auf Wunsch.
const KRANZFESTE = new Set(["eidgenoessisch", "berg", "teilverband", "kantonal"]);

export default function Feste() {
  const [events, setEvents] = useState<EventsArtifact | null>(null);
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);

  useEffect(() => {
    Promise.all([ladeEvents(), ladeModel(), ladeRatings(), ladeSchwinger()]).then(
      ([e, m, r, s]) => {
        setEvents(e);
        setModel(m);
        setRatings(r);
        setSchwinger(s);
      }
    );
  }, []);

  const byId = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );

  if (!events) return <p className="loading">Feste werden geladen …</p>;
  const kommende = events.kommende ?? [];

  return (
    <div>
      <h1>Feste</h1>
      <h2 style={{ marginTop: "0.5rem" }}>Bevorstehend</h2>
      <p className="subtitle">
        Pro veröffentlichter Paarung Prognose und informative Quote. Quoten sind{" "}
        <strong>kein Wettangebot</strong>.
      </p>

      {kommende.length === 0 ? (
        <div className="panel">
          <p>
            Für die nächsten {HORIZONT_TAGE} Tage ist derzeit kein Fest erfasst. Ausserhalb
            der Saison (Ende Oktober bis März) ist das der Normalfall — mitten in der Saison
            ein Hinweis darauf, dass die Fest-Beschaffung nicht durchgelaufen ist.
          </p>
          <p className="muted small">
            Unabhängig davon lässt sich jede Paarung direkt über die{" "}
            <a href="/" style={{ color: "var(--accent-2)" }}>
              Paar-Prognose
            </a>{" "}
            durchspielen — dieselbe Rechnung, dieselben Quoten, frei wählbare Schwinger.
          </p>
        </div>
      ) : (
        <>
          <div className="card-list">
            {kommende.map((fest) => (
              <FestCard
                key={fest.id}
                fest={fest}
                model={model}
                ratings={ratings}
                byId={byId}
              />
            ))}
          </div>
          {/* Solange KEIN Fest eine Startliste hat, steht hier sonst nur eine
              Liste von Terminen ohne eine einzige Zahl. Der Verweis auf die
              Paar-Prognose ist dann das einzige, was die Seite noch anbieten
              kann -- bisher erschien er nur, wenn gar kein Fest erfasst war. */}
          {kommende.every((f) => !(f.paarungen && f.paarungen.length > 0)) && (
            <p className="muted small" style={{ marginTop: "1rem" }}>
              Noch kein Fest hat eine Startliste veröffentlicht, darum steht hier keine
              Prognose. Jede Paarung lässt sich aber direkt über die{" "}
              <a href="/" style={{ color: "var(--accent-2)" }}>
                Paar-Prognose
              </a>{" "}
              durchspielen — dieselbe Rechnung, dieselben Quoten, frei wählbare Schwinger.
            </p>
          )}
        </>
      )}

      <Rueckblick feste={events.vergangene ?? []} checkSaisons={events.prognose_check_saisons ?? {}} />
    </div>
  );
}

/** Rückblick: vergangene Feste mit Festsieger, Kränzen und Teilnehmern aus
 *  den offiziellen Schlussranglisten (events.json, s. pipeline/export.py
 *  exportiere_events). Nach Saisonende ist das der eigentliche Inhalt der
 *  Seite -- vorher stand hier dann nur "kein Fest erfasst".
 *  Dazu der Prognose-Check (Roadmap F1): wie oft die Prognose je Fest lag,
 *  gerechnet mit dem Modell von vor der Saison (pipeline/prognose_check.py). */
function Rueckblick({
  feste,
  checkSaisons,
}: {
  feste: VergangenesFest[];
  checkSaisons: Record<string, PrognoseCheck>;
}) {
  const saisons = useMemo(
    () => [...new Set(feste.map((f) => f.datum.slice(0, 4)))].sort().reverse(),
    [feste]
  );
  const [saison, setSaison] = useState<string>("");
  const [mitRegional, setMitRegional] = useState(false);
  const aktiveSaison = saison || saisons[0] || "";

  const liste = useMemo(
    () =>
      feste
        .filter((f) => f.datum.startsWith(aktiveSaison))
        .filter((f) => mitRegional || KRANZFESTE.has(f.typ))
        .sort((a, b) => b.datum.localeCompare(a.datum) || a.name.localeCompare(b.name)),
    [feste, aktiveSaison, mitRegional]
  );
  const saisonCheck = checkSaisons[aktiveSaison];
  const mitCheck = liste.some((f) => f.prognose_check);
  // Trefferquote je Festtyp (nach Gängen gewichtet): Bergfeste und das
  // Eidgenössische sind deutlich schwerer -- dort treffen mehr Spitzen-
  // schwinger aufeinander, und es wird öfter gestellt.
  const jeTyp = useMemo(() => {
    const summe = new Map<string, { n: number; treffer: number }>();
    for (const f of feste) {
      if (!f.prognose_check || !f.datum.startsWith(aktiveSaison)) continue;
      const z = summe.get(f.typ) ?? { n: 0, treffer: 0 };
      z.n += f.prognose_check.n;
      z.treffer += f.prognose_check.treffer * f.prognose_check.n;
      summe.set(f.typ, z);
    }
    return [...summe.entries()]
      .map(([typ, z]) => ({ typ, n: z.n, treffer: z.treffer / z.n }))
      .sort((a, b) => b.treffer - a.treffer);
  }, [feste, aktiveSaison]);
  if (feste.length === 0) return null;
  const mitRangliste = feste.some((f) => f.sieger !== undefined);

  return (
    <>
      <h2>Rückblick</h2>
      <p className="subtitle" style={{ marginTop: 0 }}>
        Festsieger, vergebene Kränze und Teilnehmer laut offizieller Schlussrangliste. Ein
        Klick auf einen Sieger übernimmt ihn in die Paar-Prognose.
      </p>
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <div className="row" style={{ gap: "1rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <label className="field" htmlFor="saison">
              Saison
            </label>
            <select id="saison" value={aktiveSaison} onChange={(e) => setSaison(e.target.value)}>
              {saisons.map((j) => (
                <option key={j} value={j}>
                  {j}
                </option>
              ))}
            </select>
          </div>
          <label className="row" style={{ cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={mitRegional}
              onChange={(e) => setMitRegional(e.target.checked)}
              style={{ width: "auto" }}
            />
            <span className="small muted">Auch Regionalfeste (ohne Kranzvergabe)</span>
          </label>
        </div>
      </div>
      {saisonCheck && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <strong>Wie gut lag die Prognose {aktiveSaison}?</strong>
          <p style={{ margin: "0.4rem 0 0" }}>
            In <strong>{prozent(saisonCheck.treffer)}</strong> der {zahl(saisonCheck.n)} Gänge an{" "}
            {zahl(saisonCheck.n_feste ?? 0)} Festen trat der wahrscheinlichste Ausgang ein
            {saisonCheck.treffer_elo !== null && <> (reine Elo-Prognose: {prozent(saisonCheck.treffer_elo)})</>}.
            Dem tatsächlichen Ausgang gab das Modell im Schnitt{" "}
            <strong>{prozent(saisonCheck.p_eingetreten)}</strong>. Die Gestellt-Chance lag im Schnitt
            bei {prozent(saisonCheck.gestellt_vorhergesagt)}, gestellt wurde in{" "}
            {prozent(saisonCheck.gestellt_eingetreten)} der Gänge.
          </p>
          {jeTyp.length > 1 && (
            <p className="small" style={{ margin: "0.4rem 0 0" }}>
              Nach Festtyp:{" "}
              {jeTyp.map((t, i) => (
                <span key={t.typ} title={`${zahl(t.n)} Gänge`}>
                  {i > 0 && " · "}
                  {festtypName(t.typ)} {prozent(t.treffer)}
                </span>
              ))}
            </p>
          )}
          <p className="muted small" style={{ margin: "0.4rem 0 0" }}>
            Gerechnet mit dem Modell, das vor Saisonbeginn galt, und dem Stand jedes Schwingers vor
            dem jeweiligen Fest — also ohne Kenntnis der Ergebnisse. Ein Gestellter ist fast nie
            der wahrscheinlichste Ausgang, darum sagt die zweite Zahl mehr als die Trefferquote.
          </p>
        </div>
      )}
      {!saisonCheck && Object.keys(checkSaisons).length > 0 && (
        <p className="muted small" style={{ margin: "0 0 1rem" }}>
          Für {aktiveSaison} gibt es keinen Prognose-Check: davor lag noch keine eingeschwungene
          Saison, aus der ein Modell hätte lernen können (ausgewertet:{" "}
          {Object.keys(checkSaisons).join(", ")}).
        </p>
      )}
      <div className="panel tabelle-wrap" style={{ padding: 0 }}>
        <table style={{ minWidth: 560 }}>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Fest</th>
              <th>Festsieger</th>
              {mitRangliste && <th title="Vergebene Kränze / Teilnehmer">Kränze</th>}
              {mitCheck && (
                <th title="Anteil Gänge, bei denen der wahrscheinlichste Ausgang eintrat (Modell von vor der Saison), darunter die reine Elo-Prognose">
                  Prognose
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {liste.map((f) => (
              <tr key={f.id}>
                <td className="muted" style={{ whiteSpace: "nowrap" }}>
                  {datumKurz(f.datum)}
                </td>
                <td>
                  {f.name}{" "}
                  <span className="badge" style={{ marginLeft: 4 }}>
                    {festtypName(f.typ)}
                  </span>
                </td>
                <td>
                  {f.sieger && f.sieger.length > 0 ? (
                    f.sieger.map((s, i) => (
                      <span key={s.id}>
                        {i > 0 && " · "}
                        <Link href={`/?a=${encodeURIComponent(s.id)}`} style={{ color: "var(--text)" }}>
                          {s.name}
                        </Link>
                      </span>
                    ))
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                {mitRangliste && (
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>
                    {f.n_teilnehmer
                      ? `${f.n_kraenze ? zahl(f.n_kraenze) : "0"} / ${zahl(f.n_teilnehmer)}`
                      : "—"}
                  </td>
                )}
                {mitCheck && (
                  <td style={{ whiteSpace: "nowrap" }}>
                    {f.prognose_check ? (
                      <span
                        title={`${zahl(f.prognose_check.n)} Gänge · dem tatsächlichen Ausgang im Schnitt ${prozent(
                          f.prognose_check.p_eingetreten
                        )} gegeben · Gestellt-Chance im Schnitt ${prozent(
                          f.prognose_check.gestellt_vorhergesagt
                        )}, gestellt in ${prozent(f.prognose_check.gestellt_eingetreten)}`}
                      >
                        {prozent(f.prognose_check.treffer)}
                        <span className="muted small" style={{ display: "block" }}>
                          {f.prognose_check.treffer_elo !== null
                            ? `Elo ${prozent(f.prognose_check.treffer_elo)} · `
                            : ""}
                          {zahl(f.prognose_check.n)} Gänge
                        </span>
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {liste.length === 0 && (
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          Keine Feste für diese Auswahl.
        </p>
      )}
    </>
  );
}

function FestCard({
  fest,
  model,
  ratings,
  byId,
}: {
  fest: KommendesFest;
  model: ModelArtifact | null;
  ratings: RatingsArtifact | null;
  byId: Record<string, Schwinger>;
}) {
  const hatPaarungen = fest.paarungen && fest.paarungen.length > 0;
  return (
    <div className="fest-card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h3>{fest.name}</h3>
          <span className="muted small">
            {datumKurz(fest.datum)}
            {fest.ort ? ` · ${fest.ort}` : ""}
          </span>
        </div>
        <span className="badge">{festtypName(fest.typ)}</span>
      </div>

      {/* Ohne veröffentlichte Startliste wird NICHT prognostiziert. Vorher stand
          hier eine "hypothetische Spitzenpaarung" aus den zwei stärksten aktiven
          Schwingern des startberechtigten Teilverbands. Das war frei erfunden:
          die Rangfolge hängt nur am Teilverband, nicht am Fest, also erschien an
          allen drei Berner Festen dieselbe Paarung Staudenmann vs. Moser, an
          allen vier Innerschweizer Bissig vs. Bieri — und am "Clubschwingen
          Schwingclub Flawil" traten Staudenmann und Orlik an. An einem
          Regionalfest starten Spitzenschwinger in aller Regel gar nicht. Wer
          antritt, weiss erst die Startliste; bis dahin gibt es hier nichts zu
          rechnen. */}
      {!hatPaarungen && (
        <p className="muted small" style={{ marginTop: "0.75rem" }}>
          <span className="badge" style={{ marginRight: 6 }}>
            keine Startliste
          </span>
          {(() => {
            const tv = kreisFuerFest(fest);
            return tv
              ? `Startberechtigt sind fast ausschliesslich Schwinger des Teilverbands ${teilverbandName(
                  tv
                )}. Wer antritt, gibt erst die Startliste her — bis dahin keine Prognose.`
              : "Offenes Feld: an diesem Fest können Schwinger aus allen Teilverbänden starten. Wer antritt, gibt erst die Startliste her — bis dahin keine Prognose.";
          })()}
        </p>
      )}

      {hatPaarungen && model && ratings && (
        <div className="tabelle-wrap" style={{ marginTop: "0.85rem" }}>
          <table style={{ minWidth: 480 }}>
            <thead>
              <tr>
                <th>Paarung</th>
                <th>Sieg A</th>
                <th>Gestellt</th>
                <th>Sieg B</th>
              </tr>
            </thead>
            <tbody>
              {fest.paarungen!.map((pg, i) => (
                <PaarungZeile
                  key={`${pg.a_id}|${pg.b_id}|${i}`}
                  a={byId[pg.a_id]}
                  b={byId[pg.b_id]}
                  ratings={ratings}
                  model={model}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Eine Paarungszeile mit Prognose und informativer Quote.
 *
 *  Lädt die Kopf-an-Kopf-Historie nach, bevor sie rechnet. Ohne das ging die
 *  Seite von "noch nie gegeneinander" aus und wich für dieselbe Paarung von
 *  der Prognose-Seite ab (Staudenmann vs. Moser: 55 % statt 66 %) — bei neun
 *  gemeinsamen Gängen ist das der zweitstärkste Faktor im Modell. Bis die
 *  Historie da ist, wird mit 0 gerechnet; der Wert korrigiert sich selbst. */
function PaarungZeile({
  a,
  b,
  ratings,
  model,
}: {
  a?: Schwinger;
  b?: Schwinger;
  ratings: RatingsArtifact;
  model: ModelArtifact;
}) {
  const [paar, setPaar] = useState(KEINE_HISTORIE);
  const aId = a?.id;
  const bId = b?.id;
  useEffect(() => {
    if (!aId || !bId) return;
    let abgebrochen = false;
    ladeKopfAnKopf(aId, bId)
      .then((treffer) => {
        if (!abgebrochen) setPaar(paarHistorie(treffer));
      })
      .catch(() => {
        /* ohne Historie bleibt es bei 0 — dieselbe Annahme wie bisher */
      });
    return () => {
      abgebrochen = true;
    };
  }, [aId, bId]);

  if (!a || !b) return null;
  const ra = ratings.ratings[a.id] ?? { elo: ratings.elo_start, n_gaenge: 0 };
  const rb = ratings.ratings[b.id] ?? { elo: ratings.elo_start, n_gaenge: 0 };
  const pr = prognostiziere(model, a, b, ra.elo, rb.elo, ra.n_gaenge, rb.n_gaenge, paar);
  const zelle = (v: number) => (
    <>
      {(v * 100).toFixed(0)}%
      <span className="muted small"> · Quote {(1 / Math.max(v, 1e-6)).toFixed(2)}</span>
    </>
  );
  return (
    <tr>
      <td>
        {a.name} <span className="muted">vs</span> {b.name}
      </td>
      <td>{zelle(pr.p.sieg_a)}</td>
      <td>{zelle(pr.p.gestellt)}</td>
      <td>{zelle(pr.p.sieg_b)}</td>
    </tr>
  );
}

/** Teilnehmerkreis eines Fests: was die Pipeline ermittelt hat, sonst das
 *  Namensmuster. `teilverband: null` aus der Pipeline heisst ausdrücklich
 *  "offenes Feld" und darf NICHT auf das Namensmuster zurückfallen. */
function kreisFuerFest(fest: KommendesFest): string | null {
  if ("teilverband" in fest) return fest.teilverband ?? null;
  return teilverbandFuerFest(fest.name, fest.typ);
}
