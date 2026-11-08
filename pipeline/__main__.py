"""
FloatChat data pipeline.

    python -m pipeline backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--reset]
    python -m pipeline refresh [--days 10]
    python -m pipeline snapshot [--if-empty] [--reset] [--path data/argo_profiles.csv.gz]
    python -m pipeline fetch --start YYYY-MM-DD --end YYYY-MM-DD [--out data/argo_profiles.csv.gz]
    python -m pipeline create-reader [--password-env READER_PASSWORD]
    python -m pipeline reset

Database commands use ADMIN_DATABASE_URL (falling back to DATABASE_URL).
"""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from floatchat import config
from floatchat.db.engine import apply_schema, make_engine, reset_schema, schema_is_current
from floatchat.db.roles import create_reader_role
from pipeline.erddap import fetch_range
from pipeline.load import finish_run, load_tables, profile_count, prune, start_run
from pipeline.shape import build_tables, to_seed


def _today() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)


def _window_start() -> datetime:
    return _today() - timedelta(days=config.DATA_WINDOW_DAYS)


def ingest(engine, kind: str, get_seed: Callable[[], pd.DataFrame], embedder, cache_path=None,
           prune_before=None) -> dict:
    """Run one recorded load: get the seed rows (fetch or file), load new profiles, prune old ones."""
    apply_schema(engine)
    run_id = start_run(engine, kind)
    try:
        seed = get_seed()
        added = 0
        if not seed.empty:
            floats, profiles, measurements = build_tables(seed)
            added = load_tables(engine, floats, profiles, measurements, embedder, cache_path)
        removed = prune(engine, prune_before) if prune_before else 0
    except Exception:
        try:
            finish_run(engine, run_id, "failed", 0, 0)
        except Exception as e:  # the database itself may be the problem
            print(f"Could not record the failed run: {e}", file=sys.stderr)
        raise
    finish_run(engine, run_id, "success", added, removed)
    print(f"{kind}: {added} profiles added, {removed} removed")
    return {"added": added, "removed": removed}


def run_snapshot(engine, embedder, path, cache_path=None, if_empty=False, reset=False) -> dict:
    if reset or not schema_is_current(engine):
        reset_schema(engine)
    apply_schema(engine)
    if if_empty and profile_count(engine) > 0:
        print("Data already loaded - skipping snapshot.")
        return {"added": 0, "removed": 0}
    return ingest(engine, "snapshot", lambda: pd.read_csv(path), embedder, cache_path=cache_path)


def run_backfill(engine, embedder, start, end, reset=False, fetch=fetch_range) -> dict:
    if reset:
        reset_schema(engine)
    return ingest(engine, "backfill", lambda: to_seed(*fetch(start, end, config.BBOX)), embedder,
                  prune_before=_window_start())


def run_refresh(engine, embedder, days=10, fetch=fetch_range) -> dict:
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days + 1)
    return ingest(engine, "refresh", lambda: to_seed(*fetch(start, end, config.BBOX)), embedder,
                  prune_before=_window_start())


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    backfill = sub.add_parser("backfill", help="load a date range (default: the last 365 days)")
    backfill.add_argument("--start", type=_date)
    backfill.add_argument("--end", type=_date)
    backfill.add_argument("--reset", action="store_true", help="drop all tables first")
    refresh = sub.add_parser("refresh", help="load the last few days and prune old data")
    refresh.add_argument("--days", type=int, default=10)
    snapshot = sub.add_parser("snapshot", help="load the bundled snapshot (no network)")
    snapshot.add_argument("--path", default=config.SEED_DATA_PATH)
    snapshot.add_argument("--if-empty", action="store_true")
    snapshot.add_argument("--reset", action="store_true")
    fetch = sub.add_parser("fetch", help="download a date range into a seed CSV")
    fetch.add_argument("--start", type=_date, required=True)
    fetch.add_argument("--end", type=_date, required=True)
    fetch.add_argument("--out", default=config.SEED_DATA_PATH)
    reader = sub.add_parser("create-reader", help="create/update the read-only API role")
    reader.add_argument("--password-env", default="READER_PASSWORD")
    sub.add_parser("reset", help="drop all FloatChat tables")
    args = parser.parse_args(argv)

    if args.command == "fetch":
        core, bgc = fetch_range(args.start, args.end, config.BBOX)
        seed = to_seed(core, bgc)
        seed.to_csv(args.out, index=False, compression="gzip")
        print(f"Saved {len(seed):,} rows / {seed.groupby(['wmo_id', 'cycle_number']).ngroups:,} profiles to {args.out}")
        return

    engine = make_engine(config.ADMIN_DATABASE_URL)
    if args.command == "reset":
        reset_schema(engine)
    elif args.command == "create-reader":
        password = os.environ.get(args.password_env)
        if not password:
            sys.exit(f"Set the {args.password_env} environment variable to the reader password.")
        apply_schema(engine)
        create_reader_role(engine, password)
        print("Reader role ready.")
    else:
        from floatchat.embedder import get_embedder

        embedder = get_embedder()
        if args.command == "snapshot":
            use_cache = Path(args.path).resolve() == Path(config.SEED_DATA_PATH).resolve()
            run_snapshot(engine, embedder, args.path, config.EMBEDDING_CACHE_PATH if use_cache else None,
                         if_empty=args.if_empty, reset=args.reset)
        elif args.command == "backfill":
            end = args.end or _today() + timedelta(days=1)
            start = args.start or end - timedelta(days=config.DATA_WINDOW_DAYS + 1)
            run_backfill(engine, embedder, start, end, reset=args.reset)
        elif args.command == "refresh":
            run_refresh(engine, embedder, days=args.days)


if __name__ == "__main__":
    main()
