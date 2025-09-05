from pathlib import Path
import sqlite3
from typing import List
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from app.core import settings
from tqdm import tqdm


def load_db_files(db_dir: str) -> List[Document]:
    """
    Load all .db files from a directory and convert table rows to LangChain Documents.
    """
    docs = []
    db_path = Path(db_dir).resolve()

    for db_file in db_path.rglob("*.db"):
        print(f"📂 Loading DB: {db_file.name}")
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"SELECT * FROM {table};")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            for row in rows:
                content = ", ".join(f"{col}: {val}" for col, val in zip(columns, row))
                metadata = {"source": str(db_file), "table": table}
                docs.append(Document(page_content=content, metadata=metadata))

        conn.close()
    print(f"✅ Loaded {len(docs)} documents from .db files")
    return docs


def run_ingestion(db_dir: str = "data/raw/argo") -> dict:
    """
    Ingest .db files directly into Chroma vectorstore.
    """
    docs = load_db_files(db_dir)
    if not docs:
        return {"status": "error", "details": f"No documents found in {db_dir}"}

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    if not chunks:
        return {"status": "error", "details": "No chunks created from documents."}

    print(f"✅ Split into {len(chunks)} chunks")

    # Initialize embeddings
    embeddings = OllamaEmbeddings(model=settings.EMB_MODEL, base_url=settings.OLLAMA_URL)

    # Test embedding on first chunk
    test_vector = embeddings.embed_documents([chunks[0].page_content])
    if not test_vector or len(test_vector[0]) == 0:
        return {"status": "error", "details": "Embeddings returned empty vector. Check your Ollama model."}

    # Initialize Chroma vectorstore
    vs = Chroma(
        collection_name=settings.COLLECTION,
        persist_directory=str(settings.CHROMA_DIR),
        embedding_function=embeddings
    )

    # Batch ingestion
    BATCH_SIZE = 500  # optimized for your laptop
    print(f"🚀 Starting ingestion in batches of {BATCH_SIZE}...")
    for i in tqdm(range(0, len(chunks), BATCH_SIZE)):
        vs.add_documents(chunks[i:i+BATCH_SIZE])

    print(f"🎉 Ingestion complete: {len(chunks)} chunks added to Chroma")
    return {"status": "ingested", "added_chunks": len(chunks)}


if __name__ == "__main__":
    run_ingestion()
