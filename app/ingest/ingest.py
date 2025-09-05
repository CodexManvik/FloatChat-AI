from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.document_loaders import CSVLoader
from app.core import settings

# Hardcoded absolute path to your CSV folder
DATA_DIR = Path("C:/Project/floatchat/app/data/raw/argo")

print("Looking for CSVs in:", DATA_DIR.resolve())


def load_local_tree(data_dir: Path):
    """
    Load all CSV files from the folder recursively (case-insensitive).
    Returns a list of LangChain Document objects.
    """
    docs = []
    if not data_dir.exists():
        print(f"❌ Data folder does not exist: {data_dir.resolve()}")
        return docs

    for csv_file in data_dir.rglob("*"):
        if csv_file.suffix.lower() == ".csv":
            print("Found CSV:", csv_file)
            loader = CSVLoader(str(csv_file))
            loaded_docs = loader.load()
            if loaded_docs:
                docs.extend(loaded_docs)
    return docs


def run_ingestion(_data_dir: str = None):
    """
    Ingest CSVs, split into chunks, embed with Ollama, and store in Chroma.
    Returns a summary dict.
    """
    data_path = DATA_DIR  # ignore argument, always use hardcoded path

    # Load documents
    docs = load_local_tree(data_path)
    if not docs:
        return {"status": "error", "details": f"No CSV documents found in {data_path.resolve()}"}

    print(f"✅ Loaded {len(docs)} documents")

    # Split documents into manageable chunks
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

    print("✅ Embeddings test passed")

    # Initialize Chroma vectorstore
    vs = Chroma(
        collection_name=settings.COLLECTION,
        persist_directory=settings.CHROMA_DIR,
        embedding_function=embeddings,
    )

    # Add chunks and persist
    vs.add_documents(chunks)
    vs.persist()  # type: ignore[attr-defined]

    print(f"🚀 Ingested {len(chunks)} chunks into Chroma")
    return {"status": "ingested", "added_chunks": len(chunks)}
