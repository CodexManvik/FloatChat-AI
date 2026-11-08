import { BENCHMARK_URL, SERVER_API_URL } from "./config";
import type { Benchmark, FloatDetail, FloatPoint, Measurement, Stats, TrackPoint } from "./types";

async function get<T>(path: string, revalidate: number): Promise<T> {
  const response = await fetch(`${SERVER_API_URL}${path}`, { next: { revalidate } });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

/** Server-side reads, cached by Next.js so pages render instantly and the API is called rarely. */
export const getStats = () => get<Stats>("/stats", 600);
export const getFloats = () => get<FloatPoint[]>("/floats", 600);
export const getTrack = (id: string) => get<TrackPoint[]>(`/profiles/float/${encodeURIComponent(id)}`, 600);

export async function getFloat(id: string): Promise<FloatDetail | null> {
  const detail = await get<FloatDetail | { error: string }>(`/float/${encodeURIComponent(id)}`, 600);
  return "error" in detail ? null : detail;
}

/** All depth levels of up to 200 profiles (the API's limit per request). */
export async function getProfiles(profileIds: number[]): Promise<Measurement[]> {
  const response = await fetch(`${SERVER_API_URL}/get_profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_ids: profileIds.slice(-200) }),
    next: { revalidate: 600 },
  });
  if (!response.ok) throw new Error(`/get_profiles: HTTP ${response.status}`);
  return response.json();
}

export async function getBenchmark(): Promise<Benchmark | null> {
  try {
    const response = await fetch(BENCHMARK_URL, { next: { revalidate: 86400 } });
    return response.ok ? ((await response.json()) as Benchmark) : null;
  } catch {
    return null;
  }
}
