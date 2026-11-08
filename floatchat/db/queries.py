"""Read queries behind the API endpoints. All work with the read-only role."""

import json
import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def read_sql(engine: Engine, sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> null, timestamps -> ISO)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def get_stats(engine: Engine) -> dict:
    totals = read_sql(engine, """
        SELECT (SELECT COUNT(*) FROM floats) AS floats,
               (SELECT COUNT(*) FROM profiles) AS profiles,
               (SELECT COUNT(*) FROM measurements) AS measurements,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_oxygen) AS bgc_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_chlorophyll) AS chlorophyll_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_nitrate) AS nitrate_floats,
               (SELECT COUNT(DISTINCT float_id) FROM profiles WHERE has_ph) AS ph_floats,
               (SELECT MIN(profile_date) FROM profiles) AS start_date,
               (SELECT MAX(profile_date) FROM profiles) AS end_date,
               (SELECT MAX(depth) FROM measurements) AS max_depth,
               (SELECT MAX(finished_at) FROM ingest_runs WHERE status = 'success') AS last_updated
    """)
    regions = read_sql(engine, "SELECT region, COUNT(*) AS profiles FROM profiles GROUP BY region ORDER BY profiles DESC")
    return {**df_records(totals)[0], "regions": df_records(regions)}


def get_floats(engine: Engine) -> list[dict]:
    return df_records(read_sql(engine, """
        WITH latest AS (
            SELECT DISTINCT ON (float_id) float_id, profile_id, profile_date, profile_lat, profile_lon, region
            FROM profiles ORDER BY float_id, profile_date DESC
        ),
        counts AS (
            SELECT float_id, COUNT(*) AS n_profiles,
                   bool_or(has_oxygen OR has_chlorophyll OR has_nitrate OR has_ph) AS is_bgc
            FROM profiles GROUP BY float_id
        ),
        surface AS (
            SELECT DISTINCT ON (profile_id) profile_id, temperature, salinity
            FROM measurements WHERE profile_id IN (SELECT profile_id FROM latest)
            ORDER BY profile_id, depth
        )
        SELECT l.float_id, l.profile_date AS last_profile, l.profile_lat AS lat, l.profile_lon AS lon, l.region,
               c.n_profiles, s.temperature AS surface_temperature, s.salinity AS surface_salinity, c.is_bgc
        FROM latest l
        JOIN counts c USING (float_id)
        LEFT JOIN surface s USING (profile_id)
        ORDER BY l.float_id
    """))


def get_profiles(engine: Engine, ids: list[int], profile_ids: list[int]) -> list[dict]:
    return df_records(read_sql(engine, """
        SELECT m.id, m.time, m.lat, m.lon, m.depth, m.pressure, m.temperature, m.salinity,
               m.oxygen, m.chlorophyll, m.nitrate, m.ph, m.float_id, m.profile_id,
               p.cycle_number, p.region, f.wmo_id
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.profile_id
        JOIN floats f ON m.float_id = f.float_id
        WHERE m.profile_id = ANY(:profile_ids)
           OR m.profile_id IN (SELECT profile_id FROM measurements WHERE id = ANY(:ids))
        ORDER BY m.float_id, p.cycle_number, m.depth
    """, ids=list(ids), profile_ids=list(profile_ids)))


def get_float_info(engine: Engine, float_id: str) -> dict | None:
    info = read_sql(engine, "SELECT * FROM floats WHERE float_id = :fid", fid=float_id)
    if info.empty:
        return None
    profile_summary = read_sql(engine, """
        SELECT COUNT(*) AS total_profiles, MIN(profile_date) AS first_profile,
               MAX(profile_date) AS last_profile, COUNT(DISTINCT DATE(profile_date)) AS active_days
        FROM profiles WHERE float_id = :fid
    """, fid=float_id)
    measurement_summary = read_sql(engine, """
        SELECT COUNT(*) AS total_measurements, MIN(depth) AS min_depth, MAX(depth) AS max_depth,
               AVG(temperature) AS avg_temp, AVG(salinity) AS avg_sal
        FROM measurements WHERE float_id = :fid
    """, fid=float_id)
    return {
        "float_info": df_records(info)[0],
        "profile_summary": df_records(profile_summary)[0],
        "measurement_summary": df_records(measurement_summary)[0],
    }


def get_float_profiles(engine: Engine, float_id: str) -> list[dict]:
    return df_records(read_sql(engine, """
        SELECT p.profile_id, p.float_id, p.cycle_number, p.profile_date, p.profile_lat, p.profile_lon,
               p.region, p.n_levels, p.has_oxygen, p.has_chlorophyll, p.has_nitrate, p.has_ph,
               COUNT(m.id) AS measurement_count, AVG(m.temperature) AS avg_temp, AVG(m.salinity) AS avg_sal,
               MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM profiles p
        LEFT JOIN measurements m ON p.profile_id = m.profile_id
        WHERE p.float_id = :fid
        GROUP BY p.profile_id
        ORDER BY p.cycle_number
    """, fid=float_id))


def data_status(engine: Engine) -> dict:
    return df_records(read_sql(engine, """
        SELECT (SELECT COUNT(*) FROM measurements) AS measurements,
               (SELECT COUNT(*) FROM profiles WHERE embedding IS NOT NULL) AS indexed_profiles,
               (SELECT MAX(profile_date) FROM profiles) AS newest_data,
               (SELECT COALESCE(MAX(run_id), 0) FROM ingest_runs WHERE status = 'success') AS latest_run_id
    """))[0]


def log_query(engine: Engine, *, question: str, query_type: str | None, intent: str | None, latency_ms: int,
              success: bool, cached: bool, llm_used: bool) -> None:
    """Best effort: a logging failure must never fail the request."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO query_log (question, query_type, intent, latency_ms, success, cached, llm_used)
                VALUES (:question, :query_type, :intent, :latency_ms, :success, :cached, :llm_used)
            """), {"question": question, "query_type": query_type, "intent": intent, "latency_ms": latency_ms,
                   "success": success, "cached": cached, "llm_used": llm_used})
    except Exception as e:
        logger.warning("Could not write query_log: %s", e)
