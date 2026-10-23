"""
Configuration for FloatChat
All settings come from environment variables (or a local .env file).
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
# Default matches the Postgres container in docker-compose.yml
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://floatchat:floatchat@localhost:5433/argo")
# Hosted Postgres providers (Render, Heroku, ...) hand out postgres:// URLs
for prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix):]

# LLM Configuration
# Any OpenAI-compatible chat completions endpoint works (Ollama, LM Studio, vLLM,
# llama.cpp server, OpenAI, Groq, ...). Leave LLM_BASE_URL empty to run without
# an LLM: FloatChat then answers with data-driven summaries only.
#   Groq example:   LLM_BASE_URL=https://api.groq.com/openai/v1  LLM_MODEL=llama-3.3-70b-versatile  LLM_API_KEY=gsk_...
#   Ollama example: LLM_BASE_URL=http://localhost:11434/v1  LLM_MODEL=qwen2.5:3b
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

# ChromaDB Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "argo_profiles")

# Backend URL for frontend
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Seed data used by ingest.py
SEED_DATA_PATH = os.getenv("SEED_DATA_PATH", "./data/argo_profiles.csv.gz")
# Precomputed embeddings for the seed profiles (rebuilt automatically when descriptions change)
EMBEDDING_CACHE_PATH = os.getenv("EMBEDDING_CACHE_PATH", "./data/profile_embeddings.npz")
