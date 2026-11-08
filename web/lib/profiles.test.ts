import { describe, expect, it } from "vitest";
import { latestProfile, latestProfileIds, meanProfile, sectionPoints, sensorsOf } from "./profiles";
import type { Measurement, TrackPoint } from "./types";

const m = (profile_id: number, time: string, depth: number, temperature: number | null, salinity: number | null = 35): Measurement => ({
  id: profile_id * 100 + depth, time, lat: 0, lon: 70, depth, temperature, salinity, oxygen: null, chlorophyll: null,
  nitrate: null, ph: null, float_id: "1", profile_id, cycle_number: profile_id, region: "Arabian Sea",
});
const t = (profile_id: number, profile_date: string, extra: Partial<TrackPoint> = {}): TrackPoint => ({
  profile_id, float_id: "1", cycle_number: profile_id, profile_date, profile_lat: 0, profile_lon: 70, region: "Arabian Sea",
  n_levels: 24, has_oxygen: false, has_chlorophyll: false, has_nitrate: false, has_ph: false, avg_temp: 20, avg_sal: 35,
  min_depth: 5, max_depth: 2000, ...extra,
});

describe("profile shaping", () => {
  it("picks the latest profile ids in time order", () => {
    const track = [t(3, "2026-03-01T00:00:00"), t(1, "2026-01-01T00:00:00"), t(2, "2026-02-01T00:00:00")];
    expect(latestProfileIds(track, 2)).toEqual([2, 3]);
  });

  it("builds section points without missing values", () => {
    const rows = [m(1, "2026-01-01T00:00:00", 5, 28), m(1, "2026-01-01T00:00:00", 10, null)];
    expect(sectionPoints(rows, "temperature")).toEqual([{ date: new Date("2026-01-01T00:00:00Z"), depth: 5, value: 28 }]);
  });

  it("averages each depth across profiles", () => {
    const rows = [m(1, "2026-01-01T00:00:00", 5, 28), m(2, "2026-02-01T00:00:00", 5, 26), m(2, "2026-02-01T00:00:00", 10, 25)];
    expect(meanProfile(rows, "temperature")).toEqual([{ depth: 5, value: 27, n: 2 }, { depth: 10, value: 25, n: 1 }]);
  });

  it("returns the most recent profile sorted by depth", () => {
    const rows = [m(1, "2026-01-01T00:00:00", 5, 28), m(2, "2026-02-01T00:00:00", 10, 25), m(2, "2026-02-01T00:00:00", 5, 26)];
    expect(latestProfile(rows).map((r) => r.depth)).toEqual([5, 10]);
    expect(latestProfile([])).toEqual([]);
  });

  it("lists the sensors a float has", () => {
    expect(sensorsOf([t(1, "2026-01-01T00:00:00"), t(2, "2026-02-01T00:00:00", { has_oxygen: true, has_ph: true })]))
      .toEqual(["temperature", "salinity", "oxygen", "pH"]);
  });
});
