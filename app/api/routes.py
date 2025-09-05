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
    Trigger ingestion of database files into Chroma.
    Returns a summary of ingestion.
    """
    try:
        # Hardcoded path can be replaced by a config or env variable
        result = run_ingestion("app/data/raw/argo")  
        return {"status": "ingested", "details": result}
    except Exception as e:
        # Print/log error for debugging
        print("❌ Ingestion failed:", str(e))
        return {"status": "error", "details": str(e)}


@router.post("/ask")
def ask(req: Ask) -> Any:
    """
    Ask a query to the RAG chain.
    Initializes the chain on first request.
    """
    global _chain
    if _chain is None:
        _chain = build_chain()
    res = _chain(req.query, top_k=req.top_k)
    return {
        "query": req.query,
        "answer": res.get("answer"),
        "contexts": res.get("contexts", [])
    }
