// Clientseitige Inferenz (§7, NFR-2: < 500 ms).
// Spiegelt pipeline/features._feature_vektor, train und export.serialisiere_gbm
// exakt (per verify_inference.py auf Bit-Parität geprüft).

import type { ModelArtifact, GbmModel, GbmTree, Schwinger, Prognose, Klasse } from "./types";

const AKTUELLES_JAHR = new Date().getFullYear();

function diffOderNull(a: number | null, b: number | null): number {
  if (a === null || b === null) return 0;
  return a - b;
}

/** Baut den Merkmalsvektor A-vs-B (identisch zur Python-Pipeline, 12 Merkmale). */
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
    a.career - b.career, // career_diff
    a.form_lang - b.form_lang, // form_lang_diff
  ];
}

function softmax(logits: number[]): number[] {
  const max = Math.max(...logits);
  const exp = logits.map((l) => Math.exp(l - max));
  const sum = exp.reduce((s, e) => s + e, 0);
  return exp.map((e) => e / sum);
}

/** Logistic-Regression-Wahrscheinlichkeiten (standardisiert). */
function lrProbs(model: ModelArtifact, x: number[]): number[] {
  const { mu, sigma } = model.standardisierung;
  const z = x.map((xi, i) => (xi - mu[i]) / (sigma[i] || 1));
  const logits = model.coef.map(
    (row, k) => row.reduce((s, w, i) => s + w * z[i], 0) + model.intercept[k]
  );
  return softmax(logits);
}

function treeValue(tree: GbmTree, x: number[]): number {
  let node = 0;
  while (tree.children_left[node] !== -1) {
    const f = tree.feature[node];
    node = x[f] <= tree.threshold[node] ? tree.children_left[node] : tree.children_right[node];
  }
  return tree.value[node];
}

/** Gradient-Boosting-Wahrscheinlichkeiten (Tree-Walk, spiegelt sklearn). */
export function gbmProbs(gbm: GbmModel, x: number[]): number[] {
  const raw = [...gbm.init_raw];
  for (const stage of gbm.stages) {
    for (let k = 0; k < stage.length; k++) {
      raw[k] += gbm.learning_rate * treeValue(stage[k], x);
    }
  }
  return softmax(raw);
}

/** Vollständige Prognose: GBM für die Wahrscheinlichkeit (falls vorhanden),
 *  Logistic Regression für die Erklärbarkeit (FR-1, FR-3). */
export function prognostiziere(
  model: ModelArtifact,
  gbm: GbmModel | null,
  a: Schwinger,
  b: Schwinger,
  eloA: number,
  eloB: number,
  nA: number,
  nB: number,
  festTyp: string
): Prognose {
  const x = baueFeatures(model, a, b, eloA, eloB, nA, nB, festTyp);

  const nutzeGbm = gbm !== null && model.bestes_modell === "gbm";
  const probs = nutzeGbm ? gbmProbs(gbm as GbmModel, x) : lrProbs(model, x);
  const p: Record<Klasse, number> = {} as any;
  model.klassen.forEach((kl, i) => (p[kl] = probs[i]));

  const quote: Record<Klasse, number> = {} as any;
  (Object.keys(p) as Klasse[]).forEach((kl) => (quote[kl] = 1 / Math.max(p[kl], 1e-6)));

  // Erklärbarkeit stets über die interpretierbare LR (Richtung + Stärke, FR-3).
  const { mu, sigma } = model.standardisierung;
  const z = x.map((xi, i) => (xi - mu[i]) / (sigma[i] || 1));
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

  return { p, quote, beitraege, unsicher, modell: nutzeGbm ? "gbm" : "lr" };
}
