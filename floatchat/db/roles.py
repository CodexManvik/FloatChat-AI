"""The read-only database role the API uses."""

from psycopg import sql
from sqlalchemy.engine import Engine, make_url

READER_ROLE = "floatchat_reader"


def create_reader_role(engine: Engine, password: str, role: str = READER_ROLE) -> None:
    """Create (or update) the API role: read data, append to query_log, 5 s statement timeout."""
    role_id = sql.Identifier(role)
    raw = engine.raw_connection()
    try:
        pg = raw.driver_connection
        with pg.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            verb = "ALTER" if cur.fetchone() else "CREATE"
            cur.execute(sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(role_id, sql.Literal(password)))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(pg.info.dbname), role_id))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_id))
            cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role_id))
            cur.execute(sql.SQL("GRANT SELECT ON floats, profiles, measurements, ingest_runs TO {}").format(role_id))
            cur.execute(sql.SQL("GRANT INSERT ON query_log TO {}").format(role_id))
            cur.execute(sql.SQL("GRANT USAGE ON SEQUENCE query_log_id_seq TO {}").format(role_id))
            cur.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '5s'").format(role_id))
        pg.commit()
    finally:
        raw.close()


def reader_url(admin_url: str, password: str, role: str = READER_ROLE) -> str:
    return make_url(admin_url).set(username=role, password=password).render_as_string(hide_password=False)
