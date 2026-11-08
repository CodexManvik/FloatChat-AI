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

export type ExportFormat = "csv" | "netcdf" | "ascii";
const EXTENSIONS: Record<ExportFormat, string> = { csv: "csv", netcdf: "nc", ascii: "txt" };

/** Download up to 50 profiles in a file format (the API's /export limit), saved by the browser. */
export async function downloadProfiles(profileIds: number[], format: ExportFormat, name: string): Promise<void> {
  const response = await fetch(`${API_URL}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, profile_ids: profileIds.slice(-50) }),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: `${name}.${EXTENSIONS[format]}` });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchTrack(id: string, signal?: AbortSignal): Promise<TrackPoint[]> {
  const response = await fetch(`${API_URL}/profiles/float/${encodeURIComponent(id)}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
