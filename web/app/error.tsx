"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto grid min-h-[60dvh] max-w-[1240px] content-center px-4 py-20 sm:px-6">
      <h1 className="text-4xl font-semibold tracking-tighter md:text-5xl">The data didn&apos;t load.</h1>
      <p className="mt-4 max-w-[52ch] leading-relaxed text-ink-2">
        The FloatChat API runs on free hosting and may be waking up. Give it a few seconds and try again.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-8 w-fit rounded-full bg-accent px-5 py-2 text-sm font-medium text-accent-ink"
      >
        Try again
      </button>
    </div>
  );
}
