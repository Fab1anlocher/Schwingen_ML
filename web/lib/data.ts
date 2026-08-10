// Laden der Artefakte (clientseitig aus /public/data, §7).

import type {
  ModelArtifact,
  GbmModel,
  RatingsArtifact,
  Schwinger,
  FeatureImportanceEntry,
  EventsArtifact,
} from "./types";

async function ladeJson<T>(pfad: string): Promise<T> {
  const res = await fetch(pfad, { cache: "no-store" });
  if (!res.ok) throw new Error(`Konnte ${pfad} nicht laden (${res.status})`);
  return res.json();
}

export const ladeModel = () => ladeJson<ModelArtifact>("/data/model.json");
export const ladeRatings = () => ladeJson<RatingsArtifact>("/data/ratings.json");
export const ladeEvents = () => ladeJson<EventsArtifact>("/data/events.json");

/** GBM-Modell laden; null, falls (noch) nicht vorhanden. */
export async function ladeGbm(): Promise<GbmModel | null> {
  try {
    return await ladeJson<GbmModel>("/data/model_gbm.json");
  } catch {
    return null;
  }
}

export async function ladeSchwinger(): Promise<Schwinger[]> {
  const obj = await ladeJson<{ schwinger: Schwinger[] }>("/data/schwinger.json");
  return obj.schwinger;
}

export async function ladeFeatureImportance(): Promise<{
  lr: FeatureImportanceEntry[];
  gbm: FeatureImportanceEntry[];
}> {
  const obj = await ladeJson<{
    features: FeatureImportanceEntry[];
    features_gbm?: FeatureImportanceEntry[];
  }>("/data/feature_importance.json");
  return { lr: obj.features, gbm: obj.features_gbm ?? [] };
}
