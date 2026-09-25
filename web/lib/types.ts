// Typen der Modell-/Daten-Artefakte (§7, NFR-6).

export type Klasse = "sieg_a" | "gestellt" | "sieg_b";

/** Knoten eines exportierten Baums (pipeline/export.py _baum_json): innerer
 *  Knoten [Merkmal, Schwelle, links, rechts] -- links, wenn x <= Schwelle --,
 *  Blatt = sein Wert. */
export type BaumKnoten = number | [number, number, number, number];

/** Binäre Boosting-Stufe: Sigmoid(basis + Summe der Bäume). */
export interface BoostingStufe {
  basis: number;
  baeume: BaumKnoten[][];
}

export interface ModelArtifact {
  schema_version: string;
  /** "gradient_boosting_zweistufig" (seit 26.09.2026) oder "logistic_regression_multinomial". */
  typ: string;
  klassen: Klasse[];
  features: string[];
  feature_labels: Record<string, string>;
  /** Mittel/Streuung der Trainingsmerkmale: LR rechnet standardisiert, beide
   *  Typen nehmen das Mittel als neutralen Wert der Erklärbalken. */
  standardisierung: { mu: number[]; sigma: number[] };
  /** Nur LR. */
  coef?: number[][]; // [n_klassen][n_features]
  intercept?: number[]; // [n_klassen]
  /** Nur Gradient Boosting: Stufe "gestellt" = P(Gestellt), Stufe "sieg" =
   *  P(Sieg A | entschieden); Spiegel-Vorzeichen je Merkmal (+1 symmetrisch,
   *  -1 Differenz). S. pipeline/modell.py. */
  stufen?: { gestellt: BoostingStufe; sieg: BoostingStufe };
  spiegel?: number[];
  config: {
    min_gaenge_fuer_sicherheit: number;
    form_fenster_k: number;
    elo_start: number;
    kranzstatus_ordinal: Record<string, number>;
    /** Merkmalsdefinition, mit der dieses Modell trainiert wurde. Fehlt bei
     *  Modellen vor Version 2 -- dann gilt 1 (s. baueFeatures). */
    merkmal_version?: number;
    /** Ab Version 2: Streuung der aktiven Elo-Ratings, Einheit des Elo-Abstands. */
    elo_streuung?: number;
    /** Ab Version 2: durchschnittliche Gestellt-Quote aller Gänge. */
    gestellt_basis?: number;
  };
  erstellt: string;
}

/** Bisherige direkte Duelle eines Paars, verdichtet (s. lib/kopfAnKopf.ts). */
export interface PaarHistorie {
  /** Geglättete Bilanz aus Sicht von A, ~0 ohne Duelle (Merkmal kopf_an_kopf). */
  vorteilA: number;
  /** Anzahl bisheriger Duelle und davon gestellte (Merkmal paar_gestellt, ab Version 3). */
  duelle: number;
  gestellt: number;
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
  /** Nur ohne Porträt: Kranzstatus laut Sternen/Kränzen der Schlussranglisten
   *  (z.B. Fritz Ramseier, Eidgenosse ohne Porträt). Nur Anzeige. */
  kranzstatus_rangliste?: string | null;
  /** Gewonnene Kränze seit Datenbeginn laut offizieller Schlussrangliste.
   *  null/fehlend = keine Ranglisten geladen (NICHT: null Kränze). */
  kraenze?: number | null;
  kraenze_nach_typ?: Record<string, number> | null;
  senne_turner?: string | null;
  /** Gemessen: aus dem schlussgang.ch-Porträt. Nur dieses Feld nutzt das Modell. */
  teilverband: string | null;
  /** Nur bei Schwingern ohne Porträt-Verband: aus ihren Festbesuchen geschätzt
   *  (pipeline/verbandsschaetzung.py, Selbstprüfung ~99.8 % je Lauf). Für
   *  Anzeige und Suche -- immer als "geschätzt" kenntlich. Optional, weil
   *  ältere Artefakte das Feld nicht führen. */
  teilverband_geschaetzt?: string | null;
  /** Ohne Porträt-Verband: Teilverband bzw. Kantonal-/Gauverband über den
   *  Schwingklub laut offizieller Schlussrangliste (Mitgliedschaft, gemessen;
   *  pipeline/ranglisten.py). Vorrang vor der Schätzung aus Festbesuchen. */
  teilverband_klub?: string | null;
  kanton_klub?: string | null;
  kanton: string | null;
  schwingklub: string | null;
  bevorzugte_schwuenge: string[];
  form: number;
  /** Geschrumpfte Gestellt-Quote (Merkmalsversion 2). null/fehlend: keine
   *  Gänge bzw. älteres Artefakt -- die App rechnet dann mit dem Durchschnitt. */
  gestellt_neigung?: number | null;
  /** Mittel (tatsächlich - Elo-erwartete Punkte) über die Gänge NACH der
   *  Einschwingphase; + = übertrifft Erwartung. */
  ueberraschungsindex: number | null;
  n_bewertete_gaenge: number;
  /** Anzahl besuchter Feste seit Beginn der Datenbasis (2023).
   *  Optional, weil ein vor dieser Änderung erzeugtes schwinger.json noch
   *  `anzahl_kraenze` führte — das Artefakt kommt aus dem Repo, nicht aus
   *  diesem Build. Die frühere Kranz-Zahl ist ersatzlos entfallen: die
   *  Stern-Markierung in der PDF war das Statusabzeichen des Schwingers,
   *  kein Kranzgewinn (s. pipeline/scrape/schlussgang_pdf.py). */
  anzahl_feste?: number;
  /** Mindestens ein Gang im aktuellsten Jahr der Datenbasis. */
  aktiv: boolean;
  /** Grösster Überraschungssieg (tiefste Elo-Siegchance) nach der Einschwingphase. */
  groesster_erfolg: GroessterErfolg | null;
  /** Festsiege seit Datenbeginn laut Schlussrangliste (Rang 1, auch geteilt),
   *  jüngster zuerst. null/fehlend = keine Ranglisten geladen. */
  festsiege?: Festsieg[] | null;
  /** Gesetzt, wenn dieser Eintrag von einem gleichnamigen Porträt-Schwinger
   *  getrennt wurde (pipeline/namensvettern.py): ID jenes Schwingers. */
  namensvetter_von?: string | null;
  quellen: string[];
}

export interface Festsieg {
  event_id: string;
  name: string;
  datum: string;
  typ: string;
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
  /** Nur LR; beim Boosting null. */
  koeffizienten: Record<Klasse, number> | null;
}

export interface KommendesFest {
  id: string;
  name: string;
  datum: string;
  typ: string;
  ort?: string;
  quelle?: string;
  /** Teilverband, dessen Schwinger hier starten; null/fehlend = offenes Feld.
   *  Kommt aus pipeline/teilnehmerkreis.py (Vorausgabe des Fests). */
  teilverband?: string | null;
  teilverband_quelle?: string;
  paarungen?: { a_id: string; b_id: string }[];
}

export interface VergangenesFest {
  id: string;
  name: string;
  datum: string;
  typ: string;
  ort?: string | null;
  /** Aus der Schlussrangliste (fehlt ohne Rangliste): Festsieger -- bei
   *  Punktgleichheit mehrere --, Teilnehmer und vergebene Kränze. */
  sieger?: { id: string; name: string }[];
  n_teilnehmer?: number;
  n_kraenze?: number;
  /** Wie gut die Prognose lag, mit dem Modell von vor der Saison (nur
   *  ausgewertete Saisons, s. pipeline/prognose_check.py). */
  prognose_check?: PrognoseCheck;
}

/** Prognose-Check eines Fests oder einer Saison (Anteile 0..1). */
export interface PrognoseCheck {
  n: number;
  /** Anteil Gänge, bei denen der wahrscheinlichste Ausgang eintrat. */
  treffer: number;
  /** Dasselbe für die reine Elo-Prognose. */
  treffer_elo: number | null;
  /** Mittlere Wahrscheinlichkeit, die das Modell dem tatsächlichen Ausgang gab. */
  p_eingetreten: number;
  gestellt_vorhergesagt: number;
  gestellt_eingetreten: number;
  /** Nur je Saison. */
  n_feste?: number;
}

export interface EventsArtifact {
  schema_version: string;
  vergangene: VergangenesFest[];
  kommende: KommendesFest[];
  /** Prognose-Check je ausgewerteter Saison ("2025", "2026"). */
  prognose_check_saisons?: Record<string, PrognoseCheck>;
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
  /** Mindestzahl Gänge, ab der ein Schwinger gezählt wird (fehlt in älteren Artefakten). */
  min_gaenge?: number;
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
  // MAE/MSE auf dem Punktwert des Gangs (s. pipeline/metriken.py). Optional,
  // weil ein vor dieser Änderung erzeugtes benchmark.json sie nicht enthält —
  // ausgeliefert wird das Artefakt aus dem Repo, nicht aus diesem Build.
  mae?: number;
  mse?: number;
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
  alter_avg: number;
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

/** Ein Balken unter "Warum diese Prognose?".
 *
 *  richtung "a"/"b": das Merkmal bevorzugt diesen Schwinger; staerke = um so
 *  viele Prozentpunkte ist SEINE Siegchance dadurch höher, als wenn es bei
 *  diesem Merkmal keinen Unterschied gäbe.
 *  richtung "gestellt": das Merkmal bevorzugt niemanden (gleicher Verband,
 *  Ausgeglichenheit, …) und verschiebt nur zwischen "einer gewinnt" und
 *  "Gestellt"; veraenderung = Prozentpunkte P(Gestellt) gegenüber einer
 *  durchschnittlichen Paarung, mit Vorzeichen. */
export interface Beitrag {
  titel: string;
  unterzeile: string;
  richtung: "a" | "b" | "gestellt";
  staerke: number;
  veraenderung: number;
}

export interface Prognose {
  p: Record<Klasse, number>;
  quote: Record<Klasse, number>; // 1/p, informativ (FR-2, AK-2.3)
  beitraege: Beitrag[];
  unsicher: boolean; // FR-1 / AK-1.2
}
