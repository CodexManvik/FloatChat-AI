import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ------------------------------
# Ollama / LLM settings
# ------------------------------
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
GEN_MODEL: str = os.getenv("GEN_MODEL", "gemma2:2b")        # Model for text generation
EMB_MODEL: str = os.getenv("EMB_MODEL", "nomic-embed-text")  # Model for embeddings

# ------------------------------
# Chroma / Vectorstore settings
# ------------------------------
CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", "data/chroma"))
COLLECTION: str = os.getenv("COLLECTION", "incois_oon")

# Ensure the Chroma directory exists
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Document splitting / RAG settings
# ------------------------------
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 1200))         # Number of characters per chunk
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 200))    # Overlap between chunks
TOP_K: int = int(os.getenv("TOP_K", 8))                      # Number of top documents to retrieve

# ------------------------------
# Optional: Logging / Debug
# ------------------------------
DEBUG: bool = os.getenv("DEBUG", "True").lower() in ["true", "1", "yes"]

if DEBUG:
    print("⚡ FloatChat Settings Loaded")
    print(f"OLLAMA_URL: {OLLAMA_URL}")
    print(f"GEN_MODEL: {GEN_MODEL}")
    print(f"EMB_MODEL: {EMB_MODEL}")
    print(f"CHROMA_DIR: {CHROMA_DIR.resolve()}")
    print(f"COLLECTION: {COLLECTION}")
    print(f"CHUNK_SIZE: {CHUNK_SIZE}, CHUNK_OVERLAP: {CHUNK_OVERLAP}, TOP_K: {TOP_K}")
