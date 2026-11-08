import { parseDate } from "./format";
import type { Measurement, TrackPoint } from "./types";

export type Variable = "temperature" | "salinity" | "oxygen";

export const VARIABLES: Record<Variable, { label: string; unit: string; scheme: "thermal" | "haline" | "oxy" }> = {
  temperature: { label: "Temperature", unit: "°C", scheme: "thermal" },
  salinity: { label: "Salinity", unit: "PSU", scheme: "haline" },
  oxygen: { label: "Oxygen", unit: "µmol/kg", scheme: "oxy" },
};

/** The most recent `n` profile ids of a trajectory (oldest first). */
export function latestProfileIds(track: TrackPoint[], n: number): number[] {
  return [...track]
    .sort((a, b) => parseDate(a.profile_date).getTime() - parseDate(b.profile_date).getTime())
    .slice(-n)
    .map((p) => p.profile_id);
}

/** Measurements of one variable as {date, depth, value} points, skipping missing values. */
export function sectionPoints(rows: Measurement[], variable: Variable) {
  return rows
    .filter((r) => r[variable] != null && Number.isFinite(r[variable] as number))
    .map((r) => ({ date: parseDate(r.time), depth: r.depth, value: r[variable] as number }));
}

/** Mean of a variable at each standard depth (for comparing floats). */
export function meanProfile(rows: Measurement[], variable: Variable) {
  const sums = new Map<number, { total: number; n: number }>();
  for (const r of rows) {
    const v = r[variable];
    if (v == null || !Number.isFinite(v)) continue;
    const s = sums.get(r.depth) ?? { total: 0, n: 0 };
    s.total += v;
    s.n += 1;
    sums.set(r.depth, s);
  }
  return [...sums.entries()]
    .sort(([a], [b]) => a - b)
    .map(([depth, { total, n }]) => ({ depth, value: total / n, n }));
}

/** The rows of the most recent profile in a set of measurements. */
export function latestProfile(rows: Measurement[]): Measurement[] {
  if (!rows.length) return [];
  const latest = rows.reduce((a, b) => (parseDate(b.time) > parseDate(a.time) ? b : a));
  return rows.filter((r) => r.profile_id === latest.profile_id).sort((a, b) => a.depth - b.depth);
}

export function sensorsOf(track: TrackPoint[]): string[] {
  const any = (key: keyof TrackPoint) => track.some((p) => p[key]);
  return [
    "temperature",
    "salinity",
    ...(any("has_oxygen") ? ["oxygen"] : []),
    ...(any("has_chlorophyll") ? ["chlorophyll"] : []),
    ...(any("has_nitrate") ? ["nitrate"] : []),
    ...(any("has_ph") ? ["pH"] : []),
  ];
}
