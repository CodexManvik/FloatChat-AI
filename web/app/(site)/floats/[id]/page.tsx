import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FloatViews } from "@/components/float-views";
import { getFloat, getTrack } from "@/lib/api";
import { formatDate, formatInt, formatNumber, formatPosition, parseDate } from "@/lib/format";
import { sensorsOf } from "@/lib/profiles";

export const revalidate = 600;

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Float ${id}`, description: `Trajectory, profiles and T-S diagram of Argo float ${id}.` };
}

export default async function FloatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [detail, track] = await Promise.all([getFloat(id).catch(() => null), getTrack(id).catch(() => [])]);
  if (!detail || !track.length) notFound();

  const info = detail.float_info;
  const latest = [...track].sort((a, b) => parseDate(b.profile_date).getTime() - parseDate(a.profile_date).getTime())[0];
  const facts = [
    { label: "Profiles", value: formatInt(detail.profile_summary.total_profiles) },
    { label: "Depth range", value: `${formatInt(detail.measurement_summary.min_depth)} to ${formatInt(detail.measurement_summary.max_depth)} m` },
    { label: "Mean temperature", value: `${formatNumber(detail.measurement_summary.avg_temp, 1)} °C` },
    { label: "Mean salinity", value: `${formatNumber(detail.measurement_summary.avg_sal, 2)} PSU` },
  ];

  return (
    <div className="mx-auto max-w-[1240px] px-4 pb-20 pt-8 sm:px-6">
      <Link href="/floats" className="inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft size={14} /> All floats
      </Link>
      <header className="mt-5 grid gap-8">
        <div>
          <h1 className="text-4xl font-semibold tracking-tighter md:text-5xl">
            Float <span className="tabular font-mono">{info.float_id}</span>
          </h1>
          <p className="mt-3 max-w-[64ch] leading-relaxed text-ink-2">
            {latest.region}. Last surfaced {formatDate(latest.profile_date)} at {formatPosition(latest.profile_lat, latest.profile_lon)}.
            Measures {sensorsOf(track).join(", ")}.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-4 border-y border-line py-5 sm:grid-cols-4">
          {facts.map((f) => (
            <div key={f.label}>
              <dt className="text-xs text-ink-2">{f.label}</dt>
              <dd className="tabular mt-0.5 font-mono text-lg">{f.value}</dd>
            </div>
          ))}
        </dl>
      </header>
      <div className="mt-10">
        <FloatViews id={info.float_id} track={track} />
      </div>
    </div>
  );
}
