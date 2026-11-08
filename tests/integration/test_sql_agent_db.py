import pytest

from floatchat.sql_agent import TEMPLATES, SqlAgent

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("intent", sorted(TEMPLATES))
def test_every_template_runs(reader_engine, intent):
    df, status = SqlAgent(reader_engine, chat=lambda *a, **k: None).execute_sql_query(TEMPLATES[intent])
    assert status == "success" and not df.empty


def test_custom_question_uses_llm_sql(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "```sql\nSELECT region, COUNT(*) AS n FROM profiles GROUP BY region\n```")
    result, error = agent.run("How many profiles were recorded?")
    assert error is None and result["intent"] == "custom" and "LIMIT 1000" in result["sql_query"]


def test_unsafe_llm_sql_is_refused(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "DELETE FROM profiles")
    result, error = agent.run("How many profiles were recorded?")
    assert result is None and "unsafe" in error


def test_no_llm_means_no_custom_sql(reader_engine):
    result, error = SqlAgent(reader_engine, chat=lambda *a, **k: None).run("How many profiles were recorded?")
    assert result is None and error == "Failed to generate SQL"
