"""
FloatChat API: answers natural-language questions about Argo float data.

Statistical questions run as SQL; descriptive ones search profile embeddings
(pgvector). Public-demo protection: per-IP rate limits, a daily LLM budget,
and caches so repeated questions and dashboard calls stay cheap.
"""

import logging
import time
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StringConstraints

from api.cache import TTLCache, normalize_question
from api.limits import DailyBudget, RateLimiter, client_ip
from floatchat import __version__, config, llm
from floatchat.answer import answer_question
from floatchat.db import queries
from floatchat.db.engine import make_engine
from floatchat.embedder import get_embedder
from floatchat.exports import EXPORTERS
from floatchat.sql_agent import SqlAgent, sample_queries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("floatchat.api")

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
UNLIMITED_PATHS = {"/ping", "/health", "/docs", "/openapi.json", "/redoc"}
ERROR_ANSWER = "Something went wrong while answering that question. Please try rephrasing it."


class QueryRequest(BaseModel):
    query_text: Question


class QueryResponse(BaseModel):
    answer: str
    query_type: str
    context_documents: list[str]
    retrieved_metadata: list[dict]
    sql_results: list[dict] | None = None


class ProfileRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=5000)  # measurement ids -> whole profiles
    profile_ids: list[int] = Field(default_factory=list, max_length=200)


class ExportRequest(BaseModel):
    format: Literal["csv", "netcdf", "ascii"]
    data_ids: list[int] = Field(default_factory=list, max_length=5000)
    profile_ids: list[int] = Field(default_factory=list, max_length=50)


def create_app(engine=None, get_embedder_fn=get_embedder, chat_fn=llm.chat, query_limits=None,
               other_limit_per_minute: int = 60, llm_budget: int | None = None,
               llm_enabled=llm.is_configured) -> FastAPI:
    engine = engine or make_engine(config.DATABASE_URL)
    per_minute, per_day = query_limits or (config.QUERY_LIMIT_PER_MINUTE, config.QUERY_LIMIT_PER_DAY)
    query_limiter = RateLimiter(per_minute, per_day, noun="questions")
    other_limiter = RateLimiter(other_limit_per_minute, None)
    budget = DailyBudget(config.LLM_DAILY_BUDGET if llm_budget is None else llm_budget)
    answers = TTLCache(max_entries=500, ttl_seconds=24 * 3600)
    dashboard = TTLCache(max_entries=16, ttl_seconds=600)
    status = TTLCache(max_entries=4, ttl_seconds=60)

    def budgeted_chat(*args, **kwargs):
        if not budget.try_consume():
            return None
        return chat_fn(*args, **kwargs)

    agent = SqlAgent(engine, chat=budgeted_chat)

    def cached(cache: TTLCache, key: str, compute):
        value = cache.get(key)
        if value is None:
            value = compute()
            cache.set(key, value)
        return value

    app = FastAPI(title="FloatChat API", version=__version__,
                  description="Ask questions about Argo ocean float data in plain English.")

    # Registered before CORS so CORS is the outer layer and 429 responses still carry CORS headers
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.method != "OPTIONS" and request.url.path not in UNLIMITED_PATHS:
            limiter = query_limiter if request.url.path == "/query" else other_limiter
            allowed, message = limiter.check(client_ip(request))
            if not allowed:
                return JSONResponse(status_code=429, content={"error": "rate_limited", "message": message})
        return await call_next(request)

    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/ping")
    def ping():
        """Keep-awake endpoint: never touches the database."""
        return {"ok": True}

    @app.get("/health")
    def health():
        try:
            data = cached(status, "data", lambda: queries.data_status(engine))
            database = "connected"
        except Exception as e:
            logger.warning("Health check database error: %s", e)
            data, database = {"measurements": 0, "indexed_profiles": 0, "newest_data": None}, "disconnected"
        llm_info = cached(status, "llm", llm.status)
        ready = database == "connected" and data["indexed_profiles"] > 0
        return {
            "status": "healthy" if ready else "degraded",
            "database": database,
            "measurements": data["measurements"],
            "vector_index": "ready" if data["indexed_profiles"] else "empty",
            "indexed_profiles": data["indexed_profiles"],
            "newest_data": data["newest_data"],
            "llm": {**llm_info, "budget_exhausted": budget.exhausted},
            "version": __version__,
        }

    @app.get("/stats")
    def stats():
        return cached(dashboard, "stats", lambda: queries.get_stats(engine))

    @app.get("/floats")
    def floats():
        return cached(dashboard, "floats", lambda: queries.get_floats(engine))

    @app.post("/query", response_model=QueryResponse)
    def query(request: QueryRequest):
        question = request.query_text
        started = time.perf_counter()
        try:
            run_id = cached(status, "data", lambda: queries.data_status(engine))["latest_run_id"]
        except Exception:
            run_id = 0
        key = f"{normalize_question(question)}|{run_id}"  # new data -> new key -> no stale answers
        result = answers.get(key)
        was_cached = result is not None
        if not was_cached:
            try:
                result = answer_question(question, engine=engine, embedder_factory=get_embedder_fn,
                                         agent=agent, chat=budgeted_chat)
            except Exception:
                logger.exception("Failed to answer %r", question)
                result = {"answer": ERROR_ANSWER, "query_type": "error", "context_documents": [],
                          "retrieved_metadata": [], "intent": None, "llm_used": False}
            # Don't pin a data-only answer for 24 h when the LLM should have helped but failed (e.g. rate limit)
            llm_expected = llm_enabled() and not budget.exhausted
            if result["query_type"] != "error" and (result.get("llm_used") or not llm_expected):
                answers.set(key, result)
        queries.log_query(engine, question=question, query_type=result["query_type"], intent=result.get("intent"),
                          latency_ms=int((time.perf_counter() - started) * 1000),
                          success=result["query_type"] != "error", cached=was_cached,
                          llm_used=bool(result.get("llm_used")) and not was_cached)
        return result

    @app.post("/get_profiles")
    def get_profiles(request: ProfileRequest):
        if not request.ids and not request.profile_ids:
            return []
        return queries.get_profiles(engine, request.ids, request.profile_ids)

    @app.get("/float/{float_id}")
    def get_float(float_id: str):
        return queries.get_float_info(engine, float_id) or {"error": "Float not found"}

    @app.get("/profiles/float/{float_id}")
    def get_float_profiles(float_id: str):
        return queries.get_float_profiles(engine, float_id)

    @app.post("/export")
    def export(request: ExportRequest):
        if not request.data_ids and not request.profile_ids:
            return JSONResponse(status_code=400, content={"error": "Choose at least one profile to export"})
        exporter, media_type, filename = EXPORTERS[request.format]
        content = exporter(engine, request.data_ids, request.profile_ids)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    @app.get("/sample-queries")
    def get_sample_queries():
        return sample_queries()

    return app


app = create_app()
