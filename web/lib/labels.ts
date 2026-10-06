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

const TEILVERBAND_TEXT: Record<string, string> = {
  Suedwestschweiz: "Südwestschweiz",
};

export function teilverbandName(verband: string): string {
  return TEILVERBAND_TEXT[verband] ?? verband;
}

/** Kantonsname auf Deutsch. Die Karte führt die Namen aus dem GeoJSON
 *  ("Fribourg", "Ticino"), die Artefakte die Kantonal-/Gauverbände
 *  ("Fribourgeoise", "Emmental") -- angezeigt wird beides nur hierüber. */
const KANTON_TEXT: Record<string, string> = {
  Fribourg: "Freiburg",
  Genève: "Genf",
  Neuchâtel: "Neuenburg",
  Ticino: "Tessin",
  Valais: "Wallis",
  Vaud: "Waadt",
};

export function kantonName(name: string): string {
  return KANTON_TEXT[name] ?? name;
}

const VERBAND_TEXT: Record<string, string> = {
  Fribourgeoise: "Freiburg",
  Genevoise: "Genf",
  Neuchâteloise: "Neuenburg",
  Vaudoise: "Waadt",
  Valaisanne: "Wallis",
  Baselland: "Basel-Landschaft",
};
/** Berner Gauverbände -- als Kartenfläche und als Verband "Emmental (BE)". */
export const BERNER_GAUVERBAENDE = [
  "Oberland",
  "Emmental",
  "Mittelland",
  "Oberaargau",
  "Seeland",
  "Berner-Jura",
] as const;

/** Kantonal-/Gauverband zum Anzeigen: "Fribourgeoise" -> "Freiburg",
 *  "Emmental" -> "Emmental (BE)". */
export function kantonalverbandName(verband: string): string {
  if ((BERNER_GAUVERBAENDE as readonly string[]).includes(verband)) return `${verband} (BE)`;
  return VERBAND_TEXT[verband] ?? verband;
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

/** Name und Inhalt eines Modellstands (report_verlauf.json: Modelltyp +
 *  Merkmalsversion) für die Meilensteine der Analyse-Seite. */
export function modellStandText(
  typ: string,
  version: number,
  rating = 1
): { name: string; was: string } {
  const bekannt: Record<string, { name: string; was: string }> = {
    "lr|1": {
      name: "Lineares Modell",
      was: "Logistische Regression auf Elo, Form, Kranzstatus, Physis, Stil und direkten Duellen",
    },
    "lr|2": {
      name: "+ Stand vor dem Fest, Gestellt-Neigung",
      was: "alle Gänge eines Fests mit dem Stand davor; wie oft ein Schwinger stellt; Erfahrung logarithmisch",
    },
    "lr|3": {
      name: "+ Spitzenpaarungen, Gestellt-Bilanz",
      was: "wie stark der Schwächere eines Paars ist; wie oft genau dieses Paar gestellt hat",
    },
    "gbm|3": {
      name: "Gradient Boosting",
      was: "zweistufig (erst Gestellt, dann Sieger) mit Monotonie-Vorgaben; jüngere Gänge zählen mehr",
    },
    // Dieser Stand enthält zwei Schritte vom selben Tag (05.10.2026): das neue
    // Rating (Test-Log-Loss 0.720 -> 0.695) und die Datenkorrekturen D4/D5
    // (0.695 -> 0.683), s. docs/MODELL.md.
    "gbm|3|2": {
      name: "+ schnelleres Rating, saubere Daten",
      was: "Elo reagiert schneller (K 56 statt 24), Neulinge bewegen sich am Anfang stärker; dazu Niederlagen in alten PDFs richtig gelesen und 18 Namensvettern getrennt",
    },
  };
  return (
    (rating > 1 ? bekannt[`${typ}|${version}|${rating}`] : undefined) ??
    bekannt[`${typ}|${version}`] ?? {
      name: `${typ === "gbm" ? "Gradient Boosting" : "Lineares Modell"} · Merkmale v${version}`,
      was: "",
    }
  );
}

/** Anteil 0..1 als ganze Prozent: 0.6897 -> "69%". */
export function prozent(anteil: number): string {
  return `${Math.round(anteil * 100)}%`;
}

/** Anteil als Prozent mit einer Nachkommastelle: 0.6901 -> "69.0%". */
export function prozent1(anteil: number): string {
  return `${(anteil * 100).toFixed(1)}%`;
}

/** ISO-Datum "2026-09-05" -> "5.9.2026". */
export function datumKurz(iso: string): string {
  const [j, m, t] = iso.slice(0, 10).split("-").map(Number);
  return j && m && t ? `${t}.${m}.${j}` : iso;
}

/** Kurzname je Ansatz im Vergleich der Analyse-Seite (benchmark.json key).
 *  Dieselben Namen in der Rangliste und in der Tabelle für Fachleute. */
const ANSATZ_NAME: Record<string, string> = {
  ml_komplett: "Unser Modell",
  lr_komplett: "Lineares Modell",
  elo_angepasst: "Elo-Rating",
  elo_baseline: "Elo-Formel",
  ml_ohne_elo: "Modell ohne Elo",
  kranz_heuristik: "Faustregel Kranzstatus",
};

export function ansatzName(key: string, fallback: string): string {
  return ANSATZ_NAME[key] ?? fallback;
}

/** Stil-Typen (stiltypen.json, pipeline/stiltypen.py): Name, ein Satz für
 *  die Karte und wo der Typ auf der Stil-Landkarte liegt. */
export const STIL_TYPEN: Record<
  string,
  { name: string; satz: string; lage: string }
> = {
  werfer: {
    name: "Werfer",
    satz: "Gewinnt öfter mit dem Plattwurf (10.00), als seine Gegner erwarten lassen.",
    lage: "viel Plattwurf",
  },
  lauerer: {
    name: "Lauerer",
    satz: "Stellt oft, doch wenn er gewinnt, dann gern mit dem Plattwurf.",
    lage: "viel Plattwurf, viel gestellt",
  },
  bollwerk: {
    name: "Bollwerk",
    satz: "Stellt öfter als erwartet: Gegen ihn ist ein Sieg harte Arbeit, für beide Seiten.",
    lage: "viel gestellt",
  },
  bodenarbeiter: {
    name: "Bodenarbeiter",
    satz: "Gewinnt seltener platt als erwartet, eher mit der 9.75, also nach Arbeit am Boden.",
    lage: "wenig Plattwurf",
  },
  entscheider: {
    name: "Entscheider",
    satz: "Stellt seltener als erwartet: Seine Gänge haben fast immer einen Sieger.",
    lage: "wenig gestellt",
  },
  allrounder: {
    name: "Allrounder",
    satz: "In beiden Eigenschaften nahe am Durchschnitt, ohne ausgeprägte Vorliebe.",
    lage: "Mitte",
  },
};

export function stilTypName(typ: string): string {
  return STIL_TYPEN[typ]?.name ?? typ;
}

/** Prozentpunkte mit Vorzeichen: 7.3 -> "+7.3 %-Pkt.", -0.04 -> "±0.0 %-Pkt.". */
export function prozentpunkte(wert: number): string {
  const r = Math.round(wert * 10) / 10;
  if (r === 0) return "±0.0 %-Pkt.";
  return `${r > 0 ? "+" : "−"}${Math.abs(r).toFixed(1)} %-Pkt.`;
}
