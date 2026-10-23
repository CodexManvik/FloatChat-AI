"""
Load the ARGO seed data into PostgreSQL and build the ChromaDB vector index.

    python ingest.py             # (re)build everything
    python ingest.py --if-empty  # only build when the database is empty

The seed file (data/argo_profiles.csv.gz) holds real ARGO profiles downloaded
from the Ifremer ERDDAP server; refresh it with scripts/fetch_argo_data.py.
"""

import argparse
import hashlib
import os

import chromadb
import numpy as np
import pandas as pd
from chromadb.utils import embedding_functions
from sqlalchemy import create_engine, text

import config
from ocean_regions import region_for

SCHEMA_SQL = """
DROP TABLE IF EXISTS measurements CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS floats CASCADE;

CREATE TABLE floats (
    float_id VARCHAR(20) PRIMARY KEY,
    wmo_id INTEGER,
    deployment_date DATE,
    deployment_lat FLOAT,
    deployment_lon FLOAT,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    last_contact DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE profiles (
    profile_id SERIAL PRIMARY KEY,
    float_id VARCHAR(20) REFERENCES floats(float_id),
    cycle_number INTEGER,
    profile_date TIMESTAMP,
    profile_lat FLOAT,
    profile_lon FLOAT,
    region VARCHAR(40),
    n_levels INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES profiles(profile_id),
    float_id VARCHAR(20) REFERENCES floats(float_id),
    time TIMESTAMP,
    lat FLOAT,
    lon FLOAT,
    depth FLOAT,
    pressure FLOAT,
    temperature FLOAT,
    salinity FLOAT,
    oxygen FLOAT,
    ph FLOAT,
    chlorophyll FLOAT,
    nitrate FLOAT,
    backscatter FLOAT,
    cdom FLOAT,
    downwelling_par FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_measurements_float_id ON measurements(float_id);
CREATE INDEX idx_measurements_profile_id ON measurements(profile_id);
CREATE INDEX idx_measurements_time ON measurements(time);
CREATE INDEX idx_measurements_location ON measurements(lat, lon);
CREATE INDEX idx_measurements_depth ON measurements(depth);
CREATE INDEX idx_profiles_float_id ON profiles(float_id);
CREATE INDEX idx_profiles_date ON profiles(profile_date);
"""


def pressure_to_depth(pressure: pd.Series) -> pd.Series:
    # 1 dbar of pressure is ~1 m of seawater (within ~1% over 0-2000 m), and
    # keeping the standard levels unchanged makes depth groupings readable
    return pressure.round(0)


def build_tables(seed: pd.DataFrame):
    seed = seed.drop_duplicates(["wmo_id", "cycle_number", "pressure"]).copy()
    seed["time"] = pd.to_datetime(seed["time"], utc=True).dt.tz_localize(None)
    seed["float_id"] = seed["wmo_id"].astype(str)

    # One row per profile (float + cycle)
    profiles = (
        seed.groupby(["float_id", "cycle_number"], as_index=False)
        .agg(profile_date=("time", "first"), profile_lat=("lat", "first"),
             profile_lon=("lon", "first"), n_levels=("pressure", "size"))
        .sort_values(["profile_date", "float_id"])
        .reset_index(drop=True)
    )
    profiles["profile_id"] = profiles.index + 1
    profiles["region"] = [region_for(la, lo) for la, lo in zip(profiles["profile_lat"], profiles["profile_lon"])]

    floats = (
        profiles.sort_values("profile_date")
        .groupby("float_id", as_index=False)
        .agg(deployment_date=("profile_date", "first"), deployment_lat=("profile_lat", "first"),
             deployment_lon=("profile_lon", "first"), last_contact=("profile_date", "last"))
    )
    floats["wmo_id"] = floats["float_id"].astype(int)
    floats["status"] = "ACTIVE"
    floats["deployment_date"] = floats["deployment_date"].dt.date
    floats["last_contact"] = floats["last_contact"].dt.date

    measurements = seed.merge(profiles[["float_id", "cycle_number", "profile_id"]], on=["float_id", "cycle_number"])
    measurements["depth"] = pressure_to_depth(measurements["pressure"])
    measurements = measurements[["profile_id", "float_id", "time", "lat", "lon", "depth", "pressure",
                                 "temperature", "salinity", "oxygen"]]
    return floats, profiles, measurements


def load_postgres(engine, floats, profiles, measurements):
    with engine.begin() as conn:
        for statement in SCHEMA_SQL.split(";"):
            if statement.strip():
                conn.execute(text(statement))

    floats[["float_id", "wmo_id", "deployment_date", "deployment_lat", "deployment_lon", "status", "last_contact"]] \
        .to_sql("floats", engine, if_exists="append", index=False, chunksize=5000)
    profiles[["profile_id", "float_id", "cycle_number", "profile_date", "profile_lat", "profile_lon", "region", "n_levels"]] \
        .to_sql("profiles", engine, if_exists="append", index=False, chunksize=5000)
    measurements.to_sql("measurements", engine, if_exists="append", index=False, chunksize=10000)

    with engine.begin() as conn:
        conn.execute(text("SELECT setval('profiles_profile_id_seq', (SELECT MAX(profile_id) FROM profiles))"))

    print(f"   PostgreSQL: {len(floats)} floats, {len(profiles)} profiles, {len(measurements):,} measurements")


def value_at(levels: pd.DataFrame, depth: float, column: str):
    """Value of `column` at the level closest to `depth` (within 15%)."""
    idx = (levels["depth"] - depth).abs().idxmin()
    row = levels.loc[idx]
    if abs(row["depth"] - depth) > max(10, depth * 0.15) or pd.isna(row[column]):
        return None
    return row[column]


def describe_profile(p, levels: pd.DataFrame) -> str:
    date = p.profile_date
    ns = "N" if p.profile_lat >= 0 else "S"
    parts = [
        f"ARGO float {p.float_id} (WMO {p.float_id}) profile cycle {p.cycle_number} on "
        f"{date:%d %B %Y} at {abs(p.profile_lat):.2f}°{ns}, {p.profile_lon:.2f}°E in the {p.region}.",
        f"The profile has {p.n_levels} levels from {levels['depth'].min():.0f} m to {levels['depth'].max():.0f} m depth.",
    ]
    surf_t, surf_s = value_at(levels, 5, "temperature"), value_at(levels, 5, "salinity")
    if surf_t is not None:
        parts.append(f"Surface temperature was {surf_t:.2f}°C" + (f" and surface salinity {surf_s:.2f} PSU." if surf_s is not None else "."))
    for depth in (200, 1000):
        t, s = value_at(levels, depth, "temperature"), value_at(levels, depth, "salinity")
        if t is not None:
            parts.append(f"At {depth} m the temperature was {t:.2f}°C" + (f" and salinity {s:.2f} PSU." if s is not None else "."))
    if levels["oxygen"].notna().any():
        low = levels.loc[levels["oxygen"].idxmin()]
        parts.append(f"This is a BGC float measuring dissolved oxygen; the oxygen minimum was "
                     f"{low['oxygen']:.1f} µmol/kg at {low['depth']:.0f} m.")
    return " ".join(parts)


def build_vector_index(profiles: pd.DataFrame, measurements: pd.DataFrame):
    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    try:
        client.delete_collection(config.CHROMA_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(
        config.CHROMA_COLLECTION,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    levels_by_profile = dict(tuple(measurements.groupby("profile_id")))
    docs, metas, ids = [], [], []
    for p in profiles.itertuples():
        levels = levels_by_profile[p.profile_id].reset_index(drop=True)
        docs.append(describe_profile(p, levels))
        metas.append({
            "profile_id": int(p.profile_id),
            "float_id": str(p.float_id),
            "cycle_number": int(p.cycle_number),
            "date": p.profile_date.strftime("%Y-%m-%d"),
            "year": int(p.profile_date.year),
            "month_num": int(p.profile_date.month),
            "lat": float(p.profile_lat),
            "lon": float(p.profile_lon),
            "region": p.region,
            "has_oxygen": bool(levels["oxygen"].notna().any()),
        })
        ids.append(f"profile_{p.profile_id}")

    embeddings = embed_with_cache(docs)
    batch = 500
    for i in range(0, len(docs), batch):
        collection.add(documents=docs[i:i + batch], embeddings=embeddings[i:i + batch],
                       metadatas=metas[i:i + batch], ids=ids[i:i + batch])
    print(f"   ChromaDB: indexed {len(docs)} profiles")


def embed_with_cache(docs: list[str]) -> np.ndarray:
    """
    Embed documents, reusing vectors from the committed cache file for any
    document whose text is unchanged. Embedding thousands of documents on a
    CPU takes minutes; the cache makes a fresh install start in seconds.
    """
    hashes = [hashlib.sha1(doc.encode("utf-8")).hexdigest() for doc in docs]
    cache = {}
    if os.path.exists(config.EMBEDDING_CACHE_PATH):
        stored = np.load(config.EMBEDDING_CACHE_PATH)
        cache = dict(zip(stored["hashes"].tolist(), stored["vectors"]))

    missing = [i for i, h in enumerate(hashes) if h not in cache]
    if missing:
        print(f"   Embedding {len(missing)} new profile descriptions (cached: {len(docs) - len(missing)})...")
        new_vectors = embedding_functions.DefaultEmbeddingFunction()([docs[i] for i in missing])
        for i, vec in zip(missing, new_vectors):
            cache[hashes[i]] = np.asarray(vec, dtype=np.float16)
        try:
            np.savez_compressed(config.EMBEDDING_CACHE_PATH, hashes=np.array(hashes),
                                vectors=np.stack([cache[h] for h in hashes]))
        except OSError as e:
            print(f"   (could not update embedding cache: {e})")
    else:
        print(f"   Reusing {len(docs)} cached embeddings")

    return np.stack([cache[h] for h in hashes]).astype(np.float32)


def database_is_ready(engine) -> bool:
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM measurements")).scalar()
        collection = chromadb.PersistentClient(path=config.CHROMA_PATH).get_collection(config.CHROMA_COLLECTION)
        return count > 0 and collection.count() > 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Load ARGO seed data into PostgreSQL and ChromaDB")
    parser.add_argument("--if-empty", action="store_true", help="skip when data is already loaded")
    args = parser.parse_args()

    engine = create_engine(config.DATABASE_URL)
    if args.if_empty and database_is_ready(engine):
        print("Data already loaded - skipping ingestion.")
        return

    print(f"Loading ARGO data from {config.SEED_DATA_PATH}")
    seed = pd.read_csv(config.SEED_DATA_PATH)
    floats, profiles, measurements = build_tables(seed)

    print("1. Writing PostgreSQL tables...")
    load_postgres(engine, floats, profiles, measurements)

    print("2. Building ChromaDB vector index (first run downloads a small embedding model)...")
    build_vector_index(profiles, measurements)

    print("Ingestion complete")


if __name__ == "__main__":
    main()
