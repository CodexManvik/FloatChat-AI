"""Semantic profile search: pgvector similarity plus SQL filters in one query."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Only these filter keys reach SQL; values are always bound parameters
FILTER_SQL = {
    "region": "region = :region",
    "month_num": "EXTRACT(MONTH FROM profile_date) = :month_num",
    "year": "EXTRACT(YEAR FROM profile_date) = :year",
    "has_oxygen": "has_oxygen",
    "has_chlorophyll": "has_chlorophyll",
    "has_nitrate": "has_nitrate",
    "has_ph": "has_ph",
}
VALUE_FILTERS = ("region", "month_num", "year")


def vector_literal(vector) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vector) + "]"


def search_profiles(engine: Engine, query_vector, filters: dict, limit: int = 8) -> list[dict]:
    clauses = ["embedding IS NOT NULL"] + [FILTER_SQL[key] for key in filters if key in FILTER_SQL]
    params = {key: filters[key] for key in VALUE_FILTERS if key in filters}
    params.update(q=vector_literal(query_vector), limit=limit)
    sql = f"""
        SELECT profile_id, float_id, cycle_number, to_char(profile_date, 'YYYY-MM-DD') AS date,
               EXTRACT(YEAR FROM profile_date)::int AS year, EXTRACT(MONTH FROM profile_date)::int AS month_num,
               profile_lat AS lat, profile_lon AS lon, region,
               has_oxygen, has_chlorophyll, has_nitrate, has_ph, description,
               embedding <=> CAST(:q AS vector) AS distance
        FROM profiles
        WHERE {" AND ".join(clauses)}
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :limit
    """
    with engine.begin() as conn:
        # Filters are applied after the HNSW scan; a wider scan keeps filtered results complete
        conn.execute(text("SET LOCAL hnsw.ef_search = 200"))
        return [dict(row) for row in conn.execute(text(sql), params).mappings()]
