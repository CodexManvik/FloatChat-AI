import pytest

from floatchat.sql_agent import TEMPLATES, SqlAgent


@pytest.mark.parametrize("question,expected_intent", [
    ("What is the average temperature at different depths?", "avg_by_depth"),
    ("Show average salinity by depth range", "depth_ranges"),
    ("Compare surface temperature across ocean regions", "regional_comparison"),
    ("Average dissolved oxygen by ocean zone", "bgc_analysis"),
    ("Average chlorophyll by ocean zone", "bgc_analysis"),
    ("Show the monthly temperature trend", "temporal_trends"),
    ("Show a summary for each float", "float_summary"),
    ("How many profiles were recorded?", "custom"),
])
def test_analytical_routing(question, expected_intent):
    assert SqlAgent.is_analytical_query(question)
    assert SqlAgent.detect_query_intent(question) == expected_intent


@pytest.mark.parametrize("question", [
    "Show me salinity profiles near the equator in March 2024",
    "Tell me about floats in the Bay of Bengal",
    "What does a depth profile look like?",
])
def test_descriptive_questions_use_search(question):
    assert not SqlAgent.is_analytical_query(question)


@pytest.mark.parametrize("sql,safe", [
    ("SELECT depth, AVG(temperature) FROM measurements GROUP BY depth", True),
    ("WITH x AS (SELECT 1) SELECT * FROM x", True),
    ("SELECT created_at FROM floats", True),
    ("SELECT 1;", True),
    ("DROP TABLE floats", False),
    ("SELECT 1; DELETE FROM measurements", False),
    ("UPDATE floats SET status = 'x'", False),
    ("SELECT pg_read_file('/etc/passwd')", False),
])
def test_validate_sql(sql, safe):
    assert SqlAgent.validate_sql(sql) == safe


def test_every_template_is_safe():
    assert all(SqlAgent.validate_sql(sql) for sql in TEMPLATES.values())
