import type { StreamEvent } from "./sse";
import type { Filters, QueryResult, Step } from "./types";

/** One question and its answer as it streams in. */
export type Run = {
  id: string;
  question: string;
  status: "streaming" | "done" | "stopped" | "error";
  steps: Step[];
  answer: string;
  result: QueryResult | null;
  error: string | null;
  startedAt: number;
  finishedAt: number | null;
};

export function newRun(id: string, question: string, now: number): Run {
  return { id, question, status: "streaming", steps: [], answer: "", result: null, error: null, startedAt: now,
    finishedAt: null };
}

export function applyEvent(run: Run, event: StreamEvent, now: number): Run {
  switch (event.kind) {
    case "step":
      return { ...run, steps: [...run.steps, event.data] };
    case "token":
      return { ...run, answer: run.answer + event.data.text };
    case "result":
      // The result carries the authoritative answer and steps (a cached answer arrives as one token)
      return { ...run, status: "done", result: event.data, answer: event.data.answer, steps: event.data.steps,
        finishedAt: now };
    case "error":
      return { ...run, status: "error", error: event.data.message, finishedAt: now };
  }
}

export function stopRun(run: Run, now: number): Run {
  return run.status === "streaming" ? { ...run, status: "stopped", finishedAt: now } : run;
}

export function failRun(run: Run, message: string, now: number): Run {
  return { ...run, status: "error", error: message, finishedAt: now };
}

/** The phase shown as "in progress" in the run log while streaming. */
export function currentPhase(run: Run): "understanding" | "querying" | "writing" | null {
  if (run.status !== "streaming") return null;
  if (run.answer) return "writing";
  const last = run.steps[run.steps.length - 1];
  if (!last) return "understanding";
  if (last.step === "understood" || (last.step === "sql" && last.status === "error")) return "querying";
  return "writing";
}

/** Earlier answered turns, sent as `history` so follow-ups like "now only the Arabian Sea" work. */
export function historyFrom(runs: Run[], turns = 3) {
  return runs
    .filter((r) => r.status === "done" && r.result && r.result.query_type !== "error")
    .slice(-turns)
    .map((r) => ({
      question: r.question,
      query_type: r.result!.query_type,
      intent: r.result!.intent,
      filters: r.result!.filters ?? {},
    }));
}

const SENSOR_LABELS: Record<string, string> = {
  has_oxygen: "oxygen",
  has_chlorophyll: "chlorophyll",
  has_nitrate: "nitrate",
  has_ph: "pH",
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Filters as short human chips: ["Arabian Sea", "Mar", "2026", "oxygen"]. */
export function filterChips(filters: Filters | undefined): string[] {
  if (!filters) return [];
  const chips: string[] = [];
  if (filters.region) chips.push(filters.region);
  if (filters.month_num) chips.push(MONTHS[filters.month_num - 1]);
  if (filters.year) chips.push(String(filters.year));
  for (const [key, label] of Object.entries(SENSOR_LABELS)) {
    if (filters[key as keyof Filters]) chips.push(label);
  }
  return chips;
}

export const INTENT_LABELS: Record<string, string> = {
  avg_by_depth: "Averages by depth",
  regional_comparison: "Region comparison",
  depth_ranges: "Depth layers",
  temporal_trends: "Monthly trend",
  float_summary: "Per-float summary",
  bgc_analysis: "Biogeochemistry by zone",
  custom: "Custom SQL",
};
