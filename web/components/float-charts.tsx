"use client";

import * as Plot from "@observablehq/plot";
import { useCallback } from "react";
import { CMOCEAN, sample } from "@/lib/colors";
import { sectionPoints, VARIABLES, type Variable } from "@/lib/profiles";
import type { Measurement } from "@/lib/types";
import { PlotFigure } from "./plot-figure";

const scheme = (name: keyof typeof CMOCEAN, skipDark = false) => ({
  type: "linear" as const,
  range: skipDark ? [...CMOCEAN[name]].slice(1) : [...CMOCEAN[name]],
  interpolate: "rgb" as const,
});

/** Depth-time section: one variable interpolated between profiles (the classic oceanographer's view). */
export function SectionChart({ rows, variable }: { rows: Measurement[]; variable: Variable }) {
  const render = useCallback(
    (width: number) => {
      const points = sectionPoints(rows, variable);
      if (points.length < 3) return null;
      const meta = VARIABLES[variable];
      return Plot.plot({
        width,
        height: 360,
        marginLeft: 52,
        marginBottom: 36,
        style: { background: "transparent" },
        x: { type: "utc", label: null },
        // Square-root depth gives the upper ocean, where most structure is, room to show
        y: {
          type: "sqrt",
          reverse: true,
          label: "Depth (m)",
          domain: [0, Math.max(...points.map((p) => p.depth))],
          ticks: [0, 50, 100, 200, 400, 700, 1000, 1500, 2000],
        },
        color: { ...scheme(meta.scheme, variable === "oxygen" ? false : true), legend: true, label: `${meta.label} (${meta.unit})` },
        marks: [
          Plot.raster(points, { x: "date", y: "depth", fill: "value", interpolate: "barycentric", pixelSize: 2 }),
          Plot.dot(points, { x: "date", y: "depth", r: 0.6, fill: "currentColor", fillOpacity: 0.25 }),
          Plot.frame({ stroke: "var(--line)" }),
        ],
      });
    },
    [rows, variable],
  );
  return <PlotFigure render={render} label={`${VARIABLES[variable].label} by depth and date`} />;
}

/** Temperature-salinity diagram: every measurement, coloured by depth. */
export function TSDiagram({ rows }: { rows: Measurement[] }) {
  const render = useCallback(
    (width: number) => {
      const points = rows.filter((r) => r.temperature != null && r.salinity != null);
      if (!points.length) return null;
      return Plot.plot({
        width,
        height: 340,
        marginLeft: 48,
        style: { background: "transparent" },
        grid: true,
        x: { label: "Salinity (PSU)", nice: true },
        y: { label: "Temperature (°C)", nice: true },
        color: { ...scheme("deep"), legend: true, label: "Depth (m)" },
        marks: [Plot.dot(points, { x: "salinity", y: "temperature", fill: "depth", r: 1.8, fillOpacity: 0.85, tip: true })],
      });
    },
    [rows],
  );
  return <PlotFigure render={render} label="Temperature-salinity diagram" />;
}

const LINE: Record<Variable, string> = {
  temperature: sample("thermal", 0.62),
  salinity: sample("haline", 0.45),
  oxygen: sample("deep", 0.55),
};

/** One or more vertical profiles of a variable (series keyed by `series`). */
export function ProfileChart({
  data,
  variable,
  height = 320,
  colors,
}: {
  data: { depth: number; value: number; series: string }[];
  variable: Variable;
  height?: number;
  colors?: Record<string, string>;
}) {
  const render = useCallback(
    (width: number) => {
      if (!data.length) return null;
      const meta = VARIABLES[variable];
      const series = [...new Set(data.map((d) => d.series))];
      return Plot.plot({
        width,
        height,
        marginLeft: 52,
        style: { background: "transparent" },
        grid: true,
        y: { reverse: true, label: "Depth (m)" },
        x: { label: `${meta.label} (${meta.unit})`, nice: true },
        color: colors
          ? { domain: series, range: series.map((s) => colors[s]), legend: series.length > 1 }
          : { domain: series, range: [LINE[variable]] },
        marks: [
          Plot.line(data, { x: "value", y: "depth", z: "series", stroke: "series", strokeWidth: 2, curve: "monotone-y" }),
          Plot.dot(data, { x: "value", y: "depth", fill: "series", r: 2.2, tip: true }),
        ],
      });
    },
    [data, variable, height, colors],
  );
  return <PlotFigure render={render} label={`${VARIABLES[variable].label} profile`} />;
}
