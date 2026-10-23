"""
Tests for the FloatChat core logic that doesn't need a database:
region labelling, question filters, query routing and SQL safety checks.
"""

import pytest

from nl_to_sql import NLToSQLTranslator
from ocean_regions import parse_filters, region_for

# These methods don't touch the database, so no translator instance is needed
is_analytical = lambda q: NLToSQLTranslator.is_analytical_query(None, q)
intent = lambda q: NLToSQLTranslator.detect_query_intent(None, q)
is_safe = lambda sql: NLToSQLTranslator.validate_sql(None, sql)


@pytest.mark.parametrize("lat,lon,expected", [
    (0.5, 70, "Equatorial Indian Ocean"),
    (15, 65, "Arabian Sea"),
    (15, 88, "Bay of Bengal"),
    (13, 45, "Red Sea & Gulf of Aden"),
    (-30, 60, "Southern Indian Ocean"),
    (-20, 110, "Eastern Indian Ocean"),
])
def test_region_for(lat, lon, expected):
    assert region_for(lat, lon) == expected


def test_parse_filters():
    assert parse_filters("salinity profiles near the equator in March 2024") == {
        "region": "Equatorial Indian Ocean", "month_num": 3, "year": 2024}
    assert parse_filters("low oxygen in the Arabian Sea") == {"region": "Arabian Sea", "has_oxygen": True}
    assert parse_filters("tell me about floats") == {}


@pytest.mark.parametrize("question,expected_intent", [
    ("What is the average temperature at different depths?", "avg_by_depth"),
    ("Show average salinity by depth range", "depth_ranges"),
    ("Compare surface temperature across ocean regions", "regional_comparison"),
    ("Average dissolved oxygen by ocean zone", "bgc_analysis"),
    ("Show the monthly temperature trend", "temporal_trends"),
    ("Show a summary for each float", "float_summary"),
])
def test_analytical_routing(question, expected_intent):
    assert is_analytical(question)
    assert intent(question) == expected_intent


@pytest.mark.parametrize("question", [
    "Show me salinity profiles near the equator in March 2024",
    "Tell me about floats in the Bay of Bengal",
])
def test_descriptive_questions_use_search(question):
    assert not is_analytical(question)


@pytest.mark.parametrize("sql,safe", [
    ("SELECT depth, AVG(temperature) FROM measurements GROUP BY depth", True),
    ("WITH x AS (SELECT 1) SELECT * FROM x", True),
    ("SELECT created_at FROM floats", True),
    ("DROP TABLE floats", False),
    ("SELECT 1; DELETE FROM measurements", False),
    ("UPDATE floats SET status = 'x'", False),
])
def test_validate_sql(sql, safe):
    assert is_safe(sql) == safe
