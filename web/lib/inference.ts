// Clientseitige Logistic-Regression-Inferenz (§7, NFR-2: < 500 ms).
// Spiegelt pipeline/features._feature_vektor und pipeline/train exakt.

import type { ModelArtifact, Schwinger, Prognose, Klasse } from "./types";

const AKTUELLES_JAHR = new Date().getFullYear();

function diffOderNull(a: number | null, b: number | null): number {
  if (a === null || b === null) return 0;
  return a - b;
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

/** Baut den Merkmalsvektor A-vs-B (identisch zur Python-Pipeline). */
export function baueFeatures(
  model: ModelArtifact,
  a: Schwinger,
  b: Schwinger,
  eloA: number,
  eloB: number,
  nA: number,
  nB: number,
  kopfAnKopfA: number = 0
): number[] {
  const kranz = model.config.kranzstatus_ordinal;
  const kranzA = kranz[a.kranzstatus] ?? 0;
  const kranzB = kranz[b.kranzstatus] ?? 0;
  const alterA = a.jahrgang !== null ? AKTUELLES_JAHR - a.jahrgang : null;
  const alterB = b.jahrgang !== null ? AKTUELLES_JAHR - b.jahrgang : null;

  return [
    (eloA - eloB) / 100.0, // rating_diff
    Math.abs(eloA - eloB) / 100.0, // rating_abstand
    a.form - b.form, // form_diff
    kranzA - kranzB, // kranz_diff
    diffOderNull(alterA, alterB), // alter_diff
    diffOderNull(a.gewicht_kg, b.gewicht_kg), // gewicht_diff
    diffOderNull(a.groesse_cm, b.groesse_cm), // groesse_diff
    nA - nB, // erfahrung_diff
    a.teilverband && a.teilverband === b.teilverband ? 1 : 0, // same_teilverband
    schwungOverlap(a, b), // schwung_overlap
    (a.bevorzugte_schwuenge?.length ?? 0) - (b.bevorzugte_schwuenge?.length ?? 0), // schwung_count_diff
    kopfAnKopfA, // kopf_an_kopf
  ];
}

function softmax(logits: number[]): number[] {
  const max = Math.max(...logits);
  const exp = logits.map((l) => Math.exp(l - max));
  const sum = exp.reduce((s, e) => s + e, 0);
  return exp.map((e) => e / sum);
}

function wahrscheinlichkeiten(model: ModelArtifact, z: number[]): number[] {
  const logits = model.coef.map(
    (row, k) => row.reduce((s, w, i) => s + w * z[i], 0) + model.intercept[k]
  );
  return softmax(logits);
}

// Zweizeilige Beschriftung je Merkmal (Titel + neutrale Unterzeile). Die
// Richtung (wem es nützt) kommt datengetrieben aus dem Modell, nicht aus dem
// Text hier -- die Unterzeile beschreibt nur, was das Merkmal misst.
const BEITRAG_TEXT: Record<string, { titel: string; unter: string }> = {
  rating_diff: { titel: "Rating-Vorsprung", unter: "Elo-Differenz" },
  rating_abstand: { titel: "Ausgeglichenheit", unter: "Wie nah die Ratings liegen" },
  form_diff: { titel: "Aktuelle Form", unter: "Letzte Gänge" },
  kranz_diff: { titel: "Kranzstärke", unter: "Kranzstatus" },
  alter_diff: { titel: "Frische", unter: "Altersunterschied" },
  gewicht_diff: { titel: "Gewicht & Physis", unter: "Körpermasse" },
  groesse_diff: { titel: "Körpergrösse", unter: "Grössenunterschied" },
  erfahrung_diff: { titel: "Erfahrung", unter: "Anzahl Gänge" },
  same_teilverband: { titel: "Teilverband", unter: "Gleicher Verband" },
  schwung_overlap: { titel: "Ähnlicher Stil", unter: "Gemeinsame Schwünge" },
  schwung_count_diff: { titel: "Schwung-Vielfalt", unter: "Anzahl bevorzugter Schwünge" },
  kopf_an_kopf: { titel: "Direkte Duelle", unter: "Bisherige Begegnungen" },
};

/** Vollständige Prognose inkl. Erklärbarkeit (FR-1, FR-3). */
export function prognostiziere(
  model: ModelArtifact,
  a: Schwinger,
  b: Schwinger,
  eloA: number,
  eloB: number,
  nA: number,
  nB: number,
  kopfAnKopfA: number = 0
): Prognose {
  const x = baueFeatures(model, a, b, eloA, eloB, nA, nB, kopfAnKopfA);
  const { mu, sigma } = model.standardisierung;
  const z = x.map((xi, i) => (xi - mu[i]) / (sigma[i] || 1));

  const probs = wahrscheinlichkeiten(model, z);
  const p: Record<Klasse, number> = {} as any;
  model.klassen.forEach((kl, i) => (p[kl] = probs[i]));

  // Quote = 1/p (informativ, FR-2 / AK-2.3).
  const quote: Record<Klasse, number> = {} as any;
  (Object.keys(p) as Klasse[]).forEach((kl) => (quote[kl] = 1 / Math.max(p[kl], 1e-6)));

  // Erklärbarkeit (FR-3): Beitrag jedes Merkmals in Prozentpunkten von
  // p(Sieg A) -- Gegenprobe "was wäre p(Sieg A), wenn genau dieses Merkmal
  // keinen Unterschied machen würde (z=0), alle anderen unverändert". Direkt
  // in derselben Einheit wie die Hauptzahlen oben auf der Seite, statt eines
  // abstrakten, nicht weiter interpretierbaren Koeffizienten-Produkts.
  const iSiegA = model.klassen.indexOf("sieg_a");
  const beitraege = model.features
    .map((feat, i) => {
      const zOhneMerkmal = z.slice();
      zOhneMerkmal[i] = 0;
      const probsOhne = wahrscheinlichkeiten(model, zOhneMerkmal);
      const einflussPp = (probs[iSiegA] - probsOhne[iSiegA]) * 100;
      const text = BEITRAG_TEXT[feat] ?? { titel: model.feature_labels[feat] ?? feat, unter: "" };
      return {
        titel: text.titel,
        unterzeile: text.unter,
        richtung: (einflussPp >= 0 ? "a" : "b") as "a" | "b",
        staerke: Math.abs(einflussPp),
      };
    })
    .filter((c) => c.staerke > 0.1)
    .sort((x, y) => y.staerke - x.staerke)
    .slice(0, 6);

  const minG = model.config.min_gaenge_fuer_sicherheit;
  const unsicher = nA < minG || nB < minG;

  return { p, quote, beitraege, unsicher };
}
