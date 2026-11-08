import pytest
from sqlalchemy import text

from floatchat.sql_agent import TEMPLATES, SqlAgent, render_template

pytestmark = pytest.mark.integration


def no_llm(*a, **k):
    return None


@pytest.mark.parametrize("intent", sorted(TEMPLATES))
def test_every_template_runs(reader_engine, intent):
    sql, params = render_template(intent)
    df, status = SqlAgent(reader_engine, chat=no_llm).execute_sql_query(sql, params)
    assert status == "success" and not df.empty


def test_region_filter_restricts_a_template(reader_engine, loaded_db):
    agent = SqlAgent(reader_engine, chat=no_llm)
    everywhere, _ = agent.run("What is the average temperature at different depths?")
    arabian, error = agent.run("What is the average temperature at different depths?", filters={"region": "Arabian Sea"})
    assert error is None and ":region" in arabian["sql_query"]
    with loaded_db.connect() as conn:
        expected = conn.execute(text(
            "SELECT COUNT(*) FROM measurements m JOIN profiles p ON p.profile_id = m.profile_id "
            "WHERE p.region = 'Arabian Sea' AND m.temperature IS NOT NULL AND m.salinity IS NOT NULL")).scalar()
    assert int(arabian["results"]["measurement_count"].sum()) == expected
    assert int(everywhere["results"]["measurement_count"].sum()) > expected


def test_regional_comparison_ignores_the_region_filter(reader_engine):
    # "Compare the Arabian Sea and the Bay of Bengal" names regions, but the answer must still compare them all
    result, _ = SqlAgent(reader_engine, chat=no_llm).run("Compare surface temperature across ocean regions",
                                                         filters={"region": "Arabian Sea"})
    assert len(result["results"]) > 1


def test_filters_with_no_matching_data_report_no_results(reader_engine):
    result, error = SqlAgent(reader_engine, chat=no_llm).run("What is the average temperature at different depths?",
                                                             filters={"year": 2030})
    assert result is None and "no results" in error


def test_custom_question_uses_llm_sql(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "```sql\nSELECT region, COUNT(*) AS n FROM profiles GROUP BY region\n```")
    result, error = agent.run("How many profiles were recorded?")
    assert error is None and result["intent"] == "custom" and "LIMIT 1000" in result["sql_query"]


def test_unsafe_llm_sql_is_refused(reader_engine):
    agent = SqlAgent(reader_engine, chat=lambda *a, **k: "DELETE FROM profiles")
    result, error = agent.run("How many profiles were recorded?")
    assert result is None and "unsafe" in error


def test_no_llm_means_no_custom_sql(reader_engine):
    result, error = SqlAgent(reader_engine, chat=no_llm).run("How many profiles were recorded?")
    assert result is None and error == "Failed to generate SQL"
