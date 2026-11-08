import { API_URL } from "./config";
import type { Measurement, TrackPoint } from "./types";

/** Browser-side reads (the visitor's own IP counts against the API's limits). */
export async function fetchProfiles(profileIds: number[], signal?: AbortSignal): Promise<Measurement[]> {
  const response = await fetch(`${API_URL}/get_profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_ids: profileIds.slice(-200) }),
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function fetchTrack(id: string, signal?: AbortSignal): Promise<TrackPoint[]> {
  const response = await fetch(`${API_URL}/profiles/float/${encodeURIComponent(id)}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
