"""
Decide how to answer a question: SQL (and which kind) or profile search, with which filters.

The LLM router understands free phrasing and follow-ups; its JSON reply is validated, and the keyword router
takes over whenever no LLM is available or its reply is unusable.
"""

import json
import re
from dataclasses import dataclass, field

from floatchat.filters import FILTER_KEYS, REGION_NAMES, clean_filters
from floatchat.regions import parse_filters
from floatchat.sql_agent import TEMPLATES, SqlAgent

INTENTS = tuple(TEMPLATES) + ("custom",)
FOLLOW_UP_CUES = re.compile(r"^\s*(now|and|also|then|but|only|just|same|instead|what about|how about)\b", re.I)
HISTORY_TURNS = 3

INTENT_HELP = {
    "avg_by_depth": "average temperature/salinity at each depth",
    "regional_comparison": "compare the regions (upper 100 m)",
    "depth_ranges": "averages by depth layer (surface, intermediate, deep)",
    "temporal_trends": "monthly averages over time",
    "float_summary": "a table with one row per float (its profile count, averages, depth), e.g. most active floats",
    "bgc_analysis": "oxygen, chlorophyll, nitrate or pH by ocean zone",
    "custom": "any other statistical question that needs its own SQL, including a single number such as a count, "
              "total, maximum or minimum (e.g. 'how many profiles…', 'what was the highest temperature…')",
}


@dataclass
class Route:
    path: str                     # "analytical" (SQL) or "semantic" (profile search)
    intent: str | None            # one of INTENTS for SQL, None for search
    filters: dict = field(default_factory=dict)
    question: str = ""            # standalone question (follow-ups resolved)
    source: str = "keywords"      # "llm" or "keywords"


def keyword_route(question: str, history: list[dict] | None = None) -> Route:
    filters = clean_filters(parse_filters(question))
    if SqlAgent.is_analytical_query(question):
        return Route("analytical", SqlAgent.detect_query_intent(question), filters, question)
    previous = (history or [])[-1] if history else None
    if previous and FOLLOW_UP_CUES.search(question) and (filters or previous.get("query_type") == "semantic"):
        merged = {**clean_filters(previous.get("filters")), **filters}
        standalone = f"{previous.get('question', '')} ({question.strip()})"
        if previous.get("query_type") == "analytical" and previous.get("intent") in INTENTS:
            return Route("analytical", previous["intent"], merged, standalone)
        return Route("semantic", None, merged, standalone)
    return Route("semantic", None, filters, question)


def _prompt(question: str, history: list[dict]) -> str:
    turns = "\n".join(
        f"- {t.get('question')} -> {t.get('query_type')}, intent={t.get('intent')}, filters={json.dumps(t.get('filters') or {})}"
        for t in history[-HISTORY_TURNS:]
    ) or "(none)"
    intents = "\n".join(f"- {name}: {text}" for name, text in INTENT_HELP.items())
    return (
        "Route a question about Argo ocean-float data (Indian Ocean, temperature, salinity, oxygen, chlorophyll, "
        "nitrate, pH). Reply with JSON only:\n"
        '{"path": "analytical" | "semantic", "intent": <intent or null>, "filters": {...}, "question": <standalone>}\n\n'
        "path=analytical for statistics (averages, comparisons, counts, trends) answered with SQL; "
        "path=semantic for finding or describing particular profiles or floats.\n"
        "A request to see, find or list profiles is semantic even when it names a place or a date "
        "(e.g. 'Profiles off Sri Lanka in June 2026'). Use analytical only when the question asks for a number, "
        "a comparison, a trend or a summary table.\n"
        f"Intents (analytical only):\n{intents}\n"
        f"Filter keys: {', '.join(FILTER_KEYS)}. region is one of: {', '.join(sorted(REGION_NAMES))}. "
        "month_num is 1-12; has_* filters are true when the question is about that sensor.\n"
        "If the question follows up on the previous turn (e.g. 'now only the Arabian Sea'), keep its path and "
        "intent, merge the filters, and write the full standalone question.\n\n"
        f"Previous turns:\n{turns}\n\nQuestion: {question}"
    )


def llm_route(question: str, history: list[dict], chat) -> Route | None:
    reply = chat(_prompt(question, history or []), temperature=0.0, max_tokens=600, json_mode=True)
    if not reply:
        return None
    try:
        data = json.loads(re.sub(r"^```(json)?|```$", "", reply.strip()).strip())
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("path") not in ("analytical", "semantic"):
        return None
    filters = clean_filters(data.get("filters") if isinstance(data.get("filters"), dict) else {})
    standalone = data.get("question") if isinstance(data.get("question"), str) and data["question"].strip() else question
    if data["path"] == "analytical":
        intent = data.get("intent") if data.get("intent") in INTENTS else "custom"
        return Route("analytical", intent, filters, standalone, "llm")
    return Route("semantic", None, filters, standalone, "llm")


def route(question: str, history: list[dict] | None, chat, use_llm: bool) -> Route:
    history = (history or [])[-HISTORY_TURNS:]
    if use_llm:
        decided = llm_route(question, history, chat)
        if decided:
            return decided
    return keyword_route(question, history)
