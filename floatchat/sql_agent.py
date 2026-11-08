"""
Statistical questions -> SQL. Common question types use hand-written templates;
anything else is written by the LLM and must pass a read-only check. The API's
database role is read-only as well, so a bad query can never change data.
"""

import json
import logging
import re
import time
from collections.abc import Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from floatchat import llm
from floatchat.filters import clean_filters, sql_conditions

logger = logging.getLogger(__name__)
ChatFn = Callable[..., str | None]
MAX_SQL_REPAIRS = 2

ZONE_CASE = ("CASE WHEN m.depth < 200 THEN 'Euphotic Zone' WHEN m.depth < 1000 THEN 'Mesopelagic Zone' "
             "ELSE 'Bathypelagic Zone' END")
LAYER_CASE = ("CASE WHEN m.depth < 100 THEN 'Surface (0-100m)' WHEN m.depth < 500 THEN 'Intermediate (100-500m)' "
              "WHEN m.depth < 1000 THEN 'Deep (500-1000m)' ELSE 'Very Deep (>1000m)' END")
JOIN_PROFILES = "FROM measurements m JOIN profiles p ON p.profile_id = m.profile_id"

# {where} receives the question's filters as " AND <condition>" clauses on the profiles table (alias p)
TEMPLATES = {
    "avg_by_depth": f"""
        SELECT m.depth, AVG(m.temperature) AS avg_temperature, AVG(m.salinity) AS avg_salinity,
               COUNT(*) AS measurement_count
        {JOIN_PROFILES}
        WHERE m.temperature IS NOT NULL AND m.salinity IS NOT NULL{{where}}
        GROUP BY m.depth ORDER BY m.depth LIMIT 100""",
    "regional_comparison": f"""
        SELECT p.region, AVG(m.temperature) AS avg_temperature, AVG(m.salinity) AS avg_salinity,
               AVG(m.oxygen) AS avg_oxygen, COUNT(DISTINCT p.profile_id) AS profile_count,
               COUNT(*) AS measurement_count
        {JOIN_PROFILES}
        WHERE m.temperature IS NOT NULL AND m.depth <= 100{{where}}
        GROUP BY p.region ORDER BY avg_temperature DESC""",
    "depth_ranges": f"""
        SELECT {LAYER_CASE} AS depth_range, AVG(m.temperature) AS avg_temperature,
               AVG(m.salinity) AS avg_salinity, AVG(m.oxygen) AS avg_oxygen, COUNT(*) AS measurement_count
        {JOIN_PROFILES}
        WHERE m.temperature IS NOT NULL{{where}}
        GROUP BY 1 ORDER BY MIN(m.depth)""",
    "float_summary": """
        SELECT f.float_id, f.wmo_id, f.deployment_date, COUNT(DISTINCT p.profile_id) AS total_profiles,
               COUNT(m.id) AS total_measurements, AVG(m.temperature) AS avg_temperature,
               AVG(m.salinity) AS avg_salinity, MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM floats f
        JOIN profiles p ON f.float_id = p.float_id
        JOIN measurements m ON p.profile_id = m.profile_id
        WHERE m.temperature IS NOT NULL{where}
        GROUP BY f.float_id, f.wmo_id, f.deployment_date
        ORDER BY total_measurements DESC LIMIT 50""",
    "temporal_trends": f"""
        SELECT DATE_TRUNC('month', m.time) AS month, AVG(m.temperature) AS avg_temperature,
               AVG(m.salinity) AS avg_salinity, COUNT(*) AS measurement_count
        {JOIN_PROFILES}
        WHERE m.temperature IS NOT NULL{{where}}
        GROUP BY 1 ORDER BY month LIMIT 100""",
    "bgc_analysis": f"""
        SELECT {ZONE_CASE} AS ocean_zone, AVG(m.oxygen) AS avg_oxygen, MIN(m.oxygen) AS min_oxygen,
               MAX(m.oxygen) AS max_oxygen, AVG(m.chlorophyll) AS avg_chlorophyll, AVG(m.nitrate) AS avg_nitrate,
               AVG(m.ph) AS avg_ph, COUNT(*) AS measurement_count
        {JOIN_PROFILES}
        WHERE (m.oxygen IS NOT NULL OR m.chlorophyll IS NOT NULL OR m.nitrate IS NOT NULL OR m.ph IS NOT NULL){{where}}
        GROUP BY 1 ORDER BY MIN(m.depth)""",
}


def render_template(intent: str, filters: dict | None = None) -> tuple[str, dict]:
    """A template with the question's filters applied; returns the SQL and its bound parameters."""
    filters = clean_filters(filters)
    if intent == "regional_comparison":
        filters.pop("region", None)  # the point is to compare every region
    conditions, params = sql_conditions(filters, alias="p")
    return TEMPLATES[intent].format(where="".join(f" AND {c}" for c in conditions)).strip(), params

SCHEMA_PROMPT = """
TABLES (PostgreSQL):
floats(float_id text PK, wmo_id int, deployment_date date, deployment_lat float, deployment_lon float, last_contact date)
profiles(profile_id int PK, float_id text, cycle_number int, profile_date timestamp, profile_lat float,
         profile_lon float, region text, n_levels int, has_oxygen bool, has_chlorophyll bool, has_nitrate bool, has_ph bool)
measurements(id bigint PK, profile_id int, float_id text, time timestamp, lat float, lon float, depth float (m),
             pressure float (dbar), temperature float (degC), salinity float (PSU), oxygen float (umol/kg),
             chlorophyll float (mg/m3), nitrate float (umol/kg), ph float)
RELATIONSHIPS: floats 1-n profiles via float_id; profiles 1-n measurements via profile_id.
profiles.region is one of: 'Arabian Sea', 'Bay of Bengal', 'Equatorial Indian Ocean', 'Southern Indian Ocean',
'Eastern Indian Ocean', 'Red Sea & Gulf of Aden'.
Each profile has measurements on 24 standard depths: 5,10,20,30,50,75,100,125,150,200,250,300,400,500,600,700,800,900,1000,1200,1400,1600,1800,2000.
BGC columns (oxygen, chlorophyll, nitrate, ph) are NULL for floats without those sensors.
"""

ANALYTICAL_PATTERNS = [
    r"\b(average|mean|avg|sum|count|total|maximum|max|minimum|min)\b",
    r"\b(compare|comparison|versus|vs|between|difference)\b",
    r"\b(group|aggregate|distribution|range|trend|correlation)\b",
    r"\b(how many|how much|statistics|statistical|percentage|percent)\b",
    r"\b(greater than|less than|higher|lower|above|below|top|bottom)\b",
    r"\b(over time|temporal|monthly|yearly|seasonal)\b",
    r"\b(summary|summarize|summarise|overview|each float|per float|by month|by depth|by region|by zone)\b",
]
FORBIDDEN_SQL = ["drop", "delete", "truncate", "alter", "create", "insert", "update", "grant", "revoke",
                 "copy", "pg_read_file", "pg_sleep", "dblink", "set_config"]


class SqlAgent:
    def __init__(self, engine: Engine, chat: ChatFn = llm.chat):
        self.engine = engine
        self.chat = chat

    @staticmethod
    def is_analytical_query(question: str) -> bool:
        q = question.lower()
        return any(re.search(pattern, q) for pattern in ANALYTICAL_PATTERNS)

    @staticmethod
    def detect_query_intent(question: str) -> str:
        q = question.lower()
        if re.search(r"\b(oxygen|ph|chlorophyll|nitrate|bgc|biogeochemical)\b", q):
            return "bgc_analysis"
        if re.search(r"\b(depth range|depth ranges|zone|zones|layer|layers|surface and deep)\b", q):
            return "depth_ranges"
        if any(word in q for word in ("depth", "profile", "vertical")) and any(w in q for w in ("average", "mean")):
            return "avg_by_depth"
        if any(word in q for word in ("region", "hemisphere", "arabian", "bengal", "basin")):
            return "regional_comparison"
        if any(word in q for word in ("time", "temporal", "trend", "month", "year", "weekly")):
            return "temporal_trends"
        if any(word in q for word in ("float", "summary", "overview")):
            return "float_summary"
        return "custom"

    @staticmethod
    def validate_sql(sql: str) -> bool:
        lowered = sql.lower()
        if any(re.search(rf"\b{word}\b", lowered) for word in FORBIDDEN_SQL):
            return False
        if not re.match(r"\s*(select|with)\b", lowered):
            return False
        return ";" not in lowered.strip().rstrip(";")  # exactly one statement

    def generate_sql(self, question: str, filters: dict | None = None,
                     intent: str | None = None) -> tuple[str | None, str, dict]:
        intent = intent or self.detect_query_intent(question)
        if intent in TEMPLATES:
            sql, params = render_template(intent, filters)
            return sql, intent, params
        filters = clean_filters(filters)
        scope = (f"Only include profiles matching these filters (columns of profiles): {json.dumps(filters)}. "
                 "month_num/year refer to profiles.profile_date.\n" if filters else "")
        prompt = (
            "You are an expert PostgreSQL analyst for Argo ocean float data.\n"
            f"{SCHEMA_PROMPT}\n"
            "Rules: one read-only SELECT statement; meaningful column aliases; handle NULLs; "
            "at most 1000 rows; ORDER BY for readable output.\n"
            f"{scope}\n"
            f"Question: {question}\n"
            "Return ONLY the SQL, no explanation and no code fences."
        )
        sql = self.chat(prompt, temperature=0.0)
        if not sql:
            return None, "error", {}
        return _clean_llm_sql(sql), "custom", {}

    def _execute(self, sql: str, params: dict | None) -> tuple[pd.DataFrame, str, str]:
        """Run SQL; returns (rows, status, database error text for the repair prompt)."""
        if not self.validate_sql(sql):
            return pd.DataFrame(), "Invalid or unsafe SQL query", "The query must be one read-only SELECT statement."
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(sql), conn, params=params or {})
        except Exception as e:
            logger.info("SQL failed: %s", e)
            detail = str(getattr(e, "orig", e)).strip().splitlines()[0][:300]
            return pd.DataFrame(), f"Database error: {e.__class__.__name__}", detail
        if df.empty:
            return df, "Query executed successfully but returned no results", ""
        return df, "success", ""

    def execute_sql_query(self, sql: str, params: dict | None = None) -> tuple[pd.DataFrame, str]:
        df, status, _ = self._execute(sql, params)
        return df, status

    def _repair(self, question: str, sql: str, error: str) -> str | None:
        prompt = (
            "You are an expert PostgreSQL analyst for Argo ocean float data.\n"
            f"{SCHEMA_PROMPT}\n"
            f"This SQL, written for the question below, failed.\nQuestion: {question}\nSQL: {sql}\n"
            f"Error: {error}\n\nReturn ONLY the corrected read-only SQL, no explanation and no code fences."
        )
        fixed = self.chat(prompt, temperature=0.0)
        return _clean_llm_sql(fixed) if fixed else None

    def run(self, question: str, filters: dict | None = None, intent: str | None = None,
            emit: Callable[[dict], None] | None = None) -> tuple[dict | None, str | None]:
        emit = emit or (lambda event: None)
        if intent is None and not self.is_analytical_query(question):
            return None, "Not an analytical query"
        sql, intent, params = self.generate_sql(question, filters, intent)
        if not sql:
            return None, "Failed to generate SQL"
        repairs_left = MAX_SQL_REPAIRS if intent == "custom" else 0
        for attempt in range(1, repairs_left + 2):
            started = time.perf_counter()
            df, status, error = self._execute(sql, params)
            ok = status == "success"
            emit({"step": "sql", "attempt": attempt, "sql": sql, "params": params,
                  "status": "success" if ok else ("empty" if not error else "error"),
                  "rows": int(len(df)), "ms": int((time.perf_counter() - started) * 1000)})
            if ok:
                return {"sql_query": sql, "params": params, "results": df, "intent": intent,
                        "attempts": attempt, "summary_stats": _summary_stats(df)}, None
            if not error or attempt > repairs_left:
                break
            sql = self._repair(question, sql, error)  # LLM-written SQL failed: send the error back for a fix
            if not sql:
                break
        return None, f"SQL execution failed: {status}"


def _clean_llm_sql(sql: str) -> str:
    sql = re.sub(r"```(sql)?", "", sql).strip().rstrip(";")
    if "limit" not in sql.lower():
        sql += " LIMIT 1000"
    return sql


def _summary_stats(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include="number")
    stats = {"total_rows": int(len(df)), "columns": [str(c) for c in df.columns],
             "numeric_columns": [str(c) for c in numeric.columns], "numeric_summary": {}}
    for col in list(numeric.columns)[:5]:
        values = numeric[col].dropna()
        stats["numeric_summary"][str(col)] = (
            {"mean": float(values.mean()), "min": float(values.min()), "max": float(values.max()),
             "count": int(values.count())} if not values.empty else
            {"mean": None, "min": None, "max": None, "count": 0})
    return stats


def sample_queries() -> dict:
    return {
        "analytical_queries": {
            "Depth Analysis": ["What is the average temperature at different depths?",
                               "Show average salinity by depth range"],
            "Regional Comparison": ["Compare surface temperature across ocean regions",
                                    "Compare the Arabian Sea and the Bay of Bengal"],
            "Temporal Trends": ["Show the monthly temperature trend"],
            "Float Analysis": ["Show a summary for each float"],
            "BGC Parameters": ["Average dissolved oxygen by ocean zone", "Average chlorophyll by ocean zone"],
        },
        "semantic_queries": {
            "Find Profiles": ["Show me salinity profiles near the equator",
                              "Find warm surface water in the Bay of Bengal",
                              "Which floats measured low oxygen in the Arabian Sea?",
                              "Where is chlorophyll highest?"],
        },
        "query_tips": {
            "analytical": "Use words like 'average', 'compare', 'count', 'trend' for statistical analysis",
            "semantic": "Ask descriptive questions; mention a region, month or sensor to narrow the search",
        },
    }
