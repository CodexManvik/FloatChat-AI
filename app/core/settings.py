import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
GEN_MODEL = os.getenv("GEN_MODEL", "gemma2:2bs")
EMB_MODEL = os.getenv("EMB_MODEL", "nomic-embed-text")

CHROMA_DIR = os.getenv("CHROMA_DIR", "data/chroma")
COLLECTION = os.getenv("COLLECTION", "incois_oon")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("TOP_K", "8"))
