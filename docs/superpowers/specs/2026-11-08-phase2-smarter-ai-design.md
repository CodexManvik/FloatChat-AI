# Phase 2: Smarter AI (design)

**Date:** 2026-11-08
**Status:** approved by the user ("I approve the design, keep building"); built in this phase

## Context

Phase 1 put the API live (Render + Neon + Groq) with a keyword router, fixed SQL templates and pgvector search.
Phase 2 makes the AI part worth showing: it understands questions better, shows its work step by step, handles
follow-ups, and proves its accuracy with a published benchmark. Phase 3 (the Next.js site) builds its chat page on
the streaming endpoint defined here.

Problems found in the Phase 1 code that this phase fixes:

- **Statistical questions ignore filters.** "Average temperature at different depths *in the Arabian Sea*" detects the
  region but runs a whole-ocean template.
- **Routing is keyword-only.** Phrasings without trigger words go to the wrong path; "now only the Arabian Sea" has no
  memory of the previous question.
- **LLM-written SQL gets one try.** A typo in a column name ends in a fallback answer.
- **Answers arrive all at once** with no visibility into what happened.
- **Groq rate limits** (HTTP 429) fail the LLM call immediately.

## Goals

1. Filters (region, month, year, sensor) apply to **both** SQL answers and profile search.
2. An **LLM router** returns a structured decision (path, intent, filters, standalone question); the keyword router
   remains as the fallback when no LLM is available, the budget is spent, or the LLM's output is invalid.
3. **Follow-up questions** work: the client sends the last few turns; the router resolves "now only the Arabian Sea"
   into a standalone question with merged filters.
4. **Self-correcting SQL:** LLM-written SQL that fails is sent back with the database error, up to 2 repair attempts.
5. **Glass-box answers:** every answer carries a list of steps; a new streaming endpoint sends those steps and the
   answer text as they happen (Server-Sent Events).
6. **Evaluation suite:** a fixed set of benchmark questions with expected routing/filters and answer checks, a runner
   that scores the live API or a local one, and a published score.

## Non-goals

- The Next.js UI (Phase 3). The Streamlit stopgap gets follow-ups and a "How I answered" step list only.
- Server-side conversation storage. History travels with each request (stateless API).
- New data sources or variables.

## Design

### 1. Filters everywhere

`Filters` is a small dict with optional keys `region`, `month_num`, `year`, `has_oxygen`, `has_chlorophyll`,
`has_nitrate`, `has_ph` (the keys `floatchat/search.py` already understands). SQL templates become filter-aware: each
template reads `FROM measurements m JOIN profiles p ON p.profile_id = m.profile_id WHERE {conditions}` and the
conditions are built from the same whitelist as search (values always bound parameters). A template run with filters
answers only for the matching profiles; the answer title says so ("… in the Arabian Sea, March").

### 2. Router (`floatchat/router.py`)

```
Route(path: "analytical" | "semantic", intent: str, filters: dict, question: str, source: "llm" | "keywords")
route(question, history, chat, llm_available) -> Route
```

- **LLM router:** one JSON-mode chat call with a compact prompt: the list of intents (the templates plus `custom`),
  the allowed filter keys and region names, the last ≤3 turns of history, and the question. The reply is validated:
  unknown intents, regions or keys are dropped; a malformed reply falls back to keywords.
- **Keyword router:** today's `is_analytical_query` / `detect_query_intent` / `parse_filters`, plus a follow-up rule:
  if the question has filters but no intent of its own and the previous turn was analytical, reuse the previous
  intent with the new filters merged over the old ones ("now only the Arabian Sea").
- The router's standalone question is what the rest of the pipeline uses.

### 3. Self-correcting SQL

`SqlAgent.run(question, filters)`: templates for known intents (with filters); for `custom`, the LLM writes SQL, it is
validated (read-only check), executed, and on a database error the SQL and the error message go back to the LLM for a
fix, at most 2 repairs. Each attempt is recorded as a step. The read-only database role and 5 s timeout stay the last
line of defence.

### 4. Steps and streaming

`answer_question(...)` takes an optional `emit(event)` callback and returns the final result with a `steps` list.
Steps: `understood` (path, intent, filters, router source), `sql` (query, attempt), `rows` (count, ms), `search`
(matches, filters used, fallback note), `answer` (whether the LLM wrote it). `llm.chat_stream` streams tokens from the
OpenAI-compatible endpoint.

API:

- `POST /query` (unchanged contract, plus optional `history` in the request and `steps`, `filters` in the response).
- `POST /query/stream` → `text/event-stream` with events `step`, `token` (answer text as the LLM writes it),
  `result` (the same payload `/query` returns) and `error`. Rate-limited like `/query`; cached answers replay their
  steps and send the whole answer as one token.
- Answers to questions with history are not cached (they depend on the conversation).

### 5. Groq rate limits

`llm.chat` / `llm.chat_stream` retry once on HTTP 429, waiting `Retry-After` (capped at 10 s). A second 429 returns
`None` (data-only answer, not cached — Phase 1 behaviour).

### 6. Evaluation suite (`eval/`)

- `eval/questions.json`: ~30 questions across intents, regions, months, sensors, follow-ups and descriptive search,
  each with expectations: `path`, `intent` (analytical), `filters`, and answer checks (analytical: rows returned and,
  where relevant, the expected filter values in the SQL; semantic: every retrieved profile satisfies the filters).
- `python -m eval --api <url>` runs against any deployment (respecting rate limits by pacing requests) and writes
  `eval/results.json` plus a Markdown summary: routing accuracy, filter accuracy, answer-check pass rate, median
  latency, and how many answers the LLM wrote.
- `.github/workflows/eval.yml`: manual trigger (and weekly) against the live API; uploads the summary as the job
  summary. The README shows the latest score.

### 7. Streamlit stopgap

`app.py` sends the last 3 turns as `history` and shows the steps in a "How I answered" expander under each answer.

## Testing

Unit: filter-condition builder, router validation and keyword follow-ups, SQL repair loop (fake LLM returning bad then
good SQL), 429 retry, SSE event formatting. Integration: filter-aware templates against the fixture (region-filtered
averages differ from global ones and only use matching profiles), `/query` with history, `/query/stream` event order,
eval runner against a local app with a fake LLM.

## Done criteria

- [ ] "Average temperature at different depths in the Arabian Sea" returns Arabian-Sea-only results, live.
- [ ] A follow-up ("now only the Bay of Bengal") changes the filters and keeps the intent, live.
- [ ] `/query/stream` streams steps and tokens on the live API.
- [ ] The eval suite runs against the live API and its score is in the README.
- [ ] CI green; all Phase 1 behaviour unchanged.
