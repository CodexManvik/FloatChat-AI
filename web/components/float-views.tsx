"use client";

import { ArrowsLeftRight, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { fetchProfiles } from "@/lib/client-api";
import { sample } from "@/lib/colors";
import { formatDate, parseDate } from "@/lib/format";
import { latestProfile, latestProfileIds, VARIABLES, type Variable } from "@/lib/profiles";
import type { Measurement, TrackPoint } from "@/lib/types";
import { ProfileChart, SectionChart, TSDiagram } from "./float-charts";
import { MiniMap } from "./mini-map";

const MAX_PROFILES = 80;

function Panel({ title, note, children, className = "" }: {
  title: string;
  note?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-[var(--radius-card)] border border-line bg-surface p-4 md:p-5 ${className}`}>
      <h2 className="text-base font-semibold tracking-tight">{title}</h2>
      {note && <p className="mt-1 text-sm text-ink-2">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Skeleton({ height = 320 }: { height?: number }) {
  return <div className="w-full animate-pulse rounded-xl bg-surface-2" style={{ height }} aria-label="Loading" />;
}

export function FloatViews({ id, track }: { id: string; track: TrackPoint[] }) {
  const [rows, setRows] = useState<Measurement[] | null>(null);
  const [error, setError] = useState(false);
  const [variable, setVariable] = useState<Variable>("temperature");

  useEffect(() => {
    const abort = new AbortController();
    fetchProfiles(latestProfileIds(track, MAX_PROFILES), abort.signal)
      .then(setRows)
      .catch(() => !abort.signal.aborted && setError(true));
    return () => abort.abort();
  }, [track]);

  const sorted = useMemo(
    () => [...track].sort((a, b) => parseDate(a.profile_date).getTime() - parseDate(b.profile_date).getTime()),
    [track],
  );
  const first = sorted[0] ? parseDate(sorted[0].profile_date).getTime() : 0;
  const span = sorted.length ? parseDate(sorted[sorted.length - 1].profile_date).getTime() - first || 1 : 1;
  const points = sorted.map((p) => ({
    lat: p.profile_lat,
    lon: p.profile_lon,
    label: `Cycle ${p.cycle_number}, ${formatDate(p.profile_date)}`,
    color: sample("deep", 0.15 + 0.75 * ((parseDate(p.profile_date).getTime() - first) / span)),
  }));

  const latest = rows ? latestProfile(rows) : [];
  const latestData = (v: Variable) =>
    latest.filter((r) => r[v] != null).map((r) => ({ depth: r.depth, value: r[v] as number, series: "Latest profile" }));
  const hasOxygen = rows?.some((r) => r.oxygen != null) ?? false;
  const variables: Variable[] = hasOxygen ? ["temperature", "salinity", "oxygen"] : ["temperature", "salinity"];
  const profileCount = rows ? new Set(rows.map((r) => r.profile_id)).size : 0;

  return (
    <div className="grid gap-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Panel title="Trajectory" note={`${track.length} surfacings, from light (first) to dark (latest).`}>
          <MiniMap points={points} line height={340} minSpan={3} label={`Trajectory of float ${id}`} />
        </Panel>
        <Panel
          title="Latest profile"
          note={latest[0] ? `Cycle ${latest[0].cycle_number}, ${formatDate(latest[0].time)}` : undefined}
        >
          {rows ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {(["temperature", "salinity"] as const).map((v) =>
                latestData(v).length ? (
                  <ProfileChart key={v} data={latestData(v)} variable={v} height={300} />
                ) : (
                  <p key={v} className="grid place-items-center rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">
                    No {VARIABLES[v].label.toLowerCase()} passed quality control in this profile.
                  </p>
                ),
              )}
            </div>
          ) : error ? null : (
            <Skeleton height={300} />
          )}
        </Panel>
      </div>

      {error && (
        <p className="flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink-2" role="alert">
          <WarningCircle size={16} weight="fill" className="text-warn" />
          The measurements didn&apos;t load. The API may be waking up; refresh in a few seconds.
        </p>
      )}

      <Panel
        title="Depth-time section"
        note={rows ? `The last ${profileCount} profiles, interpolated between surfacings. Dots are the measurements.` : undefined}
      >
        <div className="mb-4 flex flex-wrap gap-1.5" role="tablist" aria-label="Variable">
          {variables.map((v) => (
            <button
              key={v}
              role="tab"
              type="button"
              aria-selected={variable === v}
              onClick={() => setVariable(v)}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                variable === v ? "border-line-strong bg-surface-2 text-ink" : "border-line text-ink-2 hover:text-ink"
              }`}
            >
              {VARIABLES[v].label}
            </button>
          ))}
        </div>
        {rows ? <SectionChart rows={rows} variable={variable} /> : !error && <Skeleton height={360} />}
      </Panel>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="Temperature-salinity diagram" note="Each water mass has its own T-S signature; colour shows depth.">
          {rows ? <TSDiagram rows={rows} /> : !error && <Skeleton height={340} />}
        </Panel>
        <section className="flex flex-col justify-between gap-6 rounded-[var(--radius-card)] border border-line bg-surface-2/50 p-5">
          <div>
            <h2 className="text-base font-semibold tracking-tight">Compare with another float</h2>
            <p className="mt-1 max-w-[42ch] text-sm leading-relaxed text-ink-2">
              Overlay two floats&apos; T-S diagrams and mean profiles to see how their water differs.
            </p>
          </div>
          <Link
            href={`/compare?floats=${id}`}
            className="inline-flex w-fit items-center gap-2 rounded-full border border-line-strong bg-surface px-4 py-2 text-sm font-medium transition-colors hover:border-accent"
          >
            <ArrowsLeftRight size={16} /> Compare
          </Link>
        </section>
      </div>
    </div>
  );
}
