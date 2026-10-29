"""Immutable response landing and transactional, replay-safe raw indexing."""

import hashlib
import json
from pathlib import Path

import duckdb


def land(root: Path, source: str, body: bytes) -> Path:
    if source not in {"eia", "pjm"}:
        raise ValueError("source must be eia or pjm")
    digest = hashlib.sha256(body).hexdigest()
    path = root / "raw" / source / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise ValueError("existing raw file failed integrity check") from None
    return path


def ingest(database: Path, root: Path, source: str, dataset: str, body: bytes) -> int:
    # Land before parsing: even malformed upstream bodies remain available for diagnosis.
    path = land(root, source, body)
    payload = json.loads(body)
    records = payload["response"]["data"] if source == "eia" else payload["items"]
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("expected a list of record objects")
    digest = path.stem
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        conn.execute("""CREATE TABLE IF NOT EXISTS raw.batches (
            source VARCHAR, dataset VARCHAR, digest VARCHAR, path VARCHAR,
            loaded_at TIMESTAMPTZ DEFAULT current_timestamp,
            PRIMARY KEY (source, dataset, digest))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS raw.records (
            source VARCHAR, dataset VARCHAR, digest VARCHAR,
            row_number INTEGER, payload JSON,
            PRIMARY KEY (source, dataset, digest, row_number))""")
        conn.execute("BEGIN TRANSACTION")
        try:
            exists = conn.execute(
                "SELECT 1 FROM raw.batches WHERE source=? AND dataset=? AND digest=?",
                [source, dataset, digest],
            ).fetchone()
            if exists:
                conn.execute("COMMIT")
                return 0
            conn.execute(
                "INSERT INTO raw.batches(source,dataset,digest,path) VALUES (?,?,?,?)",
                [source, dataset, digest, str(path.resolve())],
            )
            if records:
                conn.executemany("INSERT INTO raw.records VALUES (?,?,?,?,?)", [
                    (source, dataset, digest, i, json.dumps(row))
                    for i, row in enumerate(records)
                ])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return len(records)
