"use client";

import { ArrowRight } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

export function AskBox({ placeholder = "Average temperature at each depth in the Arabian Sea", autoFocus = false }: {
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const id = useId();

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const q = question.trim() || placeholder;
        router.push(`/chat?q=${encodeURIComponent(q)}`);
      }}
      className="group w-full"
    >
      <label htmlFor={id} className="mb-2 block text-sm text-ink-2">
        Ask in plain English
      </label>
      <div className="flex items-center gap-2 rounded-full border border-line-strong bg-surface p-1.5 pl-5 shadow-card transition-colors focus-within:border-accent">
        <input
          id={id}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder}
          maxLength={300}
          autoFocus={autoFocus}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted"
        />
        <button
          type="submit"
          className="inline-flex h-10 shrink-0 items-center gap-2 rounded-full bg-accent px-5 text-sm font-medium text-accent-ink transition-transform active:scale-[0.98]"
        >
          Ask
          <ArrowRight size={16} weight="bold" />
        </button>
      </div>
    </form>
  );
}
