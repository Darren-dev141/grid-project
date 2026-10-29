"""Exercise the real dbt DAG in an isolated warehouse; all inputs are synthetic."""

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from grid_pipeline.storage import ingest


PROJECT = Path(__file__).resolve().parents[1] / 'dbt'
EIA = 'electricity/rto/fuel-type-data'
EIA_REGION = 'electricity/rto/region-data'
EIA_SUBBA = 'electricity/rto/region-sub-ba-data'
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


def load_eia_dataset(root, dataset, rows, *, committed=True):
    payload = {'response': {'data': rows}}
    return ingest(root / 'grid.duckdb', root, 'eia', dataset,
                  json.dumps(payload).encode(), committed=committed)


def demand_pjm_row(hour, value, respondent='PJM', row_type='D', units='megawatthours'):
    return {'period': f'2026-10-01T{hour:02}', 'respondent': respondent,
            'type': row_type, 'value': None if value is None else str(value), 'value-units': units}


def demand_bge_row(hour, value, subba='BC', parent='PJM', units='megawatthours'):
    return {'period': f'2026-10-01T{hour:02}', 'subba': subba, 'parent': parent,
            'value': None if value is None else str(value), 'value-units': units}


def run_dbt(root, command='build', *, generation_only=False, demand_only=False):
    env = os.environ.copy()
    env['GRID_DATABASE'] = str(root / 'grid.duckdb')
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    executable = Path(sys.executable).parent / ('dbt.exe' if os.name == 'nt' else 'dbt')
    selection = (['--select', 'eia_pjm_hourly_generation'] if generation_only
                 else ['--select', 'eia_pjm_hourly_demand', 'eia_bge_hourly_demand']
                 if demand_only else ['--vars', '{bge_pnode_id: 999}'])
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
            fetch(tmp_path, 'fuel-mix', utc_hour('2026-10-01T00:00Z'),
                  utc_hour(f'2026-10-01T{end_hour:02}:00Z'), client=client)
    pending = json.dumps({'response': {'data': [eia_row(0, 'WND', 999)]}}).encode()
    ingest(tmp_path / 'grid.duckdb', tmp_path, 'eia', EIA, pending, committed=False)
    result = run_dbt(tmp_path, generation_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('SELECT generation_mwh FROM cleaned.eia_pjm_hourly_generation').fetchall() == [(10.0,)]
        assert conn.execute('SELECT count(*) FROM raw.batches WHERE committed').fetchone() == (2,)


def test_demand_models_select_latest_committed_rows_and_exclude_other_categories(tmp_path):
    pjm_early = json.dumps({'response': {'data': [
        demand_pjm_row(0, 100), demand_pjm_row(1, 9, row_type='DF'),
        demand_pjm_row(2, 8, row_type='NG'), demand_pjm_row(3, 7, respondent='NY'),
    ]}}).encode()
    pjm_late = json.dumps({'response': {'data': [demand_pjm_row(0, 110)]}}).encode()
    load_eia_dataset(tmp_path, EIA_REGION, [
        demand_pjm_row(0, 100), demand_pjm_row(1, 9, row_type='DF'),
        demand_pjm_row(2, 8, row_type='NG'), demand_pjm_row(3, 7, respondent='NY'),
    ])
    load_eia_dataset(tmp_path, EIA_REGION, [demand_pjm_row(0, 110)])
    load_eia_dataset(tmp_path, EIA_SUBBA, [
        demand_bge_row(0, 50), demand_bge_row(1, 60, subba='PE'),
        demand_bge_row(2, 70, parent='NY'),
    ])
    load_eia_dataset(tmp_path, EIA_REGION, [demand_pjm_row(4, 999)], committed=False)
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        conn.execute("""update raw.batches set observed_at = case digest
            when ? then TIMESTAMPTZ '2026-10-02 00:00:00+00'
            when ? then TIMESTAMPTZ '2026-10-03 00:00:00+00' end
            where dataset = ? and digest in (?, ?)""",
            [hashlib.sha256(pjm_early).hexdigest(),
             hashlib.sha256(pjm_late).hexdigest(), EIA_REGION,
             hashlib.sha256(pjm_early).hexdigest(),
             hashlib.sha256(pjm_late).hexdigest()])
    result = run_dbt(tmp_path, demand_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        pjm = conn.execute('''select extract(hour from hour_utc), respondent, demand_mwh,
            units, geography from cleaned.eia_pjm_hourly_demand order by hour_utc''').fetchall()
        bge = conn.execute('''select extract(hour from hour_utc), subba, parent, demand_mwh,
            units, geography from cleaned.eia_bge_hourly_demand order by hour_utc''').fetchall()
        assert pjm == [(0, 'PJM', 110.0, 'megawatthours', 'PJM balancing authority')]
        assert bge == [(0, 'BC', 'PJM', 50.0, 'megawatthours',
                        'BGE zone (trailing local context, about 2 days behind; not used for RTO scoring)')]


@pytest.mark.parametrize('dataset,row,expected_test', [
    (EIA_REGION, demand_pjm_row(0, 4, units='MW'), 'accepted_values_eia_pjm_hourly_demand_units'),
    (EIA_REGION, demand_pjm_row(0, -4), 'demand_pjm_demand_range'),
    (EIA_REGION, demand_pjm_row(0, 'NaN'), 'demand_pjm_demand_range'),
    (EIA_SUBBA, demand_bge_row(0, 4, units='MW'), 'accepted_values_eia_bge_hourly_demand_units'),
    (EIA_SUBBA, demand_bge_row(0, -4), 'demand_bge_demand_range'),
    (EIA_SUBBA, demand_bge_row(0, 'NaN'), 'demand_bge_demand_range'),
    # A non-null value that is not a number is a format change, not a provider gap.
    (EIA_REGION, demand_pjm_row(0, 'not-a-number'), 'demand_unparseable_value'),
    (EIA_SUBBA, demand_bge_row(0, 'not-a-number'), 'demand_unparseable_value'),
])
def test_demand_build_rejects_bad_units_negative_and_nonfinite_values(tmp_path, dataset, row, expected_test):
    load_eia_dataset(tmp_path, dataset, [row])
    result = run_dbt(tmp_path, demand_only=True)
    assert result.returncode != 0, result.stdout + result.stderr
    artifact_path = tmp_path / 'target' / 'run_results.json'
    assert artifact_path.exists(), result.stdout + result.stderr
    artifact = json.loads(artifact_path.read_text())
    failed = [r['unique_id'] for r in artifact['results'] if r['status'] == 'fail']
    assert any(expected_test in name for name in failed)


def test_provider_gaps_and_implausible_spikes_are_flagged_not_fatal(tmp_path):
    # Live EIA history (2019-2020) has null hours around DST changes and a 417,669 MWh spike.
    load_eia_dataset(tmp_path, EIA_REGION, [
        demand_pjm_row(0, 90000), demand_pjm_row(1, None), demand_pjm_row(2, 417669)])
    load_eia_dataset(tmp_path, EIA_SUBBA, [demand_bge_row(0, 3000), demand_bge_row(1, None)])
    result = run_dbt(tmp_path, demand_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        pjm = conn.execute("""select extract(hour from hour_utc), demand_mwh, quality
            from cleaned.eia_pjm_hourly_demand order by hour_utc""").fetchall()
        bge = conn.execute("""select extract(hour from hour_utc), demand_mwh, quality
            from cleaned.eia_bge_hourly_demand order by hour_utc""").fetchall()
    assert pjm == [(0, 90000.0, 'ok'), (1, None, 'missing'), (2, 417669.0, 'implausible')]
    assert bge == [(0, 3000.0, 'ok'), (1, None, 'missing')]
    warned = [r['unique_id'] for r in json.loads((tmp_path / 'target' / 'run_results.json')
              .read_text())['results'] if r['status'] == 'warn']
    assert any('demand_quality_not_ok' in name for name in warned)


def test_one_hour_spikes_and_dips_against_both_neighbours_are_implausible(tmp_path):
    # Live 2019-2026 history: normal hours stay within 3.4% of a neighbour; the
    # errors sit 15-43% above both neighbours (e.g. 192,229 between 127,489 and
    # 136,631 MWh) or 41% below (56,260 MWh).
    series = [100000, 101000, 150000, 102000, 103400, 60000, 104000, 160000]
    load_eia_dataset(tmp_path, EIA_REGION, [demand_pjm_row(h, v) for h, v in enumerate(series)])
    result = run_dbt(tmp_path, demand_only=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        quality = [q for (q,) in conn.execute(
            'select quality from cleaned.eia_pjm_hourly_demand order by hour_utc').fetchall()]
    # Hour 7 has only one neighbour, so the spike rule does not judge it.
    assert quality == ['ok', 'ok', 'implausible', 'ok', 'ok', 'implausible', 'ok', 'ok']
