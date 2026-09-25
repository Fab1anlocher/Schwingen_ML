// Clientseitige Logistic-Regression-Inferenz (§7, NFR-2: < 500 ms).
// Spiegelt pipeline/features._feature_vektor und pipeline/train exakt.

import type { ModelArtifact, Schwinger, Prognose, Klasse, Beitrag } from "./types";

const AKTUELLES_JAHR = new Date().getFullYear();

function diffOderNull(a: number | null, b: number | null): number {
  if (a === null || b === null) return 0;
  return a - b;
}

/** Spiegelt pipeline/schema.hat_portraet: Porträt über die Quelle, NICHT über
 *  den Kranzstatus (schlussgang.ch porträtiert nur Kranzer und besser, ein
 *  Kranzstatus-Test wäre zirkulär). */
export function hatPortraet(s: Schwinger): boolean {
  return (s.quellen ?? []).some((q) => q.includes("portraet"));
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

/** Baut den Merkmalsvektor A-vs-B (identisch zur Python-Pipeline,
 *  features._feature_vektor / feature_vektor_fuer_prognose).
 *
 *  Nach der Merkmalsversion DES MODELLS, nicht nach der neuesten: das
 *  ausgelieferte model.json kommt aus dem Repo und kann dem Code einen Lauf
 *  hinterherhinken. Ohne Versionsangabe gilt 1.
 *    1: Elo-Abstand / 100, Erfahrung als rohe Differenz, 13 Merkmale
 *    2: Elo-Abstand / Streuung der aktiven Ratings, Erfahrung logarithmisch,
 *       + Gestellt-Neigung (14 Merkmale) */
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
  const v2 = (model.config.merkmal_version ?? 1) >= 2;
  const skala = v2 ? (model.config.elo_streuung as number) : 100.0;

  const x = [
    (eloA - eloB) / skala, // rating_diff
    Math.abs(eloA - eloB) / skala, // rating_abstand
    a.form - b.form, // form_diff
    kranzA - kranzB, // kranz_diff
    diffOderNull(alterA, alterB), // alter_diff
    diffOderNull(a.gewicht_kg, b.gewicht_kg), // gewicht_diff
    diffOderNull(a.groesse_cm, b.groesse_cm), // groesse_diff
    v2 ? Math.log1p(nA) - Math.log1p(nB) : nA - nB, // erfahrung_diff
    a.teilverband && a.teilverband === b.teilverband ? 1 : 0, // same_teilverband
    schwungOverlap(a, b), // schwung_overlap
    (a.bevorzugte_schwuenge?.length ?? 0) - (b.bevorzugte_schwuenge?.length ?? 0), // schwung_count_diff
    kopfAnKopfA, // kopf_an_kopf
    (hatPortraet(a) ? 1 : 0) - (hatPortraet(b) ? 1 : 0), // portraet_diff
  ];
  if (v2) {
    // Fehlt die Neigung (Neuling, älteres Artefakt): Durchschnitt = neutral.
    const basis = model.config.gestellt_basis as number;
    const neigungA = a.gestellt_neigung ?? basis;
    const neigungB = b.gestellt_neigung ?? basis;
    x.push((neigungA + neigungB) / 2 - basis); // gestellt_neigung
  }
  return x;
}

/** Beruht dieses Merkmal für DIESE Paarung auf fehlenden Daten?
 *
 *  76 % des Kaders haben kein Porträt, also weder Physis noch Verband noch
 *  Schwünge noch Kranzstatus. Für sie liefert der Merkmalsvektor 0 bzw. einen
 *  Platzhalter -- das Modell rechnet damit korrekt, aber als GRUND für eine
 *  Prognose taugt ein solcher Wert nicht. Vorher erklärte die App etwa ein
 *  Porträt-gegen-Stub-Duell mit "Kranzstärke", obwohl der Stub schlicht
 *  kein Profil hat. Diese Merkmale erscheinen darum nur noch, wenn die Daten
 *  auf beiden Seiten vorliegen; der Datenunterschied selbst steht offen als
 *  portraet_diff da. Die Wahrscheinlichkeit ändert sich dadurch NICHT --
 *  nur die angezeigte Begründung. */
function beruhtAufFehlendenDaten(feat: string, a: Schwinger, b: Schwinger): boolean {
  switch (feat) {
    case "gewicht_diff":
      return a.gewicht_kg === null || b.gewicht_kg === null;
    case "groesse_diff":
      return a.groesse_cm === null || b.groesse_cm === null;
    case "alter_diff":
      return a.jahrgang === null || b.jahrgang === null;
    case "same_teilverband":
      return !a.teilverband || !b.teilverband;
    case "kranz_diff":
    case "schwung_overlap":
    case "schwung_count_diff":
      return !hatPortraet(a) || !hatPortraet(b);
    default:
      return false;
  }
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
  // NICHT "Frische": das Modell lernt aus den Daten das Gegenteil davon —
  // der ältere Schwinger gewinnt häufiger (empirisch 40.0 % vs. 29.1 %).
  // Der Titel muss richtungsneutral bleiben, die Richtung kommt aus dem Modell.
  alter_diff: { titel: "Alter", unter: "Altersunterschied in Jahren" },
  gewicht_diff: { titel: "Gewicht & Physis", unter: "Körpermasse" },
  groesse_diff: { titel: "Körpergrösse", unter: "Grössenunterschied" },
  erfahrung_diff: { titel: "Erfahrung", unter: "Anzahl Gänge" },
  same_teilverband: { titel: "Teilverband", unter: "Gleicher Verband" },
  schwung_overlap: { titel: "Ähnlicher Stil", unter: "Gemeinsame Schwünge" },
  schwung_count_diff: { titel: "Schwung-Vielfalt", unter: "Anzahl bevorzugter Schwünge" },
  kopf_an_kopf: { titel: "Direkte Duelle", unter: "Bisherige Begegnungen" },
  portraet_diff: { titel: "Datenlage", unter: "Profil mit Physis & Kranzstatus vorhanden" },
  gestellt_neigung: { titel: "Gestellt-Neigung", unter: "Wie oft beide bisher gestellt haben" },
};

/** Merkmale, die beim Tausch von A und B GLEICH bleiben (statt das Vorzeichen
 *  zu drehen). Sie können niemanden bevorzugen: das Modell hat für sie bei
 *  "Sieg A" und "Sieg B" exakt dasselbe Gewicht (Folge der Spiegelzeilen im
 *  Training) und verschiebt mit ihnen nur zwischen "einer gewinnt" und
 *  "Gestellt". Früher wurden sie wie alle anderen an p(Sieg A) gemessen und
 *  dem Gegner gutgeschrieben, sobald p(Sieg A) sank -- "Gleicher Verband:
 *  +7 %-Pkt. für B", obwohl auch B's Siegchance dadurch sank. */
const SYMMETRISCH = new Set(["rating_abstand", "same_teilverband", "schwung_overlap", "gestellt_neigung"]);

function unterzeile(feat: string, a: Schwinger, b: Schwinger): string {
  if (feat === "same_teilverband") {
    return a.teilverband === b.teilverband ? "Gleicher Verband" : "Verschiedene Verbände";
  }
  return BEITRAG_TEXT[feat]?.unter ?? "";
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
  kopfAnKopfA: number = 0
): Prognose {
  // Auf die Merkmale kürzen, die DIESES model.json kennt. Das ausgelieferte
  // Modell kommt aus dem Repo und kann dem Code einen Lauf hinterherhinken
  // (z.B. 12 Merkmale, während baueFeatures schon 13 liefert). Das geht nur
  // gut, weil neue Merkmale ausschliesslich HINTEN angehängt werden (s.
  // pipeline/features.FEATURE_NAMES) -- die ersten N stimmen dann überein.
  // Vorher klappte es nur zufällig: das überzählige z war NaN und wurde bloss
  // deshalb nie gelesen, weil die Koeffizientenzeilen kürzer waren.
  const x = baueFeatures(model, a, b, eloA, eloB, nA, nB, kopfAnKopfA).slice(
    0,
    model.features.length
  );
  const { mu, sigma } = model.standardisierung;
  const z = x.map((xi, i) => (xi - mu[i]) / (sigma[i] || 1));

  const probs = wahrscheinlichkeiten(model, z);
  const p: Record<Klasse, number> = {} as any;
  model.klassen.forEach((kl, i) => (p[kl] = probs[i]));

  // Quote = 1/p (informativ, FR-2 / AK-2.3).
  const quote: Record<Klasse, number> = {} as any;
  (Object.keys(p) as Klasse[]).forEach((kl) => (quote[kl] = 1 / Math.max(p[kl], 1e-6)));

  // Erklärbarkeit (FR-3): Gegenprobe je Merkmal -- was käme heraus, wenn
  // genau dieses Merkmal auf seinem Trainingsmittel stünde (z=0), alle
  // anderen unverändert? Bei Unterschiedsmerkmalen ist das Mittel 0 (die
  // Spiegelzeilen gleichen es aus), also "kein Unterschied zwischen den
  // beiden"; bei symmetrischen Merkmalen die durchschnittliche Paarung.
  // In Prozentpunkten, derselben Einheit wie die Zahlen oben auf der Seite.
  const iSiegA = model.klassen.indexOf("sieg_a");
  const iSiegB = model.klassen.indexOf("sieg_b");
  const iGestellt = model.klassen.indexOf("gestellt");
  const beitraege: Beitrag[] = model.features
    .map((feat, i) => ({ feat, i }))
    .filter(({ feat }) => !beruhtAufFehlendenDaten(feat, a, b))
    .map(({ feat, i }): Beitrag => {
      const zOhneMerkmal = z.slice();
      zOhneMerkmal[i] = 0;
      const ohne = wahrscheinlichkeiten(model, zOhneMerkmal);
      const titel = BEITRAG_TEXT[feat]?.titel ?? model.feature_labels[feat] ?? feat;
      const basis = { titel, unterzeile: unterzeile(feat, a, b) };
      if (SYMMETRISCH.has(feat)) {
        const d = (probs[iGestellt] - ohne[iGestellt]) * 100;
        return { ...basis, richtung: "gestellt", staerke: Math.abs(d), veraenderung: d };
      }
      // Gutgeschrieben wird dem, dessen EIGENE Siegchance steigt, und zwar
      // mit genau diesem Anstieg.
      const dA = (probs[iSiegA] - ohne[iSiegA]) * 100;
      const dB = (probs[iSiegB] - ohne[iSiegB]) * 100;
      const d = dA >= dB ? dA : dB;
      return { ...basis, richtung: dA >= dB ? "a" : "b", staerke: Math.max(d, 0), veraenderung: d };
    })
    .filter((c) => c.staerke > 0.1)
    .sort((x, y) => y.staerke - x.staerke)
    .slice(0, 6);

  const minG = model.config.min_gaenge_fuer_sicherheit;
  const unsicher = nA < minG || nB < minG;

  return { p, quote, beitraege, unsicher };
}
