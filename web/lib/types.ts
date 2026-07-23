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
  config: {
    min_gaenge_fuer_sicherheit: number;
    form_fenster_k: number;
    elo_start: number;
    kranzstatus_ordinal: Record<string, number>;
  };
  erstellt: string;
}

export interface GroessterErfolg {
  gegner_name: string;
  event_id: string;
  datum: string;
  eigenes_elo: number;
  gegner_elo: number;
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
  /** Mittel (tatsächlich - Elo-erwartete Punkte) über alle Gänge; + = übertrifft Erwartung. */
  ueberraschungsindex: number | null;
  n_bewertete_gaenge: number;
  groesster_erfolg: GroessterErfolg | null;
  quellen: string[];
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
  koeffizienten: Record<Klasse, number>;
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

export interface KantonStatistik {
  kanton: string;
  n_schwinger: number;
  elo_avg: number | null;
  n_top_schwinger: number;
  n_kranzer: number;
  n_eidgenosse: number;
  n_koenig: number;
  n_siege: number;
  n_gestellt: number;
  n_niederlagen: number;
}

export interface KantoneArtifact {
  schema_version: string;
  top_schwelle_elo: number;
  kantone: KantonStatistik[];
}

export interface GauverbaendeArtifact {
  schema_version: string;
  top_schwelle_elo: number;
  /** Gleiche Form wie KantonStatistik, aber `kanton` ist hier der Kantonal-
   * /Gauverband selbst (29 Verbände), nicht der zusammengefasste politische
   * Kanton — s. pipeline/kantone.py. */
  gauverbaende: KantonStatistik[];
}

export interface BenchmarkKandidat {
  key: "kranz_heuristik" | "elo_baseline" | "ml_ohne_elo" | "ml_komplett";
  label: string;
  accuracy: number;
  brier_score: number;
}

export interface BenchmarkArtifact {
  schema_version: string;
  holdout_jahr: number;
  n_test: number;
  kandidaten: BenchmarkKandidat[];
}

export interface ClusterPunkt {
  schwinger_id: string;
  cluster: number;
  pca_x: number;
  pca_y: number;
}

export interface ClusterZusammenfassung {
  cluster: number;
  n: number;
  gewicht_avg: number;
  groesse_avg: number;
  /** Gewicht / (Grösse/100)² — BMI-artiger Kompaktheits-Index. */
  kompaktheit_avg: number;
  elo_avg: number;
  erfahrung_avg: number;
  top_schwuenge: string[];
  /** Menschenlesbarer Satz: was diesen Cluster am stärksten vom Durchschnitt
   * unterscheidet (grösster |z-Wert| des Zentrums über alle Merkmale). */
  auszeichnung: string;
  /** Die 3 Schwinger, die im standardisierten Merkmalsraum am nächsten am
   * Cluster-Zentrum liegen — konkrete "typische Vertreter" dieses Typs. */
  typische_vertreter: string[];
  /** Teilverband, der in diesem Cluster deutlich überrepräsentiert ist
   * gegenüber der Gesamtverteilung; null wenn keiner klar heraussticht.
   * Rein beschreibend, fliesst NICHT ins Clustering ein. */
  teilverband_schwerpunkt: string | null;
}

export interface AehnlichkeitsTreffer {
  schwinger_id: string;
  score: number;
}

export interface ClusterArtifact {
  schema_version: string;
  k: number;
  silhouette: number;
  /** Merkmalsnamen in Spaltenreihenfolge (Gewicht/Grösse/Kompaktheit + die je
   * nach Datenlage automatisch gewählten häufigsten Schwünge). */
  merkmale: string[];
  punkte: ClusterPunkt[];
  cluster_zusammenfassung: ClusterZusammenfassung[];
  /** KNN im selben standardisierten Merkmalsraum wie das Clustering (Physis+Stil,
   * ohne Elo) -- ersetzt die frühere Hand-Heuristik in lib/aehnlichkeit.ts. */
  aehnlichste: Record<string, AehnlichkeitsTreffer[]>;
}

export interface Prognose {
  p: Record<Klasse, number>;
  quote: Record<Klasse, number>; // 1/p, informativ (FR-2, AK-2.3)
  beitraege: { label: string; richtung: "a" | "b"; staerke: number }[];
  unsicher: boolean; // FR-1 / AK-1.2
}
