// Anzeigetexte für Datenwerte -- EINE Stelle für die ganze App.
//
// Die Artefakte führen ASCII-Schlüssel ("Suedwestschweiz", "eidgenoessisch",
// "koenig"), weil die Pipeline sie als Werte vergleicht. Angezeigt werden
// sie nur über diese Funktionen. Vorher standen dieselben Tabellen in vier
// Seiten, und wo eine fehlte, erschien der Rohwert ("Suedwestschweiz" im
// Filter der Schwinger-Seite und auf den Typen-Karten).

/** Teilverbände; Schlüssel wie in schwinger.json (Feld teilverband*). */
export const TEILVERBAENDE = [
  "Bern",
  "Innerschweiz",
  "Nordostschweiz",
  "Nordwestschweiz",
  "Suedwestschweiz",
] as const;

const TEILVERBAND_TEXT: Record<string, string> = { Suedwestschweiz: "Südwestschweiz" };

export function teilverbandName(verband: string): string {
  return TEILVERBAND_TEXT[verband] ?? verband;
}

/** Festtyp als Adjektiv/Kurzform ("Bergfest", "Kantonal"). */
const FESTTYP_TEXT: Record<string, string> = {
  eidgenoessisch: "Eidgenössisch",
  berg: "Bergfest",
  teilverband: "Teilverband",
  kantonal: "Kantonal",
  regional: "Regional",
};

export function festtypName(typ: string): string {
  return FESTTYP_TEXT[typ] ?? typ;
}

/** Kranzstufe; "kein" bewusst ohne Text (die Tabellen zeigen dort "—"). */
const KRANZ_TEXT: Record<string, string> = {
  kranzer: "Kranzer",
  eidgenosse: "Eidgenosse",
  koenig: "Schwingerkönig",
};

export function kranzName(stufe: string): string | null {
  return KRANZ_TEXT[stufe] ?? null;
}

/** Schwungname vereinheitlicht: die Rohdaten schreiben denselben Schwung
 *  uneinheitlich ("innerer Haken" / "Innerer Haken"). Schwünge sind Nomen,
 *  darum mit Grossbuchstaben. Spiegelt pipeline/clustering.py:_normiert --
 *  beide müssen gleich normieren, sonst zählen Analyse und Typen verschieden. */
export function schwungName(name: string): string {
  const t = name.trim();
  return t ? t[0].toUpperCase() + t.slice(1) : t;
}

/** Ganze Zahl im Schweizer Format: 133'611. */
export function zahl(n: number): string {
  return Math.round(n).toLocaleString("de-CH");
}

/** Anteil 0..1 als ganze Prozent: 0.6897 -> "69%". */
export function prozent(anteil: number): string {
  return `${Math.round(anteil * 100)}%`;
}

/** ISO-Datum "2026-09-05" -> "5.9.2026". */
export function datumKurz(iso: string): string {
  const [j, m, t] = iso.slice(0, 10).split("-").map(Number);
  return j && m && t ? `${t}.${m}.${j}` : iso;
}
