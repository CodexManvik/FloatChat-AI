# Phase 2: Smarter AI Implementation Plan

> Executed inline (user-approved). Each task is test-first and ends with a commit on branch `phase2-smarter-ai`.

**Goal:** Filter-aware SQL, an LLM router with keyword fallback and follow-ups, self-correcting SQL, step-by-step
streaming answers, Groq rate-limit retries, and a published evaluation score.

**Spec:** `docs/superpowers/specs/2026-11-08-phase2-smarter-ai-design.md`

## Global constraints

- Phase 1 constraints still apply (Python 3.11, pinned dependencies, read-only DB role, rate limits, no secrets in code).
- `/query` stays backward compatible: existing fields unchanged; `history` (request) and `steps`, `filters`
  (response) are optional additions.
- Filter keys are exactly those in `floatchat.search.FILTER_SQL`; values are always bound parameters.
- Every LLM call goes through the API's budgeted chat function; every LLM failure falls back to the keyword/data-only
  path.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Tasks

### Task 1: Filter-aware SQL templates
- `floatchat/filters.py`: `FILTER_KEYS`, `clean_filters(filters) -> dict` (drops unknown keys/values),
  `sql_conditions(filters, alias="p") -> (list[str], dict)`; `search.py` reuses it.
- `sql_agent.TEMPLATES` rewritten to `FROM measurements m JOIN profiles p ... WHERE {where}`;
  `SqlAgent.generate_sql(question, filters)` / `run(question, filters=None)`.
- Tests: unit for the condition builder; integration: Arabian-Sea-filtered `avg_by_depth` uses only Arabian Sea
  measurements (row counts match a direct SQL count) and differs from the unfiltered result.

### Task 2: Router with keyword fallback and follow-ups
- `floatchat/router.py`: `Route` dataclass; `keyword_route(question, history)`; `llm_route(question, history, chat)`
  (JSON reply, validated); `route(question, history, chat, llm_available)`.
- `answer_question` uses the route (path, intent, filters, standalone question) instead of its own keyword checks.
- Tests: keyword routes for the Phase 1 questions unchanged; follow-up "now only the Arabian Sea" reuses the previous
  intent; LLM route parsing (valid, invalid intent/region dropped, malformed → keywords).

### Task 3: Self-correcting SQL and Groq 429 retry
- `SqlAgent.run` records attempts; on a database error for LLM SQL, ask the LLM to fix it (≤2 repairs).
- `llm.chat`: one retry on 429 honouring `Retry-After` (≤10 s); `llm.chat_stream` for token streaming.
- Tests: fake LLM returning broken then fixed SQL succeeds with 2 attempts; 3 broken attempts fail cleanly; 429 retry
  with a fake HTTP layer.

### Task 4: Steps and the streaming endpoint
- `answer_question(..., emit=None, history=None)` emits step events and returns `steps` and `filters` in the result.
- `/query` accepts `history`; questions with history are not cached.
- `/query/stream` (SSE): `step`, `token`, `result`, `error` events; same rate limits and query log.
- Tests: `/query` with history routes the follow-up; stream returns steps then a result whose payload equals
  `/query`'s; cached stream replays steps.

### Task 5: Streamlit stopgap updates
- `app.py` sends the last 3 turns as `history`; shows "How I answered" (steps) under each answer.

### Task 6: Evaluation suite
- `eval/questions.json` (~30 cases), `eval/__main__.py` runner (`--api`, pacing, JSON + Markdown output),
  `.github/workflows/eval.yml` (manual + weekly), README score section.
- Tests: runner scoring logic on canned responses.

### Task 7: Ship
- PR, CI green, merge, Render redeploy, run the eval against the live API, record the score, verify the done criteria.
