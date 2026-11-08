import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from floatchat.db.engine import apply_schema, make_engine, schema_is_current
from floatchat.db.roles import create_reader_role, reader_url
from tests.integration.conftest import ADMIN_URL, READER_PASSWORD

pytestmark = pytest.mark.integration


def test_schema_is_idempotent(empty_db):
    apply_schema(empty_db)  # second application must not fail
    with empty_db.connect() as conn:
        tables = set(conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).scalars())
    assert {"floats", "profiles", "measurements", "ingest_runs", "query_log"} <= tables
    assert schema_is_current(empty_db)


def test_old_schema_is_detected(empty_db):
    with empty_db.begin() as conn:
        conn.exec_driver_sql("DROP TABLE profiles CASCADE")
        conn.exec_driver_sql("CREATE TABLE profiles (profile_id SERIAL PRIMARY KEY, float_id TEXT)")
    assert not schema_is_current(empty_db)


def test_reader_role_is_read_only(empty_db):
    create_reader_role(empty_db, READER_PASSWORD)
    reader = make_engine(reader_url(ADMIN_URL, READER_PASSWORD))
    try:
        with reader.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar() == 0
        with pytest.raises(DBAPIError):
            with reader.begin() as conn:
                conn.execute(text("DELETE FROM profiles"))
        with reader.begin() as conn:  # the API may append to query_log
            conn.execute(text("INSERT INTO query_log (question) VALUES ('test')"))
        with pytest.raises(DBAPIError):
            with reader.connect() as conn:
                conn.execute(text("SELECT question FROM query_log"))
    finally:
        reader.dispose()


def test_reader_statement_timeout(empty_db):
    create_reader_role(empty_db, READER_PASSWORD)
    reader = make_engine(reader_url(ADMIN_URL, READER_PASSWORD))
    try:
        with pytest.raises(DBAPIError, match="statement timeout"):
            with reader.connect() as conn:
                conn.execute(text("SELECT pg_sleep(6)"))
    finally:
        reader.dispose()
