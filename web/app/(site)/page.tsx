import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { AskBox } from "@/components/ask-box";
import { Globe } from "@/components/globe";
import { HowItWorks } from "@/components/how-it-works";
import { getBenchmark, getFloats, getStats } from "@/lib/api";
import { BENCHMARK_TABLE_URL } from "@/lib/config";
import { formatDate, formatInt, formatMs } from "@/lib/format";
import type { Benchmark, FloatPoint, Stats } from "@/lib/types";

export const revalidate = 600;

const QUESTIONS: { q: string; how: "SQL" | "Search" }[] = [
  { q: "What is the average temperature at different depths in the Arabian Sea?", how: "SQL" },
  { q: "Which floats measured low oxygen in the Arabian Sea?", how: "Search" },
  { q: "How has the average temperature near the equator changed over time?", how: "SQL" },
  { q: "Show me salinity profiles near the equator in March 2026", how: "Search" },
  { q: "Compare chlorophyll levels across zones in the Bay of Bengal", how: "SQL" },
  { q: "How many profiles were recorded in the Arabian Sea?", how: "SQL" },
];

function stages(stats: Stats | null) {
  return [
    {
      title: "Floats measure the ocean",
      body: "Robotic Argo floats drift at 1,000 m, dive to 2,000 m every ten days and rise measuring temperature and salinity. BGC floats add oxygen, chlorophyll, nitrate and pH.",
      detail: stats ? `${formatInt(stats.floats)} floats, ${formatInt(stats.bgc_floats)} with oxygen sensors` : "Indian Ocean, last 12 months",
    },
    {
      title: "A nightly pipeline keeps a year of data",
      body: "GitHub Actions pulls new profiles from Ifremer ERDDAP, keeps quality-controlled values, puts every profile on 24 standard depths and writes a one-sentence description of it.",
      detail: "QC flags 1-2, 24 standard depths, MiniLM embeddings, Postgres + pgvector",
    },
    {
      title: "The router reads your question",
      body: "An LLM decides whether the question needs statistics or a search, and pulls out the region, month, year and sensor. Keyword rules take over if the LLM is unavailable.",
      detail: "gpt-oss-120b on Groq, validated JSON, keyword fallback",
    },
    {
      title: "SQL or search does the work",
      body: "Statistics run as vetted SQL templates, or as LLM-written SQL that is checked, run on a read-only role and repaired from database errors. Descriptions are found by vector search.",
      detail: "read-only role, 5 s timeout, up to 2 repairs, exact filtered search",
    },
    {
      title: "The answer shows its work",
      body: "The answer streams in with the chart, the SQL and this run log, so every number can be checked against the query that produced it.",
      detail: "Server-Sent Events: step, token, result",
    },
  ];
}

async function load<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

function StatStrip({ stats }: { stats: Stats }) {
  const items = [
    { value: formatInt(stats.floats), label: "active floats" },
    { value: formatInt(stats.profiles), label: "profiles" },
    { value: formatInt(stats.measurements), label: "measurements" },
    { value: formatDate(stats.end_date), label: "newest profile, refreshed nightly" },
  ];
  return (
    <dl className="grid grid-cols-2 divide-line border-y border-line md:grid-cols-4 md:divide-x">
      {items.map((item) => (
        <div key={item.label} className="px-1 py-6 md:px-6 md:first:pl-0">
          <dt className="text-sm text-ink-2">{item.label}</dt>
          <dd className="tabular mt-1 font-mono text-2xl tracking-tight md:text-3xl">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function BenchmarkBand({ benchmark }: { benchmark: Benchmark }) {
  const s = benchmark.summary;
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  const metrics = [
    { label: "Routing", value: pct(s.routing_accuracy), note: "SQL or search, and which analysis" },
    { label: "Filters", value: pct(s.filter_accuracy), note: "region, month, year and sensor" },
    { label: "Answer checks", value: pct(s.answer_pass_rate), note: "SQL applies the filters; profiles match" },
    { label: "Median latency", value: s.median_latency_ms ? formatMs(s.median_latency_ms) : "n/a", note: "full answer, live API" },
  ];
  return (
    <div className="grid gap-10 rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-card md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:p-10">
      <div>
        <p className="tabular font-mono text-6xl font-medium tracking-tighter md:text-7xl">
          {s.passed}<span className="text-muted">/{s.cases}</span>
        </p>
        <h2 className="mt-4 text-2xl font-semibold tracking-tight">benchmark questions answered fully correctly</h2>
        <p className="mt-3 max-w-[44ch] leading-relaxed text-ink-2">
          Thirty fixed questions, re-run against the live API every week. Each is checked for how it was routed,
          which filters were understood and whether the answer holds up.
        </p>
        <a href={BENCHMARK_TABLE_URL} className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-accent">
          See every question <ArrowUpRight size={14} />
        </a>
      </div>
      <dl className="grid content-center gap-x-8 gap-y-7 sm:grid-cols-2">
        {metrics.map((m) => (
          <div key={m.label}>
            <dt className="text-sm text-ink-2">{m.label}</dt>
            <dd className="tabular mt-1 font-mono text-4xl tracking-tight">{m.value}</dd>
            <dd className="mt-1 text-sm text-muted">{m.note}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const STACK = [
  { name: "Next.js", slug: "nextdotjs" },
  { name: "FastAPI", slug: "fastapi" },
  { name: "PostgreSQL", slug: "postgresql" },
  { name: "Python", slug: "python" },
  { name: "GitHub Actions", slug: "githubactions" },
  { name: "Render", slug: "render" },
  { name: "Vercel", slug: "vercel" },
];

export default async function Home() {
  const [stats, floats, benchmark] = await Promise.all([load(getStats), load(getFloats), load(getBenchmark)]);

  return (
    <>
      <section className="mx-auto grid max-w-[1240px] items-center gap-10 px-4 pb-12 pt-10 sm:px-6 md:pt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-6 lg:pb-16">
        <div className="max-w-xl">
          <h1 className="text-[2.6rem] font-semibold leading-[1.02] tracking-tighter sm:text-6xl">
            Ask the Indian Ocean anything.
          </h1>
          <p className="mt-5 max-w-[40ch] text-lg leading-relaxed text-ink-2">
            A year of real Argo float data. Ask in plain English and watch FloatChat query, search and explain.
          </p>
          <div className="mt-8">
            <AskBox />
          </div>
          <Link href="/floats" className="mt-5 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
            Or browse the floats <ArrowRight size={14} />
          </Link>
        </div>
        <div className="relative">
          {floats?.length ? (
            <Globe floats={floats as FloatPoint[]} />
          ) : (
            <div className="mx-auto aspect-square w-full max-w-[640px] animate-pulse rounded-full bg-surface-2" aria-label="Loading the globe" />
          )}
        </div>
      </section>

      {stats && (
        <section className="mx-auto max-w-[1240px] px-4 sm:px-6" aria-label="Dataset">
          <StatStrip stats={stats} />
        </section>
      )}

      <section className="mx-auto max-w-[1240px] px-4 py-20 sm:px-6 md:py-28">
        <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Start with a question</h2>
        <p className="mt-4 max-w-[60ch] leading-relaxed text-ink-2">
          Statistics become SQL on the database. Questions about particular profiles become a search of their
          descriptions. Follow-ups such as &ldquo;now only the Bay of Bengal&rdquo; keep the context.
        </p>
        <ul className="mt-10 grid gap-3 md:grid-cols-2">
          {QUESTIONS.map(({ q, how }) => (
            <li key={q}>
              <Link
                href={`/chat?q=${encodeURIComponent(q)}`}
                className="group flex h-full items-center gap-4 rounded-[var(--radius-card)] border border-line bg-surface px-5 py-4 transition-colors hover:border-line-strong"
              >
                <span className="flex-1 text-[15px] leading-snug">{q}</span>
                <span className="rounded-lg border border-line px-2 py-0.5 font-mono text-xs text-ink-2">{how}</span>
                <ArrowRight size={16} className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section id="how-it-works" className="scroll-mt-20 border-t border-line bg-surface-2/40">
        <div className="mx-auto max-w-[1240px] px-4 py-20 sm:px-6 md:py-28">
          <HowItWorks stages={stages(stats)} />
        </div>
      </section>

      {benchmark && (
        <section className="mx-auto max-w-[1240px] px-4 py-20 sm:px-6 md:py-28" aria-label="Benchmark">
          <BenchmarkBand benchmark={benchmark} />
          <p className="mt-4 text-sm text-muted">Last run {benchmark.ran_at}.</p>
        </section>
      )}

      <section className="border-t border-line" aria-label="Built with">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-center gap-x-12 gap-y-6 px-4 py-12 sm:px-6">
          {STACK.map((tool) => (
            // eslint-disable-next-line @next/next/no-img-element -- small SVG logos from Simple Icons
            <img
              key={tool.slug}
              src={`https://cdn.simpleicons.org/${tool.slug}/8a8f97`}
              alt={tool.name}
              title={tool.name}
              width={28}
              height={28}
              loading="lazy"
              className="size-7 opacity-80 transition-opacity hover:opacity-100"
            />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pb-24 pt-8 sm:px-6">
        <div className="grid items-end gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Ask your first question.</h2>
          <AskBox placeholder="Which floats measured low oxygen in the Arabian Sea?" />
        </div>
      </section>
    </>
  );
}
