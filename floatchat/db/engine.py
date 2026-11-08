from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
TABLES = ("query_log", "ingest_runs", "measurements", "profiles", "floats")


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def apply_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_PATH.read_text(encoding="utf-8"))


def reset_schema(engine: Engine) -> None:
    """Drop every FloatChat table (data is reloaded by the pipeline)."""
    with engine.begin() as conn:
        for table in TABLES:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE")


def schema_is_current(engine: Engine) -> bool:
    """False only when an older FloatChat schema (no embedding column) is present."""
    with engine.connect() as conn:
        columns = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'profiles'"
        )).scalars().all()
    return not columns or "embedding" in columns
