"use client";

import * as Plot from "@observablehq/plot";
import { ArrowsLeftRight } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useState } from "react";
import { fetchProfiles, fetchTrack } from "@/lib/client-api";
import { sample } from "@/lib/colors";
import { latestProfileIds, meanProfile } from "@/lib/profiles";
import type { Measurement, TrackPoint } from "@/lib/types";
import { ProfileChart } from "./float-charts";
import { MiniMap } from "./mini-map";
import { PlotFigure } from "./plot-figure";

// Two cmocean stops bright enough on both themes and distinct from the UI accent
const COLORS = [sample("haline", 0.62), sample("thermal", 0.48)];
const PROFILES_EACH = 40;

type Loaded = { id: string; track: TrackPoint[]; rows: Measurement[] };

function FloatPicker({ ids, value, onChange, label }: {
  ids: string[];
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  const id = useId();
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm text-ink-2">{label}</label>
      <input
        id={id}
        list={`${id}-list`}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
        inputMode="numeric"
        placeholder="Float number"
        className="tabular h-10 rounded-full border border-line-strong bg-surface px-4 font-mono text-sm outline-none placeholder:font-sans placeholder:text-muted focus:border-accent"
      />
      <datalist id={`${id}-list`}>
        {ids.map((f) => (
          <option key={f} value={f} />
        ))}
      </datalist>
    </div>
  );
}

function TSOverlay({ floats }: { floats: Loaded[] }) {
  const render = useCallback(
    (width: number) => {
      const data = floats.flatMap((f) =>
        f.rows.filter((r) => r.temperature != null && r.salinity != null).map((r) => ({ ...r, series: `Float ${f.id}` })),
      );
      if (!data.length) return null;
      const series = floats.map((f) => `Float ${f.id}`);
      return Plot.plot({
        width,
        height: 380,
        marginLeft: 48,
        grid: true,
        style: { background: "transparent" },
        x: { label: "Salinity (PSU)", nice: true },
        y: { label: "Temperature (°C)", nice: true },
        color: { domain: series, range: COLORS, legend: true },
        marks: [Plot.dot(data, { x: "salinity", y: "temperature", fill: "series", r: 1.8, fillOpacity: 0.6, tip: true })],
      });
    },
    [floats],
  );
  return <PlotFigure render={render} label="Temperature-salinity diagrams of both floats" />;
}

export function CompareView({ ids, initial }: { ids: string[]; initial: string[] }) {
  const router = useRouter();
  const [a, setA] = useState(initial[0] ?? "");
  const [b, setB] = useState(initial[1] ?? "");
  const [loaded, setLoaded] = useState<Loaded[] | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const ready = ids.includes(a) && ids.includes(b) && a !== b;

  useEffect(() => {
    if (!ready) return;
    const abort = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading state for the fetch below
    setStatus("loading");
    Promise.all(
      [a, b].map(async (id) => {
        const track = await fetchTrack(id, abort.signal);
        const rows = await fetchProfiles(latestProfileIds(track, PROFILES_EACH), abort.signal);
        return { id, track, rows };
      }),
    )
      .then((result) => {
        setLoaded(result);
        setStatus("idle");
        router.replace(`/compare?floats=${a},${b}`, { scroll: false });
      })
      .catch(() => !abort.signal.aborted && setStatus("error"));
    return () => abort.abort();
  }, [a, b, ready, router]);

  const colors = Object.fromEntries((loaded ?? []).map((f, i) => [`Float ${f.id}`, COLORS[i]]));
  const means = (variable: "temperature" | "salinity") =>
    (loaded ?? []).flatMap((f) => meanProfile(f.rows, variable).map((p) => ({ ...p, series: `Float ${f.id}` })));

  return (
    <div className="grid gap-6">
      <div className="grid items-end gap-4 rounded-[var(--radius-card)] border border-line bg-surface p-5 sm:grid-cols-[1fr_auto_1fr]">
        <FloatPicker ids={ids} value={a} onChange={setA} label="First float" />
        <ArrowsLeftRight size={18} className="mx-auto mb-3 hidden text-muted sm:block" aria-hidden />
        <FloatPicker ids={ids} value={b} onChange={setB} label="Second float" />
      </div>

      {!ready && (
        <p className="rounded-[var(--radius-card)] border border-dashed border-line p-10 text-center text-ink-2">
          {a && b && a === b ? "Pick two different floats." : "Pick two floats from the list to compare their water."}
        </p>
      )}
      {status === "error" && (
        <p className="rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink-2" role="alert">
          The measurements didn&apos;t load. The API may be waking up; try again in a few seconds.
        </p>
      )}
      {ready && status === "loading" && <div className="h-96 animate-pulse rounded-[var(--radius-card)] bg-surface-2" aria-label="Loading" />}

      {ready && loaded && status !== "loading" && (
        <>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="rounded-[var(--radius-card)] border border-line bg-surface p-5">
              <h2 className="text-base font-semibold tracking-tight">Where they drifted</h2>
              <div className="mt-4">
                <MiniMap
                  line
                  height={380}
                  label="Trajectories of both floats"
                  points={loaded.flatMap((f, i) =>
                    f.track.map((p) => ({ lat: p.profile_lat, lon: p.profile_lon, label: `Float ${f.id}, cycle ${p.cycle_number}`, color: COLORS[i], group: f.id })),
                  )}
                />
              </div>
            </section>
            <section className="rounded-[var(--radius-card)] border border-line bg-surface p-5">
              <h2 className="text-base font-semibold tracking-tight">Temperature-salinity</h2>
              <p className="mt-1 text-sm text-ink-2">Separate clouds mean different water masses.</p>
              <div className="mt-4">
                <TSOverlay floats={loaded} />
              </div>
            </section>
          </div>
          <section className="rounded-[var(--radius-card)] border border-line bg-surface p-5">
            <h2 className="text-base font-semibold tracking-tight">Mean profiles</h2>
            <p className="mt-1 text-sm text-ink-2">Averaged over each float&apos;s last {PROFILES_EACH} profiles.</p>
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              <ProfileChart data={means("temperature")} variable="temperature" colors={colors} height={340} />
              <ProfileChart data={means("salinity")} variable="salinity" colors={colors} height={340} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
