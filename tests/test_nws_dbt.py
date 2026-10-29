"""Real dbt builds on synthetic NWS records; no network access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

import duckdb
import pytest

from grid_pipeline.storage import ingest

PROJECT = Path(__file__).resolve().parents[1] / 'dbt'


def run_dbt(root):
    env = os.environ.copy()
    env['GRID_DATABASE'] = str(root / 'grid.duckdb')
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    executable = Path(sys.executable).parent / ('dbt.exe' if os.name == 'nt' else 'dbt')
    args = [str(executable), 'build', '--project-dir', str(PROJECT),
            '--profiles-dir', str(PROJECT), '--target-path', str(root / 'target'),
            '--log-path', str(root / 'logs'), '--select', 'nws_*']
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
    if 'concurrent send_bytes() calls are not supported' in result.stdout + result.stderr:
        warnings.warn('dbt concurrent send_bytes() failure: retrying once', RuntimeWarning)
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
    return result


def seed(root, dataset, payloads, digest, fetched='2026-11-01T12:00:00Z', committed=True):
    database = root / 'grid.duckdb'
    # Bootstrap the existing schema without depending on NWS client validation.
    ingest(database, root, 'eia', 'bootstrap', b'{"response":{"data":[]}}')
    with duckdb.connect(str(database)) as conn:
        conn.execute('INSERT INTO raw.batches(source,dataset,digest,path,loaded_at,committed) VALUES (?,?,?,?,?,?)',
                     ['nws', dataset, digest, 'synthetic', fetched, committed])
        for i, payload in enumerate(payloads):
            conn.execute('INSERT INTO raw.records VALUES (?,?,?,?,?)',
                         ['nws', dataset, digest, i, json.dumps(payload)])


def period(number, start, day, temperature):
    return {'number': number, 'name': 'Synthetic', 'startTime': start,
            'endTime': '2026-11-02T06:00:00-05:00', 'isDaytime': day,
            'temperature': temperature, 'temperatureUnit': 'F', 'shortForecast': 'Clear'}


def forecast(issue='2026-11-01T10:00:00Z', high=65):
    return {'properties': {'updateTime': issue, 'generatedAt': '2026-11-01T10:05:00Z', 'periods': [
        period(1, '2026-11-01T01:00:00-04:00', False, 40),
        period(2, '2026-11-01T06:00:00-05:00', True, high),
        period(3, '2026-11-01T18:00:00-05:00', False, 35),
        period(4, '2026-11-02T01:00:00Z', False, 34),
    ]}}


def test_nws_dbt_retains_issuances_revisions_local_dates_and_pending(tmp_path):
    seed(tmp_path, 'forecast', [forecast()], 'first')
    seed(tmp_path, 'forecast', [forecast(high=67)], 'revision', '2026-11-01T13:00:00Z')
    seed(tmp_path, 'forecast', [forecast('2026-11-01T11:00:00Z', 68)], 'newest', '2026-11-01T13:00:00Z')
    seed(tmp_path, 'forecast', [forecast('2026-10-31T10:00:00Z', 99)], 'stale', '2026-11-01T14:00:00Z')
    seed(tmp_path, 'forecast', [forecast('2026-11-01T12:00:00Z', 100)], 'pending', committed=False)
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('select count(*) from cleaned.nws_forecast_periods').fetchone() == (16,)
        assert conn.execute('select count(distinct issuance_id) from cleaned.nws_forecast_periods').fetchone() == (4,)
        assert conn.execute('select high_f, low_f from cleaned.nws_forecast_daily order by high_f').fetchall() == [(65, 34), (67, 34), (68, 34), (99, 34)]
        assert conn.execute('select distinct cast(local_date as varchar) from cleaned.nws_forecast_daily').fetchall() == [('2026-11-01',)]
        assert conn.execute('select high_f from cleaned.nws_forecast_latest').fetchall() == [(68,)]
        assert conn.execute("select extract(hour from timezone('UTC', start_time_utc)) from cleaned.nws_forecast_periods where digest='first' order by period_number").fetchall() == [(5,), (11,), (23,), (1,)]
        assert conn.execute('select count(*) from cleaned.nws_alerts').fetchone() == (0,)


def test_nws_dbt_heat_cold_alerts_and_revision_history(tmp_path):
    events = ['Heat Advisory', 'Extreme Heat Watch', 'Extreme Heat Warning',
              'Excessive Heat Watch', 'Excessive Heat Warning', 'Cold Weather Advisory',
              'Extreme Cold Watch', 'Extreme Cold Warning', 'Wind Chill Advisory',
              'Wind Chill Warning', 'Wind Chill Watch', 'Flood Warning']
    features = [{'id': str(i), 'type': 'Feature', 'properties': {
        'id': str(i), 'event': event, 'sent': '2026-11-01T10:00:00Z',
        'effective': '2026-11-01T10:00:00Z', 'onset': None,
        'expires': '2026-11-02T10:00:00Z', 'ends': None,
        'severity': 'Moderate', 'headline': event, 'description': 'Synthetic'}}
        for i, event in enumerate(events)]
    seed(tmp_path, 'alerts', features, 'alerts')
    seed(tmp_path, 'alerts', features[:1], 'revision', '2026-11-01T13:00:00Z')
    seed(tmp_path, 'alerts', features[:1], 'pending', committed=False)
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('select count(*) from cleaned.nws_alerts').fetchone() == (12,)
        assert conn.execute("select count(*) from cleaned.nws_alerts where event='Flood Warning'").fetchone() == (0,)
        assert conn.execute('select count(*) from cleaned.nws_forecast_daily').fetchone() == (0,)


@pytest.mark.parametrize('field,value', [('temperature', 'NaN'), ('temperatureUnit', 'C'), ('startTime', 'invalid'), ('isDaytime', None)])
def test_nws_dbt_rejects_invalid_forecast_fields(tmp_path, field, value):
    body = forecast()
    body['properties']['periods'][0][field] = value
    seed(tmp_path, 'forecast', [body], 'bad')
    result = run_dbt(tmp_path)
    assert result.returncode != 0
    artifact = json.loads((tmp_path / 'target' / 'run_results.json').read_text())
    assert any(row['status'] == 'fail' for row in artifact['results']), result.stdout + result.stderr



def test_nws_dbt_latest_fetch_tie_and_partial_days(tmp_path):
    first = forecast()
    first['properties']['periods'] = [period(1, '2026-11-01T18:00:00-05:00', False, 34)]
    revised = forecast()
    revised['properties']['periods'] = [
        period(1, '2026-11-01T18:00:00-05:00', False, 32),
        period(2, '2026-11-02T06:00:00-05:00', True, 60)]
    seed(tmp_path, 'forecast', [first], 'first')
    seed(tmp_path, 'forecast', [revised], 'revised', '2026-11-01T13:00:00Z')
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('select high_f, low_f from cleaned.nws_forecast_latest order by local_date').fetchall() == [(None, 32), (60, None)]


def test_nws_dbt_rejects_duplicate_period_numbers(tmp_path):
    body = forecast()
    body['properties']['periods'][1]['number'] = 1
    seed(tmp_path, 'forecast', [body], 'bad')
    result = run_dbt(tmp_path)
    assert result.returncode != 0
    artifact = json.loads((tmp_path / 'target' / 'run_results.json').read_text())
    assert any(row['status'] == 'fail' and row['unique_id'].endswith('nws_forecast_period_key')
               for row in artifact['results']), result.stdout + result.stderr

def test_nws_dbt_issuance_identity_is_session_timezone_independent(tmp_path):
    seed(tmp_path, 'forecast', [forecast()], 'stable')
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        conn.execute("SET TimeZone='UTC'")
        utc_id = conn.execute('select issuance_id from cleaned.nws_forecast_periods limit 1').fetchone()
        conn.execute("SET TimeZone='America/New_York'")
        assert conn.execute('select issuance_id from cleaned.nws_forecast_periods limit 1').fetchone() == utc_id
