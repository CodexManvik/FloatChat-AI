"""
Configuration for FloatChat
Supports both local development and cloud deployment
"""

import os
from urllib.parse import quote_plus

# Database Configuration
DB_PASSWORD = os.getenv("DB_PASSWORD", "Arcombad1030")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql+psycopg2://postgres:{quote_plus(DB_PASSWORD)}@localhost:5432/argo")

# LLM and Embedding Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface")  # Options: huggingface, ollama
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # Hugging Face model ID for Qwen
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Ollama Configuration (fallback)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# ChromaDB Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
VECTOR_STORE = os.getenv("VECTOR_STORE", "persistent")  # Options: persistent, memory

# Backend URL for frontend
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Data Processing Limits
MAX_FLOATS = int(os.getenv("MAX_FLOATS", "1000"))  # Increased for virtual floats from nc data
MAX_DOCUMENTS = int(os.getenv("MAX_DOCUMENTS", "30000"))  # Limited to 30k as requested
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))

