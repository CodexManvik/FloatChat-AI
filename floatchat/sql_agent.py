"""
Statistical questions -> SQL. Common question types use hand-written templates;
anything else is written by the LLM and must pass a read-only check. The API's
database role is read-only as well, so a bad query can never change data.
"""

import logging
import re
from collections.abc import Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from floatchat import llm

logger = logging.getLogger(__name__)
ChatFn = Callable[..., str | None]

ZONE_CASE = ("CASE WHEN depth < 200 THEN 'Euphotic Zone' WHEN depth < 1000 THEN 'Mesopelagic Zone' "
             "ELSE 'Bathypelagic Zone' END")
LAYER_CASE = ("CASE WHEN depth < 100 THEN 'Surface (0-100m)' WHEN depth < 500 THEN 'Intermediate (100-500m)' "
              "WHEN depth < 1000 THEN 'Deep (500-1000m)' ELSE 'Very Deep (>1000m)' END")

TEMPLATES = {
    "avg_by_depth": """
        SELECT depth, AVG(temperature) AS avg_temperature, AVG(salinity) AS avg_salinity,
               COUNT(*) AS measurement_count
        FROM measurements
        WHERE temperature IS NOT NULL AND salinity IS NOT NULL
        GROUP BY depth ORDER BY depth LIMIT 100""",
    "regional_comparison": """
        SELECT p.region, AVG(m.temperature) AS avg_temperature, AVG(m.salinity) AS avg_salinity,
               AVG(m.oxygen) AS avg_oxygen, COUNT(DISTINCT p.profile_id) AS profile_count,
               COUNT(*) AS measurement_count
        FROM measurements m JOIN profiles p ON m.profile_id = p.profile_id
        WHERE m.temperature IS NOT NULL AND m.depth <= 100
        GROUP BY p.region ORDER BY avg_temperature DESC""",
    "depth_ranges": f"""
        SELECT {LAYER_CASE} AS depth_range, AVG(temperature) AS avg_temperature, AVG(salinity) AS avg_salinity,
               AVG(oxygen) AS avg_oxygen, COUNT(*) AS measurement_count
        FROM measurements WHERE temperature IS NOT NULL
        GROUP BY 1 ORDER BY MIN(depth)""",
    "float_summary": """
        SELECT f.float_id, f.wmo_id, f.deployment_date, COUNT(DISTINCT p.profile_id) AS total_profiles,
               COUNT(m.id) AS total_measurements, AVG(m.temperature) AS avg_temperature,
               AVG(m.salinity) AS avg_salinity, MIN(m.depth) AS min_depth, MAX(m.depth) AS max_depth
        FROM floats f
        JOIN profiles p ON f.float_id = p.float_id
        JOIN measurements m ON p.profile_id = m.profile_id
        WHERE m.temperature IS NOT NULL
        GROUP BY f.float_id, f.wmo_id, f.deployment_date
        ORDER BY total_measurements DESC LIMIT 50""",
    "temporal_trends": """
        SELECT DATE_TRUNC('month', time) AS month, AVG(temperature) AS avg_temperature,
               AVG(salinity) AS avg_salinity, COUNT(*) AS measurement_count
        FROM measurements WHERE temperature IS NOT NULL
        GROUP BY 1 ORDER BY month LIMIT 100""",
    "bgc_analysis": f"""
        SELECT {ZONE_CASE} AS ocean_zone, AVG(oxygen) AS avg_oxygen, MIN(oxygen) AS min_oxygen,
               MAX(oxygen) AS max_oxygen, AVG(chlorophyll) AS avg_chlorophyll, AVG(nitrate) AS avg_nitrate,
               AVG(ph) AS avg_ph, COUNT(*) AS measurement_count
        FROM measurements
        WHERE oxygen IS NOT NULL OR chlorophyll IS NOT NULL OR nitrate IS NOT NULL OR ph IS NOT NULL
        GROUP BY 1 ORDER BY MIN(depth)""",
}

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

    def generate_sql(self, question: str) -> tuple[str | None, str]:
        intent = self.detect_query_intent(question)
        if intent in TEMPLATES:
            return TEMPLATES[intent].strip(), intent
        prompt = (
            "You are an expert PostgreSQL analyst for Argo ocean float data.\n"
            f"{SCHEMA_PROMPT}\n"
            "Rules: one read-only SELECT statement; meaningful column aliases; handle NULLs; "
            "at most 1000 rows; ORDER BY for readable output.\n\n"
            f"Question: {question}\n"
            "Return ONLY the SQL, no explanation and no code fences."
        )
        sql = self.chat(prompt, temperature=0.0)
        if not sql:
            return None, "error"
        sql = re.sub(r"```(sql)?", "", sql).strip().rstrip(";")
        if "limit" not in sql.lower():
            sql += " LIMIT 1000"
        return sql, "custom"

    def execute_sql_query(self, sql: str) -> tuple[pd.DataFrame, str]:
        if not self.validate_sql(sql):
            return pd.DataFrame(), "Invalid or unsafe SQL query"
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(sql), conn)
        except Exception as e:
            logger.info("SQL failed: %s", e)
            return pd.DataFrame(), f"Database error: {e.__class__.__name__}"
        if df.empty:
            return df, "Query executed successfully but returned no results"
        return df, "success"

    def run(self, question: str) -> tuple[dict | None, str | None]:
        if not self.is_analytical_query(question):
            return None, "Not an analytical query"
        sql, intent = self.generate_sql(question)
        if not sql:
            return None, "Failed to generate SQL"
        df, status = self.execute_sql_query(sql)
        if status != "success":
            return None, f"SQL execution failed: {status}"
        return {"sql_query": sql, "results": df, "intent": intent, "summary_stats": _summary_stats(df)}, None


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
