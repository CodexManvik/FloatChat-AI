"use client";

import * as Plot from "@observablehq/plot";
import type { FeatureCollection } from "geojson";
import { useCallback, useEffect, useState } from "react";
import { loadLand } from "@/lib/land";
import { PlotFigure } from "./plot-figure";

export type MapPoint = { lat: number; lon: number; label: string; color?: string; group?: string };

/** A small equirectangular map fitted around the points, with land outlines. */
export function MiniMap({
  points,
  line = false,
  height = 260,
  minSpan = 0,
  label,
}: {
  points: MapPoint[];
  line?: boolean;
  height?: number;
  /** Show at least this many degrees around the points, for geographic context */
  minSpan?: number;
  label: string;
}) {
  const [land, setLand] = useState<FeatureCollection | null>(null);
  useEffect(() => {
    loadLand().then(setLand);
  }, []);

  const render = useCallback(
    (width: number) => {
      if (!land || !points.length) return null;
      const lats = points.map((p) => p.lat);
      const lons = points.map((p) => p.lon);
      // Pad by a fifth of the spread (at least 0.75 degrees) so small trajectories fill the map
      const pad = Math.max(0.75, 0.2 * Math.max(Math.max(...lons) - Math.min(...lons), Math.max(...lats) - Math.min(...lats)));
      let [w, e] = [Math.min(...lons) - pad, Math.max(...lons) + pad];
      let [s, n] = [Math.min(...lats) - pad, Math.max(...lats) + pad];
      if (e - w < minSpan) [w, e] = [(w + e) / 2 - minSpan / 2, (w + e) / 2 + minSpan / 2];
      if (n - s < minSpan * 0.6) [s, n] = [(s + n) / 2 - minSpan * 0.3, (s + n) / 2 + minSpan * 0.3];
      [s, n] = [Math.max(-89, s), Math.min(89, n)];
      // d3 reads polygons on the sphere: the ring must run clockwise or it means "everything but the box"
      const box = { type: "Polygon" as const, coordinates: [[[w, s], [w, n], [e, n], [e, s], [w, s]]] };
      return Plot.plot({
        width,
        height,
        projection: { type: "equirectangular", domain: box, inset: 4 },
        marks: [
          Plot.frame({ fill: "var(--water)", stroke: "var(--line)", rx: 10 }),
          Plot.geo(land, { fill: "var(--land)" }),
          Plot.graticule({ stroke: "var(--graticule)", strokeOpacity: 1 }),
          line
            ? Plot.line(points, { x: "lon", y: "lat", z: (d: MapPoint) => d.group ?? "", stroke: "var(--text-2)", strokeWidth: 1, strokeOpacity: 0.6, curve: "linear" })
            : null,
          Plot.dot(points, {
            x: "lon",
            y: "lat",
            r: line ? 2.5 : 4,
            fill: (d: MapPoint) => d.color ?? "var(--accent)",
            stroke: "var(--surface)",
            strokeWidth: 1,
            title: "label",
            tip: true,
          }),
        ],
      });
    },
    [land, points, line, height, minSpan],
  );

  return (
    <div style={{ minHeight: height }}>
      <PlotFigure render={render} label={label} />
    </div>
  );
}
