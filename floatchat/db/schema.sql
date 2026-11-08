-- FloatChat schema. Idempotent: safe to apply on every pipeline run.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS floats (
    float_id        VARCHAR(20) PRIMARY KEY,
    wmo_id          INTEGER NOT NULL,
    deployment_date DATE,
    deployment_lat  DOUBLE PRECISION,
    deployment_lon  DOUBLE PRECISION,
    last_contact    DATE,
    status          VARCHAR(20) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS profiles (
    profile_id      SERIAL PRIMARY KEY,
    float_id        VARCHAR(20) NOT NULL REFERENCES floats(float_id) ON DELETE CASCADE,
    cycle_number    INTEGER NOT NULL,
    profile_date    TIMESTAMP NOT NULL,
    profile_lat     DOUBLE PRECISION NOT NULL,
    profile_lon     DOUBLE PRECISION NOT NULL,
    region          VARCHAR(40) NOT NULL,
    n_levels        INTEGER NOT NULL,
    has_oxygen      BOOLEAN NOT NULL DEFAULT FALSE,
    has_chlorophyll BOOLEAN NOT NULL DEFAULT FALSE,
    has_nitrate     BOOLEAN NOT NULL DEFAULT FALSE,
    has_ph          BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT,
    embedding       vector(384),
    UNIQUE (float_id, cycle_number)
);

CREATE TABLE IF NOT EXISTS measurements (
    id          BIGSERIAL PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    float_id    VARCHAR(20) NOT NULL,
    time        TIMESTAMP NOT NULL,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    depth       DOUBLE PRECISION NOT NULL,
    pressure    DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION,
    salinity    DOUBLE PRECISION,
    oxygen      DOUBLE PRECISION,
    chlorophyll DOUBLE PRECISION,
    nitrate     DOUBLE PRECISION,
    ph          DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id              SERIAL PRIMARY KEY,
    kind                VARCHAR(20) NOT NULL,
    started_at          TIMESTAMP NOT NULL DEFAULT now(),
    finished_at         TIMESTAMP,
    status              VARCHAR(20) NOT NULL DEFAULT 'running',
    profiles_added      INTEGER,
    profiles_removed    INTEGER,
    newest_profile_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_log (
    id         BIGSERIAL PRIMARY KEY,
    logged_at  TIMESTAMP NOT NULL DEFAULT now(),
    question   TEXT NOT NULL,
    query_type VARCHAR(20),
    intent     VARCHAR(40),
    latency_ms INTEGER,
    success    BOOLEAN,
    cached     BOOLEAN,
    llm_used   BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_profiles_float_id ON profiles(float_id);
CREATE INDEX IF NOT EXISTS idx_profiles_date ON profiles(profile_date);
CREATE INDEX IF NOT EXISTS idx_profiles_region ON profiles(region);
CREATE INDEX IF NOT EXISTS idx_profiles_embedding ON profiles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_measurements_profile_id ON measurements(profile_id);
CREATE INDEX IF NOT EXISTS idx_measurements_float_id ON measurements(float_id);
CREATE INDEX IF NOT EXISTS idx_measurements_depth ON measurements(depth);
