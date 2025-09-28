"""
Simple configuration for FloatChat
Local development focused
"""

from urllib.parse import quote_plus

# Database Configuration
DB_PASSWORD = "Manvik@2005"
DATABASE_URL = f"postgresql+psycopg2://postgres:{quote_plus(DB_PASSWORD)}@localhost:5432/argo"

# Ollama Configuration
OLLAMA_HOST = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "phi3:mini"

# ChromaDB Configuration
CHROMA_PATH = "./chroma_db"

# Data Processing Limits
MAX_FLOATS = 50
MAX_DOCUMENTS = 50000
BATCH_SIZE = 1000