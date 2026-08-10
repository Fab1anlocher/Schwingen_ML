// Typen der Modell-/Daten-Artefakte (§7, NFR-6).

export type Klasse = "sieg_a" | "gestellt" | "sieg_b";

export interface ModelArtifact {
  schema_version: string;
  typ: string;
  klassen: Klasse[];
  features: string[];
  feature_labels: Record<string, string>;
  standardisierung: { mu: number[]; sigma: number[] };
  coef: number[][]; // [n_klassen][n_features]
  intercept: number[]; // [n_klassen]
  bestes_modell: "lr" | "gbm";
  config: {
    min_gaenge_fuer_sicherheit: number;
    form_fenster_k: number;
    form_lang_fenster: number;
    elo_start: number;
    kranzstatus_ordinal: Record<string, number>;
  };
  erstellt: string;
}

export interface Schwinger {
  id: string;
  name: string;
  jahrgang: number | null;
  groesse_cm: number | null;
  gewicht_kg: number | null;
  kranzstatus: string;
  teilverband: string | null;
  kanton: string | null;
  schwingklub: string | null;
  bevorzugte_schwuenge: string[];
  form: number;
  form_lang: number;
  career: number;
  quellen: string[];
}

// Gradient-Boosting-Artefakt (Tree-JSON, §7).
export interface GbmTree {
  children_left: number[];
  children_right: number[];
  feature: number[];
  threshold: number[];
  value: number[];
}
export interface GbmModel {
  typ: "gradient_boosting";
  klassen: Klasse[];
  features: string[];
  learning_rate: number;
  init_raw: number[];
  stages: GbmTree[][]; // [n_stages][n_klassen]
}

export interface RatingsArtifact {
  schema_version: string;
  elo_start: number;
  ratings: Record<string, { elo: number; n_gaenge: number }>;
}

export interface FeatureImportanceEntry {
  feature: string;
  label: string;
  wichtigkeit: number;
  koeffizienten?: Record<Klasse, number>; // nur bei LR
}

export interface KommendesFest {
  id: string;
  name: string;
  datum: string;
  typ: string;
  ort?: string;
  quelle?: string;
  paarungen?: { a_id: string; b_id: string }[];
}

export interface EventsArtifact {
  schema_version: string;
  vergangene: { id: string; name: string; datum: string; typ: string }[];
  kommende: KommendesFest[];
}

export interface Prognose {
  p: Record<Klasse, number>;
  quote: Record<Klasse, number>; // 1/p, informativ (FR-2, AK-2.3)
  beitraege: { label: string; richtung: "a" | "b"; staerke: number }[];
  unsicher: boolean; // FR-1 / AK-1.2
  modell: "lr" | "gbm"; // welches Modell die Wahrscheinlichkeit lieferte
}
