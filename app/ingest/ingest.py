from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.document_loaders import CSVLoader
from app.core import settings
import os
print("Current working directory:", os.getcwd())


def load_local_tree(data_dir: str):
    """
    Load all CSV files from the folder recursively.
    Returns a list of LangChain Document objects.
    """
    docs = []
    for csv_file in Path(data_dir).rglob("*.csv"):
        loader = CSVLoader(str(csv_file))
        loaded_docs = loader.load()
        if loaded_docs:
            docs.extend(loaded_docs)
    return docs

def run_ingestion(data_dir: str = "app/data/raw/argo"):
    """
    Ingest CSVs, split into chunks, embed with Ollama, and store in Chroma.
    Returns a summary dict.
    """
    if data_dir is None:
        # Use absolute path from project root
        data_dir = os.path.join(os.getcwd(), "data", "raw", "argo")

    data_path = Path(data_dir)
    print("Looking for CSVs in:", data_path.resolve())
    
    docs = load_local_tree(data_dir)
    if not docs:
        return {"status": "error", "details": f"No CSV documents found in {data_dir}"}

    # Split documents into manageable chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    if not chunks:
        return {"status": "error", "details": "No chunks created from documents."}

    # Initialize embeddings
    embeddings = OllamaEmbeddings(model=settings.EMB_MODEL, base_url=settings.OLLAMA_URL)

    # Test embedding on first chunk
    test_vector = embeddings.embed_documents([chunks[0].page_content])
    if not test_vector or len(test_vector[0]) == 0:
        return {"status": "error", "details": "Embeddings returned empty vector. Check your Ollama model."}

    # Initialize Chroma vectorstore
    vs = Chroma(
        collection_name=settings.COLLECTION,
        persist_directory=settings.CHROMA_DIR,
        embedding_function=embeddings,
    )

    # Add chunks and persist
    vs.add_documents(chunks)
    vs.persist()

    return {"status": "ingested", "added_chunks": len(chunks)}
