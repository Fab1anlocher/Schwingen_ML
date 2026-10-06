// Kantonal-/Gauverband -> Fläche der Schweiz-Karte. Spiegelt
// pipeline/kantone.py (KANTONALVERBAND_ZU_KANTON): beide Tabellen müssen
// gleich bleiben, sonst zeigt der Kantons-Steckbrief andere Schwinger als
// die Kennzahlen der Karte (kantone.json) zählen.
//
// Bern ist auf der Karte in seine 6 Gauverbände geteilt (lib/bern-
// gauverbaende.ts); deren Flächen heissen wie der Verband. Verbände über
// zwei Kantone (Appenzell, Ob- und Nidwalden) gehören zu beiden Flächen --
// die Rohdaten unterscheiden nicht, wer aus welcher Hälfte stammt.

import { BERNER_GAUVERBAENDE } from "./labels";
import type { Schwinger } from "./types";

export const KANTONALVERBAND_ZU_KANTON: Record<string, string[]> = {
  "Berner-Jura": ["Bern"],
  Emmental: ["Bern"],
  Mittelland: ["Bern"],
  Oberaargau: ["Bern"],
  Oberland: ["Bern"],
  Seeland: ["Bern"],
  Luzern: ["Luzern"],
  "Ob- und Nidwalden": ["Obwalden", "Nidwalden"],
  Schwyz: ["Schwyz"],
  Tessin: ["Ticino"],
  Uri: ["Uri"],
  Zug: ["Zug"],
  Appenzell: ["Appenzell Ausserrhoden", "Appenzell Innerrhoden"],
  Glarus: ["Glarus"],
  Graubünden: ["Graubünden"],
  Schaffhausen: ["Schaffhausen"],
  "St. Gallen": ["St. Gallen"],
  Thurgau: ["Thurgau"],
  Zürich: ["Zürich"],
  Aargau: ["Aargau"],
  Baselland: ["Basel-Landschaft"],
  "Basel-Stadt": ["Basel-Stadt"],
  Solothurn: ["Solothurn"],
  Fribourgeoise: ["Fribourg"],
  Genevoise: ["Genève"],
  Jura: ["Jura"],
  Neuchâteloise: ["Neuchâtel"],
  Vaudoise: ["Vaud"],
  Valaisanne: ["Valais"],
};

const BERN = BERNER_GAUVERBAENDE as readonly string[];

/** Kantonal-/Gauverband eines Schwingers: Porträt, sonst über den Schwingklub
 *  (wie pipeline/export._gauverband_stats). */
export function kantonalverbandVon(s: Schwinger): string | null {
  return s.kanton ?? s.kanton_klub ?? null;
}

/** Kartenflächen eines Verbands: Berner Gauverband = eigene Fläche. */
export function flaechenFuer(verband: string | null): string[] {
  if (!verband) return [];
  if (BERN.includes(verband)) return [verband];
  return KANTONALVERBAND_ZU_KANTON[verband] ?? [];
}

/** Die Verbände, die auf einer Kartenfläche liegen. */
export function verbaendeAuf(flaeche: string): string[] {
  return Object.keys(KANTONALVERBAND_ZU_KANTON).filter((v) => flaechenFuer(v).includes(flaeche));
}
