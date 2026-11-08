"""Build the answer for a question: SQL results or matching profiles, optionally explained by the LLM."""

from collections.abc import Callable

import pandas as pd
from sqlalchemy.engine import Engine

from floatchat.db.queries import df_records
from floatchat.regions import MONTHS, parse_filters
from floatchat.search import search_profiles
from floatchat.sql_agent import SqlAgent

SYSTEM_PROMPT = (
    "You are FloatChat, an oceanography assistant for Argo float data in the Indian Ocean. "
    "Answer using only the facts in the provided context. Be concise (under 150 words), "
    "mention float IDs, dates and locations where relevant, and use Markdown bullet points. "
    "If the context does not answer the question, say so."
)
INTENT_TITLES = {
    "avg_by_depth": "Average temperature and salinity at each depth",
    "regional_comparison": "Upper-ocean (0–100 m) conditions by region",
    "depth_ranges": "Ocean conditions by depth layer",
    "temporal_trends": "Monthly averages",
    "float_summary": "Most active floats",
    "bgc_analysis": "Biogeochemistry by ocean zone",
}
SENSOR_NAMES = {"has_oxygen": "oxygen", "has_chlorophyll": "chlorophyll", "has_nitrate": "nitrate", "has_ph": "pH"}


def format_position(lat: float, lon: float) -> str:
    return f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"


def describe_filters(filters: dict) -> str:
    parts = []
    if "region" in filters:
        parts.append(f"in the {filters['region']}")
    if "month_num" in filters:
        parts.append(f"in {MONTHS[filters['month_num'] - 1].title()}")
    if "year" in filters:
        parts.append(str(filters["year"]))
    sensors = [name for key, name in SENSOR_NAMES.items() if filters.get(key)]
    if sensors:
        parts.append("from floats measuring " + " and ".join(sensors))
    return " ".join(parts)


def format_results_for_display(df: pd.DataFrame, intent: str) -> str:
    def fmt(row, col, unit, digits=2):
        value = row.get(col)
        return f"{value:.{digits}f}{unit}" if pd.notna(value) else "N/A"

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
            lines.append(f"- **{row['ocean_zone']}**: O₂ {fmt(row, 'avg_oxygen', ' µmol/kg', 1)}, "
                         f"chlorophyll {fmt(row, 'avg_chlorophyll', ' mg/m³', 3)}, "
                         f"nitrate {fmt(row, 'avg_nitrate', ' µmol/kg', 1)}, pH {fmt(row, 'avg_ph', '', 3)}")
    else:
        for _, row in df.head(10).iterrows():
            values = ", ".join(f"{col.replace('_', ' ')}: {val:.2f}" if isinstance(val, float)
                               else f"{col.replace('_', ' ')}: {val}" for col, val in row.items() if pd.notna(val))
            lines.append(f"- {values}")
    if len(df) > len(lines):
        lines.append(f"- *…and {len(df) - len(lines)} more rows (see the chart and table)*")
    return "\n".join(lines)


def _analytical_answer(question: str, agent: SqlAgent, chat) -> dict | None:
    result, error = agent.run(question)
    if error:
        return None
    df, intent = result["results"], result["intent"]
    insight = chat(
        f"Question: {question}\n\nSQL result (first rows):\n{df.head(15).to_string(index=False)}\n\n"
        "In 2-3 sentences, explain the main oceanographic pattern in this result.",
        system=SYSTEM_PROMPT,
    )
    answer = f"**{INTENT_TITLES.get(intent, 'Query results')}**\n\n{format_results_for_display(df, intent)}"
    if insight:
        answer += f"\n\n**What this means:** {insight}"
    return {
        "answer": answer,
        "query_type": "analytical",
        "context_documents": [result["sql_query"]],
        "retrieved_metadata": [{"query_type": "analytical", "intent": intent, "sql_query": result["sql_query"],
                                "row_count": int(len(df)), "columns": [str(c) for c in df.columns],
                                "summary_stats": result["summary_stats"]}],
        "sql_results": df_records(df.head(200)),
        "intent": intent,
        "llm_used": bool(insight) or intent == "custom",
    }


def _semantic_answer(question: str, engine: Engine, embedder, chat) -> dict:
    filters = parse_filters(question)
    vector = embedder.embed([question])[0]
    matches = search_profiles(engine, vector, filters)
    note = ""
    if not matches and filters:
        note = (f"No profiles were recorded {describe_filters(filters)} in this dataset, "
                "so these are the closest matches overall.\n\n")
        matches = search_profiles(engine, vector, {})
    if not matches:
        return {"answer": "I couldn't find any matching Argo profiles.", "query_type": "semantic",
                "context_documents": [], "retrieved_metadata": [], "intent": None, "llm_used": False}

    documents = [m["description"] for m in matches]
    metadata = [{k: v for k, v in m.items() if k not in ("description", "distance")} for m in matches]
    context = "\n".join(f"- {doc}" for doc in documents)
    answer = chat(f"Context:\n{context}\n\nQuestion: {question}", system=SYSTEM_PROMPT)
    llm_used = bool(answer)
    if not answer:
        scope = f" {describe_filters(filters)}" if filters and not note else ""
        bullets = "\n".join(f"- **Float {m['float_id']}**, cycle {m['cycle_number']} · {m['date']} · "
                            f"{format_position(m['lat'], m['lon'])} ({m['region']})" for m in metadata)
        answer = (f"Here are the {len(metadata)} Argo profiles{scope} most relevant to your question:\n\n"
                  f"{bullets}\n\nTop match: {documents[0]}")
    return {"answer": note + answer, "query_type": "semantic", "context_documents": documents,
            "retrieved_metadata": metadata, "intent": None, "llm_used": llm_used}


def answer_question(question: str, *, engine: Engine, embedder_factory: Callable, agent: SqlAgent, chat) -> dict:
    if agent.is_analytical_query(question):
        analytical = _analytical_answer(question, agent, chat)
        if analytical:
            return analytical
    return _semantic_answer(question, engine, embedder_factory(), chat)
