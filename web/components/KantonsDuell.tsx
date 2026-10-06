"use client";

// Kantönligeist-Duell (Seite "Karte"): zwei Kantone, Berner Gauverbände oder
// Teilverbände schicken je ihre sechs stärksten aktiven Schwinger in einen
// Mannschaftskampf -- Nr. 1 gegen Nr. 1 usw. Die Chancen je Paarung rechnet
// dasselbe Modell wie die Paar-Prognose (mit Kopf-an-Kopf-Historie), die
// Siegchance der Mannschaft folgt exakt daraus (lib/kantonsduell.ts).

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ModelArtifact, PaarHistorie, Schwinger } from "@/lib/types";
import { KANTONALVERBAND_ZU_KANTON, kantonalverbandVon } from "@/lib/kantone";
import {
  MANNSCHAFT,
  auslosen,
  duellAusgang,
  gangSatz,
  punkteText,
  staerkste,
  type Ausgang,
  type Kaempfer,
  type Ratings,
} from "@/lib/kantonsduell";
import { paarWahrscheinlichkeiten } from "@/lib/inference";
import { KEINE_HISTORIE, ladeKopfAnKopf, paarHistorie } from "@/lib/kopfAnKopf";
import { BERNER_GAUVERBAENDE, TEILVERBAENDE, kantonalverbandName, prozent, teilverbandName } from "@/lib/labels";
import { verbandVon } from "@/lib/teilverband";

interface Mannschaft {
  key: string;
  label: string;
  gruppe: string;
  mitglieder: Schwinger[];
  /** Ø Elo der sechs Stärksten -- für einen spannenden Gegnervorschlag. */
  staerke: number;
  /** Häufigster Teilverband der Mitglieder (für Duelle über Regionen hinweg). */
  teilverband: string | null;
}

const BERN = BERNER_GAUVERBAENDE as readonly string[];

type Roh = Omit<Mannschaft, "staerke" | "teilverband">;

/** Alle Mannschaften, die sechs Schwinger stellen können. */
export function mannschaften(schwinger: Schwinger[], ratings: Ratings): Mannschaft[] {
  const aus: Roh[] = [];
  for (const v of Object.keys(KANTONALVERBAND_ZU_KANTON)) {
    aus.push({
      key: `v:${v}`,
      label: kantonalverbandName(v),
      gruppe: "Kantone und Berner Gauverbände",
      mitglieder: schwinger.filter((s) => kantonalverbandVon(s) === v),
    });
  }
  aus.push({
    key: "k:Bern",
    label: "Kanton Bern (alle Gauverbände)",
    gruppe: "Kantone und Berner Gauverbände",
    mitglieder: schwinger.filter((s) => BERN.includes(kantonalverbandVon(s) ?? "")),
  });
  for (const tv of TEILVERBAENDE) {
    aus.push({
      key: `t:${tv}`,
      label: teilverbandName(tv),
      gruppe: "Teilverbände",
      mitglieder: schwinger.filter((s) => {
        const { verband, geschaetzt } = verbandVon(s);
        return verband === tv && !geschaetzt;
      }),
    });
  }
  return aus
    .map((m) => {
      const team = staerkste(m.mitglieder, ratings);
      const tv = new Map<string, number>();
      for (const s of m.mitglieder) {
        const v = verbandVon(s).verband;
        if (v) tv.set(v, (tv.get(v) ?? 0) + 1);
      }
      return {
        ...m,
        staerke: team.length === MANNSCHAFT ? team.reduce((a, k) => a + k.elo, 0) / MANNSCHAFT : 0,
        teilverband: [...tv.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null,
        voll: team.length === MANNSCHAFT,
      };
    })
    .filter((m) => m.voll)
    .map(({ voll: _voll, ...m }) => m)
    .sort((a, b) => a.gruppe.localeCompare(b.gruppe) || a.label.localeCompare(b.label));
}

function art(key: string): string {
  return key.startsWith("t:") ? "t" : "v";
}

/** Ein spannender Gegner: gleich stark (Ø Elo der sechs Besten), gleiche Art
 *  (Verband bzw. Teilverband), möglichst aus einem anderen Teilverband und
 *  ohne gemeinsame Schwinger. */
export function rivale(key: string, alle: Mannschaft[]): string {
  const ich = alle.find((m) => m.key === key);
  if (!ich) return alle[0]?.key ?? key;
  const ids = new Set(ich.mitglieder.map((s) => s.id));
  const kandidaten = alle.filter(
    (m) => m.key !== key && art(m.key) === art(key) && !m.mitglieder.some((s) => ids.has(s.id))
  );
  const fremd = kandidaten.filter((m) => m.teilverband !== ich.teilverband);
  const auswahl = fremd.length ? fremd : kandidaten;
  return (
    auswahl.sort((a, b) => Math.abs(a.staerke - ich.staerke) - Math.abs(b.staerke - ich.staerke))[0]
      ?.key ?? key
  );
}

function nachname(s: Schwinger): string {
  return s.name.split(" (")[0].split(" ").slice(-1)[0];
}

function prognoseLink(a: string, b: string): string {
  return `/?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
}

export function KantonsDuell({
  schwinger,
  ratings,
  model,
  start,
}: {
  schwinger: Schwinger[];
  ratings: Ratings;
  model: ModelArtifact;
  /** Mannschaft A aus dem Steckbrief (Schlüssel "v:<Verband>"); wechselt bei jedem Klick. */
  start: { key: string; nr: number } | null;
}) {
  const alle = useMemo(() => mannschaften(schwinger, ratings), [schwinger, ratings]);
  const vorhanden = useMemo(() => new Set(alle.map((m) => m.key)), [alle]);
  // Ohne Auswahl: die stärkste Kantons-Mannschaft gegen ihren Rivalen.
  const [keyA, setKeyA] = useState(() => {
    const v = alle.filter((m) => art(m.key) === "v" && m.key !== "k:Bern");
    return v.sort((a, b) => b.staerke - a.staerke)[0]?.key ?? "k:Bern";
  });
  const [keyB, setKeyB] = useState(() => rivale(keyA, alle));
  const [historie, setHistorie] = useState<Record<string, PaarHistorie>>({});
  const [wurf, setWurf] = useState<{ ausgaenge: Ausgang[]; saetze: string[] } | null>(null);

  useEffect(() => {
    if (start && vorhanden.has(start.key)) {
      setKeyA(start.key);
      setKeyB(rivale(start.key, alle));
      setWurf(null);
    }
  }, [start, vorhanden, alle]);

  const mA = alle.find((m) => m.key === keyA);
  const mB = alle.find((m) => m.key === keyB);
  const teamA: Kaempfer[] = useMemo(() => (mA ? staerkste(mA.mitglieder, ratings) : []), [mA, ratings]);
  const teamB: Kaempfer[] = useMemo(() => (mB ? staerkste(mB.mitglieder, ratings) : []), [mB, ratings]);
  const ueberschneidung = teamA.some((a) => mB?.mitglieder.some((s) => s.id === a.s.id))
    || teamB.some((b) => mA?.mitglieder.some((s) => s.id === b.s.id));

  // Kopf-an-Kopf je Paarung nachladen; bis dahin ohne Historie.
  useEffect(() => {
    let abbruch = false;
    teamA.forEach((a, i) => {
      const b = teamB[i];
      if (!b) return;
      const k = `${a.s.id}|${b.s.id}`;
      if (historie[k]) return;
      ladeKopfAnKopf(a.s.id, b.s.id)
        .then((t) => !abbruch && setHistorie((h) => ({ ...h, [k]: paarHistorie(t) })))
        .catch(() => !abbruch && setHistorie((h) => ({ ...h, [k]: KEINE_HISTORIE })));
    });
    return () => {
      abbruch = true;
    };
    // historie absichtlich nicht als Abhängigkeit: nur neue Paarungen laden.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamA, teamB]);

  const p = useMemo(
    () =>
      teamA.map((a, i) => {
        const b = teamB[i];
        return paarWahrscheinlichkeiten(
          model, a.s, b.s, a.elo, b.elo, a.n, b.n, historie[`${a.s.id}|${b.s.id}`] ?? KEINE_HISTORIE
        );
      }),
    [teamA, teamB, model, historie]
  );
  const ausgang = useMemo(() => (p.length === MANNSCHAFT ? duellAusgang(p) : null), [p]);

  const wechsle = (setter: (k: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    setter(e.target.value);
    setWurf(null);
  };
  const zufallsDuell = () => {
    const keys = alle.filter((m) => m.key.startsWith("v:")).map((m) => m.key);
    const a = keys[Math.floor(Math.random() * keys.length)];
    let b = a;
    while (b === a) b = keys[Math.floor(Math.random() * keys.length)];
    setKeyA(a);
    setKeyB(b);
    setWurf(null);
  };
  const ausschwingen = () => {
    const ausgaenge = auslosen(p);
    setWurf({
      ausgaenge,
      saetze: ausgaenge.map((g, i) => gangSatz(nachname(teamA[i].s), nachname(teamB[i].s), g)),
    });
  };

  const auswahl = (wert: string, onChange: ReturnType<typeof wechsle>, label: string) => (
    <select aria-label={label} value={wert} onChange={onChange} className="duell-auswahl">
      {["Kantone und Berner Gauverbände", "Teilverbände"].map((g) => (
        <optgroup key={g} label={g}>
          {alle
            .filter((m) => m.gruppe === g)
            .map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
        </optgroup>
      ))}
    </select>
  );

  const punkteWurf = wurf
    ? wurf.ausgaenge.reduce((a, g) => a + (g === "A" ? 1 : g === "G" ? 0.5 : 0), 0)
    : 0;

  return (
    <div className="panel duell">
      <div className="duell-kopf">
        {auswahl(keyA, wechsle(setKeyA), "Mannschaft A")}
        <span className="duell-gegen" aria-hidden="true">
          ⚔️
        </span>
        {auswahl(keyB, wechsle(setKeyB), "Mannschaft B")}
      </div>
      <div className="row" style={{ gap: "0.5rem", marginTop: "0.6rem" }}>
        <button type="button" className="teilen-btn" onClick={zufallsDuell}>
          🎲 Zufälliges Duell
        </button>
      </div>

      {keyA === keyB || ueberschneidung ? (
        <p className="muted" style={{ marginTop: "1rem" }}>
          Diese beiden Mannschaften überschneiden sich — wähle zwei, die verschiedene Schwinger
          stellen.
        </p>
      ) : (
        ausgang && mA && mB && (
          <>
            <div className="duell-stand">
              <div>
                <div className="duell-team">{mA.label}</div>
                <div className="duell-punkte">{ausgang.punkteA.toFixed(1)}</div>
              </div>
              <div className="muted small">erwarteter Schlussstand</div>
              <div style={{ textAlign: "right" }}>
                <div className="duell-team">{mB.label}</div>
                <div className="duell-punkte">{ausgang.punkteB.toFixed(1)}</div>
              </div>
            </div>
            <div className="probbar" role="img" aria-label="Siegchance der Mannschaften">
              <div className="seg-a" style={{ flexBasis: `${ausgang.siegA * 100}%` }}>
                {ausgang.siegA >= 0.12 && prozent(ausgang.siegA)}
              </div>
              <div className="seg-draw" style={{ flexBasis: `${ausgang.unentschieden * 100}%` }}>
                {ausgang.unentschieden >= 0.12 && prozent(ausgang.unentschieden)}
              </div>
              <div className="seg-b" style={{ flexBasis: `${ausgang.siegB * 100}%` }}>
                {ausgang.siegB >= 0.12 && prozent(ausgang.siegB)}
              </div>
            </div>
            <div className="duell-legende small muted">
              <span>{mA.label} gewinnt</span>
              <span>unentschieden</span>
              <span>{mB.label} gewinnt</span>
            </div>

            <ol className="duell-paarungen">
              {teamA.map((a, i) => {
                const b = teamB[i];
                const [pa, pg, pb] = p[i];
                const g = wurf?.ausgaenge[i];
                return (
                  <li key={`${a.s.id}-${b.s.id}`} className={g ? `duell-gang duell-gang-${g}` : "duell-gang"}>
                    <span className="duell-name">
                      {a.s.name} <span className="muted small">{Math.round(a.elo)}</span>
                    </span>
                    <Link href={prognoseLink(a.s.id, b.s.id)} className="duell-mini" title="Zur Paar-Prognose">
                      <span className="seg-a" style={{ flexBasis: `${pa * 100}%` }} />
                      <span className="seg-draw" style={{ flexBasis: `${pg * 100}%` }} />
                      <span className="seg-b" style={{ flexBasis: `${pb * 100}%` }} />
                    </Link>
                    <span className="duell-name duell-name-b">
                      <span className="muted small">{Math.round(b.elo)}</span> {b.s.name}
                    </span>
                    {wurf && <span className="duell-satz small">{wurf.saetze[i]}</span>}
                  </li>
                );
              })}
            </ol>

            <div className="row" style={{ gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
              <button type="button" className="teilen-btn duell-los" onClick={ausschwingen}>
                {wurf ? "Nochmals ausschwingen" : "Jetzt ausschwingen!"}
              </button>
              {wurf && (
                <strong>
                  Endstand {punkteText(punkteWurf)} : {punkteText(MANNSCHAFT - punkteWurf)} —{" "}
                  {punkteWurf > MANNSCHAFT / 2
                    ? `${mA.label} holt sich den Kantönligeist!`
                    : punkteWurf < MANNSCHAFT / 2
                      ? `${mB.label} holt sich den Kantönligeist!`
                      : "unentschieden, die Ehre bleibt geteilt."}
                </strong>
              )}
            </div>
            <p className="muted small" style={{ marginBottom: 0 }}>
              Je die sechs stärksten aktiven Schwinger nach Elo (mindestens 10 Gänge), Nr. 1 gegen
              Nr. 1. Sieg 1 Punkt, Gestellt ½ für beide. Die Chance jeder Paarung rechnet dasselbe
              Modell wie die Paar-Prognose, mit bisherigen Duellen; ein Klick auf den Balken öffnet
              sie. „Ausschwingen" lost einen möglichen Ausgang nach diesen Chancen aus — zum Spass,
              ein solcher Mannschaftskampf findet so nicht statt.
            </p>
          </>
        )
      )}
    </div>
  );
}
