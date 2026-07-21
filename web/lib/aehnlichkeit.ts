// Ähnlichkeit zweier Schwinger als erklärbare, gewichtete Distanz über
// Körperdaten, Kranzstatus, Verband/Klub und bevorzugte Schwünge.
// Bewusst KEIN gelerntes Modell — eine transparente Heuristik, passend zum
// Erklärbarkeits-Anspruch des Projekts (FR-3).

import type { Schwinger } from "./types";

const KRANZ_ORDINAL: Record<string, number> = {
  kein: 0,
  kranzer: 1,
  eidgenosse: 2,
  koenig: 3,
};

const GROESSE_SPANNE = 45; // ca. 160-205 cm
const GEWICHT_SPANNE = 80; // ca. 60-140 kg

function normDiff(a: number | null, b: number | null, spanne: number): number {
  if (a === null || b === null) return 0.5; // unbekannt -> neutral, weder ähnlich noch unähnlich
  return Math.min(1, Math.abs(a - b) / spanne);
}

function schwungOverlap(a: Schwinger, b: Schwinger): number {
  const sa = new Set(a.bevorzugte_schwuenge ?? []);
  const sb = new Set(b.bevorzugte_schwuenge ?? []);
  const union = new Set([...sa, ...sb]);
  if (union.size === 0) return 0;
  let inter = 0;
  for (const x of sa) if (sb.has(x)) inter += 1;
  return inter / union.size;
}

export interface AehnlichkeitsTreffer {
  schwinger: Schwinger;
  score: number;
  gruende: string[];
}

/** Ohne mind. ein reales Profilmerkmal (kein Porträt) ist jeder Vergleich
 * bedeutungslos — alle Distanzen fallen auf denselben neutralen Wert zurück. */
export function hatProfildaten(s: Schwinger): boolean {
  return (
    s.groesse_cm != null ||
    s.gewicht_kg != null ||
    s.kranzstatus !== "kein" ||
    s.teilverband != null ||
    s.bevorzugte_schwuenge.length > 0
  );
}

/** Ähnlichkeit 0..1 (1 = identisch) zwischen zwei Schwingern. */
export function aehnlichkeit(a: Schwinger, b: Schwinger): number {
  const groesseDiff = normDiff(a.groesse_cm, b.groesse_cm, GROESSE_SPANNE);
  const gewichtDiff = normDiff(a.gewicht_kg, b.gewicht_kg, GEWICHT_SPANNE);
  const kranzDiff =
    Math.abs((KRANZ_ORDINAL[a.kranzstatus] ?? 0) - (KRANZ_ORDINAL[b.kranzstatus] ?? 0)) / 3;
  const overlap = schwungOverlap(a, b);
  const gleicherVerband = a.teilverband && a.teilverband === b.teilverband ? 1 : 0;
  const gleicherKlub = a.schwingklub && a.schwingklub === b.schwingklub ? 1 : 0;

  return (
    0.3 * (1 - groesseDiff) +
    0.3 * (1 - gewichtDiff) +
    0.15 * (1 - kranzDiff) +
    0.15 * overlap +
    0.05 * gleicherVerband +
    0.05 * gleicherKlub
  );
}

/** Top-N ähnlichste Schwinger (ohne sich selbst), inkl. kurzer Begründung. */
export function findeAehnliche(
  ziel: Schwinger,
  alle: Schwinger[],
  n: number = 5
): AehnlichkeitsTreffer[] {
  if (!hatProfildaten(ziel)) return []; // sonst nur Zufallstreffer aus fehlenden Daten
  return alle
    .filter((s) => s.id !== ziel.id && hatProfildaten(s))
    .map((s) => ({ schwinger: s, score: aehnlichkeit(ziel, s), gruende: gruende(ziel, s) }))
    .sort((x, y) => y.score - x.score)
    .slice(0, n);
}

function gruende(a: Schwinger, b: Schwinger): string[] {
  const g: string[] = [];
  if (a.kranzstatus === b.kranzstatus) g.push(`beide ${b.kranzstatus}`);
  if (a.teilverband && a.teilverband === b.teilverband) g.push("gleicher Teilverband");
  if (a.schwingklub && a.schwingklub === b.schwingklub) g.push("gleicher Klub");
  if (a.groesse_cm != null && b.groesse_cm != null && Math.abs(a.groesse_cm - b.groesse_cm) <= 3)
    g.push("ähnliche Grösse");
  if (a.gewicht_kg != null && b.gewicht_kg != null && Math.abs(a.gewicht_kg - b.gewicht_kg) <= 5)
    g.push("ähnliches Gewicht");
  if (schwungOverlap(a, b) > 0)
    g.push("teilt bevorzugte Schwünge");
  return g.slice(0, 3);
}
