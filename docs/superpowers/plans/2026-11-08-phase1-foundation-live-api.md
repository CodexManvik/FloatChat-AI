# Phase 1: Foundation & Live API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ChromaDB with pgvector on Postgres, load 12 months of quality-controlled Indian Ocean Argo data (with oxygen, chlorophyll, nitrate, pH) through a refreshable pipeline, harden the API for a public demo, and deploy it on Koyeb + Neon with CI.

**Architecture:** Three Python packages: `floatchat/` (core logic: config, embedder, database access, search, SQL agent, answers), `pipeline/` (ERDDAP fetch → shape → describe/embed → load, with a CLI used by GitHub Actions), and `api/` (a thin FastAPI layer with rate limits, an LLM budget and caches). One Postgres database with pgvector holds measurements and profile embeddings. The API connects through a read-only role.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2 + psycopg 3, PostgreSQL 16 + pgvector, onnxruntime + tokenizers (all-MiniLM-L6-v2), pandas/numpy, pytest, ruff, Docker, GitHub Actions, Koyeb, Neon, cron-job.org.

**Spec:** `docs/superpowers/specs/2026-11-08-phase1-foundation-live-api-design.md`

## Global Constraints

- Python **3.11**. Pinned versions: fastapi 0.161.1, uvicorn[standard] 0.54.0, SQLAlchemy 2.1.6, psycopg[binary] 3.3.6, numpy 2.4.6, pandas 3.1.0, onnxruntime 1.31.0, tokenizers 0.23.3, xarray 2026.9.0, netCDF4 1.7.5, requests 2.34.2, python-dotenv 1.2.4, streamlit 1.66.1, plotly 7.1.0, ruff 0.17.4, httpx 0.28.1, pytest ≥ 8.
- API container memory: **≤ 350 MB RSS** after warm-up and 20 queries (Koyeb free instance: 512 MB, 0.1 vCPU).
- Database: Neon free plan, **1 GB** storage; expected usage ~100 MB.
- Data: Indian Ocean bounding box **lat −40…30, lon 30…120**; rolling **365-day** window; **24 standard pressure levels** (5–2,000 dbar); keep only measurements with QC flag **1 or 2**.
- Embeddings: **all-MiniLM-L6-v2 ONNX, 384 dimensions**, cosine distance, dynamic padding (max 256 tokens).
- `/query` limits per client IP: **10 per minute, 100 per day**; other endpoints **60 per minute**; `/ping` and `/health` unlimited. `LLM_DAILY_BUDGET` default **2,000**. Answer cache **500 entries, 24 h TTL**. Questions **≤ 300 characters**. Exports **≤ 50 profiles**.
- API database role `floatchat_reader`: `SELECT` on `floats`, `profiles`, `measurements`, `ingest_runs`; `INSERT` on `query_log`; `statement_timeout = 5s`.
- Public endpoint JSON shapes stay compatible with `app.py` (Streamlit), except `/health`'s `chromadb` key, which becomes `vector_index` (app.py updated in Task 11).
- Never put secrets in code, logs or responses. The user creates all accounts and pastes all keys; the agent never does.
- Do **not** modify the experimental dashboard (`streamlit_app.py`, `components/`, `styles/`, `utils/`, `dashboard_config.py`).
- Lint with `ruff check`; if it reports only import-order (I001) issues, run `ruff check --fix` and re-check.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `phase1-foundation`.

## File Structure

```
floatchat/
  __init__.py          package version
  config.py            all settings from env/.env
  regions.py           region boxes, question filter parsing        (from ocean_regions.py)
  llm.py               OpenAI-compatible chat client                 (from llm.py)
  embedder.py          ONNX MiniLM with dynamic padding + model download
  db/
    __init__.py
    schema.sql         idempotent schema (tables, indexes, pgvector)
    engine.py          make_engine, apply_schema, reset_schema, schema_is_current
    roles.py           create_reader_role, reader_url
    queries.py         stats, floats, profiles, float info, data_status, log_query
  search.py            pgvector search with filters
  exports.py           CSV / NetCDF / ASCII exports                  (from export_utils.py)
  sql_agent.py         SqlAgent: routing, templates, LLM SQL, safety (from nl_to_sql.py)
  answer.py            answer_question: SQL or search answer + formatting (from main.py)
pipeline/
  __init__.py
  __main__.py          CLI: backfill | refresh | snapshot | fetch | create-reader | reset
  erddap.py            ERDDAP URLs, fetch with retries, QC filter
  shape.py             standard-level interpolation, seed table, floats/profiles/measurements tables
  describe.py          profile description sentences
  embed.py             embed_with_cache
  load.py              insert new profiles (COPY), prune, ingest_runs bookkeeping
api/
  __init__.py
  main.py              FastAPI app factory + endpoints
  limits.py            RateLimiter, DailyBudget, client_ip
  cache.py             TTLCache, normalize_question
scripts/
  smoke_test.py        5 live questions against a deployed API
  container_check.sh   CI: run API image, fire 20 queries, enforce memory budget
tests/
  __init__.py
  fakes.py             FakeEmbedder (deterministic, no model download)
  fixtures/erddap_core.csv, erddap_bgc.csv, seed_small.csv.gz
  unit/                no database needed
  integration/         needs Postgres + pgvector (conftest.py manages it)
  dashboard/           old experimental-dashboard tests (excluded from CI)
.github/workflows/ci.yml, refresh.yml, backfill.yml
Dockerfile.api, Dockerfile (Streamlit), docker-compose.yml
requirements-api.txt, requirements-frontend.txt, requirements-dev.txt, requirements.txt
pyproject.toml         ruff + pytest config
DEPLOY.md
```

Removed in Task 11: root `main.py`, `nl_to_sql.py`, `export_utils.py`, `ocean_regions.py`, `llm.py`, `config.py`, `ingest.py`, `scripts/fetch_argo_data.py`, `render.yaml`, `tests/test_floatchat_core.py` (moved), ChromaDB.

---

### Task 1: Package skeleton, tooling and moved helpers

**Files:**
- Create: `floatchat/__init__.py`, `floatchat/config.py`, `floatchat/regions.py`, `floatchat/llm.py`, `pyproject.toml`, `requirements-api.txt`, `requirements-frontend.txt`, `requirements-dev.txt`, `tests/fakes.py`, `tests/unit/__init__.py`, `tests/unit/test_regions.py`, `tests/integration/__init__.py`
- Modify: `requirements.txt`
- Move: `tests/test_*.py` except `test_floatchat_core.py` → `tests/dashboard/`

**Interfaces:**
- Produces: `floatchat.config` attributes `DATABASE_URL`, `ADMIN_DATABASE_URL`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_DAILY_BUDGET`, `QUERY_LIMIT_PER_MINUTE`, `QUERY_LIMIT_PER_DAY`, `ALLOWED_ORIGINS: list[str]`, `SEED_DATA_PATH`, `EMBEDDING_CACHE_PATH`, `MODEL_DIR`, `DATA_WINDOW_DAYS`, `BBOX: tuple[float, float, float, float]`; `floatchat.__version__ = "3.0.0"`; `floatchat.regions.region_for(lat, lon) -> str`, `parse_filters(question) -> dict`, `MONTHS: list[str]`, `REGIONS`; `floatchat.llm.chat(prompt, system=None, temperature=0.2, max_tokens=600) -> str | None`, `is_configured() -> bool`, `status() -> dict`; `tests.fakes.FakeEmbedder` with `embed(texts, batch_size=64, pad_to=None) -> np.ndarray` and attribute `calls: int`.

- [ ] **Step 1: Move the old dashboard tests out of the way**

```bash
mkdir -p tests/dashboard tests/unit tests/integration tests/fixtures
git mv tests/test_api_client.py tests/test_backend_system.py tests/test_chat_component.py tests/test_chat_interface.py tests/test_connection_monitor.py tests/test_dashboard_setup.py tests/test_data_manager.py tests/test_data_manager_component.py tests/test_data_sampler.py tests/test_error_handler.py tests/test_error_system_integration.py tests/test_export_manager.py tests/test_export_component.py tests/test_layout.py tests/test_map_component.py tests/test_map_visualization.py tests/test_performance_optimizer.py tests/test_profile_component.py tests/test_profile_visualizer.py tests/test_query_direct.py tests/test_statistics_integration.py tests/test_statistics_manager.py tests/test_user_feedback.py tests/tasks.md tests/dashboard/
touch tests/unit/__init__.py tests/integration/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = ["legacy", "components", "styles", "utils", "tests/dashboard", "streamlit_app.py", "dashboard_config.py", "app.py"]

[tool.ruff.lint]
select = ["E", "F", "I", "B"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests/unit", "tests/integration"]
pythonpath = ["."]
markers = [
    "integration: needs PostgreSQL + pgvector (TEST_ADMIN_DATABASE_URL)",
    "model: downloads the ~80 MB embedding model",
]
```

- [ ] **Step 3: Create the requirements files**

`requirements-api.txt`:
```
fastapi==0.161.1
uvicorn[standard]==0.54.0
pydantic>=2.5
SQLAlchemy==2.1.6
psycopg[binary]==3.3.6
numpy==2.4.6
pandas==3.1.0
onnxruntime==1.31.0
tokenizers==0.23.3
xarray==2026.9.0
netCDF4==1.7.5
requests==2.34.2
python-dotenv==1.2.4
```

`requirements-frontend.txt`:
```
streamlit==1.66.1
plotly==7.1.0
pandas==3.1.0
requests==2.34.2
python-dotenv==1.2.4
```

`requirements-dev.txt`:
```
-r requirements-api.txt
-r requirements-frontend.txt
pytest>=8
ruff==0.17.4
httpx==0.28.1
```

`requirements.txt` (replace contents; convenience for "install everything"):
```
# Everything for local development. Containers use the split files.
-r requirements-dev.txt
```

Run: `.venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: installs without errors.

- [ ] **Step 4: Create `floatchat/__init__.py` and `floatchat/config.py`**

`floatchat/__init__.py`:
```python
"""FloatChat core: settings, data access, search, SQL agent and LLM client."""

__version__ = "3.0.0"
```

`floatchat/config.py`:
```python
"""
FloatChat settings. Everything comes from environment variables or a local .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _sqlalchemy_url(value: str) -> str:
    # Hosted Postgres providers (Neon, Render, ...) hand out postgres:// URLs
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix):]
    return value


# The API connects as the read-only role; the pipeline connects as the owner
DATABASE_URL = _sqlalchemy_url(os.getenv("DATABASE_URL", "postgresql+psycopg://floatchat:floatchat@localhost:5433/argo"))
ADMIN_DATABASE_URL = _sqlalchemy_url(os.getenv("ADMIN_DATABASE_URL", DATABASE_URL))

# LLM: any OpenAI-compatible chat completions endpoint (Groq, OpenAI, Ollama, LM Studio, ...)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
LLM_DAILY_BUDGET = int(os.getenv("LLM_DAILY_BUDGET", "2000"))

# Public demo protection
QUERY_LIMIT_PER_MINUTE = int(os.getenv("QUERY_LIMIT_PER_MINUTE", "10"))
QUERY_LIMIT_PER_DAY = int(os.getenv("QUERY_LIMIT_PER_DAY", "100"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")
    if origin.strip()
]

# Data
SEED_DATA_PATH = os.getenv("SEED_DATA_PATH", "./data/argo_profiles.csv.gz")
EMBEDDING_CACHE_PATH = os.getenv("EMBEDDING_CACHE_PATH", "./data/profile_embeddings.npz")
MODEL_DIR = os.getenv("MODEL_DIR", str(Path.home() / ".cache" / "floatchat" / "all-MiniLM-L6-v2"))
DATA_WINDOW_DAYS = int(os.getenv("DATA_WINDOW_DAYS", "365"))
BBOX = (-40.0, 30.0, 30.0, 120.0)  # lat_min, lat_max, lon_min, lon_max (Indian Ocean)
```

- [ ] **Step 5: Create `floatchat/regions.py`** (from `ocean_regions.py`, plus sensor filters)

```python
"""
Named ocean regions used to label profiles and to understand region names,
dates and sensor types in user questions. Boxes are approximate and cover
the Indian Ocean data.
"""

import re

# (name, keywords that refer to it in a question)
REGIONS = [
    ("Equatorial Indian Ocean", ["equator", "equatorial"]),
    ("Arabian Sea", ["arabian sea", "arabian"]),
    ("Bay of Bengal", ["bay of bengal", "bengal"]),
    ("Red Sea & Gulf of Aden", ["red sea", "gulf of aden"]),
    ("Southern Indian Ocean", ["southern indian", "south indian", "southern ocean"]),
    ("Eastern Indian Ocean", ["eastern indian", "east indian", "indonesia", "australia"]),
]

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# Question words that mean "only profiles from floats with this sensor"
SENSOR_PATTERNS = {
    "has_oxygen": r"\b(oxygen|o2|bgc|biogeochemical)\b",
    "has_chlorophyll": r"\b(chlorophyll|chl|chla|phytoplankton)\b",
    "has_nitrate": r"\b(nitrate|nutrients?)\b",
    "has_ph": r"\b(ph|acidity|acidification)\b",
}


def region_for(lat: float, lon: float) -> str:
    if -5 <= lat <= 5:
        return "Equatorial Indian Ocean"
    if lat > 10 and lon < 50:
        return "Red Sea & Gulf of Aden"
    if lat > 5 and lon < 78:
        return "Arabian Sea"
    if lat > 5 and lon < 100:
        return "Bay of Bengal"
    if lat < -5 and lon > 100:
        return "Eastern Indian Ocean"
    if lat < -5:
        return "Southern Indian Ocean"
    return "Eastern Indian Ocean"


def parse_filters(question: str) -> dict:
    """Extract region / month / year / sensor filters mentioned in a question."""
    q = question.lower()
    filters = {}
    for name, keywords in REGIONS:
        if any(k in q for k in keywords):
            filters["region"] = name
            break
    for i, month in enumerate(MONTHS, start=1):
        if re.search(rf"\b{month}\b|\b{month[:3]}\b", q):
            filters["month_num"] = i
            break
    for key, pattern in SENSOR_PATTERNS.items():
        if re.search(pattern, q):
            filters[key] = True
    year = re.search(r"\b(20\d{2})\b", q)
    if year:
        filters["year"] = int(year.group(1))
    return filters
```

- [ ] **Step 6: Create `floatchat/llm.py`**

Copy the root `llm.py` verbatim, changing only its import line from `import config` to `from floatchat import config`.

Run: `git diff --no-index llm.py floatchat/llm.py`
Expected: the only difference is the import line.

- [ ] **Step 7: Create `tests/fakes.py`**

```python
"""Test doubles shared by unit and integration tests."""

import hashlib

import numpy as np


class FakeEmbedder:
    """Deterministic 384-d unit vectors derived from the text hash; no model download."""

    dims = 384

    def __init__(self):
        self.calls = 0

    def embed(self, texts, batch_size=64, pad_to=None):
        self.calls += 1
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
            vector = np.random.default_rng(seed).standard_normal(self.dims).astype(np.float32)
            out[i] = vector / np.linalg.norm(vector)
        return out
```

- [ ] **Step 8: Write the regions tests** (`tests/unit/test_regions.py`, moved from `tests/test_floatchat_core.py` and extended)

```python
import pytest

from floatchat.regions import parse_filters, region_for


@pytest.mark.parametrize("lat,lon,expected", [
    (0.5, 70, "Equatorial Indian Ocean"),
    (15, 65, "Arabian Sea"),
    (15, 88, "Bay of Bengal"),
    (13, 45, "Red Sea & Gulf of Aden"),
    (-30, 60, "Southern Indian Ocean"),
    (-20, 110, "Eastern Indian Ocean"),
])
def test_region_for(lat, lon, expected):
    assert region_for(lat, lon) == expected


def test_parse_filters_region_month_year():
    assert parse_filters("salinity profiles near the equator in March 2024") == {
        "region": "Equatorial Indian Ocean", "month_num": 3, "year": 2024}


def test_parse_filters_sensors():
    assert parse_filters("low oxygen in the Arabian Sea") == {"region": "Arabian Sea", "has_oxygen": True}
    assert parse_filters("where is chlorophyll highest?") == {"has_chlorophyll": True}
    assert parse_filters("nitrate and pH in the Bay of Bengal") == {
        "region": "Bay of Bengal", "has_nitrate": True, "has_ph": True}


def test_parse_filters_nothing():
    assert parse_filters("tell me about floats") == {}
```

- [ ] **Step 9: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/unit -q`
Expected: `9 passed`

- [ ] **Step 10: Lint and commit**

Run: `.venv/Scripts/python -m ruff check floatchat tests/unit tests/fakes.py`
Expected: `All checks passed!`

```bash
git add -A floatchat tests pyproject.toml requirements*.txt
git commit -m "Add floatchat package skeleton, tooling and moved helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: ONNX embedder with dynamic padding

**Files:**
- Create: `floatchat/embedder.py`, `tests/unit/test_embedder.py`

**Interfaces:**
- Consumes: `floatchat.config.MODEL_DIR`
- Produces: `floatchat.embedder.DIMENSIONS = 384`; `ensure_model(model_dir: Path) -> Path` (folder containing `model.onnx`, `tokenizer.json`); `class Embedder(model_dir: Path | None = None)` with `embed(texts: list[str], batch_size: int = 64, pad_to: int | None = None) -> np.ndarray` (shape `(n, 384)`, float32, L2-normalised); `get_embedder() -> Embedder` (process-wide singleton).

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_embedder.py`)

```python
import numpy as np
import pytest

from floatchat.embedder import DIMENSIONS, get_embedder

TEXTS = [
    "salinity near the equator",
    "ARGO float 2902203 (WMO 2902203) profile cycle 45 on 11 February 2024 at 12.30°N, 65.20°E in the Arabian Sea.",
]


@pytest.mark.model
def test_dynamic_padding_matches_fixed_padding():
    embedder = get_embedder()
    dynamic = embedder.embed(TEXTS)
    fixed = embedder.embed(TEXTS, pad_to=256)
    assert dynamic.shape == (2, DIMENSIONS)
    cosine = (dynamic * fixed).sum(axis=1)
    assert np.allclose(cosine, 1.0, atol=1e-4)


@pytest.mark.model
def test_vectors_are_normalised_and_distinct():
    vectors = get_embedder().embed(TEXTS)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    assert float(vectors[0] @ vectors[1]) < 0.95


@pytest.mark.model
def test_empty_input():
    assert get_embedder().embed([]).shape == (0, DIMENSIONS)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_embedder.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'floatchat.embedder'`

- [ ] **Step 3: Implement `floatchat/embedder.py`**

```python
"""
Sentence embeddings with all-MiniLM-L6-v2 (ONNX), the same model ChromaDB used.

Each batch is padded only to its longest text instead of a fixed 256 tokens,
so a short question embeds in milliseconds even on a tiny CPU.
"""

import hashlib
import tarfile
import tempfile
import threading
from pathlib import Path

import numpy as np
import requests

from floatchat import config

MODEL_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
MODEL_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
DIMENSIONS = 384
MAX_TOKENS = 256


def ensure_model(model_dir: Path) -> Path:
    """Download and unpack the model once; returns the folder holding model.onnx."""
    target = model_dir / "onnx"
    if (target / "model.onnx").exists() and (target / "tokenizer.json").exists():
        return target
    model_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=model_dir) as tmp:
        archive = Path(tmp) / "onnx.tar.gz"
        digest = hashlib.sha256()
        with requests.get(MODEL_URL, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise RuntimeError("Embedding model download failed its SHA-256 check")
        with tarfile.open(archive) as tar:
            tar.extractall(model_dir, filter="data")
    return target


class Embedder:
    def __init__(self, model_dir: Path | None = None):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        folder = ensure_model(Path(model_dir or config.MODEL_DIR))
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=MAX_TOKENS)
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self._session = ort.InferenceSession(str(folder / "model.onnx"), sess_options=options,
                                             providers=["CPUExecutionProvider"])
        self._lock = threading.Lock()  # the tokenizer's padding setting is shared state

    def embed(self, texts: list[str], batch_size: int = 64, pad_to: int | None = None) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIMENSIONS), dtype=np.float32)
        out = []
        with self._lock:
            if pad_to:
                self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=pad_to)
            else:
                self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
            for i in range(0, len(texts), batch_size):
                encodings = self._tokenizer.encode_batch(texts[i:i + batch_size])
                ids = np.array([e.ids for e in encodings], dtype=np.int64)
                mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
                hidden = self._session.run(None, {"input_ids": ids, "attention_mask": mask,
                                                  "token_type_ids": np.zeros_like(ids)})[0]
                weights = mask[..., None].astype(np.float32)
                pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                norms[norms == 0] = 1e-12
                out.append((pooled / norms).astype(np.float32))
        return np.concatenate(out)


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = Embedder()
        return _embedder
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/unit/test_embedder.py -q`
Expected: `3 passed` (the first run downloads ~80 MB to `~/.cache/floatchat/`)

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check floatchat tests/unit`

```bash
git add floatchat/embedder.py tests/unit/test_embedder.py
git commit -m "Add ONNX MiniLM embedder with dynamic padding

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Database schema, engine helpers, reader role and test database fixtures

**Files:**
- Create: `floatchat/db/__init__.py`, `floatchat/db/schema.sql`, `floatchat/db/engine.py`, `floatchat/db/roles.py`, `tests/integration/conftest.py`, `tests/integration/test_schema.py`
- Modify: `docker-compose.yml` (db image only)

**Interfaces:**
- Produces: `floatchat.db.engine.make_engine(url: str) -> Engine`, `apply_schema(engine) -> None`, `reset_schema(engine) -> None`, `schema_is_current(engine) -> bool`; `floatchat.db.roles.READER_ROLE = "floatchat_reader"`, `create_reader_role(engine, password: str, role: str = READER_ROLE) -> None`, `reader_url(admin_url: str, password: str, role: str = READER_ROLE) -> str`. Test fixtures: `admin_engine` (session), `empty_db` (function, fresh schema, yields admin engine), `READER_PASSWORD`, `ADMIN_URL`.

- [ ] **Step 1: Switch the local database to pgvector**

In `docker-compose.yml`, change the `db` service image from `postgres:16-alpine` to `pgvector/pgvector:pg16`. Then recreate it:

```bash
docker compose down -v
docker compose up -d db
```

Expected: `Container floatchat-db-1 Started`. (`down -v` wipes the old ChromaDB-era local data; it is reloaded in Task 8.)

- [ ] **Step 2: Create `floatchat/db/schema.sql`**

```sql
-- FloatChat schema. Idempotent: safe to apply on every pipeline run.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS floats (
    float_id        VARCHAR(20) PRIMARY KEY,
    wmo_id          INTEGER NOT NULL,
    deployment_date DATE,
    deployment_lat  DOUBLE PRECISION,
    deployment_lon  DOUBLE PRECISION,
    last_contact    DATE,
    status          VARCHAR(20) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS profiles (
    profile_id      SERIAL PRIMARY KEY,
    float_id        VARCHAR(20) NOT NULL REFERENCES floats(float_id) ON DELETE CASCADE,
    cycle_number    INTEGER NOT NULL,
    profile_date    TIMESTAMP NOT NULL,
    profile_lat     DOUBLE PRECISION NOT NULL,
    profile_lon     DOUBLE PRECISION NOT NULL,
    region          VARCHAR(40) NOT NULL,
    n_levels        INTEGER NOT NULL,
    has_oxygen      BOOLEAN NOT NULL DEFAULT FALSE,
    has_chlorophyll BOOLEAN NOT NULL DEFAULT FALSE,
    has_nitrate     BOOLEAN NOT NULL DEFAULT FALSE,
    has_ph          BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT,
    embedding       vector(384),
    UNIQUE (float_id, cycle_number)
);

CREATE TABLE IF NOT EXISTS measurements (
    id          BIGSERIAL PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    float_id    VARCHAR(20) NOT NULL,
    time        TIMESTAMP NOT NULL,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    depth       DOUBLE PRECISION NOT NULL,
    pressure    DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION,
    salinity    DOUBLE PRECISION,
    oxygen      DOUBLE PRECISION,
    chlorophyll DOUBLE PRECISION,
    nitrate     DOUBLE PRECISION,
    ph          DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id              SERIAL PRIMARY KEY,
    kind                VARCHAR(20) NOT NULL,
    started_at          TIMESTAMP NOT NULL DEFAULT now(),
    finished_at         TIMESTAMP,
    status              VARCHAR(20) NOT NULL DEFAULT 'running',
    profiles_added      INTEGER,
    profiles_removed    INTEGER,
    newest_profile_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_log (
    id         BIGSERIAL PRIMARY KEY,
    logged_at  TIMESTAMP NOT NULL DEFAULT now(),
    question   TEXT NOT NULL,
    query_type VARCHAR(20),
    intent     VARCHAR(40),
    latency_ms INTEGER,
    success    BOOLEAN,
    cached     BOOLEAN,
    llm_used   BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_profiles_float_id ON profiles(float_id);
CREATE INDEX IF NOT EXISTS idx_profiles_date ON profiles(profile_date);
CREATE INDEX IF NOT EXISTS idx_profiles_region ON profiles(region);
CREATE INDEX IF NOT EXISTS idx_profiles_embedding ON profiles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_measurements_profile_id ON measurements(profile_id);
CREATE INDEX IF NOT EXISTS idx_measurements_float_id ON measurements(float_id);
CREATE INDEX IF NOT EXISTS idx_measurements_depth ON measurements(depth);
```

- [ ] **Step 3: Create `floatchat/db/__init__.py` and `floatchat/db/engine.py`**

`floatchat/db/__init__.py`:
```python
"""Database access: engine helpers, schema, roles and read queries."""
```

`floatchat/db/engine.py`:
```python
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
TABLES = ("query_log", "ingest_runs", "measurements", "profiles", "floats")


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def apply_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_PATH.read_text(encoding="utf-8"))


def reset_schema(engine: Engine) -> None:
    """Drop every FloatChat table (data is reloaded by the pipeline)."""
    with engine.begin() as conn:
        for table in TABLES:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE")


def schema_is_current(engine: Engine) -> bool:
    """False only when an older FloatChat schema (no embedding column) is present."""
    with engine.connect() as conn:
        columns = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'profiles'"
        )).scalars().all()
    return not columns or "embedding" in columns
```

- [ ] **Step 4: Create `floatchat/db/roles.py`**

```python
"""The read-only database role the API uses."""

from psycopg import sql
from sqlalchemy.engine import Engine, make_url

READER_ROLE = "floatchat_reader"


def create_reader_role(engine: Engine, password: str, role: str = READER_ROLE) -> None:
    """Create (or update) the API role: read data, append to query_log, 5 s statement timeout."""
    role_id = sql.Identifier(role)
    raw = engine.raw_connection()
    try:
        pg = raw.driver_connection
        with pg.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            verb = "ALTER" if cur.fetchone() else "CREATE"
            cur.execute(sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(role_id, sql.Literal(password)))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(pg.info.dbname), role_id))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_id))
            cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role_id))
            cur.execute(sql.SQL("GRANT SELECT ON floats, profiles, measurements, ingest_runs TO {}").format(role_id))
            cur.execute(sql.SQL("GRANT INSERT ON query_log TO {}").format(role_id))
            cur.execute(sql.SQL("GRANT USAGE ON SEQUENCE query_log_id_seq TO {}").format(role_id))
            cur.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '5s'").format(role_id))
        pg.commit()
    finally:
        raw.close()


def reader_url(admin_url: str, password: str, role: str = READER_ROLE) -> str:
    return make_url(admin_url).set(username=role, password=password).render_as_string(hide_password=False)
```

- [ ] **Step 5: Create the integration fixtures** (`tests/integration/conftest.py`)

```python
"""
Integration tests need PostgreSQL with pgvector. Locally: `docker compose up -d db`.
They are skipped when no database is reachable, unless FLOATCHAT_REQUIRE_DB=1 (CI).
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from floatchat.db.engine import apply_schema, make_engine, reset_schema

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL",
                      "postgresql+psycopg://floatchat:floatchat@localhost:5433/floatchat_test")
READER_PASSWORD = "reader_test_password"


def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    server = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with server.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"),
                                  {"name": parsed.database}).first()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{parsed.database}"')
    finally:
        server.dispose()


@pytest.fixture(scope="session")
def admin_engine():
    try:
        _ensure_database(ADMIN_URL)
        engine = make_engine(ADMIN_URL)
        engine.connect().close()
    except Exception as e:
        if os.getenv("FLOATCHAT_REQUIRE_DB"):
            raise
        pytest.skip(f"No test database available: {e}")
    yield engine
    engine.dispose()


@pytest.fixture
def empty_db(admin_engine):
    reset_schema(admin_engine)
    apply_schema(admin_engine)
    yield admin_engine
```

- [ ] **Step 6: Write the failing schema/role tests** (`tests/integration/test_schema.py`)

```python
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from floatchat.db.engine import apply_schema, make_engine, schema_is_current
from floatchat.db.roles import create_reader_role, reader_url
from tests.integration.conftest import ADMIN_URL, READER_PASSWORD

pytestmark = pytest.mark.integration


def test_schema_is_idempotent(empty_db):
    apply_schema(empty_db)  # second application must not fail
    with empty_db.connect() as conn:
        tables = set(conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).scalars())
    assert {"floats", "profiles", "measurements", "ingest_runs", "query_log"} <= tables
    assert schema_is_current(empty_db)


def test_old_schema_is_detected(empty_db):
    with empty_db.begin() as conn:
        conn.exec_driver_sql("DROP TABLE profiles CASCADE")
        conn.exec_driver_sql("CREATE TABLE profiles (profile_id SERIAL PRIMARY KEY, float_id TEXT)")
    assert not schema_is_current(empty_db)


def test_reader_role_is_read_only(empty_db):
    create_reader_role(empty_db, READER_PASSWORD)
    reader = make_engine(reader_url(ADMIN_URL, READER_PASSWORD))
    try:
        with reader.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar() == 0
        with pytest.raises(DBAPIError):
            with reader.begin() as conn:
                conn.execute(text("DELETE FROM profiles"))
        with reader.begin() as conn:  # the API may append to query_log
            conn.execute(text("INSERT INTO query_log (question) VALUES ('test')"))
        with pytest.raises(DBAPIError):
            with reader.connect() as conn:
                conn.execute(text("SELECT question FROM query_log"))
    finally:
        reader.dispose()


def test_reader_statement_timeout(empty_db):
    create_reader_role(empty_db, READER_PASSWORD)
    reader = make_engine(reader_url(ADMIN_URL, READER_PASSWORD))
    try:
        with pytest.raises(DBAPIError, match="statement timeout"):
            with reader.connect() as conn:
                conn.execute(text("SELECT pg_sleep(6)"))
    finally:
        reader.dispose()
```

- [ ] **Step 7: Run tests**

Run: `.venv/Scripts/python -m pytest tests/integration/test_schema.py -q`
Expected: `4 passed` (about 6 s, mostly the timeout test). If they are skipped, the `db` container is not running: run `docker compose up -d db`.

- [ ] **Step 8: Lint and commit**

Run: `.venv/Scripts/python -m ruff check floatchat tests`

```bash
git add floatchat/db tests/integration docker-compose.yml
git commit -m "Add pgvector schema, engine helpers and read-only API role

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: ERDDAP fetch with retries and quality-control filtering

**Files:**
- Create: `pipeline/__init__.py`, `pipeline/erddap.py`, `tests/fixtures/erddap_core.csv`, `tests/fixtures/erddap_bgc.csv`, `tests/unit/test_erddap.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `pipeline.erddap.Dataset` (fields `name: str`, `variables: tuple[str, ...]`, `extra: str`), constants `CORE`, `BGC`, `BASE_COLUMNS`; `build_url(dataset, start: datetime, end: datetime, bbox) -> str`; `class FetchError(RuntimeError)`; `fetch_window(dataset, start, end, bbox, get=requests.get, sleep=time.sleep, retries=3) -> pd.DataFrame` (raw ERDDAP rows, units row removed; empty on 404; raises `FetchError` after retries); `apply_qc(df, dataset) -> pd.DataFrame` (values with QC not in {1, 2} set to NaN, all-NaN rows and duplicate `(platform_number, cycle_number, pres)` dropped, `*_qc` columns removed); `fetch_range(start, end, bbox, window_days=5, get=requests.get, sleep=time.sleep, log=print) -> tuple[pd.DataFrame, pd.DataFrame]` (QC-filtered core rows with columns `BASE_COLUMNS + ("temp", "psal")`, and BGC rows with `BASE_COLUMNS + BGC.variables`).

- [ ] **Step 1: Create the fixtures** (the ERDDAP CSV format: header row, then a units row)

`tests/fixtures/erddap_core.csv`:
```
platform_number,cycle_number,time,latitude,longitude,pres,temp,psal,temp_qc,psal_qc
,,UTC,degrees_north,degrees_east,decibar,degree_Celsius,PSU,,
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,4.0,28.10,36.20,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,10.0,28.05,36.21,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,50.0,27.50,36.30,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,100.0,24.00,36.10,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,200.0,17.60,35.90,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,500.0,11.00,35.40,4,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,1000.0,8.50,35.30,1,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,1000.0,8.50,35.30,1,1
5905498,66,2024-01-01T00:17:53Z,-38.43,106.17,5.0,17.70,35.52,1,1
5905498,66,2024-01-01T00:17:53Z,-38.43,106.17,10.0,17.69,35.52,1,2
5905498,66,2024-01-01T00:17:53Z,-38.43,106.17,20.0,17.60,35.51,1,1
5905498,66,2024-01-01T00:17:53Z,-38.43,106.17,30.0,17.40,35.50,1,1
5905498,66,2024-01-01T00:17:53Z,-38.43,106.17,40.0,NaN,NaN,9,9
```

`tests/fixtures/erddap_bgc.csv`:
```
platform_number,cycle_number,time,latitude,longitude,pres,doxy_adjusted,chla_adjusted,nitrate_adjusted,ph_in_situ_total_adjusted,doxy_adjusted_qc,chla_adjusted_qc,nitrate_adjusted_qc,ph_in_situ_total_adjusted_qc
,,UTC,degrees_north,degrees_east,decibar,micromole/kg,mg/m3,micromole/kg,dimensionless,,,,
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,4.0,200.0,0.30,NaN,8.05,1,1,,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,50.0,150.0,0.80,NaN,8.00,1,1,,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,200.0,20.0,0.05,NaN,7.90,1,3,,1
2902203,45,2024-02-11T05:00:00Z,12.3,65.2,1000.0,2.0,NaN,NaN,7.80,1,,,1
```

- [ ] **Step 2: Write the failing tests** (`tests/unit/test_erddap.py`)

```python
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from pipeline.erddap import BGC, CORE, FetchError, apply_qc, build_url, fetch_range, fetch_window

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BBOX = (-40.0, 30.0, 30.0, 120.0)
START, END = datetime(2024, 1, 1), datetime(2024, 1, 11)


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fixture_get(url, timeout):
    name = "erddap_bgc.csv" if "synthetic-BGC" in url else "erddap_core.csv"
    return FakeResponse(text=(FIXTURES / name).read_text())


def test_build_url_contains_dataset_columns_and_constraints():
    url = build_url(CORE, START, END, BBOX)
    assert url.startswith("https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.csv?")
    assert "temp_qc" in url and "psal_qc" in url
    assert "time%3E=2024-01-01T00%3A00%3A00Z" in url  # "=" is kept, ">" and ":" are encoded
    assert "latitude%3E=-40.0" in url


def test_fetch_window_parses_csv_and_skips_units_row():
    df = fetch_window(CORE, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    assert len(df) == 13
    assert df["platform_number"].iloc[0] == 2902203


def test_fetch_window_404_means_no_rows():
    df = fetch_window(CORE, START, END, BBOX, get=lambda url, timeout: FakeResponse(404), sleep=lambda s: None)
    assert df.empty


def test_fetch_window_retries_then_succeeds():
    calls = []

    def flaky(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return fixture_get(url, timeout)

    df = fetch_window(CORE, START, END, BBOX, get=flaky, sleep=lambda s: None)
    assert len(calls) == 3 and not df.empty


def test_fetch_window_raises_after_retries():
    def broken(url, timeout):
        raise ConnectionError("down")

    with pytest.raises(FetchError, match="ArgoFloats"):
        fetch_window(CORE, START, END, BBOX, get=broken, sleep=lambda s: None)


def test_apply_qc_core():
    raw = fetch_window(CORE, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    clean = apply_qc(raw, CORE)
    assert "temp_qc" not in clean.columns
    row500 = clean[(clean.platform_number == 2902203) & (clean.pres == 500.0)].iloc[0]
    assert pd.isna(row500["temp"]) and row500["psal"] == 35.40      # bad temp QC removed, salinity kept
    assert len(clean[(clean.platform_number == 2902203) & (clean.pres == 1000.0)]) == 1  # duplicate dropped
    assert 40.0 not in clean[clean.platform_number == 5905498]["pres"].tolist()      # all-NaN row dropped


def test_apply_qc_bgc():
    raw = fetch_window(BGC, START, END, BBOX, get=fixture_get, sleep=lambda s: None)
    clean = apply_qc(raw, BGC)
    row200 = clean[clean.pres == 200.0].iloc[0]
    assert pd.isna(row200["chla_adjusted"]) and row200["doxy_adjusted"] == 20.0
    assert clean["nitrate_adjusted"].isna().all()


def test_fetch_range_splits_into_windows():
    urls = []

    def recording_get(url, timeout):
        urls.append(url)
        return fixture_get(url, timeout)

    core, bgc = fetch_range(START, END, BBOX, window_days=5, get=recording_get, sleep=lambda s: None,
                            log=lambda *a, **k: None)
    assert len(urls) == 4  # 2 windows x (core + BGC)
    assert not core.empty and not bgc.empty
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/unit/test_erddap.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 4: Implement**

`pipeline/__init__.py`:
```python
"""FloatChat data pipeline: ERDDAP -> standard levels -> descriptions/embeddings -> Postgres."""
```

`pipeline/erddap.py`:
```python
"""
Download Argo profiles from the Ifremer ERDDAP server and keep only good data.

Core floats provide temperature and salinity; the synthetic BGC dataset adds
quality-controlled ("adjusted") oxygen, chlorophyll, nitrate and pH.
"""

import io
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

ERDDAP = "https://erddap.ifremer.fr/erddap/tabledap"
BASE_COLUMNS = ("platform_number", "cycle_number", "time", "latitude", "longitude", "pres")
GOOD_QC = (1, 2)  # Argo flags: 1 = good, 2 = probably good


@dataclass(frozen=True)
class Dataset:
    name: str
    variables: tuple[str, ...]
    extra: str = ""


CORE = Dataset("ArgoFloats", ("temp", "psal"), "&pres<=2050")
BGC = Dataset("ArgoFloats-synthetic-BGC",
              ("doxy_adjusted", "chla_adjusted", "nitrate_adjusted", "ph_in_situ_total_adjusted"), "&pres<=2050")


class FetchError(RuntimeError):
    pass


def build_url(dataset: Dataset, start: datetime, end: datetime, bbox) -> str:
    lat_min, lat_max, lon_min, lon_max = bbox
    columns = ",".join(BASE_COLUMNS + dataset.variables + tuple(f"{v}_qc" for v in dataset.variables))
    query = (
        f"{columns}"
        f"&time>={start:%Y-%m-%dT%H:%M:%SZ}&time<{end:%Y-%m-%dT%H:%M:%SZ}"
        f"&latitude>={lat_min}&latitude<={lat_max}&longitude>={lon_min}&longitude<={lon_max}"
        f"{dataset.extra}"
    )
    return f"{ERDDAP}/{dataset.name}.csv?{urllib.parse.quote(query, safe='&=,')}"


def fetch_window(dataset: Dataset, start: datetime, end: datetime, bbox,
                 get=requests.get, sleep=time.sleep, retries: int = 3) -> pd.DataFrame:
    url = build_url(dataset, start, end, bbox)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = get(url, timeout=300)
            if resp.status_code == 404:  # ERDDAP answers 404 when no rows match
                return pd.DataFrame()
            resp.raise_for_status()
            return pd.read_csv(io.StringIO(resp.text), skiprows=[1])
        except Exception as e:
            last_error = e
            if attempt < retries:
                sleep(5 * attempt)
    raise FetchError(f"{dataset.name} {start:%Y-%m-%d}..{end:%Y-%m-%d} failed after {retries} attempts: {last_error}")


def apply_qc(df: pd.DataFrame, dataset: Dataset) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    variables = list(dataset.variables)
    for var in variables:
        qc = pd.to_numeric(df[f"{var}_qc"], errors="coerce")
        df.loc[~qc.isin(GOOD_QC), var] = np.nan
    df = df.dropna(subset=variables, how="all")
    df = df.drop_duplicates(["platform_number", "cycle_number", "pres"])
    return df.drop(columns=[f"{v}_qc" for v in variables]).reset_index(drop=True)


def fetch_range(start: datetime, end: datetime, bbox, window_days: int = 5,
                get=requests.get, sleep=time.sleep, log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    results = {}
    for dataset in (CORE, BGC):
        frames = []
        cursor = start
        while cursor < end:
            nxt = min(cursor + timedelta(days=window_days), end)
            raw = fetch_window(dataset, cursor, nxt, bbox, get=get, sleep=sleep)
            clean = apply_qc(raw, dataset)
            log(f"   {dataset.name} {cursor:%Y-%m-%d} -> {nxt:%Y-%m-%d}: {len(clean):,} rows")
            if not clean.empty:
                frames.append(clean)
            cursor = nxt
        columns = list(BASE_COLUMNS + dataset.variables)
        results[dataset.name] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    return results[CORE.name], results[BGC.name]
```

- [ ] **Step 5: Run tests**

Run: `.venv/Scripts/python -m pytest tests/unit/test_erddap.py -q`
Expected: `8 passed`

- [ ] **Step 6: Lint and commit**

Run: `.venv/Scripts/python -m ruff check pipeline tests/unit`

```bash
git add pipeline tests/fixtures/erddap_core.csv tests/fixtures/erddap_bgc.csv tests/unit/test_erddap.py
git commit -m "Add ERDDAP fetch with retries and QC filtering

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Shape profiles onto standard levels and build the tables

**Files:**
- Create: `pipeline/shape.py`, `tests/unit/test_shape.py`

**Interfaces:**
- Consumes: `pipeline.erddap.BGC`, `floatchat.regions.region_for`; QC-filtered frames from `fetch_range`.
- Produces: `pipeline.shape.STANDARD_LEVELS` (24 floats), `SEED_COLUMNS = ["wmo_id", "cycle_number", "time", "lat", "lon", "pressure", "temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]`, `MEASUREMENT_VALUES = ["temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]`; `thin_profile(group, columns, min_levels=3) -> pd.DataFrame | None`; `to_seed(core, bgc) -> pd.DataFrame` (columns `SEED_COLUMNS`); `build_tables(seed) -> tuple[floats, profiles, measurements]` where
  - `floats` columns: `float_id (str), wmo_id (int), deployment_date (date), deployment_lat, deployment_lon, last_contact (date)`
  - `profiles` columns: `float_id, cycle_number (int), profile_date (Timestamp), profile_lat, profile_lon, region, n_levels, has_oxygen, has_chlorophyll, has_nitrate, has_ph`
  - `measurements` columns: `float_id, cycle_number, time, lat, lon, depth, pressure` + `MEASUREMENT_VALUES`

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_shape.py`)

```python
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.erddap import BGC, CORE, apply_qc, fetch_window
from pipeline.shape import SEED_COLUMNS, STANDARD_LEVELS, build_tables, to_seed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BBOX = (-40.0, 30.0, 30.0, 120.0)


class FakeResponse:
    status_code = 200

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def fixture_get(url, timeout):
    name = "erddap_bgc.csv" if "synthetic-BGC" in url else "erddap_core.csv"
    return FakeResponse((FIXTURES / name).read_text())


def load_fixture_frames():
    core = apply_qc(fetch_window(CORE, datetime(2024, 1, 1), datetime(2024, 3, 1), BBOX, get=fixture_get), CORE)
    bgc = apply_qc(fetch_window(BGC, datetime(2024, 1, 1), datetime(2024, 3, 1), BBOX, get=fixture_get), BGC)
    return core, bgc


def seed_for(seed, wmo):
    return seed[seed.wmo_id == wmo].set_index("pressure")


def test_standard_levels():
    assert len(STANDARD_LEVELS) == 24
    assert STANDARD_LEVELS[0] == 5 and STANDARD_LEVELS[-1] == 2000


def test_to_seed_interpolates_onto_standard_levels():
    seed = to_seed(*load_fixture_frames())
    assert list(seed.columns) == SEED_COLUMNS
    arabian = seed_for(seed, 2902203)
    assert list(arabian.index) == [p for p in STANDARD_LEVELS if 5 <= p <= 1000]  # 19 levels
    assert abs(arabian.loc[500.0, "temperature"] - 14.1875) < 0.01  # QC-flagged 500 m value replaced by interpolation
    assert 195 < arabian.loc[5.0, "oxygen"] < 200
    assert arabian.loc[1000.0, "ph"] == 7.8
    assert pd.notna(arabian.loc[20.0, "chlorophyll"])
    assert pd.isna(arabian.loc[100.0, "chlorophyll"])  # no chlorophyll data below 50 m: no extrapolation
    assert arabian["nitrate"].isna().all()
    southern = seed_for(seed, 5905498)
    assert list(southern.index) == [5.0, 10.0, 20.0, 30.0]
    assert southern["oxygen"].isna().all()


def test_to_seed_without_bgc():
    core, _ = load_fixture_frames()
    seed = to_seed(core, pd.DataFrame())
    assert seed["oxygen"].isna().all() and len(seed) == 23


def test_build_tables():
    floats, profiles, measurements = build_tables(to_seed(*load_fixture_frames()))
    assert sorted(floats["float_id"]) == ["2902203", "5905498"]
    assert set(floats["wmo_id"]) == {2902203, 5905498}
    by_float = profiles.set_index("float_id")
    assert by_float.loc["2902203", "region"] == "Arabian Sea"
    assert by_float.loc["5905498", "region"] == "Eastern Indian Ocean"
    assert bool(by_float.loc["2902203", "has_oxygen"]) and bool(by_float.loc["2902203", "has_chlorophyll"])
    assert not bool(by_float.loc["2902203", "has_nitrate"]) and bool(by_float.loc["2902203", "has_ph"])
    assert not bool(by_float.loc["5905498", "has_oxygen"])
    assert by_float.loc["2902203", "n_levels"] == 19
    assert len(measurements) == 23
    assert {"depth", "pressure", "chlorophyll", "nitrate", "ph", "cycle_number"} <= set(measurements.columns)


def test_build_tables_accepts_old_snapshot_without_bgc_columns():
    old = pd.DataFrame({
        "wmo_id": [1901701] * 3, "cycle_number": [10] * 3, "time": ["2024-01-05T10:00:00Z"] * 3,
        "lat": [-34.5] * 3, "lon": [54.9] * 3, "pressure": [5.0, 10.0, 20.0],
        "temperature": [19.8, 19.7, 19.5], "salinity": [35.6] * 3, "oxygen": [None] * 3,
    })
    _, profiles, measurements = build_tables(old)
    assert profiles.iloc[0]["region"] == "Southern Indian Ocean"
    assert measurements["chlorophyll"].isna().all()
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/unit/test_shape.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.shape'`

- [ ] **Step 3: Implement `pipeline/shape.py`**

```python
"""
Turn raw ERDDAP rows into FloatChat tables.

Every profile is interpolated onto 24 standard pressure levels so the dataset
stays small while keeping the shape of each profile. A variable is only
interpolated inside the pressure range where it was actually measured.
"""

import numpy as np
import pandas as pd

from floatchat.regions import region_for
from pipeline.erddap import BGC

STANDARD_LEVELS = np.array(
    [5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
     600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000], dtype=float
)
KEYS = ["platform_number", "cycle_number"]
CORE_VARS = ["temp", "psal"]
RENAME = {
    "platform_number": "wmo_id", "latitude": "lat", "longitude": "lon", "pres": "pressure",
    "temp": "temperature", "psal": "salinity", "doxy_adjusted": "oxygen", "chla_adjusted": "chlorophyll",
    "nitrate_adjusted": "nitrate", "ph_in_situ_total_adjusted": "ph",
}
SEED_COLUMNS = ["wmo_id", "cycle_number", "time", "lat", "lon", "pressure",
                "temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]
MEASUREMENT_VALUES = ["temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]


def thin_profile(group: pd.DataFrame, columns: list[str], min_levels: int = 3) -> pd.DataFrame | None:
    group = group.sort_values("pres").drop_duplicates("pres")
    pres = group["pres"].to_numpy(dtype=float)
    levels = STANDARD_LEVELS[(STANDARD_LEVELS >= pres.min()) & (STANDARD_LEVELS <= pres.max())]
    if len(levels) < min_levels:
        return None
    out = {"pres": levels}
    has_values = False
    for col in columns:
        values = group[col].to_numpy(dtype=float)
        ok = ~np.isnan(values)
        if ok.sum() >= 2:
            interpolated = np.interp(levels, pres[ok], values[ok])
            measured = (levels >= pres[ok].min()) & (levels <= pres[ok].max())
            out[col] = np.where(measured, interpolated, np.nan)
            has_values = True
        else:
            out[col] = np.full(len(levels), np.nan)
    if not has_values:
        return None
    df = pd.DataFrame(out)
    first = group.iloc[0]
    for col in ("platform_number", "cycle_number", "time", "latitude", "longitude"):
        df[col] = first[col]
    return df


def _thin_all(df: pd.DataFrame, columns: list[str], min_levels: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    thinned = [p for _, g in df.groupby(KEYS) if (p := thin_profile(g, columns, min_levels)) is not None]
    return pd.concat(thinned, ignore_index=True) if thinned else pd.DataFrame()


def to_seed(core: pd.DataFrame, bgc: pd.DataFrame) -> pd.DataFrame:
    seed = _thin_all(core, CORE_VARS, min_levels=3)
    if seed.empty:
        return pd.DataFrame(columns=SEED_COLUMNS)
    bgc_vars = list(BGC.variables)
    bgc_thin = _thin_all(bgc, bgc_vars, min_levels=2)
    if bgc_thin.empty:
        for var in bgc_vars:
            seed[var] = np.nan
    else:
        seed = seed.merge(bgc_thin[KEYS + ["pres"] + bgc_vars], on=KEYS + ["pres"], how="left")
    seed = seed.rename(columns=RENAME)[SEED_COLUMNS]
    return seed.round({"lat": 4, "lon": 4, "temperature": 3, "salinity": 3, "oxygen": 2,
                       "chlorophyll": 4, "nitrate": 2, "ph": 4})


def build_tables(seed: pd.DataFrame):
    seed = seed.reindex(columns=SEED_COLUMNS)  # older snapshots lack the newer BGC columns
    seed = seed.drop_duplicates(["wmo_id", "cycle_number", "pressure"]).copy()
    seed["time"] = pd.to_datetime(seed["time"], utc=True).dt.tz_localize(None)
    seed["float_id"] = seed["wmo_id"].astype("int64").astype(str)
    seed["cycle_number"] = seed["cycle_number"].astype("int64")
    seed["depth"] = seed["pressure"].round(0)  # 1 dbar is ~1 m of seawater (within ~1% to 2,000 m)
    for col in MEASUREMENT_VALUES:
        seed[col] = pd.to_numeric(seed[col], errors="coerce")

    profiles = (
        seed.groupby(["float_id", "cycle_number"], as_index=False)
        .agg(profile_date=("time", "first"), profile_lat=("lat", "first"), profile_lon=("lon", "first"),
             n_levels=("pressure", "size"), oxygen_n=("oxygen", "count"), chlorophyll_n=("chlorophyll", "count"),
             nitrate_n=("nitrate", "count"), ph_n=("ph", "count"))
        .sort_values(["profile_date", "float_id"])
        .reset_index(drop=True)
    )
    for var in ("oxygen", "chlorophyll", "nitrate", "ph"):
        profiles[f"has_{var}"] = profiles.pop(f"{var}_n") > 0
    profiles["region"] = [region_for(lat, lon) for lat, lon in zip(profiles["profile_lat"], profiles["profile_lon"])]

    floats = (
        profiles.sort_values("profile_date")
        .groupby("float_id", as_index=False)
        .agg(deployment_date=("profile_date", "first"), deployment_lat=("profile_lat", "first"),
             deployment_lon=("profile_lon", "first"), last_contact=("profile_date", "last"))
    )
    floats["wmo_id"] = floats["float_id"].astype(int)
    floats["deployment_date"] = floats["deployment_date"].dt.date
    floats["last_contact"] = floats["last_contact"].dt.date

    measurements = seed[["float_id", "cycle_number", "time", "lat", "lon", "depth", "pressure"] + MEASUREMENT_VALUES]
    return floats, profiles, measurements.reset_index(drop=True)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/unit/test_shape.py -q`
Expected: `5 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check pipeline tests/unit`

```bash
git add pipeline/shape.py tests/unit/test_shape.py
git commit -m "Add standard-level shaping and table building with BGC variables

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Profile descriptions and the embedding cache

**Files:**
- Create: `pipeline/describe.py`, `pipeline/embed.py`, `tests/unit/test_describe.py`, `tests/unit/test_embed_cache.py`

**Interfaces:**
- Consumes: `build_tables` output (Task 5); any object with `embed(texts) -> np.ndarray` (Task 2 `Embedder` or `tests.fakes.FakeEmbedder`).
- Produces: `pipeline.describe.value_at(levels, depth, column) -> float | None`; `describe_profile(profile: Mapping, levels: pd.DataFrame) -> str` (profile keys: `float_id, cycle_number, profile_date, profile_lat, profile_lon, region, n_levels`; levels: one profile's measurement rows sorted by depth); `pipeline.embed.embed_with_cache(docs: list[str], embedder, cache_path: str | Path | None) -> np.ndarray` (float32, shape `(len(docs), 384)`).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_describe.py`:
```python
from pipeline.describe import describe_profile, value_at
from pipeline.shape import build_tables, to_seed
from tests.unit.test_shape import load_fixture_frames


def tables():
    return build_tables(to_seed(*load_fixture_frames()))


def profile_and_levels(float_id):
    _, profiles, measurements = tables()
    profile = profiles[profiles.float_id == float_id].iloc[0].to_dict()
    levels = measurements[measurements.float_id == float_id].sort_values("depth").reset_index(drop=True)
    return profile, levels


def test_value_at_tolerance():
    _, levels = profile_and_levels("2902203")
    assert value_at(levels, 200, "temperature") == levels.set_index("depth").loc[200.0, "temperature"]
    assert value_at(levels, 1500, "temperature") is None  # nothing within 15 % of 1,500 m


def test_description_of_bgc_profile():
    text = describe_profile(*profile_and_levels("2902203"))
    assert text.startswith("ARGO float 2902203 (WMO 2902203) profile cycle 45 on 11 February 2024")
    assert "12.30°N, 65.20°E in the Arabian Sea" in text
    assert "oxygen minimum" in text
    assert "chlorophyll maximum" in text
    assert "surface pH" in text
    assert "nitrate" not in text


def test_description_of_core_profile():
    text = describe_profile(*profile_and_levels("5905498"))
    assert "38.43°S" in text and "Eastern Indian Ocean" in text
    assert "oxygen" not in text
```

`tests/unit/test_embed_cache.py`:
```python
import numpy as np

from pipeline.embed import embed_with_cache
from tests.fakes import FakeEmbedder


def test_embeds_without_cache():
    embedder = FakeEmbedder()
    vectors = embed_with_cache(["a", "b"], embedder, None)
    assert vectors.shape == (2, 384) and vectors.dtype == np.float32
    assert embedder.calls == 1


def test_cache_roundtrip(tmp_path):
    cache = tmp_path / "cache.npz"
    first = embed_with_cache(["a", "b"], FakeEmbedder(), cache)
    assert cache.exists()
    embedder = FakeEmbedder()
    second = embed_with_cache(["b", "a"], embedder, cache)
    assert embedder.calls == 0  # everything came from the cache
    assert np.allclose(second[0], first[1], atol=1e-3)  # float16 storage


def test_only_new_documents_are_embedded(tmp_path):
    cache = tmp_path / "cache.npz"
    embed_with_cache(["a"], FakeEmbedder(), cache)
    embedder = FakeEmbedder()
    embed_with_cache(["a", "c"], embedder, cache)
    assert embedder.calls == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/unit/test_describe.py tests/unit/test_embed_cache.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.describe'`

- [ ] **Step 3: Implement**

`pipeline/describe.py`:
```python
"""One plain-English sentence block per profile; these are what get embedded and searched."""

from collections.abc import Mapping

import pandas as pd


def value_at(levels: pd.DataFrame, depth: float, column: str):
    """Value of `column` at the level closest to `depth` (within 15 %, or 10 m near the surface)."""
    valid = levels[levels[column].notna()]
    if valid.empty:
        return None
    row = valid.loc[(valid["depth"] - depth).abs().idxmin()]
    if abs(row["depth"] - depth) > max(10, depth * 0.15):
        return None
    return float(row[column])


def describe_profile(profile: Mapping, levels: pd.DataFrame) -> str:
    lat, lon = profile["profile_lat"], profile["profile_lon"]
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    parts = [
        f"ARGO float {profile['float_id']} (WMO {profile['float_id']}) profile cycle {profile['cycle_number']} on "
        f"{profile['profile_date']:%d %B %Y} at {abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew} in the {profile['region']}.",
        f"The profile has {profile['n_levels']} levels from {levels['depth'].min():.0f} m "
        f"to {levels['depth'].max():.0f} m depth.",
    ]
    surface_t, surface_s = value_at(levels, 5, "temperature"), value_at(levels, 5, "salinity")
    if surface_t is not None:
        salinity = f" and surface salinity {surface_s:.2f} PSU." if surface_s is not None else "."
        parts.append(f"Surface temperature was {surface_t:.2f}°C{salinity}")
    for depth in (200, 1000):
        t, s = value_at(levels, depth, "temperature"), value_at(levels, depth, "salinity")
        if t is not None:
            salinity = f" and salinity {s:.2f} PSU." if s is not None else "."
            parts.append(f"At {depth} m the temperature was {t:.2f}°C{salinity}")
    if levels["oxygen"].notna().any():
        low = levels.loc[levels["oxygen"].idxmin()]
        parts.append(f"This BGC float measures dissolved oxygen; the oxygen minimum was "
                     f"{low['oxygen']:.1f} µmol/kg at {low['depth']:.0f} m.")
    if levels["chlorophyll"].notna().any():
        top = levels.loc[levels["chlorophyll"].idxmax()]
        parts.append(f"It also measures chlorophyll; the chlorophyll maximum was "
                     f"{top['chlorophyll']:.2f} mg/m³ at {top['depth']:.0f} m.")
    if levels["nitrate"].notna().any():
        deep = levels[levels["nitrate"].notna()].iloc[-1]
        parts.append(f"Nitrate reached {deep['nitrate']:.1f} µmol/kg at {deep['depth']:.0f} m.")
    if levels["ph"].notna().any():
        shallow = levels[levels["ph"].notna()].iloc[0]
        parts.append(f"The surface pH was {shallow['ph']:.2f}.")
    return " ".join(parts)
```

`pipeline/embed.py`:
```python
"""
Embed profile descriptions, reusing vectors from a cache file for unchanged text.
Embedding thousands of descriptions on a CPU takes minutes; the cache makes a
fresh local install start in seconds.
"""

import hashlib
import os
from pathlib import Path

import numpy as np


def embed_with_cache(docs: list[str], embedder, cache_path: str | Path | None) -> np.ndarray:
    hashes = [hashlib.sha1(doc.encode("utf-8")).hexdigest() for doc in docs]
    cache: dict[str, np.ndarray] = {}
    if cache_path and os.path.exists(cache_path):
        stored = np.load(cache_path)
        cache = dict(zip(stored["hashes"].tolist(), stored["vectors"]))

    missing = [i for i, h in enumerate(hashes) if h not in cache]
    if missing:
        vectors = embedder.embed([docs[i] for i in missing])
        for i, vector in zip(missing, vectors):
            cache[hashes[i]] = np.asarray(vector, dtype=np.float16)
        if cache_path:
            np.savez_compressed(cache_path, hashes=np.array(hashes),
                                vectors=np.stack([cache[h] for h in hashes]))

    if not docs:
        return np.zeros((0, 384), dtype=np.float32)
    return np.stack([cache[h] for h in hashes]).astype(np.float32)
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/unit/test_describe.py tests/unit/test_embed_cache.py -q`
Expected: `6 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check pipeline tests/unit`

```bash
git add pipeline/describe.py pipeline/embed.py tests/unit/test_describe.py tests/unit/test_embed_cache.py
git commit -m "Add profile descriptions with BGC facts and the embedding cache

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Load new profiles, prune old ones, record runs

**Files:**
- Create: `pipeline/load.py`, `tests/integration/test_load.py`

**Interfaces:**
- Consumes: `build_tables` (Task 5), `describe_profile` (Task 6), `embed_with_cache` (Task 6), `make_engine`/`empty_db` fixture (Task 3).
- Produces: `pipeline.load.load_tables(engine, floats, profiles, measurements, embedder, cache_path=None) -> int` (profiles added; existing `(float_id, cycle_number)` pairs are skipped); `prune(engine, before: datetime) -> int` (profiles removed; their measurements cascade; floats without profiles removed); `start_run(engine, kind: str) -> int`; `finish_run(engine, run_id: int, status: str, added: int, removed: int) -> None`; `profile_count(engine) -> int`.

- [ ] **Step 1: Write the failing tests** (`tests/integration/test_load.py`)

```python
from datetime import datetime

import pytest
from sqlalchemy import text

from pipeline.load import finish_run, load_tables, profile_count, prune, start_run
from pipeline.shape import build_tables, to_seed
from tests.fakes import FakeEmbedder
from tests.unit.test_shape import load_fixture_frames

pytestmark = pytest.mark.integration


def fixture_tables():
    return build_tables(to_seed(*load_fixture_frames()))


def scalar(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


def test_load_inserts_everything(empty_db):
    added = load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    assert added == 2
    assert profile_count(empty_db) == 2
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements") == 23
    assert scalar(empty_db, "SELECT COUNT(*) FROM profiles WHERE embedding IS NOT NULL") == 2
    assert scalar(empty_db, "SELECT COUNT(*) FROM profiles WHERE description LIKE 'ARGO float%'") == 2
    assert scalar(empty_db, "SELECT has_chlorophyll FROM profiles WHERE float_id = '2902203'") is True
    assert scalar(empty_db, "SELECT deployment_date::text FROM floats WHERE float_id = '2902203'") == "2024-02-11"
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements WHERE chlorophyll IS NOT NULL") > 0


def test_load_is_idempotent(empty_db):
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    embedder = FakeEmbedder()
    assert load_tables(empty_db, *fixture_tables(), embedder) == 0
    assert embedder.calls == 0
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements") == 23


def test_prune_removes_old_profiles_and_orphan_floats(empty_db):
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    removed = prune(empty_db, before=datetime(2024, 2, 1))  # 5905498's only profile is from 1 Jan 2024
    assert removed == 1
    assert scalar(empty_db, "SELECT COUNT(*) FROM floats") == 1
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements WHERE float_id = '5905498'") == 0


def test_runs_are_recorded(empty_db):
    run_id = start_run(empty_db, "snapshot")
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    finish_run(empty_db, run_id, "success", 2, 0)
    with empty_db.connect() as conn:
        row = conn.execute(text("SELECT kind, status, profiles_added, newest_profile_date::date::text, "
                                "finished_at IS NOT NULL FROM ingest_runs WHERE run_id = :id"), {"id": run_id}).one()
    assert tuple(row) == ("snapshot", "success", 2, "2024-02-11", True)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/integration/test_load.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.load'`

- [ ] **Step 3: Implement `pipeline/load.py`**

```python
"""Write pipeline output into Postgres: new profiles only, bulk COPY for measurements."""

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.describe import describe_profile
from pipeline.embed import embed_with_cache
from pipeline.shape import MEASUREMENT_VALUES

PROFILE_INSERT = """
    INSERT INTO profiles (float_id, cycle_number, profile_date, profile_lat, profile_lon, region, n_levels,
                          has_oxygen, has_chlorophyll, has_nitrate, has_ph, description, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
"""
FLOAT_INSERT = """
    INSERT INTO floats (float_id, wmo_id, deployment_date, deployment_lat, deployment_lon, last_contact)
    VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (float_id) DO NOTHING
"""
REFRESH_FLOATS = """
    WITH firsts AS (
        SELECT DISTINCT ON (float_id) float_id, profile_date, profile_lat, profile_lon
        FROM profiles ORDER BY float_id, profile_date
    ),
    lasts AS (SELECT float_id, MAX(profile_date) AS last_date FROM profiles GROUP BY float_id)
    UPDATE floats f
    SET deployment_date = firsts.profile_date::date, deployment_lat = firsts.profile_lat,
        deployment_lon = firsts.profile_lon, last_contact = lasts.last_date::date
    FROM firsts JOIN lasts USING (float_id)
    WHERE f.float_id = firsts.float_id
"""
MEASUREMENT_COLUMNS = ["profile_id", "float_id", "time", "lat", "lon", "depth", "pressure"] + MEASUREMENT_VALUES


def _python(value):
    """pandas/numpy scalar -> plain Python value psycopg can send (NaN/NaT -> None)."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.to_pydatetime()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value.item() if hasattr(value, "item") else value


def _rows(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    return [tuple(_python(v) for v in row) for row in df[columns].itertuples(index=False, name=None)]


def _vector_literal(vector) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def load_tables(engine: Engine, floats: pd.DataFrame, profiles: pd.DataFrame, measurements: pd.DataFrame,
                embedder, cache_path=None) -> int:
    raw = engine.raw_connection()
    pg = raw.driver_connection
    try:
        with pg.cursor() as cur:
            cur.execute("SELECT float_id, cycle_number FROM profiles")
            existing = set(cur.fetchall())
            is_new = [(f, int(c)) not in existing for f, c in zip(profiles["float_id"], profiles["cycle_number"])]
            new_profiles = profiles[is_new].reset_index(drop=True)
            if new_profiles.empty:
                pg.commit()
                return 0

            new_floats = floats[floats["float_id"].isin(set(new_profiles["float_id"]))]
            cur.executemany(FLOAT_INSERT, _rows(new_floats, ["float_id", "wmo_id", "deployment_date",
                                                             "deployment_lat", "deployment_lon", "last_contact"]))

            levels_by_key = {key: group.sort_values("depth").reset_index(drop=True)
                             for key, group in measurements.groupby(["float_id", "cycle_number"])}
            descriptions = [describe_profile(p, levels_by_key[(p["float_id"], p["cycle_number"])])
                            for p in new_profiles.to_dict("records")]
            vectors = embed_with_cache(descriptions, embedder, cache_path)

            profile_rows = [
                row + (description, _vector_literal(vector))
                for row, description, vector in zip(
                    _rows(new_profiles, ["float_id", "cycle_number", "profile_date", "profile_lat", "profile_lon",
                                         "region", "n_levels", "has_oxygen", "has_chlorophyll", "has_nitrate",
                                         "has_ph"]),
                    descriptions, vectors)
            ]
            cur.executemany(PROFILE_INSERT, profile_rows)

            cur.execute(
                "SELECT p.profile_id, p.float_id, p.cycle_number FROM profiles p "
                "JOIN unnest(%s::text[], %s::int[]) AS k(float_id, cycle_number) USING (float_id, cycle_number)",
                (new_profiles["float_id"].tolist(), [int(c) for c in new_profiles["cycle_number"]]),
            )
            ids = pd.DataFrame(cur.fetchall(), columns=["profile_id", "float_id", "cycle_number"])
            new_measurements = measurements.merge(ids, on=["float_id", "cycle_number"])
            with cur.copy(f"COPY measurements ({', '.join(MEASUREMENT_COLUMNS)}) FROM STDIN") as copy:
                for row in _rows(new_measurements, MEASUREMENT_COLUMNS):
                    copy.write_row(row)

            cur.execute(REFRESH_FLOATS)
        pg.commit()
        return len(new_profiles)
    except Exception:
        pg.rollback()
        raise
    finally:
        raw.close()


def prune(engine: Engine, before: datetime) -> int:
    with engine.begin() as conn:
        removed = conn.execute(text("DELETE FROM profiles WHERE profile_date < :before"), {"before": before}).rowcount
        conn.execute(text("DELETE FROM floats f WHERE NOT EXISTS "
                          "(SELECT 1 FROM profiles p WHERE p.float_id = f.float_id)"))
        if removed:
            conn.execute(text(REFRESH_FLOATS))
    return removed


def start_run(engine: Engine, kind: str) -> int:
    with engine.begin() as conn:
        return conn.execute(text("INSERT INTO ingest_runs (kind) VALUES (:kind) RETURNING run_id"),
                            {"kind": kind}).scalar_one()


def finish_run(engine: Engine, run_id: int, status: str, added: int, removed: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ingest_runs SET finished_at = now(), status = :status, profiles_added = :added,
                   profiles_removed = :removed, newest_profile_date = (SELECT MAX(profile_date) FROM profiles)
            WHERE run_id = :run_id
        """), {"status": status, "added": added, "removed": removed, "run_id": run_id})


def profile_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar_one()
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/integration/test_load.py -q`
Expected: `4 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/Scripts/python -m ruff check pipeline tests`

```bash
git add pipeline/load.py tests/integration/test_load.py
git commit -m "Add incremental loader with COPY, pruning and run records

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Pipeline CLI and the integration seed fixture

**Files:**
- Create: `pipeline/__main__.py`, `tests/fixtures/seed_small.csv.gz`, `tests/integration/test_pipeline_cli.py`
- Modify: `tests/integration/conftest.py` (add `loaded_db`, `reader_engine` fixtures)

**Interfaces:**
- Consumes: Tasks 3–7.
- Produces: `pipeline.__main__.ingest(engine, kind, get_seed, embedder, cache_path=None, prune_before=None) -> dict` (`{"added": int, "removed": int}`; `get_seed` is called inside the recorded run, so fetch failures are recorded too); `run_snapshot(engine, embedder, path, cache_path=None, if_empty=False, reset=False) -> dict`; `run_backfill(engine, embedder, start, end, reset=False, fetch=fetch_range) -> dict`; `run_refresh(engine, embedder, days=10, fetch=fetch_range) -> dict`; `main(argv=None) -> None`. CLI: `python -m pipeline {backfill,refresh,snapshot,fetch,create-reader,reset}`. Fixtures: `loaded_db` (admin engine with `seed_small` loaded via `FakeEmbedder` and the reader role granted), `reader_engine`, constant `SEED_SMALL`.

- [ ] **Step 1: Create the small seed fixture** (once, from the bundled snapshot)

Run:
```bash
.venv/Scripts/python - <<'PY'
import pandas as pd
from floatchat.regions import region_for

d = pd.read_csv("data/argo_profiles.csv.gz")
first = d.groupby(["wmo_id", "cycle_number"], as_index=False).first()
first["region"] = [region_for(a, b) for a, b in zip(first.lat, first.lon)]
oxy_keys = d[d.oxygen.notna()][["wmo_id", "cycle_number"]].drop_duplicates()
oxygen = first.merge(oxy_keys).head(10)
by_region = first.groupby("region").head(6)
picks = pd.concat([oxygen, by_region]).drop_duplicates(["wmo_id", "cycle_number"])
keep = d.merge(picks[["wmo_id", "cycle_number"]], on=["wmo_id", "cycle_number"])
keep.to_csv("tests/fixtures/seed_small.csv.gz", index=False, compression="gzip")
print(len(picks), "profiles,", len(keep), "rows;", picks.region.value_counts().to_dict())
PY
```
Expected: roughly 40–46 profiles, with at least 6 in the Arabian Sea.

- [ ] **Step 2: Add fixtures to `tests/integration/conftest.py`** (append)

```python
from pathlib import Path

from floatchat.db.roles import create_reader_role, reader_url
from tests.fakes import FakeEmbedder

SEED_SMALL = Path(__file__).resolve().parents[1] / "fixtures" / "seed_small.csv.gz"


@pytest.fixture
def loaded_db(empty_db):
    from pipeline.__main__ import run_snapshot

    run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)
    create_reader_role(empty_db, READER_PASSWORD)
    yield empty_db


@pytest.fixture
def reader_engine(loaded_db):
    engine = make_engine(reader_url(ADMIN_URL, READER_PASSWORD))
    yield engine
    engine.dispose()
```

Move the new imports to the top of the file with the existing imports so ruff's import sorting passes.

- [ ] **Step 3: Write the failing tests** (`tests/integration/test_pipeline_cli.py`)

```python
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.__main__ import run_backfill, run_refresh, run_snapshot
from pipeline.erddap import BGC, CORE, apply_qc, fetch_window
from tests.fakes import FakeEmbedder
from tests.integration.conftest import SEED_SMALL
from tests.unit.test_shape import BBOX, fixture_get

pytestmark = pytest.mark.integration


def fake_fetch(start, end, bbox):
    core = apply_qc(fetch_window(CORE, start, end, BBOX, get=fixture_get), CORE)
    bgc = apply_qc(fetch_window(BGC, start, end, BBOX, get=fixture_get), BGC)
    return core, bgc


def runs(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT kind, status FROM ingest_runs ORDER BY run_id")).all()


def test_snapshot_loads_and_records_a_run(empty_db):
    result = run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)
    expected = pd.read_csv(SEED_SMALL).groupby(["wmo_id", "cycle_number"]).ngroups
    assert result == {"added": expected, "removed": 0}
    assert runs(empty_db) == [("snapshot", "success")]


def test_snapshot_if_empty_skips_second_load(empty_db):
    run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)
    embedder = FakeEmbedder()
    assert run_snapshot(empty_db, embedder, SEED_SMALL, if_empty=True) == {"added": 0, "removed": 0}
    assert embedder.calls == 0


def test_snapshot_resets_an_old_schema(empty_db):
    with empty_db.begin() as conn:
        conn.exec_driver_sql("DROP TABLE profiles CASCADE")
        conn.exec_driver_sql("CREATE TABLE profiles (profile_id SERIAL PRIMARY KEY, float_id TEXT)")
    assert run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)["added"] > 0


def test_backfill_with_fake_fetch_prunes_by_window(empty_db):
    # The fixture data is from 2024, older than the 365-day window, so it is loaded then pruned
    result = run_backfill(empty_db, FakeEmbedder(), datetime(2024, 1, 1), datetime(2024, 3, 1), fetch=fake_fetch)
    assert result == {"added": 2, "removed": 2}
    assert runs(empty_db)[-1] == ("backfill", "success")


def test_failed_refresh_is_recorded(empty_db):
    def broken_fetch(start, end, bbox):
        raise RuntimeError("ERDDAP down")

    with pytest.raises(RuntimeError, match="ERDDAP down"):
        run_refresh(empty_db, FakeEmbedder(), fetch=broken_fetch)
    assert runs(empty_db)[-1] == ("refresh", "failed")
```

- [ ] **Step 4: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/integration/test_pipeline_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.__main__'`

- [ ] **Step 5: Implement `pipeline/__main__.py`**

```python
"""
FloatChat data pipeline.

    python -m pipeline backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--reset]
    python -m pipeline refresh [--days 10]
    python -m pipeline snapshot [--if-empty] [--reset] [--path data/argo_profiles.csv.gz]
    python -m pipeline fetch --start YYYY-MM-DD --end YYYY-MM-DD [--out data/argo_profiles.csv.gz]
    python -m pipeline create-reader [--password-env READER_PASSWORD]
    python -m pipeline reset

Database commands use ADMIN_DATABASE_URL (falling back to DATABASE_URL).
"""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from floatchat import config
from floatchat.db.engine import apply_schema, make_engine, reset_schema, schema_is_current
from floatchat.db.roles import create_reader_role
from pipeline.erddap import fetch_range
from pipeline.load import finish_run, load_tables, profile_count, prune, start_run
from pipeline.shape import build_tables, to_seed


def _today() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)


def _window_start() -> datetime:
    return _today() - timedelta(days=config.DATA_WINDOW_DAYS)


def ingest(engine, kind: str, get_seed: Callable[[], pd.DataFrame], embedder, cache_path=None,
           prune_before=None) -> dict:
    """Run one recorded load: get the seed rows (fetch or file), load new profiles, prune old ones."""
    apply_schema(engine)
    run_id = start_run(engine, kind)
    try:
        seed = get_seed()
        added = 0
        if not seed.empty:
            floats, profiles, measurements = build_tables(seed)
            added = load_tables(engine, floats, profiles, measurements, embedder, cache_path)
        removed = prune(engine, prune_before) if prune_before else 0
    except Exception:
        try:
            finish_run(engine, run_id, "failed", 0, 0)
        except Exception as e:  # the database itself may be the problem
            print(f"Could not record the failed run: {e}", file=sys.stderr)
        raise
    finish_run(engine, run_id, "success", added, removed)
    print(f"{kind}: {added} profiles added, {removed} removed")
    return {"added": added, "removed": removed}


def run_snapshot(engine, embedder, path, cache_path=None, if_empty=False, reset=False) -> dict:
    if reset or not schema_is_current(engine):
        reset_schema(engine)
    apply_schema(engine)
    if if_empty and profile_count(engine) > 0:
        print("Data already loaded - skipping snapshot.")
        return {"added": 0, "removed": 0}
    return ingest(engine, "snapshot", lambda: pd.read_csv(path), embedder, cache_path=cache_path)


def run_backfill(engine, embedder, start, end, reset=False, fetch=fetch_range) -> dict:
    if reset:
        reset_schema(engine)
    return ingest(engine, "backfill", lambda: to_seed(*fetch(start, end, config.BBOX)), embedder,
                  prune_before=_window_start())


def run_refresh(engine, embedder, days=10, fetch=fetch_range) -> dict:
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days + 1)
    return ingest(engine, "refresh", lambda: to_seed(*fetch(start, end, config.BBOX)), embedder,
                  prune_before=_window_start())


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    backfill = sub.add_parser("backfill", help="load a date range (default: the last 365 days)")
    backfill.add_argument("--start", type=_date)
    backfill.add_argument("--end", type=_date)
    backfill.add_argument("--reset", action="store_true", help="drop all tables first")
    refresh = sub.add_parser("refresh", help="load the last few days and prune old data")
    refresh.add_argument("--days", type=int, default=10)
    snapshot = sub.add_parser("snapshot", help="load the bundled snapshot (no network)")
    snapshot.add_argument("--path", default=config.SEED_DATA_PATH)
    snapshot.add_argument("--if-empty", action="store_true")
    snapshot.add_argument("--reset", action="store_true")
    fetch = sub.add_parser("fetch", help="download a date range into a seed CSV")
    fetch.add_argument("--start", type=_date, required=True)
    fetch.add_argument("--end", type=_date, required=True)
    fetch.add_argument("--out", default=config.SEED_DATA_PATH)
    reader = sub.add_parser("create-reader", help="create/update the read-only API role")
    reader.add_argument("--password-env", default="READER_PASSWORD")
    sub.add_parser("reset", help="drop all FloatChat tables")
    args = parser.parse_args(argv)

    if args.command == "fetch":
        core, bgc = fetch_range(args.start, args.end, config.BBOX)
        seed = to_seed(core, bgc)
        seed.to_csv(args.out, index=False, compression="gzip")
        print(f"Saved {len(seed):,} rows / {seed.groupby(['wmo_id', 'cycle_number']).ngroups:,} profiles to {args.out}")
        return

    engine = make_engine(config.ADMIN_DATABASE_URL)
    if args.command == "reset":
        reset_schema(engine)
    elif args.command == "create-reader":
        password = os.environ.get(args.password_env)
        if not password:
            sys.exit(f"Set the {args.password_env} environment variable to the reader password.")
        apply_schema(engine)
        create_reader_role(engine, password)
        print("Reader role ready.")
    else:
        from floatchat.embedder import get_embedder

        embedder = get_embedder()
        if args.command == "snapshot":
            use_cache = Path(args.path).resolve() == Path(config.SEED_DATA_PATH).resolve()
            run_snapshot(engine, embedder, args.path, config.EMBEDDING_CACHE_PATH if use_cache else None,
                         if_empty=args.if_empty, reset=args.reset)
        elif args.command == "backfill":
            end = args.end or _today() + timedelta(days=1)
            start = args.start or end - timedelta(days=config.DATA_WINDOW_DAYS + 1)
            run_backfill(engine, embedder, start, end, reset=args.reset)
        elif args.command == "refresh":
            run_refresh(engine, embedder, days=args.days)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests**

Run: `.venv/Scripts/python -m pytest tests/integration/test_pipeline_cli.py -q`
Expected: `5 passed`

- [ ] **Step 7: Lint and commit**

Run: `.venv/Scripts/python -m ruff check pipeline tests`

```bash
git add pipeline/__main__.py tests/fixtures/seed_small.csv.gz tests/integration
git commit -m "Add pipeline CLI: backfill, refresh, snapshot, fetch, reader role

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Read queries, vector search and exports

**Files:**
- Create: `floatchat/db/queries.py`, `floatchat/search.py`, `floatchat/exports.py`, `tests/integration/test_queries.py`, `tests/integration/test_search.py`, `tests/integration/test_exports.py`

**Interfaces:**
- Consumes: `reader_engine`, `loaded_db` fixtures (Task 8); `tests.fakes.FakeEmbedder`.
- Produces:
  - `floatchat.db.queries`: `read_sql(engine, sql, **params) -> pd.DataFrame`; `df_records(df) -> list[dict]`; `get_stats(engine) -> dict` (keys `floats, profiles, measurements, bgc_floats, chlorophyll_floats, nitrate_floats, ph_floats, start_date, end_date, max_depth, last_updated, regions`); `get_floats(engine) -> list[dict]` (keys `float_id, last_profile, lat, lon, region, n_profiles, surface_temperature, surface_salinity, is_bgc`); `get_profiles(engine, ids, profile_ids) -> list[dict]`; `get_float_info(engine, float_id) -> dict | None`; `get_float_profiles(engine, float_id) -> list[dict]`; `data_status(engine) -> dict` (keys `measurements, indexed_profiles, newest_data, latest_run_id`); `log_query(engine, *, question, query_type, intent, latency_ms, success, cached, llm_used) -> None`.
  - `floatchat.search`: `vector_literal(vector) -> str`; `search_profiles(engine, query_vector, filters: dict, limit: int = 8) -> list[dict]` (keys `profile_id, float_id, cycle_number, date, year, month_num, lat, lon, region, has_oxygen, has_chlorophyll, has_nitrate, has_ph, description, distance`).
  - `floatchat.exports`: `fetch_measurements(engine, data_ids, profile_ids) -> pd.DataFrame`; `export_to_csv(engine, data_ids, profile_ids) -> str`; `export_to_netcdf(...) -> bytes`; `export_to_ascii(...) -> str`; `EXPORTERS: dict[str, tuple[callable, str media_type, str filename]]` for keys `csv`, `netcdf`, `ascii`.

- [ ] **Step 1: Write the failing tests**

`tests/integration/test_queries.py`:
```python
import pytest
from sqlalchemy import text

from floatchat.db import queries

pytestmark = pytest.mark.integration


def test_stats(reader_engine):
    stats = queries.get_stats(reader_engine)
    assert stats["profiles"] > 30 and stats["floats"] > 0 and stats["measurements"] > 0
    assert stats["bgc_floats"] >= 1
    assert stats["last_updated"] is not None
    assert {r["region"] for r in stats["regions"]} >= {"Arabian Sea"}


def test_floats_shape(reader_engine):
    floats = queries.get_floats(reader_engine)
    assert set(floats[0]) == {"float_id", "last_profile", "lat", "lon", "region", "n_profiles",
                              "surface_temperature", "surface_salinity", "is_bgc"}
    assert any(f["is_bgc"] for f in floats)


def test_profiles_by_profile_and_measurement_id(reader_engine):
    rows = queries.get_profiles(reader_engine, [], [1])
    assert rows and {r["profile_id"] for r in rows} == {1}
    assert {"chlorophyll", "nitrate", "ph", "oxygen", "region"} <= set(rows[0])
    by_measurement = queries.get_profiles(reader_engine, [rows[0]["id"]], [])
    assert len(by_measurement) == len(rows)  # the whole profile comes back


def test_float_info_and_trajectory(reader_engine):
    float_id = queries.get_floats(reader_engine)[0]["float_id"]
    info = queries.get_float_info(reader_engine, float_id)
    assert info["float_info"]["float_id"] == float_id
    track = queries.get_float_profiles(reader_engine, float_id)
    assert track and "embedding" not in track[0] and "profile_lat" in track[0]
    assert queries.get_float_info(reader_engine, "nope") is None


def test_data_status(reader_engine):
    status = queries.data_status(reader_engine)
    assert status["indexed_profiles"] == queries.get_stats(reader_engine)["profiles"]
    assert status["latest_run_id"] >= 1 and status["newest_data"] is not None


def test_log_query_as_reader(reader_engine, loaded_db):
    queries.log_query(reader_engine, question="hello", query_type="semantic", intent=None,
                      latency_ms=12, success=True, cached=False, llm_used=False)
    with loaded_db.connect() as conn:
        assert conn.execute(text("SELECT question FROM query_log")).scalar() == "hello"


def test_log_query_never_raises(reader_engine):
    queries.log_query(reader_engine, question="x" * 10, query_type="semantic", intent="i" * 500,
                      latency_ms=1, success=True, cached=False, llm_used=False)  # intent too long: swallowed
```

`tests/integration/test_search.py`:
```python
import pytest

from floatchat.search import search_profiles
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def query_vector(text="profiles"):
    return FakeEmbedder().embed([text])[0]


def test_returns_limit_and_keys(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {}, limit=5)
    assert len(results) == 5
    assert {"profile_id", "float_id", "date", "lat", "lon", "region", "has_oxygen", "description",
            "distance"} <= set(results[0])
    assert results == sorted(results, key=lambda r: r["distance"])


def test_region_filter(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {"region": "Arabian Sea"})
    assert results and all(r["region"] == "Arabian Sea" for r in results)


def test_month_filter(reader_engine):
    month = search_profiles(reader_engine, query_vector(), {}, limit=1)[0]["month_num"]
    results = search_profiles(reader_engine, query_vector(), {"month_num": month})
    assert results and all(int(r["date"][5:7]) == month for r in results)


def test_sensor_filter(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {"has_oxygen": True})
    assert results and all(r["has_oxygen"] for r in results)


def test_unknown_filter_keys_are_ignored_and_no_match_is_empty(reader_engine):
    assert search_profiles(reader_engine, query_vector(), {"region": "Atlantis", "evil": "1; DROP"}) == []
```

`tests/integration/test_exports.py`:
```python
import pytest

from floatchat.exports import EXPORTERS

pytestmark = pytest.mark.integration


def test_csv_includes_bgc_columns(reader_engine):
    content = EXPORTERS["csv"][0](reader_engine, [], [1, 2])
    header = content.splitlines()[0]
    assert header.startswith("float_id,profile_id,time") and "chlorophyll" in header


def test_netcdf_is_hdf5(reader_engine):
    content = EXPORTERS["netcdf"][0](reader_engine, [], [1])
    assert content[:4] == b"\x89HDF"


def test_ascii_header(reader_engine):
    content = EXPORTERS["ascii"][0](reader_engine, [], [1])
    assert content.startswith("# ARGO Float Data Export") and "# Number of profiles: 1" in content
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/integration/test_queries.py tests/integration/test_search.py tests/integration/test_exports.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'floatchat.db.queries'`

- [ ] **Step 3: Implement `floatchat/db/queries.py`**

```python
"""Read queries behind the API endpoints. All work with the read-only role."""

import json
import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def read_sql(engine: Engine, sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> null, timestamps -> ISO)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def get_stats(engine: Engine) -> dict:
    totals = read_sql(engine, """
        SELECT (SELECT COUNT(*) FROM floats) AS floats,
               (SELECT COUNT(*) FROM profiles) AS profiles,
               (SELECT COUNT(*) FROM measurements) AS measurements,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_oxygen) AS bgc_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_chlorophyll) AS chlorophyll_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_nitrate) AS nitrate_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_ph) AS ph_floats,
               (SELECT MIN(profile_date) FROM profiles) AS start_date,
               (SELECT MAX(profile_date) FROM profiles) AS end_date,
               (SELECT MAX(depth) FROM measurements) AS max_depth,
               (SELECT MAX(finished_at) FROM ingest_runs WHERE status = 'success') AS last_updated
    """)
    regions = read_sql(engine, "SELECT region, COUNT(*) AS profiles FROM profiles GROUP BY region ORDER BY profiles DESC")
    return {**df_records(totals)[0], "regions": df_records(regions)}


def get_floats(engine: Engine) -> list[dict]:
    return df_records(read_sql(engine, """
        WITH latest AS (
            SELECT DISTINCT ON (float_id) float_id, profile_id, profile_date, profile_lat, profile_lon, region
            FROM profiles ORDER BY float_id, profile_date DESC
        ),
        counts AS (
            SELECT float_id, COUNT(*) AS n_profiles,
                   bool_or(has_oxygen OR has_chlorophyll OR has_nitrate OR has_ph) AS is_bgc
            FROM profiles GROUP BY float_id
        ),
        surface AS (
            SELECT DISTINCT ON (profile_id) profile_id, temperature, salinity
            FROM measurements WHERE profile_id IN (SELECT profile_id FROM latest)
            ORDER BY profile_id, depth
        )
        SELECT l.float_id, l.profile_date AS last_profile, l.profile_lat AS lat, l.profile_lon AS lon, l.region,
               c.n_profiles, s.temperature AS surface_temperature, s.salinity AS surface_salinity, c.is_bgc
        FROM latest l
        JOIN counts c USING (float_id)
        LEFT JOIN surface s USING (profile_id)
        ORDER BY l.float_id
    """))


def get_profiles(engine: Engine, ids: list[int], profile_ids: list[int]) -> list[dict]:
    return df_records(read_sql(engine, """
        SELECT m.id, m.time, m.lat, m.lon, m.depth, m.pressure, m.temperature, m.salinity,
               m.oxygen, m.chlorophyll, m.nitrate, m.ph, m.float_id, m.profile_id,
               p.cycle_number, p.region, f.wmo_id
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.profile_id
        JOIN floats f ON m.float_id = f.float_id
        WHERE m.profile_id = ANY(:profile_ids)
           OR m.profile_id IN (SELECT profile_id FROM measurements WHERE id = ANY(:ids))
        ORDER BY m.float_id, p.cycle_number, m.depth
    """, ids=list(ids), profile_ids=list(profile_ids)))


def get_float_info(engine: Engine, float_id: str) -> dict | None:
    info = read_sql(engine, "SELECT * FROM floats WHERE float_id = :fid", fid=float_id)
    if info.empty:
        return None
    profile_summary = read_sql(engine, """
        SELECT COUNT(*) AS total_profiles, MIN(profile_date) AS first_profile,
               MAX(profile_date) AS last_profile, COUNT(DISTINCT DATE(profile_date)) AS active_days
        FROM profiles WHERE float_id = :fid
    """, fid=float_id)
    measurement_summary = read_sql(engine, """
        SELECT COUNT(*) AS total_measurements, MIN(depth) AS min_depth, MAX(depth) AS max_depth,
               AVG(temperature) AS avg_temp, AVG(salinity) AS avg_sal
        FROM measurements WHERE float_id = :fid
    """, fid=float_id)
    return {
        "float_info": df_records(info)[0],
        "profile_summary": df_records(profile_summary)[0],
        "measurement_summary": df_records(measurement_summary)[0],
    }


def get_float_profiles(engine: Engine, float_id: str) -> list[dict]:
    return df_records(read_sql(engine, """
        SELECT p.profile_id, p.float_id, p.cycle_number, p.profile_date, p.profile_lat, p.profile_lon,
               p.region, p.n_levels, p.has_oxygen, p.has_chlorophyll, p.has_nitrate, p.has_ph,
               COUNT(m.id) AS measurement_count, AVG(m.temperature) AS avg_temp, AVG(m.salinity) AS avg_sal,
               MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM profiles p
        LEFT JOIN measurements m ON p.profile_id = m.profile_id
        WHERE p.float_id = :fid
        GROUP BY p.profile_id
        ORDER BY p.cycle_number
    """, fid=float_id))


def data_status(engine: Engine) -> dict:
    return df_records(read_sql(engine, """
        SELECT (SELECT COUNT(*) FROM measurements) AS measurements,
               (SELECT COUNT(*) FROM profiles WHERE embedding IS NOT NULL) AS indexed_profiles,
               (SELECT MAX(profile_date) FROM profiles) AS newest_data,
               (SELECT COALESCE(MAX(run_id), 0) FROM ingest_runs WHERE status = 'success') AS latest_run_id
    """))[0]


def log_query(engine: Engine, *, question: str, query_type: str | None, intent: str | None, latency_ms: int,
              success: bool, cached: bool, llm_used: bool) -> None:
    """Best effort: a logging failure must never fail the request."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO query_log (question, query_type, intent, latency_ms, success, cached, llm_used)
                VALUES (:question, :query_type, :intent, :latency_ms, :success, :cached, :llm_used)
            """), {"question": question, "query_type": query_type, "intent": intent, "latency_ms": latency_ms,
                   "success": success, "cached": cached, "llm_used": llm_used})
    except Exception as e:
        logger.warning("Could not write query_log: %s", e)
```

- [ ] **Step 4: Implement `floatchat/search.py`**

```python
"""Semantic profile search: pgvector similarity plus SQL filters in one query."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Only these filter keys reach SQL; values are always bound parameters
FILTER_SQL = {
    "region": "region = :region",
    "month_num": "EXTRACT(MONTH FROM profile_date) = :month_num",
    "year": "EXTRACT(YEAR FROM profile_date) = :year",
    "has_oxygen": "has_oxygen",
    "has_chlorophyll": "has_chlorophyll",
    "has_nitrate": "has_nitrate",
    "has_ph": "has_ph",
}
VALUE_FILTERS = ("region", "month_num", "year")


def vector_literal(vector) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vector) + "]"


def search_profiles(engine: Engine, query_vector, filters: dict, limit: int = 8) -> list[dict]:
    clauses = ["embedding IS NOT NULL"] + [FILTER_SQL[key] for key in filters if key in FILTER_SQL]
    params = {key: filters[key] for key in VALUE_FILTERS if key in filters}
    params.update(q=vector_literal(query_vector), limit=limit)
    sql = f"""
        SELECT profile_id, float_id, cycle_number, to_char(profile_date, 'YYYY-MM-DD') AS date,
               EXTRACT(YEAR FROM profile_date)::int AS year, EXTRACT(MONTH FROM profile_date)::int AS month_num,
               profile_lat AS lat, profile_lon AS lon, region,
               has_oxygen, has_chlorophyll, has_nitrate, has_ph, description,
               embedding <=> CAST(:q AS vector) AS distance
        FROM profiles
        WHERE {" AND ".join(clauses)}
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :limit
    """
    with engine.begin() as conn:
        # Filters are applied after the HNSW scan; a wider scan keeps filtered results complete
        conn.execute(text("SET LOCAL hnsw.ef_search = 200"))
        return [dict(row) for row in conn.execute(text(sql), params).mappings()]
```

- [ ] **Step 5: Implement `floatchat/exports.py`** (from `export_utils.py`, with BGC columns and an injected engine)

```python
"""Export profiles as CSV, NetCDF or ASCII."""

import os
import tempfile
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

COLUMNS = ["float_id", "profile_id", "time", "lat", "lon", "depth", "pressure",
           "temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph"]


def fetch_measurements(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(f"""
            SELECT {", ".join(COLUMNS)} FROM measurements
            WHERE id = ANY(:ids) OR profile_id = ANY(:profile_ids)
            ORDER BY float_id, time, depth
        """), conn, params={"ids": list(data_ids or []), "profile_ids": list(profile_ids or [])})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def export_to_csv(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> str:
    return fetch_measurements(engine, data_ids, profile_ids).to_csv(index=False)


def export_to_ascii(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> str:
    df = fetch_measurements(engine, data_ids, profile_ids)
    out = StringIO()
    out.write("# ARGO Float Data Export\n")
    out.write(f"# Generated: {_now()}\n")
    out.write(f"# Number of profiles: {df['profile_id'].nunique()}\n")
    out.write("# Format: FLOAT DATE TIME LAT LON DEPTH TEMP SALINITY OXYGEN\n")
    out.write("# Units: WMO-ID YYYY-MM-DD HH:MM:SS degrees degrees meters celsius psu umol/kg\n")
    out.write("#" + "=" * 70 + "\n")

    def num(value, fmt):
        return format(value, fmt) if pd.notna(value) else "     NaN"

    for _, row in df.iterrows():
        out.write(f"{row['float_id']:>8} {row['time']:%Y-%m-%d %H:%M:%S} {row['lat']:8.3f} {row['lon']:8.3f} "
                  f"{row['depth']:8.1f} {num(row['temperature'], '8.3f')} {num(row['salinity'], '8.3f')} "
                  f"{num(row['oxygen'], '8.2f')}\n")
    return out.getvalue()


def export_to_netcdf(engine: Engine, data_ids: list[int], profile_ids: list[int]) -> bytes:
    import xarray as xr  # imported lazily: keeps the API's resting memory low

    df = fetch_measurements(engine, data_ids, profile_ids)
    variables = {name: (["obs"], df[name].astype(float).to_numpy())
                 for name in ("temperature", "salinity", "oxygen", "chlorophyll", "nitrate", "ph", "depth")}
    ds = xr.Dataset({
        "float_id": (["obs"], df["float_id"].to_numpy(dtype=str)),
        "latitude": (["obs"], df["lat"].to_numpy()),
        "longitude": (["obs"], df["lon"].to_numpy()),
        "time": (["obs"], pd.to_datetime(df["time"]).to_numpy()),
        **variables,
    })
    ds.attrs = {"title": "ARGO Float Data Export", "institution": "FloatChat",
                "source": "Argo GDAC via Ifremer ERDDAP", "history": f"Created {_now()}", "Conventions": "CF-1.6"}
    units = {"temperature": ("sea_water_temperature", "degree_Celsius"),
             "salinity": ("sea_water_practical_salinity", "psu"),
             "oxygen": ("moles_of_oxygen_per_unit_mass_in_sea_water", "micromole/kg"),
             "chlorophyll": ("mass_concentration_of_chlorophyll_a_in_sea_water", "mg/m3"),
             "nitrate": ("moles_of_nitrate_per_unit_mass_in_sea_water", "micromole/kg"),
             "ph": ("sea_water_ph_reported_on_total_scale", "1"),
             "depth": ("depth", "m")}
    for name, (standard_name, unit) in units.items():
        ds[name].attrs = {"standard_name": standard_name, "units": unit}
    with tempfile.TemporaryDirectory() as tmp:  # netCDF4 can only write to a real file
        path = os.path.join(tmp, "argo_data.nc")
        ds.to_netcdf(path, format="NETCDF4", engine="netcdf4")
        with open(path, "rb") as f:
            return f.read()


EXPORTERS = {
    "csv": (export_to_csv, "text/csv", "argo_data.csv"),
    "netcdf": (export_to_netcdf, "application/x-netcdf", "argo_data.nc"),
    "ascii": (export_to_ascii, "text/plain", "argo_data.txt"),
}
```

- [ ] **Step 6: Run tests**

Run: `.venv/Scripts/python -m pytest tests/integration/test_queries.py tests/integration/test_search.py tests/integration/test_exports.py -q`
Expected: `15 passed`

- [ ] **Step 7: Lint and commit**

Run: `.venv/Scripts/python -m ruff check floatchat tests`

```bash
git add floatchat/db/queries.py floatchat/search.py floatchat/exports.py tests/integration
git commit -m "Add read queries, pgvector search and exports on the new schema

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: SQL agent and answer building

**Files:**
- Create: `floatchat/sql_agent.py`, `floatchat/answer.py`, `tests/unit/test_sql_agent.py`, `tests/unit/test_answer.py`, `tests/integration/test_sql_agent_db.py`, `tests/integration/test_answer_db.py`

**Interfaces:**
- Consumes: `floatchat.llm.chat`, `floatchat.regions.parse_filters`/`MONTHS`, `floatchat.search.search_profiles`, `floatchat.db.queries.df_records`.
- Produces:
  - `floatchat.sql_agent`: `TEMPLATES: dict[str, str]`; `class SqlAgent(engine, chat=llm.chat)` with static methods `is_analytical_query(q) -> bool`, `detect_query_intent(q) -> str`, `validate_sql(sql) -> bool`, and methods `generate_sql(question) -> tuple[str | None, str]`, `execute_sql_query(sql) -> tuple[pd.DataFrame, str]`, `run(question) -> tuple[dict | None, str | None]` (result keys `sql_query, results (DataFrame), intent, summary_stats`); `sample_queries() -> dict`.
  - `floatchat.answer`: `SYSTEM_PROMPT`, `INTENT_TITLES`, `format_position(lat, lon) -> str`, `describe_filters(filters) -> str`, `format_results_for_display(df, intent) -> str`, `answer_question(question, *, engine, embedder_factory, agent, chat) -> dict` with keys `answer, query_type ("analytical" | "semantic" | "error"), context_documents, retrieved_metadata, sql_results, intent, llm_used`.

- [ ] **Step 1: Write the failing unit tests**

`tests/unit/test_sql_agent.py` (routing and safety, moved from the old core tests and extended):
```python
import pytest

from floatchat.sql_agent import TEMPLATES, SqlAgent


@pytest.mark.parametrize("question,expected_intent", [
    ("What is the average temperature at different depths?", "avg_by_depth"),
    ("Show average salinity by depth range", "depth_ranges"),
    ("Compare surface temperature across ocean regions", "regional_comparison"),
    ("Average dissolved oxygen by ocean zone", "bgc_analysis"),
    ("Average chlorophyll by ocean zone", "bgc_analysis"),
    ("Show the monthly temperature trend", "temporal_trends"),
    ("Show a summary for each float", "float_summary"),
    ("How many profiles were recorded?", "custom"),
])
def test_analytical_routing(question, expected_intent):
    assert SqlAgent.is_analytical_query(question)
    assert SqlAgent.detect_query_intent(question) == expected_intent


@pytest.mark.parametrize("question", [
    "Show me salinity profiles near the equator in March 2024",
    "Tell me about floats in the Bay of Bengal",
    "What does a depth profile look like?",
])
def test_descriptive_questions_use_search(question):
    assert not SqlAgent.is_analytical_query(question)


@pytest.mark.parametrize("sql,safe", [
    ("SELECT depth, AVG(temperature) FROM measurements GROUP BY depth", True),
    ("WITH x AS (SELECT 1) SELECT * FROM x", True),
    ("SELECT created_at FROM floats", True),
    ("SELECT 1;", True),
    ("DROP TABLE floats", False),
    ("SELECT 1; DELETE FROM measurements", False),
    ("UPDATE floats SET status = 'x'", False),
    ("SELECT pg_read_file('/etc/passwd')", False),
])
def test_validate_sql(sql, safe):
    assert SqlAgent.validate_sql(sql) == safe


def test_every_template_is_safe():
    assert all(SqlAgent.validate_sql(sql) for sql in TEMPLATES.values())
```

`tests/unit/test_answer.py`:
```python
import pandas as pd

from floatchat.answer import describe_filters, format_position, format_results_for_display


def test_format_position():
    assert format_position(-12.5, 65.25) == "12.50°S, 65.25°E"


def test_describe_filters():
    assert describe_filters({"region": "Arabian Sea", "month_num": 3, "year": 2024, "has_oxygen": True}) == \
        "in the Arabian Sea in March 2024 from floats measuring oxygen"
    assert describe_filters({}) == ""


def test_format_avg_by_depth_truncates_with_a_note():
    df = pd.DataFrame({"depth": range(20), "avg_temperature": [20.0] * 20, "avg_salinity": [35.0] * 20,
                       "measurement_count": [5] * 20})
    text = format_results_for_display(df, "avg_by_depth")
    assert text.startswith("- **0 m**: 20.00 °C, 35.00 PSU (5 readings)")
    assert "8 more rows" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/unit/test_sql_agent.py tests/unit/test_answer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'floatchat.sql_agent'`

- [ ] **Step 3: Implement `floatchat/sql_agent.py`**

```python
"""
Statistical questions -> SQL. Common question types use hand-written templates;
anything else is written by the LLM and must pass a read-only check. The API's
database role is read-only as well, so a bad query can never change data.
"""

import logging
import re
from collections.abc import Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from floatchat import llm

logger = logging.getLogger(__name__)
ChatFn = Callable[..., str | None]

ZONE_CASE = ("CASE WHEN depth < 200 THEN 'Euphotic Zone' WHEN depth < 1000 THEN 'Mesopelagic Zone' "
             "ELSE 'Bathypelagic Zone' END")
LAYER_CASE = ("CASE WHEN depth < 100 THEN 'Surface (0-100m)' WHEN depth < 500 THEN 'Intermediate (100-500m)' "
              "WHEN depth < 1000 THEN 'Deep (500-1000m)' ELSE 'Very Deep (>1000m)' END")

TEMPLATES = {
    "avg_by_depth": """
        SELECT depth, AVG(temperature) AS avg_temperature, AVG(salinity) AS avg_salinity,
               COUNT(*) AS measurement_count
        FROM measurements
        WHERE temperature IS NOT NULL AND salinity IS NOT NULL
        GROUP BY depth ORDER BY depth LIMIT 100""",
    "regional_comparison": """
        SELECT p.region, AVG(m.temperature) AS avg_temperature, AVG(m.salinity) AS avg_salinity,
               AVG(m.oxygen) AS avg_oxygen, COUNT(DISTINCT p.profile_id) AS profile_count,
               COUNT(*) AS measurement_count
        FROM measurements m JOIN profiles p ON m.profile_id = p.profile_id
        WHERE m.temperature IS NOT NULL AND m.depth <= 100
        GROUP BY p.region ORDER BY avg_temperature DESC""",
    "depth_ranges": f"""
        SELECT {LAYER_CASE} AS depth_range, AVG(temperature) AS avg_temperature, AVG(salinity) AS avg_salinity,
               AVG(oxygen) AS avg_oxygen, COUNT(*) AS measurement_count
        FROM measurements WHERE temperature IS NOT NULL
        GROUP BY 1 ORDER BY MIN(depth)""",
    "float_summary": """
        SELECT f.float_id, f.wmo_id, f.deployment_date, COUNT(DISTINCT p.profile_id) AS total_profiles,
               COUNT(m.id) AS total_measurements, AVG(m.temperature) AS avg_temperature,
               AVG(m.salinity) AS avg_salinity, MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM floats f
        JOIN profiles p ON f.float_id = p.float_id
        JOIN measurements m ON p.profile_id = m.profile_id
        WHERE m.temperature IS NOT NULL
        GROUP BY f.float_id, f.wmo_id, f.deployment_date
        ORDER BY total_measurements DESC LIMIT 50""",
    "temporal_trends": """
        SELECT DATE_TRUNC('month', time) AS month, AVG(temperature) AS avg_temperature,
               AVG(salinity) AS avg_salinity, COUNT(*) AS measurement_count
        FROM measurements WHERE temperature IS NOT NULL
        GROUP BY 1 ORDER BY month LIMIT 100""",
    "bgc_analysis": f"""
        SELECT {ZONE_CASE} AS ocean_zone, AVG(oxygen) AS avg_oxygen, MIN(oxygen) AS min_oxygen,
               MAX(oxygen) AS max_oxygen, AVG(chlorophyll) AS avg_chlorophyll, AVG(nitrate) AS avg_nitrate,
               AVG(ph) AS avg_ph, COUNT(*) AS measurement_count
        FROM measurements
        WHERE oxygen IS NOT NULL OR chlorophyll IS NOT NULL OR nitrate IS NOT NULL OR ph IS NOT NULL
        GROUP BY 1 ORDER BY MIN(depth)""",
}

SCHEMA_PROMPT = """
TABLES (PostgreSQL):
floats(float_id text PK, wmo_id int, deployment_date date, deployment_lat float, deployment_lon float, last_contact date)
profiles(profile_id int PK, float_id text, cycle_number int, profile_date timestamp, profile_lat float,
         profile_lon float, region text, n_levels int, has_oxygen bool, has_chlorophyll bool, has_nitrate bool, has_ph bool)
measurements(id bigint PK, profile_id int, float_id text, time timestamp, lat float, lon float, depth float (m),
             pressure float (dbar), temperature float (degC), salinity float (PSU), oxygen float (umol/kg),
             chlorophyll float (mg/m3), nitrate float (umol/kg), ph float)
RELATIONSHIPS: floats 1-n profiles via float_id; profiles 1-n measurements via profile_id.
profiles.region is one of: 'Arabian Sea', 'Bay of Bengal', 'Equatorial Indian Ocean', 'Southern Indian Ocean',
'Eastern Indian Ocean', 'Red Sea & Gulf of Aden'.
Each profile has measurements on 24 standard depths: 5,10,20,30,50,75,100,125,150,200,250,300,400,500,600,700,800,900,1000,1200,1400,1600,1800,2000.
BGC columns (oxygen, chlorophyll, nitrate, ph) are NULL for floats without those sensors.
"""

ANALYTICAL_PATTERNS = [
    r"\b(average|mean|avg|sum|count|total|maximum|max|minimum|min)\b",
    r"\b(compare|comparison|versus|vs|between|difference)\b",
    r"\b(group|aggregate|distribution|range|trend|correlation)\b",
    r"\b(how many|how much|statistics|statistical|percentage|percent)\b",
    r"\b(greater than|less than|higher|lower|above|below|top|bottom)\b",
    r"\b(over time|temporal|monthly|yearly|seasonal)\b",
    r"\b(summary|summarize|summarise|overview|each float|per float|by month|by depth|by region|by zone)\b",
]
FORBIDDEN_SQL = ["drop", "delete", "truncate", "alter", "create", "insert", "update", "grant", "revoke",
                 "copy", "pg_read_file", "pg_sleep", "dblink", "set_config"]


class SqlAgent:
    def __init__(self, engine: Engine, chat: ChatFn = llm.chat):
        self.engine = engine
        self.chat = chat

    @staticmethod
    def is_analytical_query(question: str) -> bool:
        q = question.lower()
        return any(re.search(pattern, q) for pattern in ANALYTICAL_PATTERNS)

    @staticmethod
    def detect_query_intent(question: str) -> str:
        q = question.lower()
        if re.search(r"\b(oxygen|ph|chlorophyll|nitrate|bgc|biogeochemical)\b", q):
            return "bgc_analysis"
        if re.search(r"\b(depth range|depth ranges|zone|zones|layer|layers|surface and deep)\b", q):
            return "depth_ranges"
        if any(word in q for word in ("depth", "profile", "vertical")) and any(w in q for w in ("average", "mean")):
            return "avg_by_depth"
        if any(word in q for word in ("region", "hemisphere", "arabian", "bengal", "basin")):
            return "regional_comparison"
        if any(word in q for word in ("time", "temporal", "trend", "month", "year", "weekly")):
            return "temporal_trends"
        if any(word in q for word in ("float", "summary", "overview")):
            return "float_summary"
        return "custom"

    @staticmethod
    def validate_sql(sql: str) -> bool:
        lowered = sql.lower()
        if any(re.search(rf"\b{word}\b", lowered) for word in FORBIDDEN_SQL):
            return False
        if not re.match(r"\s*(select|with)\b", lowered):
            return False
        return ";" not in lowered.strip().rstrip(";")  # exactly one statement

    def generate_sql(self, question: str) -> tuple[str | None, str]:
        intent = self.detect_query_intent(question)
        if intent in TEMPLATES:
            return TEMPLATES[intent].strip(), intent
        prompt = (
            "You are an expert PostgreSQL analyst for Argo ocean float data.\n"
            f"{SCHEMA_PROMPT}\n"
            "Rules: one read-only SELECT statement; meaningful column aliases; handle NULLs; "
            "at most 1000 rows; ORDER BY for readable output.\n\n"
            f"Question: {question}\n"
            "Return ONLY the SQL, no explanation and no code fences."
        )
        sql = self.chat(prompt, temperature=0.0)
        if not sql:
            return None, "error"
        sql = re.sub(r"```(sql)?", "", sql).strip().rstrip(";")
        if "limit" not in sql.lower():
            sql += " LIMIT 1000"
        return sql, "custom"

    def execute_sql_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        if not self.validate_sql(sql):
            return pd.DataFrame(), "Invalid or unsafe SQL query"
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(sql), conn)
        except Exception as e:
            logger.info("SQL failed: %s", e)
            return pd.DataFrame(), f"Database error: {e.__class__.__name__}"
        if df.empty:
            return df, "Query executed successfully but returned no results"
        return df, "success"

    def run(self, question: str) -> tuple[dict | None, str | None]:
        if not self.is_analytical_query(question):
            return None, "Not an analytical query"
        sql, intent = self.generate_sql(question)
        if not sql:
            return None, "Failed to generate SQL"
        df, status = self.execute_sql_query(sql)
        if status != "success":
            return None, f"SQL execution failed: {status}"
        return {"sql_query": sql, "results": df, "intent": intent, "summary_stats": _summary_stats(df)}, None


def _summary_stats(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include="number")
    stats = {"total_rows": int(len(df)), "columns": [str(c) for c in df.columns],
             "numeric_columns": [str(c) for c in numeric.columns], "numeric_summary": {}}
    for col in list(numeric.columns)[:5]:
        values = numeric[col].dropna()
        stats["numeric_summary"][str(col)] = (
            {"mean": float(values.mean()), "min": float(values.min()), "max": float(values.max()),
             "count": int(values.count())} if not values.empty else
            {"mean": None, "min": None, "max": None, "count": 0})
    return stats


def sample_queries() -> dict:
    return {
        "analytical_queries": {
            "Depth Analysis": ["What is the average temperature at different depths?",
                               "Show average salinity by depth range"],
            "Regional Comparison": ["Compare surface temperature across ocean regions",
                                    "Compare the Arabian Sea and the Bay of Bengal"],
            "Temporal Trends": ["Show the monthly temperature trend"],
            "Float Analysis": ["Show a summary for each float"],
            "BGC Parameters": ["Average dissolved oxygen by ocean zone", "Average chlorophyll by ocean zone"],
        },
        "semantic_queries": {
            "Find Profiles": ["Show me salinity profiles near the equator",
                              "Find warm surface water in the Bay of Bengal",
                              "Which floats measured low oxygen in the Arabian Sea?",
                              "Where is chlorophyll highest?"],
        },
        "query_tips": {
            "analytical": "Use words like 'average', 'compare', 'count', 'trend' for statistical analysis",
            "semantic": "Ask descriptive questions; mention a region, month or sensor to narrow the search",
        },
    }
```

- [ ] **Step 4: Implement `floatchat/answer.py`** (moved from `main.py`, with dependencies injected)

```python
"""Build the answer for a question: SQL results or matching profiles, optionally explained by the LLM."""

from collections.abc import Callable

import pandas as pd
from sqlalchemy.engine import Engine

from floatchat.db.queries import df_records
from floatchat.regions import MONTHS, parse_filters
from floatchat.search import search_profiles
from floatchat.sql_agent import SqlAgent

SYSTEM_PROMPT = (
    "You are FloatChat, an oceanography assistant for Argo float data in the Indian Ocean. "
    "Answer using only the facts in the provided context. Be concise (under 150 words), "
    "mention float IDs, dates and locations where relevant, and use Markdown bullet points. "
    "If the context does not answer the question, say so."
)
INTENT_TITLES = {
    "avg_by_depth": "Average temperature and salinity at each depth",
    "regional_comparison": "Upper-ocean (0–100 m) conditions by region",
    "depth_ranges": "Ocean conditions by depth layer",
    "temporal_trends": "Monthly averages",
    "float_summary": "Most active floats",
    "bgc_analysis": "Biogeochemistry by ocean zone",
}
SENSOR_NAMES = {"has_oxygen": "oxygen", "has_chlorophyll": "chlorophyll", "has_nitrate": "nitrate", "has_ph": "pH"}


def format_position(lat: float, lon: float) -> str:
    return f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"


def describe_filters(filters: dict) -> str:
    parts = []
    if "region" in filters:
        parts.append(f"in the {filters['region']}")
    if "month_num" in filters:
        parts.append(f"in {MONTHS[filters['month_num'] - 1].title()}")
    if "year" in filters:
        parts.append(str(filters["year"]))
    sensors = [name for key, name in SENSOR_NAMES.items() if filters.get(key)]
    if sensors:
        parts.append("from floats measuring " + " and ".join(sensors))
    return " ".join(parts)


def format_results_for_display(df: pd.DataFrame, intent: str) -> str:
    def fmt(row, col, unit, digits=2):
        value = row.get(col)
        return f"{value:.{digits}f}{unit}" if pd.notna(value) else "N/A"

    lines = []
    if intent == "avg_by_depth":
        for _, row in df.head(12).iterrows():
            lines.append(f"- **{row['depth']:.0f} m**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['measurement_count']:.0f} readings)")
    elif intent == "regional_comparison":
        for _, row in df.iterrows():
            lines.append(f"- **{row['region']}**: upper-100 m avg {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['profile_count']:.0f} profiles)")
    elif intent == "depth_ranges":
        for _, row in df.iterrows():
            lines.append(f"- **{row['depth_range']}**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')}, O₂ {fmt(row, 'avg_oxygen', ' µmol/kg', 1)}")
    elif intent == "temporal_trends":
        for _, row in df.head(12).iterrows():
            month = row["month"].strftime("%B %Y") if hasattr(row["month"], "strftime") else str(row["month"])
            lines.append(f"- **{month}**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['measurement_count']:.0f} readings)")
    elif intent == "float_summary":
        for _, row in df.head(10).iterrows():
            lines.append(f"- **Float {row['float_id']}**: {row['total_profiles']:.0f} profiles, "
                         f"avg {fmt(row, 'avg_temperature', ' °C')}, down to {row['max_depth']:.0f} m")
    elif intent == "bgc_analysis":
        for _, row in df.iterrows():
            lines.append(f"- **{row['ocean_zone']}**: O₂ {fmt(row, 'avg_oxygen', ' µmol/kg', 1)}, "
                         f"chlorophyll {fmt(row, 'avg_chlorophyll', ' mg/m³', 3)}, "
                         f"nitrate {fmt(row, 'avg_nitrate', ' µmol/kg', 1)}, pH {fmt(row, 'avg_ph', '', 3)}")
    else:
        for _, row in df.head(10).iterrows():
            values = ", ".join(f"{col.replace('_', ' ')}: {val:.2f}" if isinstance(val, float)
                               else f"{col.replace('_', ' ')}: {val}" for col, val in row.items() if pd.notna(val))
            lines.append(f"- {values}")
    if len(df) > len(lines):
        lines.append(f"- *…and {len(df) - len(lines)} more rows (see the chart and table)*")
    return "\n".join(lines)


def _analytical_answer(question: str, agent: SqlAgent, chat) -> dict | None:
    result, error = agent.run(question)
    if error:
        return None
    df, intent = result["results"], result["intent"]
    insight = chat(
        f"Question: {question}\n\nSQL result (first rows):\n{df.head(15).to_string(index=False)}\n\n"
        "In 2-3 sentences, explain the main oceanographic pattern in this result.",
        system=SYSTEM_PROMPT,
    )
    answer = f"**{INTENT_TITLES.get(intent, 'Query results')}**\n\n{format_results_for_display(df, intent)}"
    if insight:
        answer += f"\n\n**What this means:** {insight}"
    return {
        "answer": answer,
        "query_type": "analytical",
        "context_documents": [result["sql_query"]],
        "retrieved_metadata": [{"query_type": "analytical", "intent": intent, "sql_query": result["sql_query"],
                                "row_count": int(len(df)), "columns": [str(c) for c in df.columns],
                                "summary_stats": result["summary_stats"]}],
        "sql_results": df_records(df.head(200)),
        "intent": intent,
        "llm_used": bool(insight) or intent == "custom",
    }


def _semantic_answer(question: str, engine: Engine, embedder, chat) -> dict:
    filters = parse_filters(question)
    vector = embedder.embed([question])[0]
    matches = search_profiles(engine, vector, filters)
    note = ""
    if not matches and filters:
        note = (f"No profiles were recorded {describe_filters(filters)} in this dataset, "
                "so these are the closest matches overall.\n\n")
        matches = search_profiles(engine, vector, {})
    if not matches:
        return {"answer": "I couldn't find any matching Argo profiles.", "query_type": "semantic",
                "context_documents": [], "retrieved_metadata": [], "intent": None, "llm_used": False}

    documents = [m["description"] for m in matches]
    metadata = [{k: v for k, v in m.items() if k not in ("description", "distance")} for m in matches]
    context = "\n".join(f"- {doc}" for doc in documents)
    answer = chat(f"Context:\n{context}\n\nQuestion: {question}", system=SYSTEM_PROMPT)
    llm_used = bool(answer)
    if not answer:
        scope = f" {describe_filters(filters)}" if filters and not note else ""
        bullets = "\n".join(f"- **Float {m['float_id']}**, cycle {m['cycle_number']} · {m['date']} · "
                            f"{format_position(m['lat'], m['lon'])} ({m['region']})" for m in metadata)
        answer = (f"Here are the {len(metadata)} Argo profiles{scope} most relevant to your question:\n\n"
                  f"{bullets}\n\nTop match: {documents[0]}")
    return {"answer": note + answer, "query_type": "semantic", "context_documents": documents,
            "retrieved_metadata": metadata, "intent": None, "llm_used": llm_used}


def answer_question(question: str, *, engine: Engine, embedder_factory: Callable, agent: SqlAgent, chat) -> dict:
    if agent.is_analytical_query(question):
        analytical = _analytical_answer(question, agent, chat)
        if analytical:
            return analytical
    return _semantic_answer(question, engine, embedder_factory(), chat)
```

- [ ] **Step 5: Write the database-backed tests**

`tests/integration/test_sql_agent_db.py`:
```python
import pytest

from floatchat.sql_agent import TEMPLATES, SqlAgent

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("intent", sorted(TEMPLATES))
def test_every_template_runs(reader_engine, intent):
    df, status = SqlAgent(reader_engine, chat=lambda *a, **k: None).execute_sql_query(TEMPLATES[intent])
    assert status == "success" and not df.empty


def test_custom_question_uses_llm_sql(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "```sql\nSELECT region, COUNT(*) AS n FROM profiles GROUP BY region\n```")
    result, error = agent.run("How many profiles were recorded?")
    assert error is None and result["intent"] == "custom" and "LIMIT 1000" in result["sql_query"]


def test_unsafe_llm_sql_is_refused(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "DELETE FROM profiles")
    result, error = agent.run("How many profiles were recorded?")
    assert result is None and "unsafe" in error


def test_no_llm_means_no_custom_sql(reader_engine):
    result, error = SqlAgent(reader_engine, chat=lambda *a, **k: None).run("How many profiles were recorded?")
    assert result is None and error == "Failed to generate SQL"
```

`tests/integration/test_answer_db.py`:
```python
import pytest

from floatchat.answer import answer_question
from floatchat.sql_agent import SqlAgent
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def ask(engine, question, chat=lambda *a, **k: None):
    return answer_question(question, engine=engine, embedder_factory=FakeEmbedder,
                           agent=SqlAgent(engine, chat=chat), chat=chat)


def test_analytical_answer(reader_engine):
    result = ask(reader_engine, "What is the average temperature at different depths?")
    assert result["query_type"] == "analytical" and result["intent"] == "avg_by_depth"
    assert result["answer"].startswith("**Average temperature and salinity at each depth**")
    assert result["sql_results"] and result["retrieved_metadata"][0]["row_count"] > 0
    assert result["llm_used"] is False


def test_semantic_answer_with_region_filter(reader_engine):
    result = ask(reader_engine, "Show me profiles in the Arabian Sea")
    assert result["query_type"] == "semantic"
    assert all(m["region"] == "Arabian Sea" for m in result["retrieved_metadata"])
    assert result["answer"].startswith("Here are the")


def test_semantic_answer_falls_back_when_filters_match_nothing(reader_engine):
    result = ask(reader_engine, "profiles in the Arabian Sea in December 2030")
    assert result["answer"].startswith("No profiles were recorded in the Arabian Sea in December 2030")
    assert result["retrieved_metadata"]


def test_llm_text_is_used_when_available(reader_engine):
    result = ask(reader_engine, "Show me profiles in the Arabian Sea", chat=lambda *a, **k: "MOCK ANSWER")
    assert result["answer"] == "MOCK ANSWER" and result["llm_used"] is True
```


- [ ] **Step 6: Run all new tests**

Run: `.venv/Scripts/python -m pytest tests/unit/test_sql_agent.py tests/unit/test_answer.py tests/integration/test_sql_agent_db.py tests/integration/test_answer_db.py -q`
Expected: `36 passed`

- [ ] **Step 7: Lint and commit**

Run: `.venv/Scripts/python -m ruff check floatchat tests`

```bash
git add floatchat/sql_agent.py floatchat/answer.py tests
git commit -m "Move SQL agent and answer building into the core package

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The FastAPI app with rate limits, LLM budget and caches; remove the old modules

**Files:**
- Create: `api/__init__.py`, `api/limits.py`, `api/cache.py`, `api/main.py`, `tests/unit/test_limits.py`, `tests/unit/test_cache.py`, `tests/integration/test_api.py`
- Modify: `app.py` (backend URL setting and health keys only)
- Delete: `main.py`, `nl_to_sql.py`, `export_utils.py`, `ocean_regions.py`, `llm.py`, `config.py`, `ingest.py`, `scripts/fetch_argo_data.py`, `render.yaml`, `tests/test_floatchat_core.py`

**Interfaces:**
- Consumes: everything in `floatchat/`.
- Produces: `api.limits.RateLimiter(per_minute, per_day, noun="requests", clock=time.time)` with `check(key) -> tuple[bool, str | None]`; `DailyBudget(limit, clock=time.time)` with `try_consume() -> bool` and property `exhausted`; `client_ip(request) -> str`. `api.cache.TTLCache(max_entries, ttl_seconds, clock=time.time)` with `get(key)`, `set(key, value)`, `clear()`; `normalize_question(q) -> str`. `api.main.create_app(engine=None, get_embedder_fn=get_embedder, chat_fn=llm.chat, query_limits=None, other_limit_per_minute=60, llm_budget=None) -> FastAPI`; module-level `app`.

- [ ] **Step 1: Write the failing unit tests**

`tests/unit/test_limits.py`:
```python
from api.limits import DailyBudget, RateLimiter


class Clock:
    def __init__(self, now=1_700_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_per_minute_limit_and_recovery():
    clock = Clock()
    limiter = RateLimiter(per_minute=2, per_day=None, noun="questions", clock=clock)
    assert limiter.check("a") == (True, None)
    assert limiter.check("a")[0]
    allowed, message = limiter.check("a")
    assert not allowed and "2 questions per minute" in message
    assert limiter.check("b")[0]  # other visitors are unaffected
    clock.now += 61
    assert limiter.check("a")[0]


def test_per_day_limit_resets_next_utc_day():
    clock = Clock(1_700_000_000.0)
    limiter = RateLimiter(per_minute=100, per_day=2, noun="questions", clock=clock)
    assert limiter.check("a")[0] and limiter.check("a")[0]
    allowed, message = limiter.check("a")
    assert not allowed and "2 questions per day" in message
    clock.now += 86_400
    assert limiter.check("a")[0]


def test_daily_budget():
    clock = Clock()
    budget = DailyBudget(2, clock=clock)
    assert budget.try_consume() and budget.try_consume()
    assert not budget.try_consume() and budget.exhausted
    clock.now += 86_400
    assert not budget.exhausted and budget.try_consume()
```

`tests/unit/test_cache.py`:
```python
from api.cache import TTLCache, normalize_question


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_ttl_expiry():
    clock = Clock()
    cache = TTLCache(max_entries=10, ttl_seconds=60, clock=clock)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}
    clock.now = 61
    assert cache.get("k") is None


def test_lru_eviction():
    cache = TTLCache(max_entries=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")
    cache.set("c", 3)
    assert cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3


def test_normalize_question():
    assert normalize_question("  What is the  average temperature?? ") == "what is the average temperature"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/unit/test_limits.py tests/unit/test_cache.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'api'`

- [ ] **Step 3: Implement `api/__init__.py`, `api/limits.py`, `api/cache.py`**

`api/__init__.py`:
```python
"""FloatChat HTTP API."""
```

`api/limits.py`:
```python
"""In-memory protection for the public demo (one API instance, so memory is enough)."""

import threading
import time
from collections import defaultdict, deque


def _utc_day(timestamp: float) -> int:
    return int(timestamp // 86_400)


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int | None, noun: str = "requests", clock=time.time):
        self.per_minute, self.per_day, self.noun = per_minute, per_day, noun
        self._clock = clock
        self._recent: dict[str, deque] = defaultdict(deque)
        self._daily: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, str | None]:
        now = self._clock()
        day = _utc_day(now)
        with self._lock:
            recent = self._recent[key]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= self.per_minute:
                return False, (f"Too many {self.noun}: the demo allows {self.per_minute} {self.noun} per minute. "
                               "Please wait a moment and try again.")
            if self.per_day is not None:
                counted_day, count = self._daily.get(key, (day, 0))
                if counted_day != day:
                    count = 0
                if count >= self.per_day:
                    return False, (f"Daily limit reached: the demo allows {self.per_day} {self.noun} per day "
                                   "per visitor. Please come back tomorrow.")
                self._daily[key] = (day, count + 1)
            recent.append(now)
            if len(self._recent) > 10_000:
                self._evict(now)
            return True, None

    def _evict(self, now: float) -> None:
        for key in [k for k, q in self._recent.items() if not q or now - q[-1] >= 60]:
            del self._recent[key]


class DailyBudget:
    """Caps LLM calls per UTC day; when it runs out, answers fall back to data-only mode."""

    def __init__(self, limit: int, clock=time.time):
        self.limit = limit
        self._clock = clock
        self._day = None
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        day = _utc_day(self._clock())
        if day != self._day:
            self._day, self._used = day, 0

    def try_consume(self) -> bool:
        with self._lock:
            self._roll()
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    @property
    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self._used >= self.limit
```

`api/cache.py`:
```python
import re
import threading
import time
from collections import OrderedDict


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower()).rstrip("?.! ")


class TTLCache:
    def __init__(self, max_entries: int, ttl_seconds: float, clock=time.time):
        self.max_entries, self.ttl = max_entries, ttl_seconds
        self._clock = clock
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored_at, value = item
            if self._clock() - stored_at >= self.ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key, value) -> None:
        with self._lock:
            self._items[key] = (self._clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
```

- [ ] **Step 4: Run unit tests**

Run: `.venv/Scripts/python -m pytest tests/unit/test_limits.py tests/unit/test_cache.py -q`
Expected: `6 passed`

- [ ] **Step 5: Write the failing API tests** (`tests/integration/test_api.py`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import create_app
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def make_client(engine, **kwargs):
    kwargs.setdefault("get_embedder_fn", FakeEmbedder)
    kwargs.setdefault("chat_fn", lambda *a, **k: None)
    return TestClient(create_app(engine=engine, **kwargs))


def ask(client, question, ip="1.1.1.1"):
    return client.post("/query", json={"query_text": question}, headers={"X-Forwarded-For": ip})


def test_ping_and_health(reader_engine):
    client = make_client(reader_engine)
    assert client.get("/ping").json() == {"ok": True}
    health = client.get("/health").json()
    assert health["status"] == "healthy" and health["database"] == "connected"
    assert health["vector_index"] == "ready" and health["indexed_profiles"] > 0
    assert health["llm"]["budget_exhausted"] is False and health["version"] == "3.0.0"


def test_stats_floats_and_profiles(reader_engine):
    client = make_client(reader_engine)
    assert client.get("/stats").json()["profiles"] > 0
    floats = client.get("/floats").json()
    track = client.get(f"/profiles/float/{floats[0]['float_id']}").json()
    assert track and track[0]["float_id"] == floats[0]["float_id"]
    assert client.get(f"/float/{floats[0]['float_id']}").json()["float_info"]["float_id"] == floats[0]["float_id"]
    assert client.get("/float/nope").json() == {"error": "Float not found"}
    profiles = client.post("/get_profiles", json={"profile_ids": [track[0]["profile_id"]]}).json()
    assert profiles and "chlorophyll" in profiles[0]


def test_query_analytical_and_semantic(reader_engine):
    client = make_client(reader_engine)
    analytical = ask(client, "What is the average temperature at different depths?").json()
    assert analytical["query_type"] == "analytical" and analytical["sql_results"]
    assert set(analytical) == {"answer", "query_type", "context_documents", "retrieved_metadata", "sql_results"}
    semantic = ask(client, "Show me profiles in the Arabian Sea").json()
    assert semantic["query_type"] == "semantic"
    assert all(m["region"] == "Arabian Sea" for m in semantic["retrieved_metadata"])


def test_query_validation(reader_engine):
    client = make_client(reader_engine)
    assert ask(client, "   ").status_code == 422
    assert ask(client, "x" * 301).status_code == 422


def test_rate_limit_per_ip(reader_engine):
    client = make_client(reader_engine, query_limits=(2, 100))
    assert ask(client, "Show me profiles in the Arabian Sea").status_code == 200
    assert ask(client, "Show me profiles in the Bay of Bengal").status_code == 200
    limited = ask(client, "Show me profiles near the equator")
    assert limited.status_code == 429 and limited.json()["error"] == "rate_limited"
    assert ask(client, "Show me profiles near the equator", ip="2.2.2.2").status_code == 200


def test_cache_and_query_log(reader_engine, loaded_db):
    client = make_client(reader_engine)
    first = ask(client, "Show me profiles in the Arabian Sea").json()
    second = ask(client, "show me profiles in the arabian sea?").json()
    assert first == second
    with loaded_db.connect() as conn:
        rows = conn.execute(text("SELECT cached, success FROM query_log ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [(False, True), (True, True)]


def test_llm_budget_falls_back_to_data_only(reader_engine):
    calls = []

    def chat(*a, **k):
        calls.append(1)
        return "MOCK ANSWER"

    client = make_client(reader_engine, chat_fn=chat, llm_budget=1)
    assert ask(client, "Show me profiles in the Arabian Sea").json()["answer"] == "MOCK ANSWER"
    fallback = ask(client, "Show me profiles in the Bay of Bengal").json()["answer"]
    assert fallback.startswith("Here are the") and len(calls) == 1
    assert client.get("/health").json()["llm"]["budget_exhausted"] is True


def test_exports(reader_engine):
    client = make_client(reader_engine)
    csv = client.post("/export", json={"format": "csv", "profile_ids": [1]})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert client.post("/export", json={"format": "csv", "profile_ids": list(range(51))}).status_code == 422
    assert client.post("/export", json={"format": "xlsx", "profile_ids": [1]}).status_code == 422
    assert client.post("/export", json={"format": "csv"}).status_code == 400


def test_cors_only_for_allowed_origins(reader_engine):
    client = make_client(reader_engine)
    ok = client.options("/stats", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/stats", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_unexpected_error_returns_friendly_answer(reader_engine, monkeypatch):
    import api.main

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(api.main, "answer_question", boom)
    result = ask(make_client(reader_engine), "Show me profiles in the Arabian Sea").json()
    assert result["query_type"] == "error" and "kaboom" not in result["answer"]
```

- [ ] **Step 6: Implement `api/main.py`**

```python
"""
FloatChat API: answers natural-language questions about Argo float data.

Statistical questions run as SQL; descriptive ones search profile embeddings
(pgvector). Public-demo protection: per-IP rate limits, a daily LLM budget,
and caches so repeated questions and dashboard calls stay cheap.
"""

import logging
import time
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StringConstraints

from api.cache import TTLCache, normalize_question
from api.limits import DailyBudget, RateLimiter, client_ip
from floatchat import __version__, config, llm
from floatchat.answer import answer_question
from floatchat.db import queries
from floatchat.db.engine import make_engine
from floatchat.embedder import get_embedder
from floatchat.exports import EXPORTERS
from floatchat.sql_agent import SqlAgent, sample_queries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("floatchat.api")

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
UNLIMITED_PATHS = {"/ping", "/health", "/docs", "/openapi.json", "/redoc"}
ERROR_ANSWER = "Something went wrong while answering that question. Please try rephrasing it."


class QueryRequest(BaseModel):
    query_text: Question


class QueryResponse(BaseModel):
    answer: str
    query_type: str
    context_documents: list[str]
    retrieved_metadata: list[dict]
    sql_results: list[dict] | None = None


class ProfileRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=5000)  # measurement ids -> whole profiles
    profile_ids: list[int] = Field(default_factory=list, max_length=200)


class ExportRequest(BaseModel):
    format: Literal["csv", "netcdf", "ascii"]
    data_ids: list[int] = Field(default_factory=list, max_length=5000)
    profile_ids: list[int] = Field(default_factory=list, max_length=50)


def create_app(engine=None, get_embedder_fn=get_embedder, chat_fn=llm.chat, query_limits=None,
               other_limit_per_minute: int = 60, llm_budget: int | None = None) -> FastAPI:
    engine = engine or make_engine(config.DATABASE_URL)
    per_minute, per_day = query_limits or (config.QUERY_LIMIT_PER_MINUTE, config.QUERY_LIMIT_PER_DAY)
    query_limiter = RateLimiter(per_minute, per_day, noun="questions")
    other_limiter = RateLimiter(other_limit_per_minute, None)
    budget = DailyBudget(config.LLM_DAILY_BUDGET if llm_budget is None else llm_budget)
    answers = TTLCache(max_entries=500, ttl_seconds=24 * 3600)
    dashboard = TTLCache(max_entries=16, ttl_seconds=600)
    status = TTLCache(max_entries=4, ttl_seconds=60)

    def budgeted_chat(*args, **kwargs):
        if not budget.try_consume():
            return None
        return chat_fn(*args, **kwargs)

    agent = SqlAgent(engine, chat=budgeted_chat)

    def cached(cache: TTLCache, key: str, compute):
        value = cache.get(key)
        if value is None:
            value = compute()
            cache.set(key, value)
        return value

    app = FastAPI(title="FloatChat API", version=__version__,
                  description="Ask questions about Argo ocean float data in plain English.")

    # Registered before CORS so CORS is the outer layer and 429 responses still carry CORS headers
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.method != "OPTIONS" and request.url.path not in UNLIMITED_PATHS:
            limiter = query_limiter if request.url.path == "/query" else other_limiter
            allowed, message = limiter.check(client_ip(request))
            if not allowed:
                return JSONResponse(status_code=429, content={"error": "rate_limited", "message": message})
        return await call_next(request)

    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/ping")
    def ping():
        """Keep-awake endpoint: never touches the database."""
        return {"ok": True}

    @app.get("/health")
    def health():
        try:
            data = cached(status, "data", lambda: queries.data_status(engine))
            database = "connected"
        except Exception as e:
            logger.warning("Health check database error: %s", e)
            data, database = {"measurements": 0, "indexed_profiles": 0, "newest_data": None}, "disconnected"
        llm_info = cached(status, "llm", llm.status)
        ready = database == "connected" and data["indexed_profiles"] > 0
        return {
            "status": "healthy" if ready else "degraded",
            "database": database,
            "measurements": data["measurements"],
            "vector_index": "ready" if data["indexed_profiles"] else "empty",
            "indexed_profiles": data["indexed_profiles"],
            "newest_data": data["newest_data"],
            "llm": {**llm_info, "budget_exhausted": budget.exhausted},
            "version": __version__,
        }

    @app.get("/stats")
    def stats():
        return cached(dashboard, "stats", lambda: queries.get_stats(engine))

    @app.get("/floats")
    def floats():
        return cached(dashboard, "floats", lambda: queries.get_floats(engine))

    @app.post("/query", response_model=QueryResponse)
    def query(request: QueryRequest):
        question = request.query_text
        started = time.perf_counter()
        try:
            run_id = cached(status, "data", lambda: queries.data_status(engine))["latest_run_id"]
        except Exception:
            run_id = 0
        key = f"{normalize_question(question)}|{run_id}"  # new data -> new key -> no stale answers
        result = answers.get(key)
        was_cached = result is not None
        if not was_cached:
            try:
                result = answer_question(question, engine=engine, embedder_factory=get_embedder_fn,
                                         agent=agent, chat=budgeted_chat)
            except Exception:
                logger.exception("Failed to answer %r", question)
                result = {"answer": ERROR_ANSWER, "query_type": "error", "context_documents": [],
                          "retrieved_metadata": [], "intent": None, "llm_used": False}
            if result["query_type"] != "error":
                answers.set(key, result)
        queries.log_query(engine, question=question, query_type=result["query_type"], intent=result.get("intent"),
                          latency_ms=int((time.perf_counter() - started) * 1000),
                          success=result["query_type"] != "error", cached=was_cached,
                          llm_used=bool(result.get("llm_used")) and not was_cached)
        return result

    @app.post("/get_profiles")
    def get_profiles(request: ProfileRequest):
        if not request.ids and not request.profile_ids:
            return []
        return queries.get_profiles(engine, request.ids, request.profile_ids)

    @app.get("/float/{float_id}")
    def get_float(float_id: str):
        return queries.get_float_info(engine, float_id) or {"error": "Float not found"}

    @app.get("/profiles/float/{float_id}")
    def get_float_profiles(float_id: str):
        return queries.get_float_profiles(engine, float_id)

    @app.post("/export")
    def export(request: ExportRequest):
        if not request.data_ids and not request.profile_ids:
            return JSONResponse(status_code=400, content={"error": "Choose at least one profile to export"})
        exporter, media_type, filename = EXPORTERS[request.format]
        content = exporter(engine, request.data_ids, request.profile_ids)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    @app.get("/sample-queries")
    def get_sample_queries():
        return sample_queries()

    return app


app = create_app()
```

- [ ] **Step 7: Run the API tests**

Run: `.venv/Scripts/python -m pytest tests/integration/test_api.py -q`
Expected: `10 passed`

- [ ] **Step 8: Remove the old modules and update `app.py`**

```bash
git rm -q main.py nl_to_sql.py export_utils.py ocean_regions.py llm.py config.py ingest.py scripts/fetch_argo_data.py render.yaml tests/test_floatchat_core.py
```

In `app.py`, replace the import `import config` with:
```python
import os

from dotenv import load_dotenv

load_dotenv()
```
and replace `API = config.BACKEND_URL.rstrip("/")` with:
```python
API = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
```
In `render_sidebar()`, replace:
```python
            row(health["chromadb"] == "connected", "Vector index", f"{health['indexed_profiles']:,} profiles")
```
with:
```python
            row(health["vector_index"] == "ready", "Vector index", f"{health['indexed_profiles']:,} profiles")
```

Run: `grep -rn "import config\|from nl_to_sql\|ocean_regions\|export_utils\|chromadb" --include=*.py . | grep -v "^./legacy\|^./.venv\|^./components\|^./tests/dashboard"`
Expected: no output.

- [ ] **Step 9: Run the whole suite and lint**

Run: `.venv/Scripts/python -m pytest -q` then `.venv/Scripts/python -m ruff check .`
Expected: all tests pass; `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add -A api tests app.py
git commit -m "Add hardened FastAPI app and remove the ChromaDB-era modules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Containers, local stack, refreshed snapshot and the memory check

**Files:**
- Create: `Dockerfile.api`, `scripts/container_check.sh`
- Modify: `Dockerfile` (Streamlit only), `docker-compose.yml`, `.dockerignore`, `.env.example`, `data/argo_profiles.csv.gz`, `data/profile_embeddings.npz`

**Interfaces:**
- Consumes: the pipeline CLI (Task 8) and the API (Task 11).
- Produces: image `floatchat-api` (port 8000 or `$PORT`); `scripts/container_check.sh <image> <reader-database-url>` exits non-zero if `/health` fails or memory exceeds 350 MB; compose services `db`, `backend`, `frontend`.

- [ ] **Step 1: Create `Dockerfile.api`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MODEL_DIR=/models/all-MiniLM-L6-v2

COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY floatchat/ floatchat/
# Bake the embedding model into the image so the API never downloads at runtime
RUN python -c "from pathlib import Path; from floatchat.embedder import ensure_model; ensure_model(Path('/models/all-MiniLM-L6-v2'))"

COPY api/ api/
COPY pipeline/ pipeline/
COPY data/ data/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
```

- [ ] **Step 2: Update the Streamlit `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements-frontend.txt .
RUN pip install -r requirements-frontend.txt

COPY app.py .
COPY .streamlit/ .streamlit/

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

- [ ] **Step 3: Update `.dockerignore`**

```
.git
.venv
venv
.env
chroma_db
**/__pycache__
.pytest_cache
.ruff_cache
.claude
legacy
tests
docs
components
styles
utils
```

- [ ] **Step 4: Update `docker-compose.yml`**

```yaml
# One-command local stack: docker compose up --build
# App: http://localhost:8501   API docs: http://localhost:8000/docs
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: argo
      POSTGRES_USER: floatchat
      POSTGRES_PASSWORD: floatchat
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U floatchat -d argo"]
      interval: 3s
      timeout: 3s
      retries: 20

  backend:
    build:
      context: .
      dockerfile: Dockerfile.api
    command: >
      sh -c "python -m pipeline snapshot --if-empty &&
             python -m pipeline create-reader &&
             uvicorn api.main:app --host 0.0.0.0 --port 8000"
    env_file:
      - path: .env
        required: false
    environment:
      ADMIN_DATABASE_URL: postgresql+psycopg://floatchat:floatchat@db:5432/argo
      DATABASE_URL: postgresql+psycopg://floatchat_reader:local-reader-password@db:5432/argo
      READER_PASSWORD: local-reader-password
      ALLOWED_ORIGINS: http://localhost:8501,http://localhost:3000
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: .
    environment:
      BACKEND_URL: http://backend:8000
    ports:
      - "8501:8501"
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 5: Update `.env.example`**

```
# Copy to .env and adjust. Docker Compose sets the database URLs itself.

# Database (local, outside Docker). The API uses the read-only role; the pipeline uses the owner.
DATABASE_URL=postgresql+psycopg://floatchat_reader:local-reader-password@localhost:5433/argo
ADMIN_DATABASE_URL=postgresql+psycopg://floatchat:floatchat@localhost:5433/argo
READER_PASSWORD=local-reader-password

# LLM: any OpenAI-compatible chat completions endpoint.
# A hosted (https) endpoint without an API key counts as "not configured" (data-only answers).
# Groq (free key at https://console.groq.com/keys):
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=
#   Ollama on your machine:        LLM_BASE_URL=http://localhost:11434/v1   LLM_MODEL=qwen2.5:3b
#   Ollama, API running in Docker: LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_TIMEOUT=60
LLM_DAILY_BUDGET=2000

# Public demo protection
QUERY_LIMIT_PER_MINUTE=10
QUERY_LIMIT_PER_DAY=100
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8501

# Where the Streamlit frontend finds the API
BACKEND_URL=http://127.0.0.1:8000
```

- [ ] **Step 6: Create `scripts/container_check.sh`**

```bash
#!/usr/bin/env bash
# Start the API image, fire 20 questions, and fail if memory exceeds the Koyeb budget.
# Usage: scripts/container_check.sh <image> <reader-database-url>
set -euo pipefail
IMAGE="$1"
DATABASE_URL="$2"
NAME=floatchat-api-check
LIMIT_MB=350

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network host -e DATABASE_URL="$DATABASE_URL" \
  -e QUERY_LIMIT_PER_MINUTE=1000 -e QUERY_LIMIT_PER_DAY=1000 "$IMAGE" >/dev/null
trap 'docker logs "$NAME" | tail -30; docker rm -f "$NAME" >/dev/null' EXIT

for _ in $(seq 1 60); do curl -sf localhost:8000/ping >/dev/null && break; sleep 1; done
curl -sf localhost:8000/health | tee /dev/stderr | grep -q '"status":"healthy"'

QUESTIONS=("What is the average temperature at different depths?"
           "Show me profiles in the Arabian Sea"
           "Compare surface temperature across ocean regions"
           "Which floats measured low oxygen?")
for i in $(seq 0 19); do
  q="${QUESTIONS[$((i % 4))]} $i"
  curl -sf -X POST localhost:8000/query -H 'Content-Type: application/json' \
    -d "{\"query_text\": \"$q\"}" >/dev/null
done

usage=$(docker stats --no-stream --format '{{.MemUsage}}' "$NAME" | cut -d/ -f1 | tr -d ' ')
mb=$(python3 -c "
import re, sys
value = sys.argv[1]
number = float(re.match(r'[\d.]+', value).group())
unit = value[len(re.match(r'[\d.]+', value).group()):]
print(int(number * {'B': 1e-6, 'kB': 1e-3, 'KiB': 1.024e-3, 'MB': 1, 'MiB': 1.048576, 'GB': 1000, 'GiB': 1073.741824}[unit]))
" "$usage")
echo "API memory after 20 questions: ${mb} MB (limit ${LIMIT_MB} MB)"
[ "$mb" -le "$LIMIT_MB" ]
```

Run: `chmod +x scripts/container_check.sh` (Git Bash on Windows: `git update-index --chmod=+x scripts/container_check.sh` after adding).

- [ ] **Step 7: Regenerate the bundled snapshot with the new variables** (real ERDDAP data; ~20 minutes, run in the background)

Run: `.venv/Scripts/python -m pipeline fetch --start 2024-01-01 --end 2024-04-01 --out data/argo_profiles.csv.gz`
Expected: ends with `Saved ~88,000 rows / ~3,900 profiles to data/argo_profiles.csv.gz`. Then check the new columns:

Run: `.venv/Scripts/python -c "import pandas as pd; d=pd.read_csv('data/argo_profiles.csv.gz'); print(d.notna().sum()[['oxygen','chlorophyll','nitrate','ph']])"`
Expected: non-zero counts for all four.

- [ ] **Step 8: Rebuild the embedding cache and verify the full stack**

```bash
docker compose down -v
docker compose up -d db
ADMIN_DATABASE_URL=postgresql+psycopg://floatchat:floatchat@localhost:5433/argo .venv/Scripts/python -m pipeline snapshot --reset
```
Expected: `snapshot: ~3900 profiles added, 0 removed` and an updated `data/profile_embeddings.npz` (a few minutes: every description is new).

```bash
docker compose up -d --build
docker compose logs backend | tail -5
curl -s localhost:8000/health
```
Expected: logs show `Data already loaded - skipping snapshot.` then `Reader role ready.` and Uvicorn running; `/health` returns `"status":"healthy"` and `"vector_index":"ready"`. Open http://localhost:8501 and ask "Average chlorophyll by ocean zone" and "Show me profiles in the Arabian Sea": both answer, with charts.

- [ ] **Step 9: Run the memory check locally**

Run: `bash scripts/container_check.sh floatchat-backend postgresql+psycopg://floatchat_reader:local-reader-password@localhost:5433/argo`
Expected: last line `API memory after 20 questions: <N> MB (limit 350 MB)` with N ≤ 350, exit code 0. (Docker Desktop on Windows does not support `--network host` the same way as Linux; if the script cannot reach the container locally, rely on the CI run in Task 13 and record N from there.)

- [ ] **Step 10: Commit**

```bash
git add Dockerfile Dockerfile.api .dockerignore docker-compose.yml .env.example scripts/container_check.sh data/
git commit -m "Add API container, pgvector compose stack and refreshed snapshot with BGC data

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: GitHub Actions: CI, daily refresh and backfill

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/refresh.yml`, `.github/workflows/backfill.yml`

**Interfaces:**
- Consumes: `python -m pipeline` CLI, `scripts/container_check.sh`, the pytest markers.
- Produces: workflows `CI`, `Daily data refresh`, `Backfill data`. Secret used: `NEON_ADMIN_URL`.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: floatchat
          POSTGRES_PASSWORD: floatchat
          POSTGRES_DB: floatchat_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U floatchat"
          --health-interval 5s
          --health-retries 20
    env:
      TEST_ADMIN_DATABASE_URL: postgresql+psycopg://floatchat:floatchat@localhost:5433/floatchat_test
      FLOATCHAT_REQUIRE_DB: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements-*.txt
      - uses: actions/cache@v4
        with:
          path: ~/.cache/floatchat
          key: minilm-onnx-v1
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -q

  container:
    needs: test
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: floatchat
          POSTGRES_PASSWORD: floatchat
          POSTGRES_DB: argo
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U floatchat"
          --health-interval 5s
          --health-retries 20
    env:
      ADMIN_DATABASE_URL: postgresql+psycopg://floatchat:floatchat@localhost:5433/argo
      READER_PASSWORD: ci-reader-password
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements-*.txt
      - uses: actions/cache@v4
        with:
          path: ~/.cache/floatchat
          key: minilm-onnx-v1
      - run: pip install -r requirements-api.txt
      - name: Load the small fixture and create the reader role
        run: |
          python -m pipeline snapshot --path tests/fixtures/seed_small.csv.gz --reset
          python -m pipeline create-reader
      - run: docker build -f Dockerfile.api -t floatchat-api .
      - run: bash scripts/container_check.sh floatchat-api postgresql+psycopg://floatchat_reader:ci-reader-password@localhost:5433/argo
```

- [ ] **Step 2: Create `.github/workflows/refresh.yml`**

```yaml
name: Daily data refresh

on:
  schedule:
    - cron: "0 2 * * *"   # 02:00 UTC every day
  workflow_dispatch:
    inputs:
      days:
        description: "How many recent days to fetch"
        default: "10"

permissions:
  contents: read
  actions: write   # needed to keep this scheduled workflow enabled

jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements-api.txt
      - uses: actions/cache@v4
        with:
          path: ~/.cache/floatchat
          key: minilm-onnx-v1
      - run: pip install -r requirements-api.txt
      - name: Fetch new profiles and prune old ones
        env:
          ADMIN_DATABASE_URL: ${{ secrets.NEON_ADMIN_URL }}
        run: python -m pipeline refresh --days "${{ github.event.inputs.days || '10' }}"
      - name: Keep this schedule from being auto-disabled after 60 days
        if: always()
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh workflow enable refresh.yml --repo "${{ github.repository }}"
```

- [ ] **Step 3: Create `.github/workflows/backfill.yml`**

```yaml
name: Backfill data

on:
  workflow_dispatch:
    inputs:
      start:
        description: "Start date YYYY-MM-DD (blank = 365 days ago)"
        required: false
      end:
        description: "End date YYYY-MM-DD (blank = today)"
        required: false
      reset:
        description: "Drop all tables first (type 'yes' to confirm)"
        default: "no"

jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 300
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements-api.txt
      - uses: actions/cache@v4
        with:
          path: ~/.cache/floatchat
          key: minilm-onnx-v1
      - run: pip install -r requirements-api.txt
      - name: Backfill
        env:
          ADMIN_DATABASE_URL: ${{ secrets.NEON_ADMIN_URL }}
          START: ${{ github.event.inputs.start }}
          END: ${{ github.event.inputs.end }}
          RESET: ${{ github.event.inputs.reset }}
        run: |
          args=()
          [ -n "$START" ] && args+=(--start "$START")
          [ -n "$END" ] && args+=(--end "$END")
          [ "$RESET" = "yes" ] && args+=(--reset)
          python -m pipeline backfill "${args[@]}"
```

- [ ] **Step 4: Validate the YAML locally**

Run: `.venv/Scripts/python -c "import yaml, glob; [yaml.safe_load(open(p)) for p in glob.glob('.github/workflows/*.yml')]; print('ok')"` (install with `pip install pyyaml` if missing; it is not a project dependency)
Expected: `ok`

- [ ] **Step 5: Commit and push the branch to run CI**

```bash
git add .github/workflows
git commit -m "Add CI, daily refresh and backfill workflows

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin phase1-foundation
```

Run: `gh run watch --repo CodexManvik/FloatChat-AI $(gh run list --repo CodexManvik/FloatChat-AI --branch phase1-foundation --workflow CI --limit 1 --json databaseId -q '.[0].databaseId')`
Expected: both `test` and `container` jobs succeed; the container job prints `API memory after 20 questions: <N> MB (limit 350 MB)`. If a job fails, read its log with `gh run view --log-failed`, fix, commit, and push again.

---

### Task 14: Smoke test script, DEPLOY.md and README updates

**Files:**
- Create: `scripts/smoke_test.py`, `DEPLOY.md`
- Modify: `readme.md` (the "How it's built" and "Run it on your machine" sections)

**Interfaces:**
- Consumes: the API endpoints.
- Produces: `python scripts/smoke_test.py <api-url>` (exit 0 when all checks pass).

- [ ] **Step 1: Create `scripts/smoke_test.py`**

```python
"""
Ask a deployed FloatChat API five real questions and report answers and timings.

    python scripts/smoke_test.py https://floatchat-api-<name>.koyeb.app
"""

import sys
import time

import requests

QUESTIONS = [
    "What is the average temperature at different depths?",
    "Compare surface temperature across ocean regions",
    "Average dissolved oxygen by ocean zone",
    "Show me salinity profiles near the equator",
    "Which floats measured low oxygen in the Arabian Sea?",
]
SLOW_SECONDS = 20


def main(base_url: str) -> int:
    base_url = base_url.rstrip("/")
    failures = 0
    ping = requests.get(f"{base_url}/ping", timeout=60)
    print(f"/ping -> {ping.status_code} {ping.json()}")
    health = requests.get(f"{base_url}/health", timeout=60).json()
    print(f"/health -> {health['status']}, {health['indexed_profiles']} profiles, newest {health['newest_data']}, "
          f"LLM configured={health['llm']['configured']} reachable={health['llm']['reachable']}")
    if health["status"] != "healthy":
        failures += 1
    for question in QUESTIONS:
        started = time.perf_counter()
        resp = requests.post(f"{base_url}/query", json={"query_text": question}, timeout=120)
        seconds = time.perf_counter() - started
        ok = resp.status_code == 200 and resp.json().get("query_type") in ("analytical", "semantic")
        failures += (not ok) or seconds > SLOW_SECONDS
        summary = resp.json().get("answer", resp.text)[:110].replace("\n", " ") if resp.ok else resp.text[:110]
        print(f"{'OK ' if ok else 'ERR'} {seconds:5.1f}s [{resp.json().get('query_type', '-') if resp.ok else resp.status_code}] "
              f"{question}\n      {summary}")
    print("All checks passed." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
```

Run: `.venv/Scripts/python scripts/smoke_test.py http://localhost:8000` (with the compose stack from Task 12 running)
Expected: five `OK` lines and `All checks passed.`

- [ ] **Step 2: Create `DEPLOY.md`**

````markdown
# Deploying FloatChat

FloatChat's live demo runs entirely on free tiers:

| Piece | Service | Why |
|---|---|---|
| Database (Postgres + pgvector) | [Neon](https://neon.com) free plan | 1 GB storage; suspends when idle |
| API (FastAPI container) | [Koyeb](https://www.koyeb.com) free instance | 512 MB / 0.1 vCPU; sleeps after 1 h idle |
| Keep-awake ping | [cron-job.org](https://cron-job.org) | calls `/ping` every 30 min |
| Data loading | GitHub Actions | backfill once, refresh daily at 02:00 UTC |
| LLM | [Groq](https://console.groq.com) | free API key |

You create every account and paste every secret yourself. Nothing secret goes in the repo.

## 1. Neon: database and roles

1. Sign up at neon.com and create a project named `floatchat`, **Postgres 16**, in the region you will
   also use on Koyeb (**Frankfurt** or **Washington, D.C.**).
2. On the project dashboard, open **Connect**, choose the `neondb` database and the owner role, and copy the
   connection string. This is the **admin URL**. It looks like
   `postgresql://neondb_owner:...@ep-...-pooler.<region>.aws.neon.tech/neondb?sslmode=require`.
3. Pick a strong password for the read-only API role (e.g. 24+ random characters) and keep it handy.
4. On your machine, in the repo folder, create the schema and the reader role:

   ```bash
   ADMIN_DATABASE_URL='<admin URL>' READER_PASSWORD='<reader password>' python -m pipeline create-reader
   ```

   Expected: `Reader role ready.`
5. Build the **reader URL**: the admin URL with `neondb_owner:<owner password>` replaced by
   `floatchat_reader:<reader password>`.

## 2. GitHub: secret and first data load

1. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
   name `NEON_ADMIN_URL`, value = the admin URL.
2. **Actions → Backfill data → Run workflow** (leave the inputs blank). It loads the last 365 days
   (about 30–60 minutes). Expected last log line: `backfill: <N> profiles added, 0 removed`.
3. **Actions → Daily data refresh** runs every day at 02:00 UTC. Run it once by hand to check it works.

## 3. Koyeb: the API

1. Sign up at koyeb.com and create a **Web Service** from **GitHub**, selecting this repository and the
   `main` branch.
2. Builder: **Dockerfile**, path `Dockerfile.api`. Instance: **Free**. Region: the same as Neon.
3. Port: `8000`, protocol HTTP, public route `/`. Health check: HTTP `GET /ping`.
4. Environment variables (mark the database URL and key as **Secret**):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the **reader URL** |
   | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
   | `LLM_MODEL` | `llama-3.3-70b-versatile` (or any current Groq chat model) |
   | `LLM_API_KEY` | your Groq key |
   | `LLM_DAILY_BUDGET` | `2000` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now; add the Vercel URL in Phase 3 |

5. Deploy. When it is healthy, note the public URL, e.g. `https://floatchat-api-<name>.koyeb.app`.
6. Check it:

   ```bash
   python scripts/smoke_test.py https://floatchat-api-<name>.koyeb.app
   ```

   Expected: `All checks passed.`

## 4. cron-job.org: keep the API awake

1. Sign up at cron-job.org and create a cron job:
   - URL: `https://floatchat-api-<name>.koyeb.app/ping`
   - Schedule: every 30 minutes
2. `/ping` never touches the database, so Neon still suspends between real visits.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Koyeb build runs out of memory | Builds run on Koyeb's builders, not the free instance; retry. If it repeats, check the build log for a failing `pip install` |
| `/health` says `"database": "disconnected"` | Check `DATABASE_URL` uses `floatchat_reader` and the right password, and keeps `?sslmode=require` |
| `/health` says `"vector_index": "empty"` | The backfill has not run yet or failed: check **Actions → Backfill data** |
| LLM shows *missing or invalid LLM_API_KEY* | Re-paste the Groq key in Koyeb and redeploy |
| Daily refresh failed | Usually ERDDAP being slow or down; the site keeps serving the previous data. Re-run the workflow later |
| Koyeb's free tier changes | The API is a plain Docker image: Render (free, sleeps after 15 min) or any Docker host works with the same environment variables |
````

- [ ] **Step 3: Update `readme.md`**

In section **"## 🏗️ How it's built"**, replace the architecture diagram with:

````markdown
```
 ┌─────────────┐  HTTP  ┌──────────────── API (FastAPI on Koyeb) ─────────────────┐
 │  Streamlit  │ ─────► │ POST /query ─► statistical? ─ yes ─► SQL agent ─► Postgres │
 │  (app.py)   │ ◄───── │                └─ no ─► pgvector search (+ filters)        │
 └─────────────┘  JSON  │                         └─► LLM (Groq) writes the answer   │
                        │ rate limits · LLM budget · answer cache · query log        │
                        └──────────────────────────────▲─────────────────────────────┘
                                                       │ read-only role
   GitHub Actions (daily) ─► ERDDAP ─► pipeline ─► Neon Postgres + pgvector
```
````

Replace the table under **"### 1. Data pipeline"** with:

```markdown
| Component | What it does |
|---|---|
| `pipeline/erddap.py` | Downloads profiles from Ifremer ERDDAP in 5-day windows with retries: temperature and salinity from core floats; oxygen, chlorophyll, nitrate and pH from BGC floats. Keeps only quality-controlled values (Argo QC flags 1–2). |
| `pipeline/shape.py` | Interpolates every profile onto 24 standard depths (5–2,000 m), labels its region and notes which sensors it has. |
| `pipeline/describe.py` | Writes a plain-English description of each profile; these sentences are what search runs on. |
| `pipeline/load.py` | Inserts only new profiles (bulk `COPY`), embeds their descriptions, removes data older than 12 months, and records every run. |
| `python -m pipeline …` | `backfill` (last 12 months), `refresh` (last 10 days, run daily by GitHub Actions), `snapshot` (the bundled offline data), `fetch`, `create-reader`. |
| `data/` | A bundled 3-month snapshot plus precomputed embeddings, so local setup needs no network. |
```

Replace **"### 2. Storage"** with:

```markdown
### 2. Storage

One **PostgreSQL** database with the **pgvector** extension (Neon in production):

- `floats`, `profiles`, `measurements` hold the data. Each profile row also stores its description and a
  384-number embedding, so search is one SQL query combining filters and vector similarity.
- `ingest_runs` records every data load (it feeds "updated N hours ago"); `query_log` records questions
  (no personal data).
- The API connects as **`floatchat_reader`**: it can only read data and append to `query_log`, and every
  statement is stopped after 5 seconds. Even an LLM-written query can't change anything.
```

In **"### 3. Backend"**, add these rows to the endpoint table:

```markdown
| `GET /ping` | Keep-awake check that never touches the database. |
```

and replace the "Supporting modules" table with:

```markdown
| Component | What it does |
|---|---|
| `floatchat/sql_agent.py` | Decides if a question is statistical and which kind; runs vetted SQL templates or LLM-written SQL after a read-only check. |
| `floatchat/search.py` | pgvector similarity search with region, month, year and sensor filters. |
| `floatchat/answer.py` | Turns SQL rows or matching profiles into the answer, with an LLM explanation when available. |
| `floatchat/embedder.py` | all-MiniLM-L6-v2 (ONNX), padded per batch so a question embeds in milliseconds. |
| `floatchat/llm.py` | Client for any OpenAI-compatible API (Groq, OpenAI, Ollama, …), with a data-only fallback. |
| `api/` | FastAPI app: per-visitor rate limits, a daily LLM budget, answer caching, CORS and the query log. |
```

In **"### Option B: without Docker"**, replace the command block with:

```bash
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db                # Postgres + pgvector on port 5433

python -m pipeline snapshot            # load the bundled data (~30 s)
python -m pipeline create-reader       # the API's read-only role (password from READER_PASSWORD)
uvicorn api.main:app --port 8000       # terminal 1: API
streamlit run app.py                   # terminal 2: frontend → http://localhost:8501
```

and replace `Run the tests with …` with: ``Run the tests with `pytest` (integration tests use the `db` container; they are skipped if it isn't running).``

Add a new section before **"## 💬 Using FloatChat"**:

```markdown
### Deploying your own copy

See [DEPLOY.md](DEPLOY.md): Neon (database), Koyeb (API), GitHub Actions (daily data), cron-job.org
(keep-awake) and Groq (LLM), all on free tiers.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke_test.py DEPLOY.md readme.md
git commit -m "Add smoke test, deployment guide and README updates for the new stack

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 15: Deploy with the user and verify the done criteria

This task is done together with the user, who creates the accounts and enters every secret. The agent gives one step at a time from `DEPLOY.md`, waits for the user to confirm, and verifies results with read-only checks.

**Files:**
- Modify: `readme.md` (add the live API URL), `docs/superpowers/specs/2026-11-08-phase1-foundation-live-api-design.md` (tick the done criteria)

- [ ] **Step 1: Merge the branch**

Open a pull request from `phase1-foundation` to `main` (`gh pr create`), wait for CI to pass, and merge it with the user's approval. Koyeb deploys from `main`.

- [ ] **Step 2: Neon (user)**

Walk the user through DEPLOY.md section 1. Verify with the user's admin URL in their own terminal (the agent never sees or types the password):

Run (user): `ADMIN_DATABASE_URL='<admin URL>' READER_PASSWORD='<reader password>' python -m pipeline create-reader`
Expected: `Reader role ready.`

- [ ] **Step 3: GitHub secret and backfill (user, then agent checks)**

The user adds `NEON_ADMIN_URL` and starts **Backfill data**. Then:

Run: `gh run watch --repo CodexManvik/FloatChat-AI $(gh run list --repo CodexManvik/FloatChat-AI --workflow "Backfill data" --limit 1 --json databaseId -q '.[0].databaseId')`
Expected: success; log shows `backfill: <N> profiles added` with N roughly 12,000–16,000.

- [ ] **Step 4: Koyeb (user)**

Walk the user through DEPLOY.md section 3. When the service is healthy:

Run: `.venv/Scripts/python scripts/smoke_test.py https://<koyeb-url>`
Expected: `All checks passed.`; `/health` shows `LLM configured=True reachable=True`.

- [ ] **Step 5: Live protection checks**

Run:
```bash
for i in $(seq 1 11); do curl -s -o /dev/null -w "%{http_code} " -X POST https://<koyeb-url>/query -H 'Content-Type: application/json' -d '{"query_text":"Show me profiles in the Arabian Sea"}'; done; echo
```
Expected: ten `200` then `429` (the 11th within a minute). Asking the same question twice returns the second answer noticeably faster (cache).

- [ ] **Step 6: Keep-awake and daily refresh (user, then agent checks next day)**

The user creates the cron-job.org job (DEPLOY.md section 4) and runs **Daily data refresh** once by hand. After the next scheduled 02:00 UTC run:

Run: `gh run list --repo CodexManvik/FloatChat-AI --workflow "Daily data refresh" --limit 3`
Expected: the scheduled run succeeded. `/stats` → `last_updated` is from that run.

- [ ] **Step 7: Memory on Koyeb**

Ask the user to open the Koyeb service's **Metrics** tab after the smoke test. Expected: memory below ~350 MB.

- [ ] **Step 8: Record the result**

Add the live API URL to `readme.md` under the title (e.g. `**Live API:** https://<koyeb-url>/docs`), tick the done criteria in the spec, then:

```bash
git add readme.md docs/superpowers/specs/2026-11-08-phase1-foundation-live-api-design.md
git commit -m "Record Phase 1 deployment

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```
