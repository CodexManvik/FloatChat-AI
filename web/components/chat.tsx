"use client";

import {
  ArrowClockwise,
  ArrowRight,
  ArrowUp,
  CaretDown,
  Check,
  Copy,
  Stop,
  WarningCircle,
} from "@phosphor-icons/react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { formatDate, formatMs, formatPosition } from "@/lib/format";
import {
  applyEvent,
  compactAnalytical,
  currentPhase,
  failRun,
  filterChips,
  historyFrom,
  INTENT_LABELS,
  newRun,
  stopRun,
  type Run,
} from "@/lib/run";
import { RateLimitedError, streamQuery } from "@/lib/sse";
import type { ProfileMatch, QueryResult } from "@/lib/types";
import { AnswerMarkdown } from "./answer-markdown";
import { DownloadMenu } from "./download-menu";
import { MiniMap } from "./mini-map";
import { DataTable, ResultChart } from "./result-charts";
import { RunLog, SqlBlock } from "./run-log";

const STARTERS = [
  "What is the average temperature at different depths in the Arabian Sea?",
  "Which floats measured low oxygen in the Arabian Sea?",
  "Compare surface temperature across ocean regions",
  "Show me salinity profiles near the equator in March 2026",
];
const REGIONS = ["Arabian Sea", "Bay of Bengal", "Southern Indian Ocean", "Equatorial Indian Ocean"];

function suggestions(result: QueryResult): string[] {
  const out: string[] = [];
  if (result.intent !== "regional_comparison") {
    const other = REGIONS.find((r) => r !== result.filters?.region);
    if (other) out.push(`Now only the ${other}`);
  }
  if (result.query_type === "analytical" && !result.filters?.month_num) out.push("And just in March");
  if (result.query_type === "semantic" && !result.filters?.has_oxygen) out.push("Only the ones measuring oxygen");
  return out;
}

function Segmented<T extends string>({ value, options, onChange }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex rounded-full border border-line bg-surface-2 p-0.5 text-sm">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          type="button"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-full px-3 py-1 transition-colors ${
            value === o.value ? "bg-surface text-ink shadow-card" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function AnalyticalResult({ result }: { result: QueryResult }) {
  const rows = result.sql_results ?? [];
  const sql = (result.retrieved_metadata[0]?.sql_query as string | undefined) ?? result.context_documents[0] ?? "";
  const chart = ResultChart({ intent: result.intent, rows });
  const [tab, setTab] = useState<"chart" | "table" | "sql">(chart ? "chart" : "table");
  if (!rows.length) return null;
  return (
    <div className="mt-5 rounded-[var(--radius-card)] border border-line bg-surface p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm font-medium">{INTENT_LABELS[result.intent ?? "custom"] ?? "Result"}</span>
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            ...(chart ? [{ value: "chart" as const, label: "Chart" }] : []),
            { value: "table" as const, label: `Data (${rows.length})` },
            { value: "sql" as const, label: "SQL" },
          ]}
        />
      </div>
      {tab === "chart" && chart}
      {tab === "table" && <DataTable rows={rows} />}
      {tab === "sql" && <SqlBlock sql={sql} />}
    </div>
  );
}

function SemanticResult({ result }: { result: QueryResult }) {
  const profiles = result.retrieved_metadata as unknown as ProfileMatch[];
  if (!profiles.length) return null;
  return (
    <div className="mt-5 grid gap-4 rounded-[var(--radius-card)] border border-line bg-surface p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:p-5">
      <div className="md:col-span-2">
        <DownloadMenu profileIds={profiles.map((p) => p.profile_id)} name="floatchat_profiles" note="these profiles" />
      </div>
      <MiniMap
        points={profiles.map((p) => ({ lat: p.lat, lon: p.lon, label: `Float ${p.float_id}, ${p.date}` }))}
        label="Map of the matching profiles"
        height={280}
        minSpan={16}
      />
      <ul className="grid content-start gap-2">
        {profiles.map((p) => {
          const sensors = filterChips({ has_oxygen: p.has_oxygen, has_chlorophyll: p.has_chlorophyll, has_nitrate: p.has_nitrate, has_ph: p.has_ph });
          return (
            <li key={p.profile_id}>
              <Link
                href={`/floats/${p.float_id}`}
                className="group flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 transition-colors hover:border-line-strong"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    Float {p.float_id} <span className="font-normal text-muted">cycle {p.cycle_number}</span>
                  </div>
                  <div className="tabular truncate text-xs text-ink-2">
                    {formatDate(p.date)}, {formatPosition(p.lat, p.lon)}, {p.region}
                  </div>
                  {sensors.length > 0 && <div className="mt-1 text-xs text-muted">Sensors: {sensors.join(", ")}</div>}
                </div>
                <ArrowRight size={14} className="shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RunSummary({ run }: { run: Run }) {
  const [open, setOpen] = useState(false);
  const understood = run.steps.find((s) => s.step === "understood");
  const elapsed = run.finishedAt ? run.finishedAt - run.startedAt : null;
  const repaired = run.steps.some((s) => s.step === "sql" && s.status !== "success");
  const fallback = understood?.step === "understood" && understood.router === "keywords";
  const how = understood?.step === "understood"
    ? understood.path === "analytical" ? `SQL, ${INTENT_LABELS[understood.intent ?? "custom"]?.toLowerCase() ?? "custom"}` : "profile search"
    : "answer";
  const chips = understood?.step === "understood" ? filterChips(understood.filters) : [];
  return (
    <div className="rounded-xl border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2 text-left text-sm"
      >
        <span className="text-ink-2">Answered with</span>
        <span className="font-medium">{how}</span>
        {chips.map((c) => (
          <span key={c} className="rounded-lg border border-line bg-surface-2 px-1.5 py-px text-xs text-ink-2">{c}</span>
        ))}
        {(fallback || repaired) && (
          <span className="inline-flex items-center gap-1 text-xs text-warn">
            <WarningCircle size={12} weight="fill" /> {fallback ? "keyword fallback" : "SQL repaired"}
          </span>
        )}
        <span className="tabular ml-auto font-mono text-xs text-muted">{run.steps.length} steps{elapsed != null ? `, ${formatMs(elapsed)}` : ""}</span>
        <CaretDown size={12} className={`text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-line px-3 py-3">
          <RunLog steps={run.steps} phase={null} />
        </div>
      )}
    </div>
  );
}

function Turn({ run, now, onRetry, onAsk, isLast }: {
  run: Run;
  now: number;
  onRetry: (q: string) => void;
  onAsk: (q: string) => void;
  isLast: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const phase = currentPhase(run);
  const waking = run.status === "streaming" && run.steps.length === 0 && now - run.startedAt > 4000;
  // Once done, an analytical answer shows its title and explanation; the rows live in the chart and table
  const compact = run.status === "done" && run.result?.query_type === "analytical" ? compactAnalytical(run.answer) : null;

  return (
    <article className="grid gap-4" aria-busy={run.status === "streaming"}>
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-surface-2 px-4 py-2.5 text-[15px] leading-relaxed">{run.question}</p>
      </div>

      <div className="grid gap-4">
        {run.status === "streaming" ? (
          <div className="rounded-xl border border-line bg-surface px-3 py-3">
            <RunLog steps={run.steps} phase={phase} />
            {waking && (
              <p className="mt-2 pl-8 text-xs text-ink-2">The API is waking up (free hosting sleeps when idle). This takes a few seconds.</p>
            )}
          </div>
        ) : run.steps.length > 0 ? (
          <RunSummary run={run} />
        ) : null}

        {compact ? (
          <>
            <AnswerMarkdown text={compact.title} />
            <AnswerMarkdown text={compact.insight} />
          </>
        ) : (
          run.answer && <AnswerMarkdown text={run.answer} streaming={run.status === "streaming"} />
        )}

        {run.status === "error" && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm" role="alert">
            <WarningCircle size={18} weight="fill" className="text-warn" />
            <span className="flex-1 text-ink-2">{run.error}</span>
            <button type="button" onClick={() => onRetry(run.question)} className="inline-flex items-center gap-1.5 rounded-full border border-line-strong px-3 py-1 hover:bg-surface-2">
              <ArrowClockwise size={14} /> Try again
            </button>
          </div>
        )}
        {run.status === "stopped" && (
          <p className="text-sm text-muted">
            Stopped.{" "}
            <button type="button" onClick={() => onRetry(run.question)} className="text-ink-2 underline underline-offset-4 hover:text-ink">
              Ask again
            </button>
          </p>
        )}

        {run.status === "done" && run.result?.query_type === "analytical" && <AnalyticalResult result={run.result} />}
        {run.status === "done" && run.result?.query_type === "semantic" && <SemanticResult result={run.result} />}

        {run.status === "done" && run.result && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(run.answer);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink"
              aria-label="Copy answer"
            >
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </button>
            <button
              type="button"
              onClick={() => onRetry(run.question)}
              className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink"
              aria-label="Ask again"
            >
              <ArrowClockwise size={15} />
            </button>
            {isLast &&
              suggestions(run.result).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onAsk(s)}
                  className="rounded-full border border-line px-3 py-1 text-sm text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
                >
                  {s}
                </button>
              ))}
          </div>
        )}
      </div>
    </article>
  );
}

export function Chat({ initialQuestion, coverage }: { initialQuestion?: string; coverage: string }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [input, setInput] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const runsRef = useRef<Run[]>([]);
  const controller = useRef<AbortController | null>(null);
  const started = useRef(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const streaming = runs.some((r) => r.status === "streaming");

  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);

  // Tick while streaming so the "waking up" notice can appear
  useEffect(() => {
    if (!streaming) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [streaming]);

  const update = useCallback((id: string, fn: (run: Run) => Run) => {
    setRuns((all) => all.map((r) => (r.id === id ? fn(r) : r)));
  }, []);

  const ask = useCallback(
    async (raw: string) => {
      const question = raw.trim().slice(0, 300);
      if (!question || runsRef.current.some((r) => r.status === "streaming")) return;
      const id = crypto.randomUUID();
      const history = historyFrom(runsRef.current);
      setRuns((all) => [...all, newRun(id, question, Date.now())]);
      setInput("");
      requestAnimationFrame(() => document.getElementById(`turn-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));

      const abort = new AbortController();
      controller.current = abort;
      try {
        await streamQuery(question, history, (event) => update(id, (r) => applyEvent(r, event, Date.now())), abort.signal);
        update(id, (r) => (r.status === "streaming" ? failRun(r, "The answer stopped early. Please try again.", Date.now()) : r));
      } catch (error) {
        if (abort.signal.aborted) update(id, (r) => stopRun(r, Date.now()));
        else if (error instanceof RateLimitedError) update(id, (r) => failRun(r, error.message, Date.now()));
        else update(id, (r) => failRun(r, "Couldn't reach the FloatChat API. It may be waking up; try again in a few seconds.", Date.now()));
      } finally {
        controller.current = null;
      }
    },
    [update],
  );

  useEffect(() => {
    if (initialQuestion && !started.current) {
      started.current = true;
      // Ask the question from the link once
      ask(initialQuestion);
    }
  }, [initialQuestion, ask]);

  function submit() {
    if (streaming) controller.current?.abort();
    else ask(input);
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-[860px] flex-col px-4 sm:px-6">
      <div className="flex-1 py-8">
        {runs.length === 0 ? (
          <div className="pt-[8vh]">
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">What would you like to know?</h1>
            <p className="mt-3 max-w-[56ch] leading-relaxed text-ink-2">
              Ask about temperature, salinity, oxygen, chlorophyll, nitrate or pH in the Indian Ocean. Statistics
              become SQL; questions about particular profiles become a search.
            </p>
            <ul className="mt-8 grid gap-2 sm:grid-cols-2">
              {STARTERS.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => ask(q)}
                    className="h-full w-full rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 text-left text-[15px] leading-snug transition-colors hover:border-line-strong"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="grid gap-12">
            {runs.map((run, i) => (
              <div key={run.id} id={`turn-${run.id}`} className="scroll-mt-24">
                <Turn run={run} now={now} onRetry={ask} onAsk={ask} isLast={i === runs.length - 1} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="sticky bottom-0 bg-gradient-to-t from-bg from-70% to-transparent pb-4 pt-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="flex items-end gap-2 rounded-[22px] border border-line-strong bg-surface p-1.5 pl-4 shadow-card transition-colors focus-within:border-accent"
        >
          <label htmlFor="composer" className="sr-only">Your question</label>
          <textarea
            id="composer"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={300}
            placeholder={runs.length ? "Ask a follow-up" : "Ask about the Indian Ocean"}
            className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[15px] leading-snug text-ink outline-none placeholder:text-muted [field-sizing:content]"
          />
          <button
            type="submit"
            disabled={!streaming && !input.trim()}
            aria-label={streaming ? "Stop" : "Ask"}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-accent-ink transition-transform active:scale-[0.96] disabled:opacity-40"
          >
            {streaming ? <Stop size={16} weight="fill" /> : <ArrowUp size={18} weight="bold" />}
          </button>
        </form>
        <p className="mt-2 text-center text-xs text-muted">{coverage}</p>
      </div>
    </div>
  );
}
