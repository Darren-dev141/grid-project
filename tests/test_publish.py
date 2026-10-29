import csv
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from grid_pipeline.publish import PublishError, publish, report_rows
from grid_pipeline.storage import ingest


PROJECT = Path(__file__).resolve().parents[1] / 'dbt'


def load(root, bad=False):
    eia = {'response': {'data': [
        {'period': '2026-11-01T05', 'respondent': 'PJM', 'fueltype': fuel,
         'value': '10', 'value-units': 'MW' if bad else 'megawatthours'}
        for fuel in ['COL', 'NG', 'NUC', 'OIL', 'OTH', 'SUN', 'WAT', 'WND']
    ]}}
    pjm = {'items': [
        {'datetime_beginning_utc': f'11/01/2026 {hour}:00:00',
         'pnode_id': 999, 'total_lmp_rt': price}
        for hour, price in [('05', 20), ('06', -5)]
    ]}
    for source, dataset, payload in [('eia', 'electricity/rto/fuel-type-data', eia), ('pjm', 'rt_hrl_lmps', pjm)]:
        ingest(root / 'grid.duckdb', root, source, dataset, json.dumps(payload).encode())


def test_publish_validates_snapshot_and_preserves_previous_on_failure(tmp_path):
    root, output = tmp_path / 'data', tmp_path / 'export'
    load(root)
    snapshot = publish(root / 'grid.duckdb', output, PROJECT, 999, data_kind='synthetic')
    pointer = (output / 'current.json').read_bytes()
    assert json.loads(pointer)['snapshot_id'] == snapshot.name
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    assert manifest['data_kind'] == 'synthetic'
    assert manifest['rows'] == 2 and manifest['renewable_share_hours'] == 1
    assert manifest['price_last_hour_utc'] == '2026-11-01T06:00:00+00:00'
    assert manifest['renewable_share_last_hour_utc'] == '2026-11-01T05:00:00+00:00'
    csv_path = snapshot / 'grid_hourly.csv'
    assert manifest['csv_sha256'] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
    with csv_path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert [row['local_hour'] for row in rows] == ['1', '1']
    assert [row['utc_offset_minutes'] for row in rows] == ['-240', '-300']
    assert rows[0]['hour_local'] == '2026-11-01T01:00:00-04:00'
    assert rows[1]['hour_local'] == '2026-11-01T01:00:00-05:00'
    assert rows[1]['renewable_share'] == ''
    assert rows[1]['price_usd_per_mwh'] == '-5.0'
    # dbt built the isolated copy, not the live source database.
    with duckdb.connect(str(root / 'grid.duckdb')) as conn:
        assert conn.execute("select count(*) from information_schema.tables where table_schema='serving'").fetchone() == (0,)
    load(root, bad=True)
    with pytest.raises(PublishError, match='validation failed'):
        publish(root / 'grid.duckdb', output, PROJECT, 999, data_kind='synthetic')
    assert (output / 'current.json').read_bytes() == pointer
    assert manifest['csv_sha256'] == hashlib.sha256(csv_path.read_bytes()).hexdigest()


def test_empty_serving_data_cannot_publish():
    with duckdb.connect() as conn:
        conn.execute('CREATE SCHEMA serving')
        conn.execute('CREATE TABLE serving.grid_hourly(hour_utc TIMESTAMP, price_usd_per_mwh DOUBLE)')
        with pytest.raises(PublishError, match='no price'):
            report_rows(conn)
