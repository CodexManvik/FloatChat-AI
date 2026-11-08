"use client";

import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { scale } from "@/lib/colors";
import { formatDate, formatInt, formatNumber } from "@/lib/format";
import type { FloatPoint } from "@/lib/types";

const PAGE = 48;

export function FloatIndex({ floats }: { floats: FloatPoint[] }) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<string | null>(null);
  const [bgcOnly, setBgcOnly] = useState(false);
  const [shown, setShown] = useState(PAGE);

  const regions = useMemo(() => {
    const counts = new Map<string, number>();
    floats.forEach((f) => counts.set(f.region, (counts.get(f.region) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [floats]);
  const temps = floats.map((f) => f.surface_temperature).filter((t): t is number => t != null);
  const color = scale("thermal", Math.min(...temps), Math.max(...temps));

  const list = useMemo(
    () =>
      floats
        .filter((f) => (!region || f.region === region) && (!bgcOnly || f.is_bgc) && f.float_id.includes(query.trim()))
        .sort((a, b) => b.n_profiles - a.n_profiles),
    [floats, region, bgcOnly, query],
  );

  const pill = (active: boolean) =>
    `rounded-full border px-3 py-1 text-sm transition-colors ${
      active ? "border-line-strong bg-surface-2 text-ink" : "border-line text-ink-2 hover:text-ink"
    }`;

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <label className="flex h-10 w-full items-center gap-2 rounded-full border border-line-strong bg-surface px-4 focus-within:border-accent lg:w-72">
          <MagnifyingGlass size={16} className="text-muted" aria-hidden />
          <span className="sr-only">Find a float by its number</span>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value.replace(/\D/g, ""));
              setShown(PAGE);
            }}
            inputMode="numeric"
            placeholder="Float number"
            className="tabular min-w-0 flex-1 bg-transparent font-mono text-sm outline-none placeholder:font-sans placeholder:text-muted"
          />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Region">
          <button type="button" className={pill(!region)} aria-pressed={!region} onClick={() => setRegion(null)}>
            All regions
          </button>
          {regions.map(([name, n]) => (
            <button key={name} type="button" className={pill(region === name)} aria-pressed={region === name} onClick={() => { setRegion(name); setShown(PAGE); }}>
              {name} <span className="tabular text-muted">{n}</span>
            </button>
          ))}
          <button type="button" className={pill(bgcOnly)} aria-pressed={bgcOnly} onClick={() => setBgcOnly((b) => !b)}>
            BGC floats only
          </button>
        </div>
      </div>

      <p className="mt-6 text-sm text-ink-2">
        {formatInt(list.length)} {list.length === 1 ? "float" : "floats"}, most active first
      </p>

      {list.length === 0 ? (
        <p className="mt-6 rounded-[var(--radius-card)] border border-dashed border-line p-10 text-center text-ink-2">
          No floats match. Try another number or region.
        </p>
      ) : (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {list.slice(0, shown).map((f) => (
            <li key={f.float_id}>
              <Link
                href={`/floats/${f.float_id}`}
                className="group flex items-center gap-4 rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 transition-colors hover:border-line-strong"
              >
                <span
                  className="size-9 shrink-0 rounded-lg border border-line"
                  style={{ background: color(f.surface_temperature) }}
                  title={`Surface ${formatNumber(f.surface_temperature, 1)} °C`}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="tabular font-mono text-[15px]">{f.float_id}</span>
                    {f.is_bgc && <span className="rounded-md border border-line px-1.5 text-[11px] text-ink-2">BGC</span>}
                  </span>
                  <span className="tabular block truncate text-xs text-ink-2">
                    {f.region}, {formatInt(f.n_profiles)} profiles, last {formatDate(f.last_profile)}
                  </span>
                </span>
                <span className="tabular hidden font-mono text-sm text-ink-2 sm:block">{formatNumber(f.surface_temperature, 1)}°</span>
                <ArrowRight size={14} className="shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {list.length > shown && (
        <div className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={() => setShown((n) => n + PAGE)}
            className="rounded-full border border-line-strong px-5 py-2 text-sm hover:bg-surface-2"
          >
            Show {Math.min(PAGE, list.length - shown)} more
          </button>
        </div>
      )}
    </div>
  );
}
