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
              ? `Startberechtigt sind fast ausschliesslich Schwinger des Teilverbands ${
                  TV_LABEL[tv] ?? tv
                }. Wer antritt, gibt erst die Startliste her — bis dahin keine Prognose.`
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

/** Teilnehmerkreis eines Fests: was die Pipeline ermittelt hat, sonst das
 *  Namensmuster. `teilverband: null` aus der Pipeline heisst ausdrücklich
 *  "offenes Feld" und darf NICHT auf das Namensmuster zurückfallen. */
function kreisFuerFest(fest: KommendesFest): string | null {
  if ("teilverband" in fest) return fest.teilverband ?? null;
  return teilverbandFuerFest(fest.name, fest.typ);
}
