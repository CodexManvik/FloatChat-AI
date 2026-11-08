"use client";

import {
  CaretDown,
  CheckCircle,
  CircleNotch,
  Copy,
  Database,
  MagnifyingGlass,
  NavigationArrow,
  PenNib,
  WarningCircle,
} from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { formatMs } from "@/lib/format";
import { filterChips, INTENT_LABELS } from "@/lib/run";
import type { Step } from "@/lib/types";

type Phase = "understanding" | "querying" | "writing" | null;

const PHASE_LABEL: Record<Exclude<Phase, null>, string> = {
  understanding: "Reading the question",
  querying: "Running the query",
  writing: "Writing the answer",
};

type Tone = "ok" | "warn" | "active";

function StatusIcon({ tone }: { tone: Tone }) {
  if (tone === "active") return <CircleNotch size={16} weight="bold" className="animate-spin text-accent" aria-hidden />;
  if (tone === "warn") return <WarningCircle size={16} weight="fill" className="text-warn" aria-hidden />;
  return <CheckCircle size={16} weight="fill" className="text-ok" aria-hidden />;
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-lg border border-line bg-surface-2 px-2 py-0.5 text-xs text-ink-2">{children}</span>;
}

function Row({
  icon,
  tone,
  title,
  meta,
  children,
  detail,
}: {
  icon: React.ReactNode;
  tone: Tone;
  title: string;
  meta?: string;
  children?: React.ReactNode;
  detail?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  return (
    <motion.li
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
      className="relative grid grid-cols-[20px_1fr] gap-x-3 pb-3 last:pb-0"
    >
      <span className="relative z-10 mt-0.5 grid size-5 place-items-center rounded-full bg-surface">
        <StatusIcon tone={tone} />
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-ink-2" aria-hidden>
            {icon}
          </span>
          <span className="text-sm font-medium">{title}</span>
          {meta && <span className="tabular font-mono text-xs text-muted">{meta}</span>}
          {detail && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              {open ? "Hide" : "Details"}
              <CaretDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            </button>
          )}
        </div>
        {children && <div className="mt-1.5 flex flex-wrap gap-1.5">{children}</div>}
        <AnimatePresence initial={false}>
          {open && detail && (
            <motion.div
              initial={reduce ? false : { height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="pt-2">{detail}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
}

export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative rounded-xl border border-line bg-surface-2">
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(sql);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-surface px-2 py-1 text-xs text-ink-2 shadow-card hover:text-ink"
      >
        <Copy size={12} /> {copied ? "Copied" : "Copy SQL"}
      </button>
      <pre className="max-h-72 overflow-auto p-3 pr-24 font-mono text-[12px] leading-relaxed text-ink-2">
        <code>{sql.trim()}</code>
      </pre>
    </div>
  );
}

function stepRow(step: Step, index: number) {
  switch (step.step) {
    case "understood": {
      const chips = filterChips(step.filters);
      const how = step.path === "analytical" ? `SQL, ${INTENT_LABELS[step.intent ?? "custom"] ?? step.intent}` : "Profile search";
      return (
        <Row
          key={index}
          icon={<NavigationArrow size={14} />}
          tone={step.router === "llm" ? "ok" : "warn"}
          title={`Understood: ${how}`}
          meta={step.router === "llm" ? "AI router" : "keyword fallback"}
        >
          {chips.length ? chips.map((c) => <Chip key={c}>{c}</Chip>) : <Chip>no filters</Chip>}
        </Row>
      );
    }
    case "sql": {
      const title =
        step.status === "success"
          ? step.attempt > 1 ? `Repaired SQL ran (attempt ${step.attempt})` : "SQL ran"
          : step.status === "empty" ? "SQL returned no rows" : `SQL failed, repairing (attempt ${step.attempt})`;
      const meta = [step.rows != null && step.status === "success" ? `${step.rows} rows` : null, formatMs(step.ms)]
        .filter(Boolean)
        .join(" / ");
      return (
        <Row
          key={index}
          icon={<Database size={14} />}
          tone={step.status === "success" ? "ok" : "warn"}
          title={title}
          meta={meta}
          detail={<SqlBlock sql={step.sql} />}
        />
      );
    }
    case "search":
      return (
        <Row
          key={index}
          icon={<MagnifyingGlass size={14} />}
          tone={step.fallback_without_filters ? "warn" : "ok"}
          title={step.fallback_without_filters ? "No exact match, widened the search" : "Searched the profile index"}
          meta={`${step.matches} matches`}
        />
      );
    case "answer":
      return (
        <Row
          key={index}
          icon={<PenNib size={14} />}
          tone={step.llm_used ? "ok" : "warn"}
          title={step.llm_used ? "Answer written by the LLM" : "Answer built from the data alone"}
        />
      );
  }
}

export function RunLog({
  steps,
  phase,
  elapsedMs,
  className = "",
}: {
  steps: Step[];
  phase: Phase;
  elapsedMs?: number | null;
  className?: string;
}) {
  return (
    <div className={className}>
      <ol className="relative before:absolute before:bottom-2 before:left-[9.5px] before:top-2 before:w-px before:bg-line-strong" aria-label="How this answer was worked out">
        {steps.map(stepRow)}
        {phase && (
          <Row key="phase" icon={null} tone="active" title={PHASE_LABEL[phase]} />
        )}
      </ol>
      {elapsedMs != null && !phase && (
        <p className="tabular mt-2 pl-8 font-mono text-xs text-muted">Answered in {formatMs(elapsedMs)}</p>
      )}
    </div>
  );
}
