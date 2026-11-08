"""Semantic profile search: pgvector similarity plus SQL filters in one query."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from floatchat.filters import clean_filters, sql_conditions


def vector_literal(vector) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vector) + "]"


def search_profiles(engine: Engine, query_vector, filters: dict, limit: int = 8, ef_search: int = 200) -> list[dict]:
    conditions, params = sql_conditions(clean_filters(filters), alias="profiles")
    clauses = ["embedding IS NOT NULL"] + conditions
    params.update(q=vector_literal(query_vector), limit=limit)
    columns = """profile_id, float_id, cycle_number, to_char(profile_date, 'YYYY-MM-DD') AS date,
               EXTRACT(YEAR FROM profile_date)::int AS year, EXTRACT(MONTH FROM profile_date)::int AS month_num,
               profile_lat AS lat, profile_lon AS lon, region,
               has_oxygen, has_chlorophyll, has_nitrate, has_ph, description,
               embedding <=> CAST(:q AS vector) AS distance"""
    if len(clauses) == 1:
        # No filters: the approximate HNSW index is fast and accurate enough
        sql = f"SELECT {columns} FROM profiles WHERE {clauses[0]} ORDER BY embedding <=> CAST(:q AS vector) LIMIT :limit"
    else:
        # With filters, the HNSW index would return only its nearest candidates and the filters would run
        # afterwards, which can leave nothing even when matches exist. Filter first (materialized, so the
        # index can't be used), then rank every match exactly. Fast at the ~20k profiles we keep.
        sql = f"""
            WITH matches AS MATERIALIZED (SELECT {columns} FROM profiles WHERE {" AND ".join(clauses)})
            SELECT * FROM matches ORDER BY distance LIMIT :limit
        """
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))
        return [dict(row) for row in conn.execute(text(sql), params).mappings()]
