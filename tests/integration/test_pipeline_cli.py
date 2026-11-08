from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.__main__ import run_backfill, run_refresh, run_snapshot
from pipeline.erddap import BGC, CORE, apply_qc, fetch_window
from tests.fakes import FakeEmbedder
from tests.integration.conftest import SEED_SMALL
from tests.unit.test_shape import BBOX, fixture_get

pytestmark = pytest.mark.integration


def fake_fetch(start, end, bbox):
    core = apply_qc(fetch_window(CORE, start, end, BBOX, get=fixture_get), CORE)
    bgc = apply_qc(fetch_window(BGC, start, end, BBOX, get=fixture_get), BGC)
    return core, bgc


def runs(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT kind, status FROM ingest_runs ORDER BY run_id")).all()


def test_snapshot_loads_and_records_a_run(empty_db):
    result = run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)
    expected = pd.read_csv(SEED_SMALL).groupby(["wmo_id", "cycle_number"]).ngroups
    assert result == {"added": expected, "removed": 0}
    assert runs(empty_db) == [("snapshot", "success")]


def test_snapshot_if_empty_skips_second_load(empty_db):
    run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)
    embedder = FakeEmbedder()
    assert run_snapshot(empty_db, embedder, SEED_SMALL, if_empty=True) == {"added": 0, "removed": 0}
    assert embedder.calls == 0


def test_snapshot_resets_an_old_schema(empty_db):
    with empty_db.begin() as conn:
        conn.exec_driver_sql("DROP TABLE profiles CASCADE")
        conn.exec_driver_sql("CREATE TABLE profiles (profile_id SERIAL PRIMARY KEY, float_id TEXT)")
    assert run_snapshot(empty_db, FakeEmbedder(), SEED_SMALL)["added"] > 0


def test_backfill_with_fake_fetch_prunes_by_window(empty_db):
    # The fixture data is from 2024, older than the 365-day window, so it is loaded then pruned
    result = run_backfill(empty_db, FakeEmbedder(), datetime(2024, 1, 1), datetime(2024, 3, 1), fetch=fake_fetch)
    assert result == {"added": 2, "removed": 2}
    assert runs(empty_db)[-1] == ("backfill", "success")


def test_backfill_keeps_finished_months_when_a_later_month_fails(empty_db):
    def fetch_failing_in_february(start, end, bbox):
        if start >= datetime(2024, 2, 1):
            raise RuntimeError("ERDDAP refused the connection")
        core, bgc = fake_fetch(start, end, bbox)
        in_window = lambda df: df[pd.to_datetime(df["time"]).dt.tz_localize(None) < end]  # noqa: E731
        return in_window(core), in_window(bgc)

    with pytest.raises(RuntimeError, match="refused"):
        run_backfill(empty_db, FakeEmbedder(), datetime(2024, 1, 1), datetime(2024, 3, 1),
                     fetch=fetch_failing_in_february, chunk_days=31)
    with empty_db.connect() as conn:
        floats = conn.execute(text("SELECT float_id FROM profiles")).scalars().all()
        run = conn.execute(text("SELECT status, profiles_added FROM ingest_runs ORDER BY run_id DESC")).first()
    assert floats == ["5905498"]  # January's profile was saved before February failed
    assert tuple(run) == ("failed", 1)


def test_backfill_fetches_month_by_month(empty_db):
    windows = []

    def recording_fetch(start, end, bbox):
        windows.append((start, end))
        return fake_fetch(start, end, bbox)

    run_backfill(empty_db, FakeEmbedder(), datetime(2024, 1, 1), datetime(2024, 3, 1),
                 fetch=recording_fetch, chunk_days=31)
    assert windows == [(datetime(2024, 1, 1), datetime(2024, 2, 1)), (datetime(2024, 2, 1), datetime(2024, 3, 1))]


def test_failed_refresh_is_recorded(empty_db):
    def broken_fetch(start, end, bbox):
        raise RuntimeError("ERDDAP down")

    with pytest.raises(RuntimeError, match="ERDDAP down"):
        run_refresh(empty_db, FakeEmbedder(), fetch=broken_fetch)
    assert runs(empty_db)[-1] == ("refresh", "failed")
