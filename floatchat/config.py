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
# Shared secret that lets a trusted server-side frontend (the Streamlit app) pass each visitor's IP for rate limiting
FRONTEND_TOKEN = os.getenv("FRONTEND_TOKEN", "")
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
