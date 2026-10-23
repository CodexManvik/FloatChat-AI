"""
FloatChat backend - FastAPI service that answers natural language questions
about ARGO float data using NL-to-SQL for analytical questions and RAG
(ChromaDB + optional LLM) for descriptive ones.
"""

import json
import logging

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import create_engine, text

import config
import llm
from export_utils import export_to_ascii, export_to_csv, export_to_netcdf
from nl_to_sql import NLToSQLTranslator, process_analytical_query
from ocean_regions import MONTHS, parse_filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("floatchat")

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)

app = FastAPI(
    title="FloatChat API",
    description="Query ARGO oceanographic data in natural language (NL-to-SQL + RAG)",
    version="2.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SYSTEM_PROMPT = (
    "You are FloatChat, an oceanography assistant for ARGO float data in the Indian Ocean. "
    "Answer using only the facts in the provided context. Be concise (under 150 words), "
    "mention float IDs, dates and locations where relevant, and use Markdown bullet points. "
    "If the context does not answer the question, say so."
)


def get_collection():
    try:
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        return client.get_collection(
            config.CHROMA_COLLECTION,
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        )
    except Exception as e:
        logger.warning(f"ChromaDB collection not available ({e}). Run `python ingest.py` first.")
        return None


collection = get_collection()

try:
    nl_sql_translator = NLToSQLTranslator()
except Exception as e:
    logger.warning(f"NL-to-SQL translator unavailable: {e}")
    nl_sql_translator = None


def df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> null, timestamps -> ISO)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def read_sql(sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


class QueryRequest(BaseModel):
    query_text: str


class QueryResponse(BaseModel):
    answer: str
    query_type: str = "semantic"
    context_documents: list[str]
    retrieved_metadata: list[dict]
    sql_results: list[dict] | None = None


@app.get("/health")
async def health_check():
    try:
        with engine.connect() as conn:
            measurements = conn.execute(text("SELECT COUNT(*) FROM measurements")).scalar()
        database = "connected"
    except Exception:
        measurements, database = 0, "disconnected"
    return {
        "status": "healthy" if database == "connected" and collection is not None else "degraded",
        "database": database,
        "measurements": measurements,
        "chromadb": "connected" if collection is not None else "disconnected",
        "indexed_profiles": collection.count() if collection is not None else 0,
        "llm": llm.status(),
    }


@app.get("/stats")
async def get_stats():
    """Headline numbers for the dataset."""
    totals = read_sql("""
        SELECT (SELECT COUNT(*) FROM floats) AS floats,
               (SELECT COUNT(*) FROM profiles) AS profiles,
               (SELECT COUNT(*) FROM measurements) AS measurements,
               (SELECT COUNT(DISTINCT float_id) FROM measurements WHERE oxygen IS NOT NULL) AS bgc_floats,
               (SELECT MIN(profile_date) FROM profiles) AS start_date,
               (SELECT MAX(profile_date) FROM profiles) AS end_date,
               (SELECT MAX(depth) FROM measurements) AS max_depth
    """)
    regions = read_sql("SELECT region, COUNT(*) AS profiles FROM profiles GROUP BY region ORDER BY profiles DESC")
    return {**df_records(totals)[0], "regions": df_records(regions)}


@app.get("/floats")
async def get_floats():
    """Latest position and surface readings of every float."""
    df = read_sql("""
        WITH latest AS (
            SELECT DISTINCT ON (float_id) float_id, profile_id, profile_date, profile_lat, profile_lon, region
            FROM profiles ORDER BY float_id, profile_date DESC
        ),
        counts AS (SELECT float_id, COUNT(*) AS n_profiles FROM profiles GROUP BY float_id),
        surface AS (
            SELECT DISTINCT ON (profile_id) profile_id, temperature, salinity
            FROM measurements ORDER BY profile_id, depth
        ),
        bgc AS (SELECT DISTINCT float_id FROM measurements WHERE oxygen IS NOT NULL)
        SELECT l.float_id, l.profile_date AS last_profile, l.profile_lat AS lat, l.profile_lon AS lon,
               l.region, c.n_profiles, s.temperature AS surface_temperature, s.salinity AS surface_salinity,
               (b.float_id IS NOT NULL) AS is_bgc
        FROM latest l
        JOIN counts c USING (float_id)
        LEFT JOIN surface s USING (profile_id)
        LEFT JOIN bgc b USING (float_id)
        ORDER BY l.float_id
    """)
    return df_records(df)


@app.post("/query", response_model=QueryResponse)
async def query_rag_pipeline(request: QueryRequest):
    """
    Handles both analytical (SQL) and semantic (RAG) queries
    """
    question = request.query_text.strip()
    if nl_sql_translator and nl_sql_translator.is_analytical_query(question):
        try:
            result = analytical_query(question)
            if result:
                return result
        except Exception as e:
            logger.warning(f"SQL processing error, falling back to semantic search: {e}")
    return semantic_search_query(question)


def format_results_for_display(df: pd.DataFrame, intent: str) -> str:
    """Format SQL results as readable Markdown bullets based on query intent"""

    def fmt(row, col, unit, digits=2):
        val = row.get(col)
        return f"{val:.{digits}f}{unit}" if pd.notna(val) else "N/A"

    lines = []
    if intent == "avg_by_depth":
        for _, row in df.head(12).iterrows():
            lines.append(f"- **{row['depth']:.0f} m**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['measurement_count']:.0f} readings)")
    elif intent == "regional_comparison":
        for _, row in df.iterrows():
            lines.append(f"- **{row['region']}**: upper-100 m avg {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['profile_count']:.0f} profiles)")
    elif intent == "depth_ranges":
        for _, row in df.iterrows():
            lines.append(f"- **{row['depth_range']}**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')}, O₂ {fmt(row, 'avg_oxygen', ' µmol/kg', 1)}")
    elif intent == "temporal_trends":
        for _, row in df.head(12).iterrows():
            month = row["month"].strftime("%B %Y") if hasattr(row["month"], "strftime") else str(row["month"])
            lines.append(f"- **{month}**: {fmt(row, 'avg_temperature', ' °C')}, "
                         f"{fmt(row, 'avg_salinity', ' PSU')} ({row['measurement_count']:.0f} readings)")
    elif intent == "float_summary":
        for _, row in df.head(10).iterrows():
            lines.append(f"- **Float {row['float_id']}**: {row['total_profiles']:.0f} profiles, "
                         f"avg {fmt(row, 'avg_temperature', ' °C')}, down to {row['max_depth']:.0f} m")
    elif intent == "bgc_analysis":
        for _, row in df.iterrows():
            lines.append(f"- **{row['ocean_zone']}**: avg O₂ {fmt(row, 'avg_oxygen', ' µmol/kg', 1)} "
                         f"(min {fmt(row, 'min_oxygen', '', 1)}, max {fmt(row, 'max_oxygen', '', 1)})")
    else:
        for i, (_, row) in enumerate(df.head(10).iterrows()):
            values = ", ".join(f"{col.replace('_', ' ')}: {val:.2f}" if isinstance(val, float) else f"{col.replace('_', ' ')}: {val}"
                               for col, val in row.items() if pd.notna(val))
            lines.append(f"- {values}")
    if len(df) > len(lines):
        lines.append(f"- *…and {len(df) - len(lines)} more rows (see the chart and table)*")
    return "\n".join(lines)


INTENT_TITLES = {
    "avg_by_depth": "Average temperature and salinity at each depth",
    "regional_comparison": "Upper-ocean (0–100 m) conditions by region",
    "depth_ranges": "Ocean conditions by depth layer",
    "temporal_trends": "Monthly averages",
    "float_summary": "Most active floats",
    "bgc_analysis": "Dissolved oxygen by ocean zone",
}


def analytical_query(question: str) -> dict | None:
    sql_result, error = process_analytical_query(question, nl_sql_translator)
    if error:
        logger.info(f"SQL path not used: {error}")
        return None

    sql_query, results_df, intent = sql_result["sql_query"], sql_result["results"], sql_result["intent"]
    title = INTENT_TITLES.get(intent, "Query results")
    formatted = format_results_for_display(results_df, intent)

    insight = llm.chat(
        f"Question: {question}\n\nSQL result (first rows):\n{results_df.head(15).to_string(index=False)}\n\n"
        "In 2-3 sentences, explain the main oceanographic pattern in this result.",
        system=SYSTEM_PROMPT,
    )
    answer = f"**{title}**\n\n{formatted}"
    if insight:
        answer += f"\n\n**What this means:** {insight}"

    return {
        "answer": answer,
        "query_type": "analytical",
        "context_documents": [sql_query],
        "retrieved_metadata": [{
            "query_type": "analytical",
            "intent": intent,
            "sql_query": sql_query,
            "row_count": int(len(results_df)),
            "columns": [str(c) for c in results_df.columns],
            "summary_stats": sql_result["summary_stats"],
        }],
        "sql_results": df_records(results_df.head(200)),
    }


def format_position(lat: float, lon: float) -> str:
    return f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"


def chroma_where(filters: dict) -> dict | None:
    clauses = [{key: value} for key, value in filters.items()]
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def describe_filters(filters: dict) -> str:
    parts = []
    if "region" in filters:
        parts.append(f"in the {filters['region']}")
    if "month_num" in filters:
        parts.append(f"in {MONTHS[filters['month_num'] - 1].title()}")
    if "year" in filters:
        parts.append(str(filters["year"]))
    return " ".join(parts)


def semantic_search_query(question: str) -> dict:
    """Handle descriptive queries with vector search over profile summaries"""
    if collection is None:
        return {"answer": "The vector index is not built yet. Run `python ingest.py` and restart the API.",
                "context_documents": [], "retrieved_metadata": []}

    filters = parse_filters(question)
    results = collection.query(query_texts=[question], n_results=8, where=chroma_where(filters))
    filters_note = ""
    if not results["ids"][0] and filters:
        filters_note = (f"No profiles were recorded {describe_filters(filters)} in this dataset, "
                        "so these are the closest matches overall.\n\n")
        results = collection.query(query_texts=[question], n_results=8)

    documents, metadata = results["documents"][0], results["metadatas"][0]
    if not documents:
        return {"answer": "I couldn't find any matching ARGO profiles.", "context_documents": [], "retrieved_metadata": []}

    context = "\n".join(f"- {doc}" for doc in documents)
    answer = llm.chat(f"Context:\n{context}\n\nQuestion: {question}", system=SYSTEM_PROMPT)
    if not answer:
        scope = f" {describe_filters(filters)}" if filters and not filters_note else ""
        bullets = "\n".join(
            f"- **Float {m['float_id']}**, cycle {m['cycle_number']} · {m['date']} · "
            f"{format_position(m['lat'], m['lon'])} ({m['region']})"
            for m in metadata
        )
        answer = (f"Here are the {len(metadata)} ARGO profiles{scope} most relevant to your question:\n\n"
                  f"{bullets}\n\nTop match: {documents[0]}")

    return {
        "answer": filters_note + answer,
        "query_type": "semantic",
        "context_documents": documents,
        "retrieved_metadata": metadata,
    }


class ProfileRequest(BaseModel):
    ids: list[int] = []          # measurement ids (returns their whole profiles)
    profile_ids: list[int] = []  # profile ids


@app.post("/get_profiles")
async def get_profiles_by_ids(request: ProfileRequest):
    """
    Returns full measurement data (with float context) for the requested
    profiles, or for the profiles that contain the requested measurement ids.
    """
    if not request.ids and not request.profile_ids:
        return []
    df = read_sql("""
        SELECT m.id, m.time, m.lat, m.lon, m.depth, m.pressure, m.temperature, m.salinity,
               m.oxygen, m.float_id, m.profile_id, p.cycle_number, p.region, f.wmo_id
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.profile_id
        JOIN floats f ON m.float_id = f.float_id
        WHERE m.profile_id = ANY(:profile_ids)
           OR m.profile_id IN (SELECT profile_id FROM measurements WHERE id = ANY(:ids))
        ORDER BY m.float_id, p.cycle_number, m.depth
    """, ids=request.ids, profile_ids=request.profile_ids)
    return df_records(df)


@app.get("/float/{float_id}")
async def get_float_info(float_id: str):
    """Get comprehensive information about a specific ARGO float"""
    float_df = read_sql("SELECT * FROM floats WHERE float_id = :fid", fid=float_id)
    if float_df.empty:
        return {"error": "Float not found"}
    profile_summary = read_sql("""
        SELECT COUNT(*) AS total_profiles, MIN(profile_date) AS first_profile,
               MAX(profile_date) AS last_profile, COUNT(DISTINCT DATE(profile_date)) AS active_days
        FROM profiles WHERE float_id = :fid
    """, fid=float_id)
    measurement_summary = read_sql("""
        SELECT COUNT(*) AS total_measurements, MIN(depth) AS min_depth, MAX(depth) AS max_depth,
               AVG(temperature) AS avg_temp, AVG(salinity) AS avg_sal
        FROM measurements WHERE float_id = :fid
    """, fid=float_id)
    return {
        "float_info": df_records(float_df)[0],
        "profile_summary": df_records(profile_summary)[0],
        "measurement_summary": df_records(measurement_summary)[0],
    }


@app.get("/profiles/float/{float_id}")
async def get_float_profiles(float_id: str):
    """Get all profiles (the trajectory) of a specific float"""
    df = read_sql("""
        SELECT p.*, COUNT(m.id) AS measurement_count, AVG(m.temperature) AS avg_temp,
               AVG(m.salinity) AS avg_sal, MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM profiles p
        LEFT JOIN measurements m ON p.profile_id = m.profile_id
        WHERE p.float_id = :fid
        GROUP BY p.profile_id
        ORDER BY p.cycle_number
    """, fid=float_id)
    return df_records(df)


@app.get("/statistics/system")
async def get_system_statistics():
    """Summary statistics used by the dashboard"""
    stats = await get_stats()
    return {
        "active_floats": stats["floats"],
        "total_profiles": stats["profiles"],
        "total_measurements": stats["measurements"],
        "data_quality": 1.0,
        "date_range": [stats["start_date"], stats["end_date"]],
        "recent_activity": [],
    }


@app.get("/data/regions")
async def get_regions():
    regions = read_sql("SELECT DISTINCT region FROM profiles ORDER BY region")
    return {"regions": regions["region"].tolist()}


class ExportRequest(BaseModel):
    format: str  # "ascii", "netcdf", "csv"
    data_ids: list[int] = []     # measurement ids
    profile_ids: list[int] = []  # whole profiles


@app.post("/export")
async def export_data(request: ExportRequest):
    """
    Export ARGO data in specified format (ASCII, NetCDF, CSV)
    """
    exporters = {
        "ascii": (export_to_ascii, "text/plain", "argo_data.txt"),
        "netcdf": (export_to_netcdf, "application/octet-stream", "argo_data.nc"),
        "csv": (export_to_csv, "text/csv", "argo_data.csv"),
    }
    fmt = request.format.lower()
    if fmt not in exporters:
        return {"error": "Unsupported format. Use 'ascii', 'netcdf', or 'csv'"}
    try:
        exporter, media_type, filename = exporters[fmt]
        content = exporter(request.data_ids, request.profile_ids)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}


@app.get("/sample-queries")
async def get_sample_queries():
    """Sample queries organized by category"""
    from nl_to_sql import get_sample_analytical_queries

    return {
        "analytical_queries": get_sample_analytical_queries(),
        "semantic_queries": {
            "Find Profiles": [
                "Show me salinity profiles near the equator in March 2024",
                "Find warm surface water in the Bay of Bengal",
                "Which floats measured low oxygen in the Arabian Sea?",
                "Deep profiles in the Southern Indian Ocean in February",
            ],
        },
        "query_tips": {
            "analytical": "Use words like 'average', 'compare', 'count', 'trend' for statistical analysis",
            "semantic": "Ask descriptive questions; mention a region or month to narrow the search",
        },
    }


@app.get("/extensibility/status")
async def get_extensibility_status():
    """Current dataset support and planned extensions"""
    return {
        "current_status": "Extensibility Framework Ready",
        "supported_datasets": {
            "implemented": ["ARGO Floats"],
            "framework_ready": ["Gliders", "Buoys", "Satellites", "Custom Datasets"],
        },
    }
