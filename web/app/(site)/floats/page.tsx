import type { Metadata } from "next";
import { FloatIndex } from "@/components/float-index";
import { getFloats } from "@/lib/api";

export const revalidate = 600;
export const metadata: Metadata = {
  title: "Floats",
  description: "Every Argo float that reported in the Indian Ocean in the last 12 months.",
};

export default async function FloatsPage() {
  const floats = await getFloats().catch(() => []);
  return (
    <div className="mx-auto max-w-[1240px] px-4 pb-20 pt-10 sm:px-6">
      <h1 className="text-4xl font-semibold tracking-tighter md:text-5xl">Floats</h1>
      <p className="mt-3 max-w-[60ch] leading-relaxed text-ink-2">
        Every float that reported in the last 12 months. The swatch is its latest surface temperature. Open one to see
        where it drifted and what it measured on the way down.
      </p>
      <div className="mt-10">
        {floats.length ? (
          <FloatIndex floats={floats} />
        ) : (
          <p className="rounded-[var(--radius-card)] border border-dashed border-line p-10 text-center text-ink-2">
            The float list didn&apos;t load. The API may be waking up; refresh in a few seconds.
          </p>
        )}
      </div>
    </div>
  );
}
