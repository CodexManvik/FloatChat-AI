"""
Integration tests need PostgreSQL with pgvector. Locally: `docker compose up -d db`.
They are skipped when no database is reachable, unless FLOATCHAT_REQUIRE_DB=1 (CI).
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from floatchat.db.engine import apply_schema, make_engine, reset_schema

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL",
                      "postgresql+psycopg://floatchat:floatchat@localhost:5433/floatchat_test")
READER_PASSWORD = "reader_test_password"


def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    server = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with server.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"),
                                  {"name": parsed.database}).first()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{parsed.database}"')
    finally:
        server.dispose()


@pytest.fixture(scope="session")
def admin_engine():
    try:
        _ensure_database(ADMIN_URL)
        engine = make_engine(ADMIN_URL)
        engine.connect().close()
    except Exception as e:
        if os.getenv("FLOATCHAT_REQUIRE_DB"):
            raise
        pytest.skip(f"No test database available: {e}")
    yield engine
    engine.dispose()


@pytest.fixture
def empty_db(admin_engine):
    reset_schema(admin_engine)
    apply_schema(admin_engine)
    yield admin_engine
