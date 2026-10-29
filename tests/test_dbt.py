"""Exercise the real dbt DAG in an isolated warehouse; all inputs are synthetic."""

import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb

from grid_pipeline.storage import ingest


PROJECT = Path(__file__).resolve().parents[1] / 'dbt'
EIA = 'electricity/rto/fuel-type-data'
FUELS = ['COL', 'NG', 'NUC', 'OIL', 'OTH', 'SUN', 'WAT', 'WND']


def eia_row(hour, fuel, value, units='megawatthours'):
    return {'period': f'2026-10-01T{hour:02}', 'respondent': 'PJM',
            'fueltype': fuel, 'value': str(value), 'value-units': units}


def pjm_row(hour, price, node=999):
    return {'datetime_beginning_utc': f'10/01/2026 {hour:02}:00:00',
            'pnode_id': node, 'total_lmp_rt': price}


def load(root, source, rows):
    payload = {'response': {'data': rows}} if source == 'eia' else {'items': rows}
    return ingest(root / 'grid.duckdb', root, source,
                  EIA if source == 'eia' else 'rt_hrl_lmps', json.dumps(payload).encode())


def run_dbt(root, command='build', *, generation_only=False):
    env = os.environ.copy()
    env['GRID_DATABASE'] = str(root / 'grid.duckdb')
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    executable = Path(sys.executable).parent / ('dbt.exe' if os.name == 'nt' else 'dbt')
    selection = (['--select', 'eia_pjm_hourly_generation'] if generation_only
                 else ['--vars', '{bge_pnode_id: 999}'])
    result = subprocess.run([
        str(executable), command, '--project-dir', str(PROJECT),
        '--profiles-dir', str(PROJECT), '--target-path', str(root / 'target'),
        '--log-path', str(root / 'logs'), *selection,
    ], env=env, capture_output=True, text=True, timeout=120)
    return result


def test_dbt_revisions_missing_mix_and_geography(tmp_path):
    # Eight categories: three renewable, nuclear excluded from renewable numerator.
    rows = [eia_row(0, fuel, 10) for fuel in FUELS]
    rows += [eia_row(1, 'WND', 30)]  # Incomplete mix must not appear 100% renewable.
    rows += [eia_row(2, fuel, 0) for fuel in FUELS]  # Zero denominator.
    rows += [eia_row(3, fuel, -1 if fuel == 'WAT' else 10) for fuel in FUELS]
    load(tmp_path, 'eia', rows)
    load(tmp_path, 'pjm', [pjm_row(0, 20), pjm_row(4, -5), pjm_row(0, 999, 123)])
    load(tmp_path, 'eia', [eia_row(0, 'WND', 30)])
    load(tmp_path, 'pjm', [pjm_row(0, 25)])
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        rows = conn.execute('''select extract(hour from hour_utc), price_usd_per_mwh,
            renewable_share, mix_complete from serving.grid_hourly order by hour_utc''').fetchall()
        assert rows == [(0, 25.0, .5, True), (1, None, None, False),
                        (2, None, None, True), (3, None, None, False),
                        (4, -5.0, None, False)]
        assert conn.execute('select count(*) from cleaned.eia_pjm_hourly_generation').fetchone() == (25,)
        assert conn.execute('select distinct generation_geography from serving.grid_hourly').fetchall() == [('PJM balancing authority',)]
    # Repeat a page and rebuild: no change to the business output.
    assert load(tmp_path, 'eia', [eia_row(0, 'WND', 30)]) == 0
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dbt_rejects_bad_units_nulls_and_nonfinite_prices(tmp_path):
    load(tmp_path, 'eia', [eia_row(0, 'WND', 10, 'MW'), eia_row(1, 'SUN', 'unknown')])
    load(tmp_path, 'pjm', [pjm_row(0, 'NaN')])
    result = run_dbt(tmp_path)
    assert result.returncode != 0
    artifact_path = tmp_path / 'target' / 'run_results.json'
    assert artifact_path.exists(), result.stdout + result.stderr
    artifact = json.loads(artifact_path.read_text())
    failed = [r['unique_id'] for r in artifact['results'] if r['status'] == 'fail']
    assert any('accepted_values' in name for name in failed)
    assert any('not_null_eia_pjm_hourly_generation_generation_mwh' in name for name in failed)
    assert any('finite_values' in name for name in failed)


def test_generation_can_build_without_a_price_node(tmp_path):
    load(tmp_path, 'eia', [eia_row(0, fuel, 10) for fuel in FUELS])
    result = run_dbt(tmp_path, generation_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('SELECT count(*) FROM cleaned.eia_pjm_hourly_generation').fetchone() == (8,)


def test_fresh_reversion_wins_and_pending_batches_are_excluded(tmp_path, monkeypatch):
    import httpx
    from grid_pipeline.fetch import fetch, utc_hour
    monkeypatch.setenv('EIA_API_KEY', 'synthetic-secret')
    for end_hour, value in [(1, 10), (2, 20), (3, 10)]:
        payload = {'response': {'data': [eia_row(0, 'WND', value)], 'total': '1'}}
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )) as client:
            fetch(tmp_path, 'eia', utc_hour('2026-10-01T00:00Z'),
                  utc_hour(f'2026-10-01T{end_hour:02}:00Z'), client=client)
    pending = json.dumps({'response': {'data': [eia_row(0, 'WND', 999)]}}).encode()
    ingest(tmp_path / 'grid.duckdb', tmp_path, 'eia', EIA, pending, committed=False)
    result = run_dbt(tmp_path, generation_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('SELECT generation_mwh FROM cleaned.eia_pjm_hourly_generation').fetchall() == [(10.0,)]
        assert conn.execute('SELECT count(*) FROM raw.batches WHERE committed').fetchone() == (2,)
