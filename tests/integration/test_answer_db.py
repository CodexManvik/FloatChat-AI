import pytest

from floatchat.answer import answer_question
from floatchat.sql_agent import SqlAgent
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def ask(engine, question, chat=lambda *a, **k: None, **kwargs):
    return answer_question(question, engine=engine, embedder_factory=FakeEmbedder,
                           agent=SqlAgent(engine, chat=chat), chat=chat, **kwargs)


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
    assert result["filters"] == {"region": "Arabian Sea"}
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


def test_steps_describe_what_happened(reader_engine):
    result = ask(reader_engine, "What is the average temperature at different depths in the Arabian Sea?")
    steps = result["steps"]
    assert [s["step"] for s in steps] == ["understood", "sql", "answer"]
    assert steps[0]["path"] == "analytical" and steps[0]["router"] == "keywords"
    assert steps[1]["status"] == "success" and steps[1]["rows"] > 0
    search_steps = ask(reader_engine, "Show me profiles in the Arabian Sea")["steps"]
    assert [s["step"] for s in search_steps] == ["understood", "search", "answer"]
    assert search_steps[1]["matches"] > 0


def test_streamed_tokens_add_up_to_the_answer(reader_engine):
    events = []

    def stream_chat(prompt, **kwargs):
        yield from ["Mock ", "streamed ", "insight."]

    for question in ("What is the average temperature at different depths?", "Show me profiles in the Arabian Sea"):
        events.clear()
        result = ask(reader_engine, question, emit=events.append, stream_chat=stream_chat)
        tokens = "".join(e["text"] for e in events if e["type"] == "token")
        assert tokens == result["answer"] and "Mock streamed insight." in result["answer"]
        assert result["llm_used"] is True
        assert [e["step"] for e in events if e["type"] == "step"] == [s["step"] for s in result["steps"]]


def test_follow_up_uses_the_history(reader_engine):
    first = ask(reader_engine, "What is the average temperature at different depths?")
    turn = {"question": "What is the average temperature at different depths?", "query_type": first["query_type"],
            "intent": first["intent"], "filters": first["filters"]}
    follow_up = ask(reader_engine, "now only the Arabian Sea", history=[turn])
    assert follow_up["intent"] == "avg_by_depth" and follow_up["filters"] == {"region": "Arabian Sea"}
    assert follow_up["answer"].startswith("**Average temperature and salinity at each depth in the Arabian Sea**")
