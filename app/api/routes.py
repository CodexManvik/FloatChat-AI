from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Any
from app.ingest.ingest import run_ingestion
from app.core.rag import build_chain

router = APIRouter()
_chain = None  # RAG chain, initialized on first request

class Ask(BaseModel):
    query: str
    top_k: Optional[int] = None

@router.get("/health")
def health() -> dict:
    """
    Health check endpoint.
    """
    return {"status": "ok"}

@router.post("/ingest")
def ingest() -> dict:
    """
    Trigger ingestion of CSV/data files.
    Returns a summary of ingestion.
    """
    try:
        result = run_ingestion("data/raw/argo")  # path relative to project root
        return {"status": "ingested", "details": result}
    except Exception as e:
        # Log the error in the console
        print("❌ Ingestion failed:", str(e))
        return {"status": "error", "details": str(e)}


@router.post("/ask")
def ask(req: Ask) -> Any:
    """
    Ask a query to the RAG chain.
    Lazily initializes the chain on first request.
    """
    global _chain
    if _chain is None:
        _chain = build_chain()
    res = _chain(req.query, top_k=req.top_k)
    return {"query": req.query, "answer": res}
