"""Real dbt validation of NOAA revisions, flags and staged batches."""
import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import httpx

from grid_pipeline import ncei
from grid_pipeline.storage import ingest
from test_ncei import START, END, row


def run_dbt(root):
    env = os.environ.copy()
    env['GRID_DATABASE'] = str(root / 'grid.duckdb')
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    project = Path(__file__).resolve().parents[1] / 'dbt'
    args = [sys.executable, '-m', 'grid_pipeline.dbt_runner', 'build', '--project-dir', str(project), '--profiles-dir', str(project),
            '--target-path', str(root / 'target'), '--log-path', str(root / 'logs'), '--select', 'ncei_*']
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)


def test_revisions_reversion_quality_and_staging(tmp_path):
    original = [row()]
    revision = [row(high='75')]
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=original))) as client:
        ncei.fetch(tmp_path, START, END, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=revision))) as client:
        ncei.fetch(tmp_path, START, END, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=original))) as client:
        assert ncei.fetch(tmp_path, START, END, client=client)['indexed'] == 0
    db = tmp_path / 'grid.duckdb'
    ingest(db, tmp_path, 'ncei', ncei.DATASET, json.dumps([row(high='99')]).encode(), committed=False)
    cases = [row('2026-10-21', low=None), row('2026-10-22', low='80'),
             row('2026-10-23', high='NaN'), dict(row('2026-10-24'), TMAX_ATTRIBUTES=',X,1')]
    ingest(db, tmp_path, 'ncei', ncei.DATASET, json.dumps(cases).encode())
    result = run_dbt(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(db)) as conn:
        assert conn.execute('select high_f, low_f, quality from cleaned.ncei_bwi_daily_temps order by local_date limit 1').fetchone() == (72, 44, 'ok')
        assert conn.execute('select quality from cleaned.ncei_bwi_daily_temps order by local_date').fetchall() == [('ok',), ('missing',), ('implausible',), ('implausible',), ('flagged',)]
        assert conn.execute('select count(*) from raw.records').fetchone() == (7,)


def test_non_numeric_value_fails_build(tmp_path):
    ingest(tmp_path / 'grid.duckdb', tmp_path, 'ncei', ncei.DATASET,
           json.dumps([row(high='provider format changed')]).encode())
    result = run_dbt(tmp_path)
    assert result.returncode != 0
    assert 'ncei_unparseable_value' in result.stdout
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('select quality from cleaned.ncei_bwi_daily_temps').fetchone() == ('invalid',)
