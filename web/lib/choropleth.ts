// Klassierte (statt stufenlos geblendete) Farbskala für die Schweiz-Karte.
// Vorher: eine einzelne Farbe per CSS-Alpha eingeblendet (0.12..0.92 Deckkraft)
// -- auf dem dunklen Hintergrund bleiben Alpha-Unterschiede in der Praxis kaum
// wahrnehmbar, die Karte wirkt "zu grün, zu wenig systematisch". Jetzt: feste
// Farbstufen (echte Helligkeits-/Sättigungsschritte, keine Transparenz) nach
// Quantil-Klassen -- klassische Choroplethen-Technik, jede Klasse enthält
// (ungefähr) gleich viele Kantone/Gauverbände statt gleich breite Wertspannen,
// robust gegenüber schiefen Verteilungen (z.B. viele Kantone mit 0 Top-Schwingern).

// Sequenzielle Grün-Stufen (hell→dunkel), auf hellem Papier-Hintergrund
// kalibriert: die hellste Stufe ist noch klar von der Hintergrundfarbe
// unterscheidbar (nicht mehr das dunkle Theme von früher).
export const KLASSEN_FARBEN = [
  "#c3e3d3",
  "#8ccbb0",
  "#4ea987",
  "#2c7e62",
  "#184f3d",
];

/** Quantil-Grenzen für n Klassen; dedupliziert (z.B. bei vielen Nullen fallen
 * mehrere Grenzen zusammen -> entsprechend weniger tatsächliche Klassen). */
export function quantilGrenzen(werte: number[], nKlassen: number): number[] {
  if (werte.length === 0) return [];
  const sortiert = [...werte].sort((a, b) => a - b);
  const grenzen: number[] = [sortiert[0]];
  for (let i = 1; i < nKlassen; i++) {
    const idx = Math.floor((i / nKlassen) * (sortiert.length - 1));
    grenzen.push(sortiert[idx]);
  }
  grenzen.push(sortiert[sortiert.length - 1]);
  return Array.from(new Set(grenzen));
}

/** Klassenindex (0-basiert) für einen Wert anhand der Quantil-Grenzen. */
export function klasseFuer(wert: number, grenzen: number[]): number {
  for (let i = grenzen.length - 2; i >= 0; i--) {
    if (wert >= grenzen[i]) return i;
  }
  return 0;
}
