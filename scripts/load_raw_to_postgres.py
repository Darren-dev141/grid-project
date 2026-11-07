"""Mirror the local DuckDB raw landing zone into the Postgres deployment target.

S5 deployment layer (PLAN decision 4): ingestion stays DuckDB-local and
append-only; this script copies raw.batches / raw.records into the Supabase
Postgres database so `dbt build --target supabase` reads the same raw sources
the local target reads. Inserts are keyed on the raw tables' primary keys with
ON CONFLICT DO NOTHING, so re-running a window is a no-op and the Postgres raw
zone accumulates history across scheduled runs.

Connection comes only from the environment, using the same variable names as
dbt/profiles.yml's `supabase` output (SUPABASE_DB_HOST / _PORT / _USER /
_PASSWORD / _NAME), or a single SUPABASE_DB_URL if set. No defaults for
credentials: a missing variable is a loud failure, never a silent skip. A
paused Supabase project fails the connection and therefore fails the run —
that is the intended keep-alive alarm, not a bug.

Usage:
    python scripts/load_raw_to_postgres.py [--database data/grid.duckdb]
    python scripts/load_raw_to_postgres.py --check   # connectivity probe only
"""

import argparse
import os
from pathlib import Path
import sys

import duckdb
import psycopg


BATCHES_DDL = """
CREATE TABLE IF NOT EXISTS raw.batches (
    source VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    path VARCHAR,
    loaded_at TIMESTAMPTZ DEFAULT now(),
    committed BOOLEAN DEFAULT TRUE,
    observed_at TIMESTAMPTZ,
    PRIMARY KEY (source, dataset, digest)
)
"""

RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS raw.records (
    source VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    row_number INTEGER NOT NULL,
    payload JSONB,
    PRIMARY KEY (source, dataset, digest, row_number)
)
"""


def connection_kwargs() -> dict:
    url = os.environ.get("SUPABASE_DB_URL")
    if url:
        return {"conninfo": url}
    required = ("SUPABASE_DB_HOST", "SUPABASE_DB_USER", "SUPABASE_DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "load_raw_to_postgres: missing required environment variables: "
            + ", ".join(missing)
            + " (set them as repo secrets; see dbt/profiles.yml)"
        )
    return {
        "host": os.environ["SUPABASE_DB_HOST"],
        "port": int(os.environ.get("SUPABASE_DB_PORT", "5432")),
        "user": os.environ["SUPABASE_DB_USER"],
        "password": os.environ["SUPABASE_DB_PASSWORD"],
        "dbname": os.environ.get("SUPABASE_DB_NAME", "postgres"),
        "connect_timeout": 30,
    }


def connect_postgres() -> psycopg.Connection:
    kwargs = connection_kwargs()
    if "conninfo" in kwargs:
        return psycopg.connect(kwargs["conninfo"], connect_timeout=30)
    return psycopg.connect(**kwargs)


def check(database: Path) -> int:
    with connect_postgres() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = current_database()")
            cur.fetchone()
            cur.execute("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'raw'")
            has_raw = cur.fetchone()[0] == 1
    print(f"load_raw_to_postgres: Postgres reachable; raw schema present: {bool(has_raw)}")
    return 0


def transfer(database: Path) -> int:
    if not database.is_file():
        raise SystemExit(f"load_raw_to_postgres: warehouse not found: {database}")
    with duckdb.connect(str(database), read_only=True) as duck:
        tables = {row[0] for row in duck.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        ).fetchall()}
        if not {"batches", "records"} <= tables:
            raise SystemExit(
                f"load_raw_to_postgres: raw.batches/raw.records missing in {database}; "
                "run ingestion first"
            )
        batches = duck.execute(
            "SELECT source, dataset, digest, path, loaded_at, committed, observed_at "
            "FROM raw.batches ORDER BY source, dataset, digest"
        ).fetchall()
        records = duck.execute(
            "SELECT source, dataset, digest, row_number, payload::VARCHAR "
            "FROM raw.records ORDER BY source, dataset, digest, row_number"
        ).fetchall()

    with connect_postgres() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cur.execute(BATCHES_DDL)
            cur.execute(RECORDS_DDL)
            before_b = cur.execute("SELECT count(*) FROM raw.batches").fetchone()[0]
            before_r = cur.execute("SELECT count(*) FROM raw.records").fetchone()[0]
            cur.executemany(
                "INSERT INTO raw.batches (source, dataset, digest, path, loaded_at, committed, observed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                batches,
            )
            cur.executemany(
                "INSERT INTO raw.records (source, dataset, digest, row_number, payload) "
                "VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT DO NOTHING",
                records,
            )
            after_b = cur.execute("SELECT count(*) FROM raw.batches").fetchone()[0]
            after_r = cur.execute("SELECT count(*) FROM raw.records").fetchone()[0]
        conn.commit()

    print(
        "load_raw_to_postgres: "
        f"batches {before_b} -> {after_b} (+{after_b - before_b} new, {len(batches)} offered); "
        f"records {before_r} -> {after_r} (+{after_r - before_r} new, {len(records)} offered)"
    )
    if after_b < before_b or after_r < before_r:
        raise SystemExit("load_raw_to_postgres: row counts went backwards; refusing to call this success")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path,
                        default=Path(os.environ.get("GRID_DATABASE", "data/grid.duckdb")),
                        help="DuckDB warehouse written by ingestion (default: $GRID_DATABASE or data/grid.duckdb)")
    parser.add_argument("--check", action="store_true",
                        help="Only probe Postgres connectivity (fails loudly if the project is paused/unreachable)")
    args = parser.parse_args(argv)
    return check(args.database) if args.check else transfer(args.database)


if __name__ == "__main__":
    sys.exit(main())
