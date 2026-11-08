import { describe, expect, it } from "vitest";
import { applyEvent, compactAnalytical, currentPhase, filterChips, historyFrom, newRun, stopRun } from "./run";
import type { QueryResult, Step } from "./types";

const understood: Step = { step: "understood", path: "analytical", intent: "avg_by_depth",
  filters: { region: "Arabian Sea" }, question: "q", router: "llm" };
const sql: Step = { step: "sql", attempt: 1, sql: "SELECT 1", status: "success", rows: 24, ms: 120 };
const result = (answer: string): QueryResult => ({ answer, query_type: "analytical", context_documents: [],
  retrieved_metadata: [], sql_results: [], intent: "avg_by_depth", filters: { region: "Arabian Sea" },
  steps: [understood, sql, { step: "answer", llm_used: true }] });

describe("run reducer", () => {
  it("collects steps and tokens, then takes the result as authoritative", () => {
    let run = newRun("1", "q", 0);
    expect(currentPhase(run)).toBe("understanding");
    run = applyEvent(run, { kind: "step", data: understood }, 1);
    expect(currentPhase(run)).toBe("querying");
    run = applyEvent(run, { kind: "step", data: sql }, 2);
    run = applyEvent(run, { kind: "token", data: { text: "Hel" } }, 3);
    run = applyEvent(run, { kind: "token", data: { text: "lo" } }, 4);
    expect(run.answer).toBe("Hello");
    expect(currentPhase(run)).toBe("writing");
    run = applyEvent(run, { kind: "result", data: result("Hello") }, 5);
    expect(run.status).toBe("done");
    expect(run.steps).toHaveLength(3);
    expect(run.finishedAt).toBe(5);
    expect(currentPhase(run)).toBeNull();
  });

  it("a failed SQL attempt keeps the run in the querying phase", () => {
    let run = applyEvent(newRun("1", "q", 0), { kind: "step", data: understood }, 1);
    run = applyEvent(run, { kind: "step", data: { ...sql, status: "error" } as Step }, 2);
    expect(currentPhase(run)).toBe("querying");
  });

  it("stops only a streaming run and records errors", () => {
    const stopped = stopRun(newRun("1", "q", 0), 7);
    expect(stopped.status).toBe("stopped");
    expect(stopRun(stopped, 9).finishedAt).toBe(7);
    const failed = applyEvent(newRun("2", "q", 0), { kind: "error", data: { message: "boom" } }, 3);
    expect(failed).toMatchObject({ status: "error", error: "boom" });
  });

  it("builds history from the last three answered turns only", () => {
    const done = (id: string) => applyEvent(newRun(id, `q${id}`, 0), { kind: "result", data: result("a") }, 1);
    const runs = [done("1"), done("2"), stopRun(newRun("3", "q3", 0), 1), done("4"), done("5")];
    expect(historyFrom(runs).map((h) => h.question)).toEqual(["q2", "q4", "q5"]);
    expect(historyFrom(runs)[0]).toEqual({ question: "q2", query_type: "analytical", intent: "avg_by_depth",
      filters: { region: "Arabian Sea" } });
  });
});

describe("compactAnalytical", () => {
  it("keeps the title and the explanation", () => {
    const answer = "**Averages by depth**\n\n- **5 m**: 28 °C\n- **10 m**: 27 °C\n\n**What this means:** Warm on top.";
    expect(compactAnalytical(answer)).toEqual({ title: "**Averages by depth**", insight: "**What this means:** Warm on top." });
  });

  it("returns null without an explanation", () => {
    expect(compactAnalytical("**Averages by depth**\n\n- **5 m**: 28 °C")).toBeNull();
    expect(compactAnalytical("**T**\n\n**What this means:**")).toBeNull();
  });
});

describe("filterChips", () => {
  it("names filters in reading order", () => {
    expect(filterChips({ region: "Bay of Bengal", month_num: 3, year: 2026, has_oxygen: true, has_ph: true })).toEqual(
      ["Bay of Bengal", "Mar", "2026", "oxygen", "pH"]);
    expect(filterChips(undefined)).toEqual([]);
  });
});
