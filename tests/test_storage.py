import json

import duckdb
import pytest

from grid_pipeline.storage import ingest, land


@pytest.mark.parametrize("source,body", [
    ("eia", b'{ "response": { "data": [{"value":"12"}] } }\n'),
    ("pjm", b'{"items":[{"total_lmp_rt":-5.5}]}'),
])
def test_replay_is_idempotent_and_raw_bytes_unchanged(tmp_path, source, body):
    db = tmp_path / "grid.duckdb"
    assert ingest(db, tmp_path, source, "test", body) == 1
    assert ingest(db, tmp_path, source, "test", body) == 0
    assert land(tmp_path, source, body).read_bytes() == body
    with duckdb.connect(str(db)) as conn:
        assert conn.execute("SELECT count(*) FROM raw.records").fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM raw.batches").fetchone() == (1,)


def test_revisions_are_preserved(tmp_path):
    db = tmp_path / "grid.duckdb"
    for value in [1, 2]:
        body = json.dumps({"response": {"data": [{"value": value}]}}).encode()
        assert ingest(db, tmp_path, "eia", "test", body) == 1
    with duckdb.connect(str(db)) as conn:
        assert conn.execute("SELECT count(*) FROM raw.records").fetchone() == (2,)


@pytest.mark.parametrize("body", [b"invalid json", b'{"items":{}}', b'{"items":[1]}'])
def test_invalid_response_landed_but_not_loaded(tmp_path, body):
    with pytest.raises((ValueError, KeyError)):
        ingest(tmp_path / "grid.duckdb", tmp_path, "pjm", "test", body)
    assert land(tmp_path, "pjm", body).read_bytes() == body
    assert not (tmp_path / "grid.duckdb").exists()


def test_dataset_identity_and_empty_page(tmp_path):
    db = tmp_path / "grid.duckdb"
    body = b'{"items":[]}'
    assert ingest(db, tmp_path, "pjm", "one", body) == 0
    assert ingest(db, tmp_path, "pjm", "two", body) == 0
    with duckdb.connect(str(db)) as conn:
        assert conn.execute("SELECT count(*) FROM raw.batches").fetchone() == (2,)


def test_corrupt_raw_file_is_rejected(tmp_path):
    body = b'{"items":[]}'
    path = land(tmp_path, "pjm", body)
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        land(tmp_path, "pjm", body)


def test_source_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError):
        land(tmp_path, "../outside", b"{}")
