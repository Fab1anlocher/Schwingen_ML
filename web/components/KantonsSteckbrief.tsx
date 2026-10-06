"use client";

// Kantons-Steckbrief (Seite "Karte"): wer ist der Beste aus meinem Kanton?
// Kantonsmeister (höchstes Elo unter den aktiven Schwingern), die Top 5 und
// ein paar Fun Facts. Physis und Schwünge gibt es nur aus den Porträts -- die
// Fakten sagen darum immer "mit Porträt".

import Link from "next/link";
import { useMemo } from "react";
import type { Schwinger } from "@/lib/types";
import { flaechenFuer, kantonalverbandVon, verbaendeAuf } from "@/lib/kantone";
import { MIN_GAENGE, staerkste, type Ratings } from "@/lib/kantonsduell";
import {
  BERNER_GAUVERBAENDE,
  kantonName,
  kantonalverbandName,
  kranzName,
  schwungName,
} from "@/lib/labels";
import { kranzstatusVon } from "@/lib/teilverband";

const MIT_KRANZ = new Set(["kranzer", "eidgenosse", "koenig"]);

function prognoseLink(a: string, b: string): string {
  return `/?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
}

export function KantonsSteckbrief({
  flaeche,
  schwinger,
  ratings,
  saison,
  onDuell,
}: {
  flaeche: string;
  schwinger: Schwinger[];
  ratings: Ratings;
  saison: string;
  onDuell: (verband: string) => void;
}) {
  const verbaende = useMemo(() => verbaendeAuf(flaeche), [flaeche]);
  const mitglieder = useMemo(
    () => schwinger.filter((s) => verbaende.includes(kantonalverbandVon(s) ?? "")),
    [schwinger, verbaende]
  );
  const top = useMemo(() => staerkste(mitglieder, ratings, 5), [mitglieder, ratings]);

  const fakten = useMemo(() => {
    const aktiv = mitglieder.filter((s) => s.aktiv);
    const schwuenge = new Map<string, number>();
    let mitSchwung = 0;
    for (const s of mitglieder) {
      if (!s.bevorzugte_schwuenge?.length) continue;
      mitSchwung++;
      for (const n of new Set(s.bevorzugte_schwuenge.map(schwungName))) {
        schwuenge.set(n, (schwuenge.get(n) ?? 0) + 1);
      }
    }
    const lieblings = [...schwuenge.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
    const max = (werte: Schwinger[], feld: (s: Schwinger) => number | null) =>
      werte
        .filter((s) => feld(s) !== null)
        .sort((a, b) => feld(b)! - feld(a)! || a.name.localeCompare(b.name))[0];
    const festsiege = mitglieder.flatMap((s) =>
      (s.festsiege ?? []).filter((f) => f.datum.startsWith(saison)).map(() => s)
    );
    const siegerZahl = new Map<string, { s: Schwinger; n: number }>();
    for (const s of festsiege) siegerZahl.set(s.id, { s, n: (siegerZahl.get(s.id)?.n ?? 0) + 1 });
    const bester = [...siegerZahl.values()].sort((a, b) => b.n - a.n || a.s.name.localeCompare(b.s.name))[0];
    return {
      lieblings: lieblings && mitSchwung >= 3 ? { name: lieblings[0], n: lieblings[1], von: mitSchwung } : null,
      schwerster: max(aktiv, (s) => s.gewicht_kg),
      groesster: max(aktiv, (s) => s.groesse_cm),
      juengsterKranzer: max(
        aktiv.filter((s) => MIT_KRANZ.has(kranzstatusVon(s))),
        (s) => s.jahrgang
      ),
      eidgenossen: aktiv.filter((s) => ["eidgenosse", "koenig"].includes(kranzstatusVon(s))).length,
      festsiege: festsiege.length,
      festsieger: bester,
      kraenze: mitglieder.reduce((a, s) => a + (s.kraenze ?? 0), 0),
    };
  }, [mitglieder, saison]);

  const meister = top[0];
  // Grosse Namen, die seit über einem Jahr keinen Gang mehr hatten (verletzt,
  // Pause, Rücktritt): stärker als der aktive Kantonsmeister, darum erwähnt.
  const pausiert = useMemo(
    () =>
      mitglieder
        .filter((s) => !s.aktiv && (ratings[s.id]?.n_gaenge ?? 0) >= MIN_GAENGE)
        .filter((s) => !meister || ratings[s.id].elo > meister.elo)
        .sort((a, b) => ratings[b.id].elo - ratings[a.id].elo)
        .slice(0, 2),
    [mitglieder, ratings, meister]
  );
  const bernerGau = (BERNER_GAUVERBAENDE as readonly string[]).includes(flaeche);
  const titel = bernerGau
    ? `${flaeche} (Kanton Bern)`
    : verbaende.length === 1 && flaechenFuer(verbaende[0]).length > 1
      ? `${kantonName(flaeche)} · Verband ${kantonalverbandName(verbaende[0])}`
      : kantonName(flaeche);

  if (mitglieder.length === 0) {
    return (
      <div className="panel">
        <h2 style={{ marginTop: 0 }}>{titel}</h2>
        <p className="muted">Hier sind keine Schwinger erfasst.</p>
      </div>
    );
  }

  return (
    <div className="panel steckbrief">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>{titel}</h2>
        <span className="muted small">
          {mitglieder.filter((s) => s.aktiv).length} aktive Schwinger
        </span>
      </div>

      {meister && (
        <div className="kantonsmeister">
          <span className="krone" aria-hidden="true">
            👑
          </span>
          <div>
            <div className="eyebrow">{bernerGau ? "Gauverbandsmeister" : "Kantonsmeister"} nach Elo</div>
            <strong className="kantonsmeister-name">{meister.s.name}</strong>
            <div className="muted small">
              Elo {Math.round(meister.elo)}
              {kranzName(kranzstatusVon(meister.s)) && ` · ${kranzName(kranzstatusVon(meister.s))}`}
              {meister.s.schwingklub && ` · ${meister.s.schwingklub}`}
            </div>
          </div>
        </div>
      )}

      {pausiert.length > 0 && (
        <p className="muted small" style={{ margin: "0.5rem 0 0" }}>
          Pausiert (seit über einem Jahr ohne Gang):{" "}
          {pausiert.map((s) => `${s.name} (Elo ${Math.round(ratings[s.id].elo)})`).join(", ")}
        </p>
      )}

      <div className="grid-2" style={{ marginTop: "0.8rem" }}>
        <div>
          <div className="eyebrow">Die stärksten fünf</div>
          <ol className="steckbrief-top">
            {top.map((k) => (
              <li key={k.s.id}>
                <span>{k.s.name}</span>
                <span className="muted small">{Math.round(k.elo)}</span>
              </li>
            ))}
          </ol>
          {top.length >= 2 && (
            <Link className="teilen-btn" href={prognoseLink(top[0].s.id, top[1].s.id)}>
              Kantonsfinal: {top[0].s.name.split(" ").slice(-1)[0]} gegen{" "}
              {top[1].s.name.split(" ").slice(-1)[0]} →
            </Link>
          )}
        </div>
        <div>
          <div className="eyebrow">Gut zu wissen</div>
          <ul className="steckbrief-fakten">
            {fakten.lieblings && (
              <li>
                Lieblingsschwung: <strong>{fakten.lieblings.name}</strong>{" "}
                <span className="muted small">
                  ({fakten.lieblings.n} von {fakten.lieblings.von} mit Porträt)
                </span>
              </li>
            )}
            {fakten.schwerster && (
              <li>
                Der Schwerste: <strong>{fakten.schwerster.name}</strong>{" "}
                <span className="muted small">{fakten.schwerster.gewicht_kg} kg</span>
              </li>
            )}
            {fakten.groesster && (
              <li>
                Der Grösste: <strong>{fakten.groesster.name}</strong>{" "}
                <span className="muted small">{fakten.groesster.groesse_cm} cm</span>
              </li>
            )}
            {fakten.juengsterKranzer && (
              <li>
                Jüngster Kranzer: <strong>{fakten.juengsterKranzer.name}</strong>{" "}
                <span className="muted small">Jg. {fakten.juengsterKranzer.jahrgang}</span>
              </li>
            )}
            <li>
              {fakten.eidgenossen === 0
                ? "Kein aktiver Eidgenosse"
                : `${fakten.eidgenossen} aktive${fakten.eidgenossen === 1 ? "r" : ""} Eidgenosse${fakten.eidgenossen === 1 ? "" : "n"}`}
              {" · "}
              {fakten.kraenze} Kränze seit 2023
            </li>
            <li>
              {fakten.festsiege === 0
                ? `Kein Festsieg ${saison}`
                : `${fakten.festsiege} Festsieg${fakten.festsiege === 1 ? "" : "e"} ${saison}`}
              {fakten.festsieger && fakten.festsiege > 0 && (
                <span className="muted small">
                  {" "}
                  (am meisten: {fakten.festsieger.s.name}, {fakten.festsieger.n})
                </span>
              )}
            </li>
          </ul>
          <p className="muted small" style={{ marginBottom: 0 }}>
            Schwerster, Grösster und Lieblingsschwung nur aus den Porträts von schlussgang.ch.
          </p>
        </div>
      </div>

      {verbaende.length > 0 && top.length >= 2 && (
        <button type="button" className="teilen-btn" style={{ marginTop: "0.9rem" }} onClick={() => onDuell(verbaende[0])}>
          ⚔️ Kantönligeist-Duell mit {kantonalverbandName(verbaende[0])} starten
        </button>
      )}
    </div>
  );
}
