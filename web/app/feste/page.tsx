"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import { ladeKopfAnKopf, kopfAnKopfVorteilA } from "@/lib/kopfAnKopf";
import { teilverbandFuerFest } from "@/lib/teilverband";
import type {
  EventsArtifact,
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
  KommendesFest,
} from "@/lib/types";

// Spiegelt pipeline/scrape/agenda.HORIZONT_TAGE — wie weit die Vorschau reicht.
const HORIZONT_TAGE = 60;

// "Suedwestschweiz" ist der Datenwert (ASCII-Schlüssel), nicht die Schreibweise
// für die Anzeige.
const TV_LABEL: Record<string, string> = {
  Suedwestschweiz: "Südwestschweiz",
};

const TYP_LABEL: Record<string, string> = {
  eidgenoessisch: "Eidgenössisches",
  berg: "Bergfest",
  kantonal: "Kantonales",
  teilverband: "Teilverband",
  regional: "Regional",
};

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
      <h1>Bevorstehende Feste</h1>
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
      )}
    </div>
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
  const favoriten =
    !hatPaarungen && model && ratings ? baueFavoriten(fest, model, ratings, byId) : [];
  return (
    <div className="fest-card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h3>{fest.name}</h3>
          <span className="muted small">
            {fest.datum}
            {fest.ort ? ` · ${fest.ort}` : ""}
          </span>
        </div>
        <span className="badge">{TYP_LABEL[fest.typ] ?? fest.typ}</span>
      </div>

      {!hatPaarungen && (
        <>
          <p className="muted small" style={{ marginTop: "0.75rem" }}>
            <span className="badge" style={{ marginRight: 6 }}>
              keine Startliste
            </span>
            {(() => {
              const tv = kreisFuerFest(fest);
              return tv
                ? `Stärkste aktive Schwinger des Teilverbands ${TV_LABEL[tv] ?? tv} — an diesem Fest startet fast nur, wer ihm angehört. Wer tatsächlich antritt, gibt erst die Startliste her.`
                : "Offenes Feld: an diesem Fest können Schwinger aus allen Teilverbänden starten. Gezeigt sind die stärksten aktiven — nicht die gemeldeten.";
            })()}
          </p>
          {favoriten.length >= 2 && model && ratings && (
            <SpitzenpaarungVorschau
              a={byId[favoriten[0].id]}
              b={byId[favoriten[1].id]}
              ratings={ratings}
              model={model}
            />
          )}
        </>
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
  const [h2h, setH2h] = useState(0);
  const aId = a?.id;
  const bId = b?.id;
  useEffect(() => {
    if (!aId || !bId) return;
    let abgebrochen = false;
    ladeKopfAnKopf(aId, bId)
      .then((treffer) => {
        if (!abgebrochen) setH2h(kopfAnKopfVorteilA(treffer));
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
  const pr = prognostiziere(model, a, b, ra.elo, rb.elo, ra.n_gaenge, rb.n_gaenge, h2h);
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

/** Prognose + Quote für die stärkste denkbare Paarung, solange das Fest noch
 *  keine offiziellen Paarungen ausweist. Ausdrücklich hypothetisch beschriftet:
 *  ob sich die beiden treffen, entscheidet erst die Einteilung am Fest. */
function SpitzenpaarungVorschau({
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
  if (!a || !b) return null;
  return (
    <div className="tabelle-wrap" style={{ marginTop: "0.85rem" }}>
      <p className="muted small" style={{ margin: "0 0 0.4rem" }}>
        <span className="badge" style={{ marginRight: 6 }}>
          hypothetisch
        </span>
        Mögliche Spitzenpaarung der zwei Topfavoriten — ob sie sich treffen, entscheidet die
        Einteilung am Fest.
      </p>
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
          <PaarungZeile a={a} b={b} ratings={ratings} model={model} />
        </tbody>
      </table>
    </div>
  );
}

/** Teilnehmerkreis eines Fests: was die Pipeline ermittelt hat, sonst das
 *  Namensmuster. `teilverband: null` aus der Pipeline heisst ausdrücklich
 *  "offenes Feld" und darf NICHT auf das Namensmuster zurückfallen. */
function kreisFuerFest(fest: KommendesFest): string | null {
  if ("teilverband" in fest) return fest.teilverband ?? null;
  return teilverbandFuerFest(fest.name, fest.typ);
}

function baueFavoriten(
  fest: KommendesFest,
  model: ModelArtifact,
  ratings: RatingsArtifact,
  byId: Record<string, Schwinger>
) {
  const ord = model.config.kranzstatus_ordinal;
  // An Teilverbands- und Kantonalfesten startet fast nur, wer dem Verband
  // angehört (79–97 %, s. lib/teilverband.ts). Ohne diesen Filter zeigte die
  // Liste an JEDEM Fest dieselben national stärksten Schwinger — an einem
  // Nordwestschweizer Fest also sechs Namen, von denen keiner antritt.
  // Ein Fest-Bonus (berg/eidgenössisch) stand hier zusätzlich im Code, war
  // aber wirkungslos: für alle gleich, kürzt sich in der Rangfolge weg.
  // Bevorzugt der von der Pipeline aus der Vorausgabe bestimmte Kreis
  // (deckt auch Regionalfeste ab, deren Name nur einen Ort nennt). Das
  // Namensmuster greift nur bei Artefakten ohne dieses Feld.
  const teilverband = kreisFuerFest(fest);
  return Object.entries(ratings.ratings)
    .map(([id, r]) => {
      const s = byId[id];
      if (!s || !s.aktiv) return null;
      // Ohne erfassten Teilverband (Schwinger ohne Porträt) lässt sich die
      // Startberechtigung nicht beurteilen — dann lieber weglassen als raten.
      if (teilverband && s.teilverband !== teilverband) return null;
      const kranz = ord[s.kranzstatus] ?? 0;
      return { id, name: s.name, elo: r.elo, index: r.elo + kranz * 25 };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null)
    .sort((a, b) => b.index - a.index)
    .slice(0, 6);
}
