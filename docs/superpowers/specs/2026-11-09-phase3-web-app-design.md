# Phase 3: Next.js web app

**Status:** design written to keep building overnight (user preference: build, then review). Everything below is
easy to change; the decisions most worth a look are marked ★.

## Goal

Replace the Streamlit stopgap with a fast, good-looking site a recruiter can open on a phone: a landing page that
explains how FloatChat works and lets you try it, a chat that shows its work live, and float pages with real
oceanography views. Architecture A stays: FastAPI owns all data and AI; the site only displays results.

## Decisions

- ★ **Where:** `web/` in this repo (one repo, one README). Vercel project root directory = `web`.
- **Stack:** Next.js (App Router, TypeScript, React Server Components), Tailwind CSS, Observable Plot for charts,
  d3-geo + topojson for maps. No map tiles, no API keys, nothing paid.
- ★ **Calls go from the browser straight to the API** (`NEXT_PUBLIC_API_URL`). Each visitor's real IP reaches the
  API's rate limiter through Cloudflare, so no proxy or shared token is needed, and SSE streams directly. Render's
  `ALLOWED_ORIGINS` must include the Vercel domain. Landing-page numbers are fetched on the server with
  revalidation (10 minutes), so the page renders instantly and costs the API almost nothing.
- **Benchmark score** comes from `eval/latest.json` on GitHub (raw URL), revalidated daily, so the site always shows
  the latest weekly run without a redeploy.
- ★ **Look ("scientific instrument", not "AI product"):** the generic AI palette (purple/indigo glows, cyan on navy,
  gradient text) is out. Instead:
  - **Neutrals:** graphite. Dark `#0d0e10` → `#16181b` surfaces, light `#f3f4f2` → `#ffffff`; hairline borders.
    Both themes, following the system setting, with a toggle.
  - **One UI accent: marine safety orange** (`#ff5b1f` dark / `#e2470f` light), the colour of buoys and ocean
    instruments. Used only for the primary action, focus, live state and the active step.
  - **Data colours are the oceanographers' own:** cmocean `thermal` (temperature), `haline` (salinity), `oxy`
    (oxygen), `deep` (depth), exported from the cmocean package. UI accent and data colours never mix.
  - **Type:** Geist for text, Geist Mono for numbers, SQL and the run log. Tabular numerals everywhere data appears.
  - **Shape:** cards 14 px, inputs and buttons full pill, chips 8 px. Icons from Phosphor (one weight).
  - **Motion (dial 5):** spring entrances, steps sliding into the run log as they happen, globe auto-rotation;
    all of it off under `prefers-reduced-motion`.
- **Agent UI, from current agent-UX guidance** (visible tool calls with inputs/outputs, a chronological action log,
  calibrated confidence instead of long reasoning prose, explicit stop/retry controls):
  - each answer opens with a compact **run log**: one row per step (Understood, SQL attempt n, Search, Writing) with
    a status icon, duration and an expandable detail (filters, SQL text, rows, matches);
  - honest signals are first-class: "keyword fallback" when the LLM router wasn't used, "repaired SQL" when a retry
    happened, "no exact match, widened" when filters found nothing;
  - **Stop** cancels the stream; **Retry** re-asks; **Copy SQL**; suggested follow-ups as chips.
- Light/dark contrast WCAG AA. Works at 360 px width.

## Pages

### `/` Landing
1. **Hero:** "Ask the Indian Ocean anything" over a rotating globe (canvas, orthographic d3-geo projection, drag to
   spin) with every active float as a dot coloured by surface temperature; click a float to open its page.
   Live counters: floats, profiles, measurements, newest data date.
2. **Try it:** a question box plus sample-question chips; submitting opens `/chat?q=…` and starts streaming.
3. **How it works:** a scroll-through of five steps with small diagrams: Argo floats dive → nightly pipeline (ERDDAP,
   QC, 24 standard depths, descriptions, embeddings) → Postgres + pgvector → router (LLM with keyword fallback) picks
   SQL or search and filters → answer with the step trace. Each step names the real component.
4. **Proof:** benchmark card (questions fully correct, routing / filters / answer checks, median latency) linking to
   the per-question table; stack badges; GitHub link.

### `/chat`
- Streams `POST /query/stream` with `fetch` + a `ReadableStream` SSE parser (EventSource can't POST).
- **Live step trace** above each answer: Understood (router, path, analysis, filters as chips) → SQL attempt(s) with
  rows and ms, or Search with match count → Writing. Steps appear as events arrive; the answer text streams in.
- Result views: per-analysis chart (depth profile lines, region bars, depth-layer bars, monthly lines, top floats,
  BGC by zone), the SQL (collapsible, monospace), the data table; for searches, matching profiles as cards with a
  mini map and links to float pages.
- Follow-ups: the last 3 answered turns go along as `history`. Clear 429 / network / cold-start messages.

### `/floats/[id]`
- Summary (WMO id, profiles, first/last date, sensors, region), trajectory map, latest profile (temperature,
  salinity, oxygen vs depth), **T-S diagram** (all profiles, dots coloured by depth), **depth-time section**
  (temperature as a heatmap, date × depth). Built from `/float/{id}`, `/profiles/float/{id}` and `/get_profiles`.

### `/compare?floats=a,b`
- Two floats side by side: overlaid T-S diagrams and mean temperature/salinity profiles. Entry from a float page.

## API changes

None planned; the existing endpoints cover every view. If a view needs a cheaper query (e.g. a float's full
depth-time grid in one call) it is added as a read-only endpoint with a test.

## Testing

- Vitest unit tests for the SSE parser, the step-trace reducer and the chart data shaping.
- CI job: `npm ci`, lint, type-check, unit tests, `next build`.
- Manual check in the browser pane against the live API (desktop and 375 px), with screenshots for the PR.

## Deployment (user steps, documented in DEPLOY.md)

Import the repo on Vercel with root directory `web`, set `NEXT_PUBLIC_API_URL`, then add the Vercel domain to
`ALLOWED_ORIGINS` on Render.

## Non-goals

Accounts, server-side chat history, retiring Streamlit and the launch video (Phase 4).

## Done criteria

- [ ] Landing page live on Vercel with real numbers, globe, how-it-works and the benchmark score.
- [ ] Chat streams steps and tokens from the live API, follow-ups work, charts render per analysis.
- [ ] Float page shows trajectory, T-S diagram and depth-time section; compare works for two floats.
- [ ] CI builds and tests the web app; Lighthouse performance and accessibility ≥ 90 on the landing page.
