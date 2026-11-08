"use client";

import * as Plot from "@observablehq/plot";
import type { FeatureCollection } from "geojson";
import { useCallback, useEffect, useState } from "react";
import { loadLand } from "@/lib/land";
import { PlotFigure } from "./plot-figure";

export type MapPoint = { lat: number; lon: number; label: string; color?: string };

/** A small equirectangular map fitted around the points, with land outlines. */
export function MiniMap({
  points,
  line = false,
  height = 260,
  label,
}: {
  points: MapPoint[];
  line?: boolean;
  height?: number;
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
      const pad = 6;
      const box = {
        type: "Polygon" as const,
        coordinates: [[
          [Math.min(...lons) - pad, Math.min(...lats) - pad], [Math.max(...lons) + pad, Math.min(...lats) - pad],
          [Math.max(...lons) + pad, Math.max(...lats) + pad], [Math.min(...lons) - pad, Math.max(...lats) + pad],
          [Math.min(...lons) - pad, Math.min(...lats) - pad],
        ]],
      };
      return Plot.plot({
        width,
        height,
        projection: { type: "equirectangular", domain: box, inset: 4 },
        marks: [
          Plot.frame({ fill: "var(--water)", stroke: "var(--line)", rx: 10 }),
          Plot.geo(land, { fill: "var(--land)" }),
          Plot.graticule({ stroke: "var(--graticule)", strokeOpacity: 1 }),
          line ? Plot.line(points, { x: "lon", y: "lat", stroke: "var(--text-2)", strokeWidth: 1, strokeOpacity: 0.6, curve: "linear" }) : null,
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
    [land, points, line, height],
  );

  return (
    <div style={{ minHeight: height }}>
      <PlotFigure render={render} label={label} />
    </div>
  );
}
