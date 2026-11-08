import pytest
from sqlalchemy import text

from floatchat.db import queries

pytestmark = pytest.mark.integration


def test_stats(reader_engine):
    stats = queries.get_stats(reader_engine)
    assert stats["profiles"] > 30 and stats["floats"] > 0 and stats["measurements"] > 0
    assert stats["bgc_floats"] >= 1
    assert stats["last_updated"] is not None
    assert {r["region"] for r in stats["regions"]} >= {"Arabian Sea"}


def test_floats_shape(reader_engine):
    floats = queries.get_floats(reader_engine)
    assert set(floats[0]) == {"float_id", "last_profile", "lat", "lon", "region", "n_profiles",
                              "surface_temperature", "surface_salinity", "is_bgc"}
    assert any(f["is_bgc"] for f in floats)


def test_profiles_by_profile_and_measurement_id(reader_engine):
    rows = queries.get_profiles(reader_engine, [], [1])
    assert rows and {r["profile_id"] for r in rows} == {1}
    assert {"chlorophyll", "nitrate", "ph", "oxygen", "region"} <= set(rows[0])
    by_measurement = queries.get_profiles(reader_engine, [rows[0]["id"]], [])
    assert len(by_measurement) == len(rows)  # the whole profile comes back


def test_float_info_and_trajectory(reader_engine):
    float_id = queries.get_floats(reader_engine)[0]["float_id"]
    info = queries.get_float_info(reader_engine, float_id)
    assert info["float_info"]["float_id"] == float_id
    track = queries.get_float_profiles(reader_engine, float_id)
    assert track and "embedding" not in track[0] and "profile_lat" in track[0]
    assert queries.get_float_info(reader_engine, "nope") is None


def test_data_status(reader_engine):
    status = queries.data_status(reader_engine)
    assert status["indexed_profiles"] == queries.get_stats(reader_engine)["profiles"]
    assert status["latest_run_id"] >= 1 and status["newest_data"] is not None


def test_log_query_as_reader(reader_engine, loaded_db):
    queries.log_query(reader_engine, question="hello", query_type="semantic", intent=None,
                      latency_ms=12, success=True, cached=False, llm_used=False)
    with loaded_db.connect() as conn:
        assert conn.execute(text("SELECT question FROM query_log")).scalar() == "hello"


def test_log_query_never_raises(reader_engine):
    queries.log_query(reader_engine, question="x" * 10, query_type="semantic", intent="i" * 500,
                      latency_ms=1, success=True, cached=False, llm_used=False)  # intent too long: swallowed
