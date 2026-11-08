import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto grid min-h-[60dvh] max-w-[1240px] content-center px-4 py-20 sm:px-6">
      <p className="tabular font-mono text-sm text-muted">404</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tighter md:text-5xl">Nothing surfaced here.</h1>
      <p className="mt-4 max-w-[52ch] leading-relaxed text-ink-2">
        This page doesn&apos;t exist, or the float hasn&apos;t reported in the last 12 months.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/floats" className="rounded-full border border-line-strong px-5 py-2 text-sm hover:bg-surface-2">Browse floats</Link>
        <Link href="/chat" className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-accent-ink">Ask a question</Link>
      </div>
    </div>
  );
}
