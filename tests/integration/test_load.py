from datetime import datetime

import pytest
from sqlalchemy import text

from pipeline.load import finish_run, load_tables, profile_count, prune, start_run
from pipeline.shape import build_tables, to_seed
from tests.fakes import FakeEmbedder
from tests.unit.test_shape import load_fixture_frames

pytestmark = pytest.mark.integration


def fixture_tables():
    return build_tables(to_seed(*load_fixture_frames()))


def scalar(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


def test_load_inserts_everything(empty_db):
    added = load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    assert added == 2
    assert profile_count(empty_db) == 2
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements") == 23
    assert scalar(empty_db, "SELECT COUNT(*) FROM profiles WHERE embedding IS NOT NULL") == 2
    assert scalar(empty_db, "SELECT COUNT(*) FROM profiles WHERE description LIKE 'ARGO float%'") == 2
    assert scalar(empty_db, "SELECT has_chlorophyll FROM profiles WHERE float_id = '2902203'") is True
    assert scalar(empty_db, "SELECT deployment_date::text FROM floats WHERE float_id = '2902203'") == "2024-02-11"
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements WHERE chlorophyll IS NOT NULL") > 0


def test_load_is_idempotent(empty_db):
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    embedder = FakeEmbedder()
    assert load_tables(empty_db, *fixture_tables(), embedder) == 0
    assert embedder.calls == 0
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements") == 23


def test_prune_removes_old_profiles_and_orphan_floats(empty_db):
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    removed = prune(empty_db, before=datetime(2024, 2, 1))  # 5905498's only profile is from 1 Jan 2024
    assert removed == 1
    assert scalar(empty_db, "SELECT COUNT(*) FROM floats") == 1
    assert scalar(empty_db, "SELECT COUNT(*) FROM measurements WHERE float_id = '5905498'") == 0


def test_runs_are_recorded(empty_db):
    run_id = start_run(empty_db, "snapshot")
    load_tables(empty_db, *fixture_tables(), FakeEmbedder())
    finish_run(empty_db, run_id, "success", 2, 0)
    with empty_db.connect() as conn:
        row = conn.execute(text("SELECT kind, status, profiles_added, newest_profile_date::date::text, "
                                "finished_at IS NOT NULL FROM ingest_runs WHERE run_id = :id"), {"id": run_id}).one()
    assert tuple(row) == ("snapshot", "success", 2, "2024-02-11", True)
