import pytest
from sqlalchemy import create_engine, text

from floatchat.search import search_profiles
from tests.fakes import FakeEmbedder
from tests.integration.conftest import ADMIN_URL

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


def test_filtered_search_finds_every_match_even_when_the_index_would_miss(loaded_db):
    # In production (20k profiles) the HNSW index returned only its nearest candidates and the filters then
    # removed all of them, so "low oxygen in the Arabian Sea" found nothing. Force the index and a tiny
    # candidate list to reproduce that on the small fixture.
    forced_index = create_engine(ADMIN_URL, connect_args={"options": "-c enable_seqscan=off"})
    try:
        with loaded_db.connect() as conn:
            expected = conn.execute(text("SELECT COUNT(*) FROM profiles WHERE has_oxygen")).scalar()
        results = search_profiles(forced_index, query_vector(), {"has_oxygen": True}, limit=50, ef_search=1)
        assert expected > 1 and len(results) == expected
    finally:
        forced_index.dispose()


def test_invalid_filters_are_dropped_and_no_match_is_empty(reader_engine):
    unfiltered = search_profiles(reader_engine, query_vector(), {})
    assert search_profiles(reader_engine, query_vector(), {"region": "Atlantis", "evil": "1; DROP"}) == unfiltered
    assert search_profiles(reader_engine, query_vector(), {"year": 2030}) == []
