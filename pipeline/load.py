"""Write pipeline output into Postgres: new profiles only, bulk COPY for measurements."""

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.describe import describe_profile
from pipeline.embed import embed_with_cache
from pipeline.shape import MEASUREMENT_VALUES

PROFILE_INSERT = """
    INSERT INTO profiles (float_id, cycle_number, profile_date, profile_lat, profile_lon, region, n_levels,
                          has_oxygen, has_chlorophyll, has_nitrate, has_ph, description, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
"""
FLOAT_INSERT = """
    INSERT INTO floats (float_id, wmo_id, deployment_date, deployment_lat, deployment_lon, last_contact)
    VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (float_id) DO NOTHING
"""
REFRESH_FLOATS = """
    WITH firsts AS (
        SELECT DISTINCT ON (float_id) float_id, profile_date, profile_lat, profile_lon
        FROM profiles ORDER BY float_id, profile_date
    ),
    lasts AS (SELECT float_id, MAX(profile_date) AS last_date FROM profiles GROUP BY float_id)
    UPDATE floats f
    SET deployment_date = firsts.profile_date::date, deployment_lat = firsts.profile_lat,
        deployment_lon = firsts.profile_lon, last_contact = lasts.last_date::date
    FROM firsts JOIN lasts USING (float_id)
    WHERE f.float_id = firsts.float_id
"""
MEASUREMENT_COLUMNS = ["profile_id", "float_id", "time", "lat", "lon", "depth", "pressure"] + MEASUREMENT_VALUES


def _python(value):
    """pandas/numpy scalar -> plain Python value psycopg can send (NaN/NaT -> None)."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.to_pydatetime()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value.item() if hasattr(value, "item") else value


def _rows(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    return [tuple(_python(v) for v in row) for row in df[columns].itertuples(index=False, name=None)]


def _vector_literal(vector) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def load_tables(engine: Engine, floats: pd.DataFrame, profiles: pd.DataFrame, measurements: pd.DataFrame,
                embedder, cache_path=None) -> int:
    raw = engine.raw_connection()
    pg = raw.driver_connection
    try:
        with pg.cursor() as cur:
            cur.execute("SELECT float_id, cycle_number FROM profiles")
            existing = set(cur.fetchall())
            is_new = [(f, int(c)) not in existing for f, c in zip(profiles["float_id"], profiles["cycle_number"])]
            new_profiles = profiles[is_new].reset_index(drop=True)
            if new_profiles.empty:
                pg.commit()
                return 0

            new_floats = floats[floats["float_id"].isin(set(new_profiles["float_id"]))]
            cur.executemany(FLOAT_INSERT, _rows(new_floats, ["float_id", "wmo_id", "deployment_date",
                                                             "deployment_lat", "deployment_lon", "last_contact"]))

            levels_by_key = {key: group.sort_values("depth").reset_index(drop=True)
                             for key, group in measurements.groupby(["float_id", "cycle_number"])}
            descriptions = [describe_profile(p, levels_by_key[(p["float_id"], p["cycle_number"])])
                            for p in new_profiles.to_dict("records")]
            vectors = embed_with_cache(descriptions, embedder, cache_path)

            profile_rows = [
                row + (description, _vector_literal(vector))
                for row, description, vector in zip(
                    _rows(new_profiles, ["float_id", "cycle_number", "profile_date", "profile_lat", "profile_lon",
                                         "region", "n_levels", "has_oxygen", "has_chlorophyll", "has_nitrate",
                                         "has_ph"]),
                    descriptions, vectors)
            ]
            cur.executemany(PROFILE_INSERT, profile_rows)

            cur.execute(
                "SELECT p.profile_id, p.float_id, p.cycle_number FROM profiles p "
                "JOIN unnest(%s::text[], %s::int[]) AS k(float_id, cycle_number) USING (float_id, cycle_number)",
                (new_profiles["float_id"].tolist(), [int(c) for c in new_profiles["cycle_number"]]),
            )
            ids = pd.DataFrame(cur.fetchall(), columns=["profile_id", "float_id", "cycle_number"])
            new_measurements = measurements.merge(ids, on=["float_id", "cycle_number"])
            with cur.copy(f"COPY measurements ({', '.join(MEASUREMENT_COLUMNS)}) FROM STDIN") as copy:
                for row in _rows(new_measurements, MEASUREMENT_COLUMNS):
                    copy.write_row(row)

            cur.execute(REFRESH_FLOATS)
        pg.commit()
        return len(new_profiles)
    except Exception:
        pg.rollback()
        raise
    finally:
        raw.close()


def prune(engine: Engine, before: datetime) -> int:
    with engine.begin() as conn:
        removed = conn.execute(text("DELETE FROM profiles WHERE profile_date < :before"), {"before": before}).rowcount
        conn.execute(text("DELETE FROM floats f WHERE NOT EXISTS "
                          "(SELECT 1 FROM profiles p WHERE p.float_id = f.float_id)"))
        if removed:
            conn.execute(text(REFRESH_FLOATS))
    return removed


def start_run(engine: Engine, kind: str) -> int:
    with engine.begin() as conn:
        return conn.execute(text("INSERT INTO ingest_runs (kind) VALUES (:kind) RETURNING run_id"),
                            {"kind": kind}).scalar_one()


def finish_run(engine: Engine, run_id: int, status: str, added: int, removed: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ingest_runs SET finished_at = now(), status = :status, profiles_added = :added,
                   profiles_removed = :removed, newest_profile_date = (SELECT MAX(profile_date) FROM profiles)
            WHERE run_id = :run_id
        """), {"status": status, "added": added, "removed": removed, "run_id": run_id})


def profile_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM profiles")).scalar_one()
