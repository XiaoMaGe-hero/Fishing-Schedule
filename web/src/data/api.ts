// The only file that fetches data. Components never call the network themselves.
import { DATA_BASE_URL } from "../config";
import type { Conditions, Meta, Recommendations, RiverFlow } from "./generated/types";

export class DataError extends Error {}

async function getJson<T>(path: string): Promise<T> {
  if (!DATA_BASE_URL) throw new DataError("not-configured");
  let response: Response;
  try {
    // the bucket sits behind a CDN; a short-lived query string keeps a phone from showing an old copy for hours
    response = await fetch(`${DATA_BASE_URL}/${path}?t=${Math.floor(Date.now() / 300_000)}`);
  } catch {
    throw new DataError("network");
  }
  if (!response.ok) throw new DataError(`http-${response.status}`);
  const data = (await response.json()) as { schema_version?: number };
  if (data.schema_version !== 1) throw new DataError("unknown-schema");
  return data as T;
}

export const fetchConditions = (spotId: string) => getJson<Conditions>(`conditions/${spotId}.json`);
export const fetchRecommendations = () => getJson<Recommendations>("recommendations.json");
export const fetchMeta = () => getJson<Meta>("meta.json");
export const fetchRiverFlow = () => getJson<RiverFlow>("river_flow.json");
