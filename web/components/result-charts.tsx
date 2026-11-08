"use client";

import * as Plot from "@observablehq/plot";
import { useCallback, useMemo } from "react";
import { CMOCEAN, sample } from "@/lib/colors";
import { parseDate } from "@/lib/format";
import { PlotFigure } from "./plot-figure";

type Row = Record<string, unknown>;

// Data colours come from the cmocean scales, never the UI accent
const TEMP = sample("thermal", 0.62);
const SALT = sample("haline", 0.45);
const OXY = sample("deep", 0.55);

const num = (v: unknown) => (typeof v === "number" ? v : v == null ? NaN : Number(v));

function base(width: number, height = 320): Plot.PlotOptions {
  return { width, height, marginLeft: 52, marginBottom: 40, style: { background: "transparent" }, grid: true };
}

type DepthPoint = { depth: number; t: number; s: number };

function depthPanel(width: number, data: DepthPoint[], key: "t" | "s", label: string, stroke: string) {
  const points = data.filter((d) => Number.isFinite(d[key]));
  return Plot.plot({
    ...base(width, 360),
    y: { reverse: true, label: "Depth (m)" },
    x: { label, nice: true },
    marks: [
      Plot.line(points, { x: key, y: "depth", stroke, strokeWidth: 2, curve: "monotone-y" }),
      Plot.dot(points, { x: key, y: "depth", fill: stroke, r: 2.5, tip: true }),
    ],
  });
}

function DepthProfiles({ rows }: { rows: Row[] }) {
  const data = useMemo(
    () => rows.map((r) => ({ depth: num(r.depth), t: num(r.avg_temperature), s: num(r.avg_salinity) })),
    [rows],
  );
  const temp = useCallback((w: number) => depthPanel(w, data, "t", "Temperature (°C)", TEMP), [data]);
  const salt = useCallback((w: number) => depthPanel(w, data, "s", "Salinity (PSU)", SALT), [data]);
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <PlotFigure render={temp} label="Average temperature by depth" />
      <PlotFigure render={salt} label="Average salinity by depth" />
    </div>
  );
}

function Bars({ rows, x, y, label, color, scheme }: {
  rows: Row[]; x: string; y: string; label: string; color?: string; scheme?: keyof typeof CMOCEAN;
}) {
  const render = useCallback(
    (width: number) => {
      const data = rows.map((r) => ({ ...r, [y]: num(r[y]) }));
      return Plot.plot({
        ...base(width, 300),
        marginBottom: 56,
        x: { label: null, tickRotate: data.length > 5 ? -20 : 0 },
        y: { label, nice: true },
        color: scheme ? { type: "linear", range: [...CMOCEAN[scheme]].slice(1), interpolate: "rgb" } : undefined,
        marks: [
          Plot.barY(data, { x, y, fill: scheme ? y : color, rx: 4, tip: true, sort: { x: "-y" } }),
          Plot.ruleY([0], { stroke: "var(--line-strong)" }),
        ],
      });
    },
    [rows, x, y, label, color, scheme],
  );
  return <PlotFigure render={render} label={label} />;
}

function MonthlyTrend({ rows }: { rows: Row[] }) {
  const render = useCallback(
    (width: number) => {
      const data = rows.map((r) => ({ month: parseDate(String(r.month)), t: num(r.avg_temperature) }));
      return Plot.plot({
        ...base(width, 300),
        x: { label: null, type: "utc" },
        y: { label: "Temperature (°C)", nice: true },
        marks: [
          Plot.line(data, { x: "month", y: "t", stroke: TEMP, strokeWidth: 2, curve: "monotone-x" }),
          Plot.dot(data, { x: "month", y: "t", fill: TEMP, r: 3, tip: true }),
        ],
      });
    },
    [rows],
  );
  return <PlotFigure render={render} label="Monthly average temperature" />;
}

function TopFloats({ rows }: { rows: Row[] }) {
  const render = useCallback(
    (width: number) => {
      const data = rows.slice(0, 15).map((r) => ({ float: String(r.float_id), n: num(r.total_profiles), t: num(r.avg_temperature) }));
      return Plot.plot({
        ...base(width, Math.max(220, data.length * 22 + 40)),
        marginLeft: 72,
        grid: false,
        x: { label: "Profiles", nice: true, grid: true },
        y: { label: null },
        color: { type: "linear", range: [...CMOCEAN.thermal].slice(1), interpolate: "rgb", legend: false },
        marks: [Plot.barX(data, { y: "float", x: "n", fill: "t", rx: 3, sort: { y: "-x" }, tip: true })],
      });
    },
    [rows],
  );
  return <PlotFigure render={render} label="Most active floats" />;
}

/** The chart that fits an analysis, or nothing when a table says it better. */
export function ResultChart({ intent, rows }: { intent: string | null; rows: Row[] }) {
  if (!rows.length) return null;
  const has = (col: string) => col in rows[0];
  switch (intent) {
    case "avg_by_depth":
      return has("depth") ? <DepthProfiles rows={rows} /> : null;
    case "regional_comparison":
      return <Bars rows={rows} x="region" y="avg_temperature" label="Temperature, upper 100 m (°C)" scheme="thermal" />;
    case "depth_ranges":
      return <Bars rows={rows} x="depth_range" y="avg_temperature" label="Temperature (°C)" scheme="thermal" />;
    case "temporal_trends":
      return has("month") ? <MonthlyTrend rows={rows} /> : null;
    case "float_summary":
      return has("float_id") ? <TopFloats rows={rows} /> : null;
    case "bgc_analysis":
      return has("avg_oxygen") ? <Bars rows={rows} x="ocean_zone" y="avg_oxygen" label="Dissolved oxygen (µmol/kg)" color={OXY} /> : null;
    default:
      return null;
  }
}

export function DataTable({ rows, max = 50 }: { rows: Row[]; max?: number }) {
  if (!rows.length) return null;
  const columns = Object.keys(rows[0]);
  const show = (v: unknown) =>
    typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString("en-US") : v.toFixed(3)) : v == null ? "" : String(v);
  return (
    <div className="max-h-80 overflow-auto rounded-xl border border-line">
      <table className="tabular w-full text-left text-[13px]">
        <thead className="sticky top-0 bg-surface-2 text-ink-2">
          <tr>
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">{c.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-[12px]">
          {rows.slice(0, max).map((row, i) => (
            <tr key={i} className="border-t border-line">
              {columns.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-1.5">{show(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > max && <p className="border-t border-line px-3 py-2 text-xs text-muted">Showing {max} of {rows.length} rows.</p>}
    </div>
  );
}
