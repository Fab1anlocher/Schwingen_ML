// Laden der Artefakte (clientseitig aus /public/data, §7).

import type {
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
  FeatureImportanceEntry,
  EventsArtifact,
  KantoneArtifact,
  GauverbaendeArtifact,
  BenchmarkArtifact,
  ClusterArtifact,
  SimulationBacktest,
} from "./types";
import type { VerlaufLauf } from "@/components/VerlaufDiagramm";

async function ladeJson<T>(pfad: string): Promise<T> {
  const res = await fetch(pfad, { cache: "no-store" });
  if (!res.ok) throw new Error(`Konnte ${pfad} nicht laden (${res.status})`);
  return res.json();
}

export const ladeModel = () => ladeJson<ModelArtifact>("/data/model.json");
export const ladeRatings = () => ladeJson<RatingsArtifact>("/data/ratings.json");
export const ladeEvents = () => ladeJson<EventsArtifact>("/data/events.json");
export const ladeKantone = () => ladeJson<KantoneArtifact>("/data/kantone.json");
export const ladeGauverbaende = () => ladeJson<GauverbaendeArtifact>("/data/gauverbaende.json");
export const ladeBenchmark = () => ladeJson<BenchmarkArtifact>("/data/benchmark.json");
export const ladeCluster = () => ladeJson<ClusterArtifact>("/data/cluster.json");
/** Fehlt, solange kein echter Pipeline-Lauf mit Ranglisten stattgefunden hat. */
export const ladeSimulationBacktest = () =>
  ladeJson<SimulationBacktest>("/data/simulation_backtest.json").catch(() => null);

export async function ladeSchwinger(): Promise<Schwinger[]> {
  const obj = await ladeJson<{ schwinger: Schwinger[] }>("/data/schwinger.json");
  return obj.schwinger;
}

/** Merkmalswichtigkeit samt Messart: "koeffizient" (LR) oder "permutation"
 *  (Boosting: Anstieg des Log-Loss ohne das Merkmal). Ältere Artefakte ohne
 *  Angabe stammen von der LR. */
export async function ladeFeatureImportance(): Promise<{
  art: "koeffizient" | "permutation";
  features: FeatureImportanceEntry[];
}> {
  const obj = await ladeJson<{ art?: "koeffizient" | "permutation"; features: FeatureImportanceEntry[] }>(
    "/data/feature_importance.json"
  );
  return { art: obj.art ?? "koeffizient", features: obj.features };
}

/** Verlauf der Modellgüte je Tag (report_verlauf.json, Roadmap T1); leer, wenn
 *  die Datei (noch) fehlt. */
export async function ladeVerlauf(): Promise<VerlaufLauf[]> {
  try {
    const obj = await ladeJson<{ laeufe: VerlaufLauf[] }>("/data/report_verlauf.json");
    return obj.laeufe ?? [];
  } catch {
    return [];
  }
}
