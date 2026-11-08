import pytest

from floatchat.answer import answer_question
from floatchat.sql_agent import SqlAgent
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def ask(engine, question, chat=lambda *a, **k: None):
    return answer_question(question, engine=engine, embedder_factory=FakeEmbedder,
                           agent=SqlAgent(engine, chat=chat), chat=chat)


def test_analytical_answer(reader_engine):
    result = ask(reader_engine, "What is the average temperature at different depths?")
    assert result["query_type"] == "analytical" and result["intent"] == "avg_by_depth"
    assert result["answer"].startswith("**Average temperature and salinity at each depth**")
    assert result["sql_results"] and result["retrieved_metadata"][0]["row_count"] > 0
    assert result["llm_used"] is False


def test_analytical_answer_applies_the_question_filters(reader_engine):
    result = ask(reader_engine, "What is the average temperature at different depths in the Arabian Sea?")
    assert result["answer"].startswith("**Average temperature and salinity at each depth in the Arabian Sea**")
    assert result["retrieved_metadata"][0]["filters"] == {"region": "Arabian Sea"}
    assert ":region" in result["retrieved_metadata"][0]["sql_query"]


def test_semantic_answer_with_region_filter(reader_engine):
    result = ask(reader_engine, "Show me profiles in the Arabian Sea")
    assert result["query_type"] == "semantic"
    assert all(m["region"] == "Arabian Sea" for m in result["retrieved_metadata"])
    assert result["answer"].startswith("Here are the")


def test_semantic_answer_falls_back_when_filters_match_nothing(reader_engine):
    result = ask(reader_engine, "profiles in the Arabian Sea in December 2030")
    assert result["answer"].startswith("No profiles were recorded in the Arabian Sea in December 2030")
    assert result["retrieved_metadata"]


def test_llm_text_is_used_when_available(reader_engine):
    result = ask(reader_engine, "Show me profiles in the Arabian Sea", chat=lambda *a, **k: "MOCK ANSWER")
    assert result["answer"] == "MOCK ANSWER" and result["llm_used"] is True
