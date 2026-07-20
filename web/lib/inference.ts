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
  festTyp: string
): number[] {
  const kranz = model.config.kranzstatus_ordinal;
  const kranzA = kranz[a.kranzstatus] ?? 0;
  const kranzB = kranz[b.kranzstatus] ?? 0;
  const alterA = a.jahrgang !== null ? AKTUELLES_JAHR - a.jahrgang : null;
  const alterB = b.jahrgang !== null ? AKTUELLES_JAHR - b.jahrgang : null;

  return [
    (eloA - eloB) / 100.0, // rating_diff
    a.form - b.form, // form_diff
    kranzA - kranzB, // kranz_diff
    diffOderNull(alterA, alterB), // alter_diff
    diffOderNull(a.gewicht_kg, b.gewicht_kg), // gewicht_diff
    diffOderNull(a.groesse_cm, b.groesse_cm), // groesse_diff
    nA - nB, // erfahrung_diff
    festTyp === "berg" ? 1 : 0, // bergfest
    festTyp === "eidgenoessisch" || festTyp === "berg" ? 1 : 0, // gross_fest
    a.teilverband && a.teilverband === b.teilverband ? 1 : 0, // same_teilverband
    schwungOverlap(a, b), // schwung_overlap
    (a.bevorzugte_schwuenge?.length ?? 0) - (b.bevorzugte_schwuenge?.length ?? 0), // schwung_count_diff
  ];
}

function softmax(logits: number[]): number[] {
  const max = Math.max(...logits);
  const exp = logits.map((l) => Math.exp(l - max));
  const sum = exp.reduce((s, e) => s + e, 0);
  return exp.map((e) => e / sum);
}

/** Vollständige Prognose inkl. Erklärbarkeit (FR-1, FR-3). */
export function prognostiziere(
  model: ModelArtifact,
  a: Schwinger,
  b: Schwinger,
  eloA: number,
  eloB: number,
  nA: number,
  nB: number,
  festTyp: string
): Prognose {
  const x = baueFeatures(model, a, b, eloA, eloB, nA, nB, festTyp);
  const { mu, sigma } = model.standardisierung;
  const z = x.map((xi, i) => (xi - mu[i]) / (sigma[i] || 1));

  // Logits je Klasse.
  const logits = model.coef.map(
    (row, k) => row.reduce((s, w, i) => s + w * z[i], 0) + model.intercept[k]
  );
  const probs = softmax(logits);
  const p: Record<Klasse, number> = {} as any;
  model.klassen.forEach((kl, i) => (p[kl] = probs[i]));

  // Quote = 1/p (informativ, FR-2 / AK-2.3).
  const quote: Record<Klasse, number> = {} as any;
  (Object.keys(p) as Klasse[]).forEach((kl) => (quote[kl] = 1 / Math.max(p[kl], 1e-6)));

  // Erklärbarkeit (FR-3): Beitrag jedes Merkmals zur A-vs-B-Log-Odds.
  const iA = model.klassen.indexOf("sieg_a");
  const iB = model.klassen.indexOf("sieg_b");
  const beitraege = model.features
    .map((feat, i) => {
      const contrib = (model.coef[iA][i] - model.coef[iB][i]) * z[i];
      return {
        label: model.feature_labels[feat] ?? feat,
        richtung: (contrib >= 0 ? "a" : "b") as "a" | "b",
        staerke: Math.abs(contrib),
      };
    })
    .filter((c) => c.staerke > 1e-6)
    .sort((x, y) => y.staerke - x.staerke)
    .slice(0, 4);

  const minG = model.config.min_gaenge_fuer_sicherheit;
  const unsicher = nA < minG || nB < minG;

  return { p, quote, beitraege, unsicher };
}
