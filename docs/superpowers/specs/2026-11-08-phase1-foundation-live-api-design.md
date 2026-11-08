# Phase 1: Foundation & live API (design)

**Date:** 2026-11-08
**Status:** approved in brainstorming, awaiting spec review

## Context: the overall plan

FloatChat currently runs locally with Docker: a Streamlit frontend, a FastAPI backend, PostgreSQL for measurements
and ChromaDB for profile search, over a bundled 3-month Indian Ocean snapshot of real Argo data. The goal is a
**public, always-on deployment that impresses recruiters**, built in four phases. Each phase gets its own
spec → plan → implementation cycle and ends deployed and working.

| Phase | Scope |
|---|---|
| **1. Foundation & live API** (this spec) | Neon Postgres + pgvector (replaces ChromaDB); 12 months of data with more BGC variables; daily refresh; API protection; deployment on Koyeb; CI |
| 2. Smarter AI | LLM router, self-correcting SQL, streaming step-by-step answers (SSE), follow-up memory, evaluation suite with a published score |
| 3. Next.js frontend | Landing page (float globe, live stats, scroll-through "how it works", try-it box, eval score), chat with live step trace, float pages with T-S diagram / depth-time section / float comparison; deployed on Vercel |
| 4. Launch | Final README, launch video, retire the Streamlit app |

Decisions already made for the whole project:

- **Architecture A:** FastAPI owns all AI and data logic; the Next.js frontend only displays results.
- **Hosting, all free:** Vercel (frontend), Koyeb free instance (API), Neon free plan (Postgres + pgvector),
  Groq free tier (LLM), cron-job.org (keep-awake ping). Hugging Face Spaces was ruled out because Docker Spaces
  now require a paid account.
- **Data scope:** the Indian Ocean, rolling 12-month window (fits comfortably in Neon's 1 GB free storage; the
  existing region model already covers it).

## Goals

1. A public API URL that answers both question types (SQL and profile search) over 12 months of real, quality-
   controlled Argo data, including oxygen, chlorophyll, nitrate and pH.
2. Data that refreshes itself daily with no manual work.
3. A public demo that can't be abused: the Groq key is protected by rate limits, a daily LLM budget and caching.
4. Fits free-tier limits: API under ~350 MB RAM on a 512 MB / 0.1 vCPU instance; database ~100 MB of 1 GB.
5. Reproducible: CI on every change, and a `DEPLOY.md` someone else can follow.

## Non-goals (later phases)

- LLM routing, self-correcting SQL, streaming, follow-up memory, evaluation suite (Phase 2)
- The Next.js site and new science views (Phase 3)
- Retiring Streamlit, launch video (Phase 4). In Phase 1 the Streamlit app keeps working against the new backend.

## 1. Storage and data model

One database: Neon Postgres with the pgvector extension. ChromaDB is removed.

**Tables**

- `floats`: one row per float (`float_id` = WMO number as text, `wmo_id`, first/last position and date, status).
- `profiles`: one row per dive cycle.
  - Columns: `profile_id` (serial), `float_id`, `cycle_number`, `profile_date`, `profile_lat`, `profile_lon`,
    `region`, `n_levels` (existing names kept so current endpoints and the Streamlit app keep working).
  - Sensor flags: `has_oxygen`, `has_chlorophyll`, `has_nitrate`, `has_ph`.
  - Search columns: `description` (text) and `embedding vector(384)`.
  - Constraints and indexes: **unique `(float_id, cycle_number)`**; indexes on `profile_date` and `region`; an
    **HNSW index on `embedding` (cosine)**.
- `measurements`: one row per depth level: `profile_id`, `float_id`, `time`, `lat`, `lon`, `depth`, `pressure`,
  `temperature`, `salinity`, `oxygen`, `chlorophyll`, `nitrate`, `ph`. The unused `backscatter`, `cdom`,
  `downwelling_par` columns are dropped. Indexes on `profile_id`, `float_id`, `depth`.
- `ingest_runs` (new): `run_id`, `kind` (`backfill` / `refresh` / `snapshot`), `started_at`, `finished_at`, `status`,
  `profiles_added`, `profiles_removed`, `newest_profile_date`. Drives "data updated N hours ago".
- `query_log` (new): `logged_at`, `question`, `query_type`, `intent`, `latency_ms`, `success`, `cached`,
  `llm_used`. No IP addresses or other personal data.

**Search** is a single SQL query that combines filters and vector similarity:
`... WHERE region = :region AND EXTRACT(month FROM profile_date) = :month ... ORDER BY embedding <=> :q LIMIT 8`.
If the filters return nothing, the query is retried without them, as today.

**Database roles**

- `floatchat_admin` (owner): used only by the GitHub Actions data jobs and local ingest.
- `floatchat_reader`: used by the API. `SELECT` on `floats`, `profiles`, `measurements`, `ingest_runs`;
  `INSERT` on `query_log` only. Role-level `statement_timeout = 5s`. LLM-generated SQL can therefore never write,
  even if it gets past the code-level check.

**Size estimate:** ~15,500 profiles, ~370,000 measurement rows, ~25 MB of embeddings; ~100 MB total with indexes.

**Local development:** `docker-compose.yml` switches to the `pgvector/pgvector:pg16` image; the same migration
creates the same schema locally and on Neon.

**Schema management:** a single idempotent SQL migration file (`floatchat/db/schema.sql`) applied by the pipeline
(`CREATE ... IF NOT EXISTS`). No migration framework at this size.

## 2. Data pipeline and daily refresh

The fetch/ingest scripts become a `pipeline/` package with four steps.

1. **Fetch** (`pipeline/erddap.py`): download profiles for a date range and bounding box from Ifremer ERDDAP in
   5-day windows with retries.
   - Core dataset `ArgoFloats`: `temp`, `psal`; each value is kept only if its own QC flag (`temp_qc`, `psal_qc`)
     is 1 or 2 (good / probably good), otherwise it becomes missing and is filled by interpolation.
   - BGC dataset `ArgoFloats-synthetic-BGC`: `doxy_adjusted`, `chla_adjusted`, `nitrate_adjusted`,
     `ph_in_situ_total_adjusted`, each kept only if its `*_adjusted_qc` is 1 or 2.
   - Rows where every variable is missing are dropped.
   - Duplicate (float, cycle, pressure) rows are dropped, as in the current script.
2. **Shape** (`pipeline/shape.py`): interpolate each profile onto the 24 standard pressure levels (5–2,000 dbar),
   label its region (`ocean_regions.region_for`), and set the sensor flags.
3. **Describe & embed** (`pipeline/describe.py`, `pipeline/embed.py`): build the description sentence (current wording, extended with
   chlorophyll/nitrate/pH facts when present). Embed with all-MiniLM-L6-v2 via onnxruntime **without padding to
   256 tokens** (dynamic padding per batch). The embedding cache file is kept for the bundled snapshot.
4. **Load** (`pipeline/load.py`): apply the schema, insert new profiles and their measurements
   (`ON CONFLICT (float_id, cycle_number) DO NOTHING`), update `floats`, delete profiles older than the window,
   and record an `ingest_runs` row. Bulk inserts use `COPY` for speed.

**Entry point:** `python -m pipeline {backfill|refresh|snapshot} [--start] [--end]`.

- `backfill`: the last 12 months (or a given range) into the database pointed to by `DATABASE_URL`.
- `refresh`: the last 10 days (late-arriving profiles), then prune anything older than 12 months.
- `snapshot`: load the bundled `data/` snapshot. Used by local Docker and tests; no network needed.

**GitHub Actions**

- `backfill.yml`: manual trigger (`workflow_dispatch`) with optional start/end inputs; uses the
  `NEON_ADMIN_URL` secret.
- `refresh.yml`: daily at 02:00 UTC plus manual trigger. A final step re-enables the workflow through the GitHub
  API, so GitHub's 60-day inactivity rule never disables it.
- **Failure behaviour:** fetch retries (3 attempts with backoff per window); if a run still fails, the job fails
  (red mark plus GitHub's email notification). An `ingest_runs` row with `status = 'failed'` is written when the
  database is reachable. The live site keeps serving the previous data.

**Bundled snapshot:** `data/argo_profiles.csv.gz` plus the embedding cache stay in the repo for offline local use
and tests, regenerated occasionally with `fetch` (not by the daily job, to avoid daily data commits).

## 3. API structure and protection

**Code layout**

```
floatchat/          core logic, no web framework imports
  config.py         settings from env
  db/               engine/session, schema.sql, queries (stats, floats, profiles, exports)
  search.py         vector search with filters (pgvector)
  sql_agent.py      current nl_to_sql logic, moved and adapted to the new schema
  llm.py            OpenAI-compatible client (current llm.py)
  regions.py        current ocean_regions.py
  embedder.py       ONNX MiniLM query embedder (shared with pipeline/embed.py)
  answer.py         builds the answer (SQL rows or matching profiles, LLM explanation)  (from main.py)
  exports.py        CSV / NetCDF / ASCII exports                                   (from export_utils.py)
api/
  main.py           FastAPI app, routers, CORS, middleware
  limits.py         per-IP rate limiter + daily LLM budget
  cache.py          answer cache
pipeline/           see section 2
```

The existing `main.py`, `nl_to_sql.py`, `ocean_regions.py`, `llm.py`, `export_utils.py` and `ingest.py` move into
this layout. **The public endpoints and their JSON shapes stay the same** (`/query`, `/stats`, `/floats`,
`/get_profiles`, `/profiles/float/{id}`, `/float/{id}`, `/export`, `/health`, `/sample-queries`), so the Streamlit
app keeps working. `/stats` gains `last_updated` and the BGC float counts; `/health` gains `newest_data` and
`version`. New: `GET /ping` (no database access) for the keep-awake scheduler.

**Protection for the public demo**

- **Rate limits per client IP** (taken from `X-Forwarded-For` behind Koyeb's proxy): 10 `/query` calls per minute
  and 100 per day. Over the limit: HTTP 429 with a friendly JSON message the frontend can show. Other endpoints:
  60 calls per minute. Stored in memory (single instance; resets on restart, which is acceptable).
- **Daily LLM budget:** `LLM_DAILY_BUDGET` (default 2,000 calls). When exhausted, answers fall back to
  data-only mode and `/health` reports `llm.budget_exhausted = true`. The site never errors because of it.
- **Answer cache:** key = normalised question + newest `ingest_runs.run_id`; in-memory LRU with 500 entries and a
  24 h TTL. New data changes the key, so the cache never serves stale answers.
- **Input limits:** questions are trimmed and capped at 300 characters (HTTP 422 beyond that); exports are capped at
  50 profiles per request.
- **CORS:** `ALLOWED_ORIGINS` env var (the Vercel domain(s) and `http://localhost:3000`, `http://localhost:8501`).
- **Secrets:** Groq key and database URLs exist only as Koyeb / GitHub secrets and in local `.env`; never in
  responses or logs.
- **Query log:** every `/query` writes one `query_log` row (best effort; logging failures never fail the request).

## 4. Deployment

- **`Dockerfile.api`:** `python:3.11-slim`, `requirements-api.txt` (FastAPI, uvicorn, SQLAlchemy, psycopg,
  pgvector, onnxruntime, tokenizers, numpy, pandas, xarray + netCDF4 for exports, requests). The MiniLM model is
  downloaded at build time. Runs uvicorn with 1 worker. Memory budget: **≤ 350 MB RSS** after warm-up and 20
  queries, measured locally with `docker stats`.
- The existing `Dockerfile` remains for the Streamlit frontend until Phase 4.
- **Neon:** one project, region matched to the Koyeb instance (Frankfurt or Washington). Roles as in section 1.
- **Koyeb:** one free web service deploying `Dockerfile.api` from the GitHub repo, auto-deploy on push to `main`,
  health check on `/health`. Environment: `DATABASE_URL` (reader role), `LLM_BASE_URL`, `LLM_MODEL`,
  `LLM_API_KEY`, `LLM_DAILY_BUDGET`, `ALLOWED_ORIGINS`.
- **Keep awake:** cron-job.org calls `GET /ping` every 30 minutes (Koyeb's free instance sleeps after 1 h idle).
  `/ping` returns `{"ok": true}` without touching the database, so it keeps the API awake while Neon can still
  suspend between real visits and save its compute hours.
- **GitHub secrets:** `NEON_ADMIN_URL` (for the data jobs).
- **`DEPLOY.md`:** step-by-step account setup (Neon, Koyeb, cron-job.org), role creation SQL, where each secret
  goes, how to run the backfill, and how to verify. The user creates accounts and enters keys; Claude does not.

## 5. CI and testing

**`ci.yml`** on every push and pull request:

1. **Lint:** `ruff check`.
2. **Unit tests:** region parsing, question routing, SQL safety check, rate limiter, LLM budget, answer cache,
   description builder, dynamic-padding embedder (same vectors as the padded version within 1e-4 cosine).
3. **Pipeline tests:** recorded ERDDAP CSV responses in `tests/fixtures/` (core + BGC, a few profiles each) cover
   parsing, QC filtering, interpolation, BGC merge and de-duplication. No network.
4. **Integration tests:** a `pgvector/pgvector:pg16` service container. Load a ~50-profile fixture via the pipeline,
   create the reader role, then call the API with FastAPI's TestClient: SQL question, search question,
   region/month/oxygen filters, `/floats`, `/stats`, CSV/NetCDF/ASCII export, HTTP 429 after the limit, and a
   write attempt through the reader role that must fail.
5. **Container check:** build `Dockerfile.api`, start it against the CI database, call `/health`, and fail if
   memory exceeds 350 MB.

**`scripts/smoke_test.py <api-url>`:** asks five real questions against a deployed API and prints answers,
query types and latencies; run after each deploy.

The existing `tests/test_floatchat_core.py` cases move with the code. The older dashboard tests
(`components/`) are excluded from CI because they belong to the experimental dashboard, which is retired in
Phase 4.

## Done criteria

- [ ] The Koyeb URL answers SQL and search questions over 12 months of Indian Ocean data with oxygen,
      chlorophyll, nitrate and pH.
- [ ] `/health` shows the database connected, the newest data date, and the LLM connected (with the user's Groq key).
- [ ] The daily refresh has run successfully on schedule at least once, visible in `ingest_runs`.
- [ ] Rate limits, the LLM budget fallback and the answer cache verified (tests plus one manual check on the live API).
- [ ] CI is green; the API container stays under 350 MB.
- [ ] The Streamlit app still works locally against the new backend (`docker compose up`).
- [ ] `DEPLOY.md` is complete and the smoke test passes against the live URL.

## Risks

| Risk | Mitigation |
|---|---|
| 0.1 vCPU makes queries slow | Dynamic padding (short questions embed in milliseconds); no heavy work on the server; caching; measure in the container check |
| Koyeb free-tier terms change (acquired by Mistral AI in 2026) | The API is a plain Docker image; moving to Render free or a paid host is a config change, documented in `DEPLOY.md` |
| ERDDAP slow or down | Retries; the daily job fails visibly; the site serves the last good data |
| Neon compute-hour cap (100 CU-hours/month) | The keep-awake ping uses `/ping`, which never touches the database, so Neon only runs during real visits and data jobs. Check usage after the first week |
| Neon cold start (~1 s after auto-suspend) | Acceptable for a first question; the answer cache and Neon's warm period cover follow-ups |
| Groq free-tier limits | Daily LLM budget, caching, data-only fallback |
