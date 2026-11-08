import type { Metadata } from "next";
import { CompareView } from "@/components/compare-view";
import { getFloats } from "@/lib/api";

export const metadata: Metadata = {
  title: "Compare floats",
  description: "Overlay two Argo floats' trajectories, T-S diagrams and mean profiles.",
};

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ floats?: string }> }) {
  const { floats: param } = await searchParams;
  const floats = await getFloats().catch(() => []);
  const ids = floats.sort((a, b) => b.n_profiles - a.n_profiles).map((f) => f.float_id);
  const initial = (param ?? "").split(",").filter((id) => ids.includes(id)).slice(0, 2);
  // Suggest a contrasting second float: the most active one from another region
  if (initial.length === 1) {
    const region = floats.find((f) => f.float_id === initial[0])?.region;
    const other = floats.find((f) => f.region !== region);
    if (other) initial.push(other.float_id);
  }
  return (
    <div className="mx-auto max-w-[1240px] px-4 pb-20 pt-10 sm:px-6">
      <h1 className="text-4xl font-semibold tracking-tighter md:text-5xl">Compare floats</h1>
      <p className="mt-3 max-w-[60ch] leading-relaxed text-ink-2">
        Two floats, side by side: where they drifted, the water they sampled and how their profiles differ.
      </p>
      <div className="mt-10">
        <CompareView ids={ids} initial={initial} />
      </div>
    </div>
  );
}
