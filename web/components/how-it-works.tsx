"use client";

import { CheckCircle } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import type { Step } from "@/lib/types";
import { RunLog } from "./run-log";

type Stage = { title: string; body: string; detail: string };

const DEMO_QUESTION = "What is the average temperature at different depths in the Arabian Sea?";
const DEMO_STEPS: Step[] = [
  { step: "understood", path: "analytical", intent: "avg_by_depth", filters: { region: "Arabian Sea" },
    question: DEMO_QUESTION, router: "llm" },
  { step: "sql", attempt: 1, status: "success", rows: 24,
    sql: "SELECT m.depth, AVG(m.temperature) AS avg_temperature, AVG(m.salinity) AS avg_salinity,\n       COUNT(*) AS measurement_count\nFROM measurements m JOIN profiles p ON p.profile_id = m.profile_id\nWHERE p.region = :region\nGROUP BY m.depth ORDER BY m.depth" },
  { step: "answer", llm_used: true },
];

export function HowItWorks({ stages }: { stages: Stage[] }) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.index));
        }
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    refs.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // The run log fills in as the story reaches the router (stage 3), the query (4) and the answer (5)
  const shown = active < 2 ? [] : DEMO_STEPS.slice(0, active - 1);
  const phase = active < 2 ? null : active === 2 ? "querying" : active === 3 ? "writing" : null;

  return (
    <div className="grid gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-20">
      <div className="lg:sticky lg:top-24 lg:self-start">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">How an answer is made</h2>
        <p className="mt-4 max-w-[46ch] leading-relaxed text-ink-2">
          Five systems, from a float two kilometres down to the sentence on your screen. Nothing is hidden: the chat
          shows this same log for every question.
        </p>
        <div className="mt-8 rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-card">
          <ol className="grid gap-2.5" aria-label="Pipeline stages">
            {stages.map((stage, i) => (
              <li key={stage.title} className="flex items-center gap-3 text-sm">
                {i < active ? (
                  <CheckCircle size={16} weight="fill" className="text-ok" aria-hidden />
                ) : (
                  <span
                    className={`grid size-4 place-items-center rounded-full border ${
                      i === active ? "border-accent bg-accent-soft" : "border-line-strong"
                    }`}
                    aria-hidden
                  />
                )}
                <span className={i === active ? "font-medium text-ink" : "text-ink-2"}>{stage.title}</span>
              </li>
            ))}
          </ol>
          <div className="mt-5 border-t border-line pt-5">
            <p className="text-sm text-ink-2">
              <span className="text-muted">Question:</span> {DEMO_QUESTION}
            </p>
            {shown.length || phase ? (
              <RunLog steps={shown} phase={phase} className="mt-4" />
            ) : (
              <p className="mt-4 text-sm text-muted">The run log fills in once the question reaches the router.</p>
            )}
          </div>
        </div>
      </div>

      <ol className="grid gap-6 lg:gap-0">
        {stages.map((stage, i) => (
          <li
            key={stage.title}
            data-index={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            className="lg:flex lg:min-h-[62vh] lg:items-center"
          >
            <div className={`transition-opacity duration-500 ${i === active ? "lg:opacity-100" : "lg:opacity-40"}`}>
              <h3 className="text-xl font-semibold tracking-tight md:text-2xl">{stage.title}</h3>
              <p className="mt-3 max-w-[52ch] leading-relaxed text-ink-2">{stage.body}</p>
              <p className="tabular mt-4 font-mono text-xs text-muted">{stage.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
