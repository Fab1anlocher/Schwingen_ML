// Kopf-an-Kopf-Historie laden + zur geglätteten Bilanz verdichten. Spiegelt
// pipeline/features.py::_kopf_an_kopf_vorteil exakt (gleiches K, gleiche
// Formel) — muss synchron bleiben, sonst weicht Live-Prognose vom Modell ab.

import type { Klasse } from "./types";

export interface H2HTreffer {
  event_id: string;
  ergebnis: Klasse;
}

/** Lädt die Historie und spiegelt das Ergebnis direkt auf die gewünschte A/B-Reihenfolge
 * (die API liefert es relativ zur kanonisch kleineren ID, s. web/app/api/kopf-an-kopf). */
export async function ladeKopfAnKopf(aId: string, bId: string): Promise<H2HTreffer[]> {
  const res = await fetch(`/api/kopf-an-kopf?a=${encodeURIComponent(aId)}&b=${encodeURIComponent(bId)}`);
  const daten = await res.json();
  const treffer: H2HTreffer[] = daten.treffer ?? [];
  if (aId < bId) return treffer;
  return treffer.map((t) => ({
    ...t,
    ergebnis: t.ergebnis === "sieg_a" ? "sieg_b" : t.ergebnis === "sieg_b" ? "sieg_a" : "gestellt",
  }));
}

const KOPF_AN_KOPF_K = 2.0;

/** Geglättete Bilanz aus A's Sicht: ~0 ohne Historie, sonst Richtung ±1
 * (Empirical-Bayes-Glättung gegen 0.5, identisch zu pipeline/features.py). */
export function kopfAnKopfVorteilA(treffer: H2HTreffer[]): number {
  if (treffer.length === 0) return 0;
  const summe = treffer.reduce(
    (s, t) => s + (t.ergebnis === "sieg_a" ? 1 : t.ergebnis === "gestellt" ? 0.5 : 0),
    0
  );
  const quote = (summe + KOPF_AN_KOPF_K * 0.5) / (treffer.length + KOPF_AN_KOPF_K);
  return 2 * (quote - 0.5);
}
