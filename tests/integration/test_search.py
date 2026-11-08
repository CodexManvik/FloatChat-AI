import pytest

from floatchat.search import search_profiles
from tests.fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def query_vector(text="profiles"):
    return FakeEmbedder().embed([text])[0]


def test_returns_limit_and_keys(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {}, limit=5)
    assert len(results) == 5
    assert {"profile_id", "float_id", "date", "lat", "lon", "region", "has_oxygen", "description",
            "distance"} <= set(results[0])
    assert results == sorted(results, key=lambda r: r["distance"])


def test_region_filter(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {"region": "Arabian Sea"})
    assert results and all(r["region"] == "Arabian Sea" for r in results)


def test_month_filter(reader_engine):
    month = search_profiles(reader_engine, query_vector(), {}, limit=1)[0]["month_num"]
    results = search_profiles(reader_engine, query_vector(), {"month_num": month})
    assert results and all(int(r["date"][5:7]) == month for r in results)


def test_sensor_filter(reader_engine):
    results = search_profiles(reader_engine, query_vector(), {"has_oxygen": True})
    assert results and all(r["has_oxygen"] for r in results)


def test_unknown_filter_keys_are_ignored_and_no_match_is_empty(reader_engine):
    assert search_profiles(reader_engine, query_vector(), {"region": "Atlantis", "evil": "1; DROP"}) == []
