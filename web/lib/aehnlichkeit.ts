// Erklärbarkeits-Helfer für "Ähnliche Schwinger" (FR-3). Die Ähnlichkeit
// selbst kommt seit dem KNN-Upgrade aus pipeline/clustering.py (echtes
// K-Means/KNN im selben standardisierten Merkmalsraum wie die Schwingertypen,
// s. cluster.json:aehnlichste) -- dieses Modul erklärt nur noch in Worten,
// WARUM zwei Schwinger als ähnlich gelten, ohne selbst zu werten.

import type { Schwinger } from "./types";

function schwungOverlap(a: Schwinger, b: Schwinger): boolean {
  const sb = new Set(b.bevorzugte_schwuenge ?? []);
  return (a.bevorzugte_schwuenge ?? []).some((x) => sb.has(x));
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

/** Kurze, menschenlesbare Begründung, warum zwei Schwinger als ähnlich gelten. */
export function gruende(a: Schwinger, b: Schwinger): string[] {
  const g: string[] = [];
  if (a.groesse_cm != null && b.groesse_cm != null && Math.abs(a.groesse_cm - b.groesse_cm) <= 3)
    g.push("ähnliche Grösse");
  if (a.gewicht_kg != null && b.gewicht_kg != null && Math.abs(a.gewicht_kg - b.gewicht_kg) <= 5)
    g.push("ähnliches Gewicht");
  if (schwungOverlap(a, b)) g.push("teilt bevorzugte Schwünge");
  if (a.kranzstatus === b.kranzstatus) g.push(`beide ${b.kranzstatus}`);
  if (a.teilverband && a.teilverband === b.teilverband) g.push("gleicher Teilverband");
  return g.slice(0, 3);
}
