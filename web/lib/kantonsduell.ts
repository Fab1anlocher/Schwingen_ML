// Kantönligeist-Duell (Seite "Karte"): zwei Mannschaften schicken je ihre
// stärksten aktiven Schwinger ins Sägemehl, Nr. 1 gegen Nr. 1 usw. -- wie ein
// Mannschafts- oder Länderkampf. Jede Paarung rechnet das Prognosemodell
// (wie die Paar-Prognose, mit Kopf-an-Kopf-Historie); hier steht nur, was
// daraus folgt. Punkte: Sieg 1, Gestellt ½ für beide.

import type { Schwinger } from "./types";

export const MANNSCHAFT = 6;
/** Erst ab so vielen Gängen ist das Elo aussagekräftig (Kantonsmeister, Duell). */
export const MIN_GAENGE = 10;

export type Ratings = Record<string, { elo: number; n_gaenge: number }>;

export interface Kaempfer {
  s: Schwinger;
  elo: number;
  n: number;
}

/** Die stärksten aktiven Schwinger nach Elo (mindestens MIN_GAENGE Gänge). */
export function staerkste(kandidaten: Schwinger[], ratings: Ratings, anzahl = MANNSCHAFT): Kaempfer[] {
  return kandidaten
    .filter((s) => s.aktiv && (ratings[s.id]?.n_gaenge ?? 0) >= MIN_GAENGE)
    .map((s) => ({ s, elo: ratings[s.id].elo, n: ratings[s.id].n_gaenge }))
    .sort((a, b) => b.elo - a.elo || a.s.name.localeCompare(b.s.name))
    .slice(0, anzahl);
}

/** Verteilung der Punkte von A in halben Punkten (0 .. 2·Gänge) aus
 *  [Sieg A, Gestellt, Sieg B] je Gang -- exakt, ohne Simulation. */
export function punkteVerteilung(p: number[][]): number[] {
  let v = [1];
  for (const [pa, pg, pb] of p) {
    const neu = new Array(v.length + 2).fill(0);
    v.forEach((w, i) => {
      neu[i] += w * pb;
      neu[i + 1] += w * pg;
      neu[i + 2] += w * pa;
    });
    v = neu;
  }
  return v;
}

export interface DuellAusgang {
  siegA: number;
  unentschieden: number;
  siegB: number;
  /** Erwartete Punkte (Sieg 1, Gestellt ½). */
  punkteA: number;
  punkteB: number;
}

export function duellAusgang(p: number[][]): DuellAusgang {
  const v = punkteVerteilung(p);
  const mitte = p.length; // halbe Punkte bei Gleichstand
  let siegA = 0;
  let siegB = 0;
  let erwartet = 0;
  v.forEach((w, h) => {
    if (h > mitte) siegA += w;
    if (h < mitte) siegB += w;
    erwartet += (w * h) / 2;
  });
  return { siegA, unentschieden: v[mitte] ?? 0, siegB, punkteA: erwartet, punkteB: p.length - erwartet };
}

export type Ausgang = "A" | "G" | "B";

/** Einen Ausgang je Gang auslosen (zufall: Zahlen in [0, 1)). */
export function auslosen(p: number[][], zufall: () => number = Math.random): Ausgang[] {
  return p.map(([pa, pg]) => {
    const z = zufall();
    return z < pa ? "A" : z < pa + pg ? "G" : "B";
  });
}

const SIEG = [
  "{s} legt {v} ins Sägemehl",
  "{s} bodigt {v}",
  "{s} wirft {v} auf den Rücken",
  "{s} setzt sich gegen {v} durch",
  "{s} lässt {v} keine Chance",
];
const GESTELLT = [
  "{a} und {b} stellen – keiner gibt nach",
  "Gestellt: {a} und {b} schenken sich nichts",
  "{a} gegen {b}: nach Ablauf der Zeit gestellt",
];

/** Ein Satz zum ausgelosten Gang ("Orlik legt Staudenmann ins Sägemehl"). */
export function gangSatz(a: string, b: string, ausgang: Ausgang, zufall: () => number = Math.random): string {
  const wahl = (liste: string[]) => liste[Math.floor(zufall() * liste.length)];
  if (ausgang === "G") return wahl(GESTELLT).replace("{a}", a).replace("{b}", b);
  const [s, v] = ausgang === "A" ? [a, b] : [b, a];
  return wahl(SIEG).replace("{s}", s).replace("{v}", v);
}

/** Punkte als Text mit halben Punkten: 3.5 -> "3½". */
export function punkteText(punkte: number): string {
  const ganz = Math.floor(punkte + 1e-9);
  return Math.abs(punkte - ganz - 0.5) < 1e-9 ? `${ganz === 0 ? "" : ganz}½` : String(Math.round(punkte));
}
