# 🌊 FloatChat: talk to the ocean

**Ask questions about real ocean data in plain English, and get answers with maps and charts.**

![FloatChat overview](docs/screenshots/overview.png)

**Contents:** [What FloatChat is](#-what-floatchat-is) · [How it's built](#-how-its-built) ·
[Run it on your machine](#-run-it-on-your-machine) · [Using it](#-using-floatchat) ·
[Limitations & roadmap](#-limitations--roadmap)

---

## 🌍 What FloatChat is

### The ocean has sensors everywhere, and almost nobody can use the data

[Argo](https://argo.ucsd.edu) is an international program that keeps about **4,000 robotic floats** drifting in
the world's oceans. Each float parks about 1,000 m deep. Every ~10 days it dives to 2,000 m, then rises to the
surface measuring **temperature, salinity** and, on biogeochemical (BGC) floats, **dissolved oxygen** and other
chemistry. At the surface it sends this **profile** home by satellite. Argo data feed climate research, monsoon and
cyclone forecasting, fisheries and ocean models, and the data are free for anyone to use.

The catch is that using the data takes specialist skills. It comes as NetCDF files from data servers, organised by
float and cycle, with quality flags and pressure coordinates. To answer something simple, like *"how much colder is
the Bay of Bengal at 500 m than at the surface?"* or *"where is the oxygen minimum zone in the Arabian Sea?"*, you
need to know which files to download, how to read them, and how to write the analysis code.

### Why we're building FloatChat

FloatChat removes that barrier. You type a question as you'd ask a colleague, and FloatChat:

1. works out what kind of question it is,
2. finds the right data, either by **writing SQL** for statistical questions or by **searching** thousands of
   profiles for descriptive ones,
3. answers in words, optionally explained by a large language model (LLM), and
4. draws the **maps, depth profiles and charts** that go with the answer, with the data ready to download.

It's built for students, researchers, educators and curious people who want to explore the ocean without first
becoming data engineers.

### What happens when you ask a question

| You ask… | FloatChat… |
|---|---|
| *"What is the average temperature at different depths?"* | spots a statistical question → runs SQL on PostgreSQL → answers with a temperature/salinity vs depth chart and the SQL it used |
| *"Show me salinity profiles near the equator in March 2024"* | spots a descriptive question → reads "equator" and "March 2024" as filters → searches its vector index of profile descriptions → shows the matching profiles on a map and plots them |
| *"Which floats measured low oxygen in the Arabian Sea?"* | limits the search to oxygen-measuring floats in the Arabian Sea → lists them with their oxygen minimum and depth |

| Statistical question → SQL + chart | Descriptive question → search + map & profiles |
|---|---|
| ![SQL answer](docs/screenshots/chat-sql.png) | ![RAG answer](docs/screenshots/chat-rag.png) |

### The data in this demo

The repo ships with **real Argo observations** from the **Indian Ocean, January–March 2024**, downloaded from the
[Ifremer ERDDAP](https://erddap.ifremer.fr/erddap/) server:

- **438 floats**, **3,891 profiles**, **88,541 measurements** from the surface down to 2,000 m
- **61 BGC floats** with dissolved-oxygen data, which show the Arabian Sea's oxygen minimum zone clearly
- Each profile is labelled with a region: Arabian Sea, Bay of Bengal, Equatorial, Southern and Eastern Indian Ocean,
  Red Sea & Gulf of Aden

You can download a different period or ocean region with one command (see [Using other data](#using-other-data)).

---

## 🏗️ How it's built

```
                       ┌────────────────────────── backend (FastAPI, main.py) ───────────────────────────┐
 ┌─────────────┐  HTTP │                                                                                 │
 │  Streamlit  │ ────► │  POST /query ─► is it statistical?                                              │
 │  frontend   │       │                  ├─ yes ─► nl_to_sql.py: template or LLM-written SQL ─► PostgreSQL
 │  (app.py)   │ ◄──── │                  └─ no ──► ChromaDB vector search (+ region/month/oxygen filters)│
 └─────────────┘  JSON │                              └─► llm.py: LLM writes the answer from the matches │
                       │  /stats /floats /get_profiles /export … ─────────────────────────► PostgreSQL   │
                       └─────────────────────────────────────────────────────────────────────────────────┘
                                ▲
     scripts/fetch_argo_data.py ─► data/argo_profiles.csv.gz ─► ingest.py ─► PostgreSQL + ChromaDB
```

### 1. Data pipeline: getting the ocean data in

| Component | What it does |
|---|---|
| `scripts/fetch_argo_data.py` | Downloads Argo profiles for a date range and region from ERDDAP, in 5-day chunks. Core floats provide temperature and salinity; the BGC dataset adds dissolved oxygen. Each profile is interpolated onto 24 standard pressure levels (5–2,000 dbar) so the dataset stays small. The result is saved as `data/argo_profiles.csv.gz`. |
| `data/argo_profiles.csv.gz` | The bundled seed dataset (0.9 MB). Nothing extra needs downloading. |
| `ingest.py` | Turns the seed file into a database. It creates the PostgreSQL tables, writes one sentence-style description per profile (*"Float 2902203, cycle 45, 11 Feb 2024, 12.3°N 65.2°E in the Arabian Sea, surface 28.1 °C…"*), embeds those descriptions and stores them in ChromaDB. `--if-empty` skips everything if the data is already loaded. |
| `data/profile_embeddings.npz` | Precomputed embeddings for the bundled profiles. Embedding about 4,000 descriptions on a CPU takes ~5 minutes; with this cache a fresh install is ready in ~30 seconds. Profiles whose descriptions change are re-embedded automatically. |
| `ocean_regions.py` | Defines the named regions. It labels each profile with its region, and spots region names, months, years and oxygen terms in your questions so they can be used as search filters. |

### 2. Storage

- **PostgreSQL** holds the numbers, in three tables:
  - `floats`: one row per float (WMO ID, first/last position and date)
  - `profiles`: one row per dive cycle (float, cycle number, date, position, region, number of levels)
  - `measurements`: one row per depth level (pressure/depth, temperature, salinity, oxygen)
- **ChromaDB** holds the vector index: one embedded text description per profile, plus metadata (float, date, month,
  region, position, whether it measures oxygen) used for filtering.

### 3. Backend: the FastAPI service (`main.py`)

| Endpoint | Purpose |
|---|---|
| `POST /query` | The main endpoint. It takes a question and returns the answer text, the query type (`analytical` or `semantic`), the SQL rows or matching profiles, and the context used. |
| `GET /stats` | Dataset totals, date range and profiles per region (the overview tiles). |
| `GET /floats` | Each float's latest position and surface readings (the overview map). |
| `POST /get_profiles` | All depth levels for the requested profiles (the profile plots). |
| `GET /profiles/float/{id}`, `GET /float/{id}` | One float's trajectory and summary (the float explorer). |
| `POST /export` | Profiles as CSV, NetCDF or ASCII. |
| `GET /health` | Status of the database, vector index and LLM. |

Interactive API docs are at `http://localhost:8000/docs` while the backend is running.

Supporting modules:

| Component | What it does |
|---|---|
| `nl_to_sql.py` | Decides whether a question is statistical, and which kind (by depth, by region, by depth layer, monthly trend, per float, oxygen). Known kinds run hand-written SQL templates. Other statistical questions go to the LLM, which writes the SQL. Before anything runs, the SQL is checked to be a single read-only `SELECT`. |
| `llm.py` | A small client for any **OpenAI-compatible** chat API: Groq, OpenAI, Ollama, LM Studio, vLLM and others. When no LLM is configured, or the call fails, FloatChat falls back to answers built directly from the data, so the app still works. |
| `export_utils.py` | Builds the CSV, NetCDF (CF-style attributes) and ASCII exports. |
| `config.py` | Reads all settings from environment variables / `.env`. |

### 4. Frontend: the Streamlit app (`app.py`)

- **Overview page:** headline numbers, a live map of every float coloured by surface temperature, profiles per
  region, and a **float explorer**. Click any float on the map to see its trajectory and latest depth profiles.
- **Ask FloatChat page:** a chat with suggestion cards. Each answer comes with:
  - a badge showing how it was answered (SQL or profile search) and how long it took
  - a chart, or a map plus temperature/salinity/oxygen profiles
  - the data table and SQL
  - download buttons
- The sidebar shows whether the database, vector index and LLM are connected.

### 5. Packaging & deployment

| Component | What it does |
|---|---|
| `Dockerfile` | One image for backend and frontend, with the embedding model pre-downloaded. |
| `docker-compose.yml` | Runs PostgreSQL, the backend (which loads the data on first start) and the frontend. |
| `render.yaml` | Blueprint for deploying to [Render](https://render.com). |
| `.env.example` | Every setting, with examples for Groq, Ollama, LM Studio and OpenAI. |
| `tests/test_floatchat_core.py` | Tests for region parsing, question routing and the SQL safety check. |

### Repository layout

```
FloatChat-AI/
├── app.py                  # Streamlit frontend (the demo)
├── main.py                 # FastAPI backend
├── nl_to_sql.py            # question routing + SQL templates + SQL safety
├── llm.py                  # OpenAI-compatible LLM client (Groq, Ollama, …)
├── ingest.py               # loads data into PostgreSQL + ChromaDB
├── ocean_regions.py        # region labels + question filters
├── export_utils.py         # CSV / NetCDF / ASCII export
├── config.py               # settings from .env
├── scripts/fetch_argo_data.py
├── data/                   # bundled Argo data + embedding cache
├── docs/screenshots/
├── tests/
├── Dockerfile, docker-compose.yml, render.yaml, requirements.txt, .env.example
├── streamlit_app.py, components/, styles/, utils/   # experimental dashboard (WIP, see README_DASHBOARD.md)
└── legacy/                 # early prototype scripts, kept for reference
```

---

## 🚀 Run it on your machine

### What you need

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**, installed and running
- **git**
- *(optional)* a free **[Groq API key](https://console.groq.com/keys)**, so the AI can write explanations

You don't need to download any data, models or databases by hand; Docker fetches everything. The app uses ports
**8501** (app), **8000** (API) and **5433** (database).

### Option A: Docker (recommended)

**1. Clone the repository**

```bash
git clone https://github.com/CodexManvik/FloatChat-AI.git
```

```bash
cd FloatChat-AI
```

**2. Create your settings file**

```bash
cp .env.example .env
```

(On Windows Command Prompt use `copy .env.example .env`.) To use Groq, open `.env` and paste your key:

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_your_key_here
```

You can skip the key: FloatChat still answers every question, just without written explanations. If Groq has
retired that model, choose any chat model listed in the Groq console.

**3. Start everything**

```bash
docker compose up --build
```

The first run takes a few minutes while Docker downloads Python packages and builds the image. The backend then
loads the data in about 30 seconds. You're ready when the log shows `Uvicorn running on http://0.0.0.0:8000`.

**4. Open the app**

- App: **http://localhost:8501**
- API docs: http://localhost:8000/docs

The sidebar should show green dots for PostgreSQL and the vector index. The LLM dot is green if your key works and
amber if no LLM is configured.

**Stopping and restarting**

- `Ctrl+C`, or `docker compose down` stops everything; your data is kept.
- `docker compose up` starts again in seconds.
- After editing `.env`, run `docker compose up -d backend` to apply the change.
- `docker compose down -v` wipes the database; it is reloaded on the next start.

### Option B: without Docker (for development)

You need Python 3.11+ and PostgreSQL. The easiest way to get PostgreSQL is `docker compose up -d db`, which listens
on port 5433 and matches the default `DATABASE_URL`.

```bash
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # add your LLM key, or point DATABASE_URL at your own PostgreSQL

python ingest.py                   # load data into PostgreSQL + build the vector index (~30 s)
uvicorn main:app --port 8000       # terminal 1: backend
streamlit run app.py               # terminal 2: frontend → http://localhost:8501
```

Run the tests with `python -m pytest tests/test_floatchat_core.py`.

### Troubleshooting

| Problem | Fix |
|---|---|
| `port is already allocated` | Something else is using 8501, 8000 or 5433. Stop it, or change the left-hand port in `docker-compose.yml`. |
| App says it can't reach the API | The backend is still loading data; wait for `Uvicorn running…` in the logs (`docker compose logs -f backend`). |
| LLM dot is red: *missing or invalid LLM_API_KEY* | Check the key in `.env`, then run `docker compose up -d backend`. |
| LLM dot is red: *cannot connect* | Check `LLM_BASE_URL`. If you use Ollama on your own machine while the app runs in Docker, use `http://host.docker.internal:11434/v1`. |
| You want a clean start | `docker compose down -v`, then `docker compose up --build`. |

---

## 💬 Using FloatChat

Questions to try:

- What is the average temperature at different depths?
- Compare surface temperature across ocean regions
- Show average salinity by depth range
- Show me salinity profiles near the equator in March 2024
- Which floats measured low oxygen in the Arabian Sea?
- Average dissolved oxygen by ocean zone
- Show the monthly temperature trend
- Show a summary for each float

Tips:

- Words like *average, compare, trend, count, summary* trigger the SQL path. Descriptive questions search the
  profiles; naming a region, month or "oxygen" narrows the search.
- **Demo links:** `http://localhost:8501/?q=Average%20dissolved%20oxygen%20by%20ocean%20zone` opens the chat with that
  question already asked. They're handy in presentations.
- The **Data & export** tab under an answer downloads its profiles as CSV, NetCDF or ASCII.

### Using other data

```bash
python scripts/fetch_argo_data.py --start 2024-06-01 --end 2024-09-01 --bbox=-40,30,30,120
python ingest.py
```

`--bbox` is `lat_min,lat_max,lon_min,lon_max`. New data needs new embeddings, which takes a few minutes on a CPU;
after that the cache is updated. If you fetch another ocean basin, update the region boxes in `ocean_regions.py`.

---

## 🗺️ Limitations & roadmap

- The data is a three-month Indian Ocean snapshot, not a live feed. Next step: scheduled ingestion of recent profiles.
- Deciding between SQL and search uses keywords; an LLM-based router would understand more phrasings.
- Region boundaries are approximate boxes.
- Only temperature, salinity and oxygen are loaded. BGC floats also measure pH, chlorophyll and nitrate, which could
  be added to `fetch_argo_data.py`.
- `streamlit_app.py` and `components/` are an experimental, feature-heavy dashboard that still uses mock data in
  places. They are not part of the demo (see `README_DASHBOARD.md`).
- `legacy/` holds early prototype scripts that are no longer used.

## 🙏 Acknowledgments

These data were collected and made freely available by the International Argo Program and the national programs
that contribute to it ([argo.ucsd.edu](https://argo.ucsd.edu), [ocean-ops.org](https://www.ocean-ops.org)). The
Argo Program is part of the Global Ocean Observing System. Data were accessed through the
[Ifremer ERDDAP](https://erddap.ifremer.fr/erddap/) server.
