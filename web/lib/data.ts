// Laden der Artefakte (clientseitig aus /public/data, §7).

import type {
  ModelArtifact,
  RatingsArtifact,
  Schwinger,
  FeatureImportanceEntry,
  EventsArtifact,
  KantoneArtifact,
} from "./types";

async function ladeJson<T>(pfad: string): Promise<T> {
  const res = await fetch(pfad, { cache: "no-store" });
  if (!res.ok) throw new Error(`Konnte ${pfad} nicht laden (${res.status})`);
  return res.json();
}

export const ladeModel = () => ladeJson<ModelArtifact>("/data/model.json");
export const ladeRatings = () => ladeJson<RatingsArtifact>("/data/ratings.json");
export const ladeEvents = () => ladeJson<EventsArtifact>("/data/events.json");
export const ladeKantone = () => ladeJson<KantoneArtifact>("/data/kantone.json");

export async function ladeSchwinger(): Promise<Schwinger[]> {
  const obj = await ladeJson<{ schwinger: Schwinger[] }>("/data/schwinger.json");
  return obj.schwinger;
}

export async function ladeFeatureImportance(): Promise<FeatureImportanceEntry[]> {
  const obj = await ladeJson<{ features: FeatureImportanceEntry[] }>(
    "/data/feature_importance.json"
  );
  return obj.features;
}
