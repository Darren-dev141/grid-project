"""Synthetic raw-to-mart checks using the real DuckDB/dbt DAG."""
from datetime import date, datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

import duckdb
import pytest

from grid_pipeline.storage import ingest
from grid_pipeline.warehouse import build


def test_daily_history_dst_quality_gaps_and_peak_ties(tmp_path):
    tz = ZoneInfo('America/New_York')
    rows = []
    for day in [date(2026, 3, 8), date(2026, 3, 9), date(2026, 11, 1),
                date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 7)]:
        start = datetime.combine(day, datetime.min.time(), tz).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz).astimezone(timezone.utc)
        hours = int((end - start).total_seconds() / 3600)
        for i in range(1, hours + 1):
            value = 100
            if day == date(2026, 3, 9) and i == 2:
                value = None
            if day == date(2026, 11, 2) and i == 3:
                continue
            if day == date(2026, 11, 4):
                value = None
            if day == date(2026, 11, 5) and i == 12:
                value = 300000
            if day == date(2026, 11, 1) and i in (1, 2):
                value = 105
            if day == date(2026, 3, 8) and i == hours:
                value = 105
            rows.append({'period': (start + timedelta(hours=i)).strftime('%Y-%m-%dT%H'),
                         'respondent': 'PJM', 'type': 'D', 'value': value,
                         'value-units': 'megawatthours'})
    rows.append(dict(rows[0], respondent='BGE', value=999999))
    db = tmp_path / 'grid.duckdb'
    ingest(db, tmp_path, 'eia', 'electricity/rto/region-data',
           json.dumps({'response': {'data': rows}}).encode())
    temps = [{'DATE': day, 'STATION': 'USW00093721', 'TMAX': '70', 'TMIN': '40',
              'TMAX_ATTRIBUTES': attrs, 'TMIN_ATTRIBUTES': ',,W'}
             for day, attrs in [('2026-03-08', ',,W'), ('2026-03-09', ',X,W'),
                                ('2026-11-06', ',,W')]]
    ingest(db, tmp_path, 'ncei', 'daily-summaries', json.dumps(temps).encode())
    build(db, select=['+mart_day_history'], artifact_root=tmp_path)
    with duckdb.connect(str(db)) as conn:
        def day(d):
            return conn.execute('''select expected_hours, observed_hours, ok_hours, complete,
                peak_mw, peak_hour_ending, tmax_f, tmin_f
                from marts.mart_day_history where local_date = ?''', [d]).fetchone()
        assert day('2026-03-08') == (23, 23, 23, True, 105, 24, 70, 40)
        assert day('2026-03-09') == (24, 24, 23, False, 100, 1, None, None)
        assert conn.execute("select temperature_quality, day_type from marts.mart_day_history where local_date='2026-03-09'").fetchone() == ('flagged', 'weekday')
        assert day('2026-11-01') == (25, 25, 25, True, 105, 1, None, None)
        assert conn.execute("select peak_hour_utc from marts.mart_day_history where local_date='2026-11-01'").fetchone()[0] == datetime(2026, 11, 1, 5)
        assert day('2026-11-02') == (24, 23, 23, False, 100, 1, None, None)
        assert day('2026-11-03') == (24, 0, 0, False, None, None, None, None)
        assert day('2026-11-04') == (24, 24, 0, False, None, None, None, None)
        assert day('2026-11-05') == (24, 24, 23, False, 100, 1, None, None)
        assert day('2026-11-06') == (24, 0, 0, False, None, None, 70, 40)
        assert day('2026-11-07') == (24, 24, 24, True, 100, 1, None, None)
        assert conn.execute('select count(*), count(distinct local_date) from marts.mart_day_history').fetchone() == (245, 245)


def test_empty_history(tmp_path):
    db = tmp_path / 'grid.duckdb'
    ingest(db, tmp_path, 'eia', 'bootstrap', b'{"response":{"data":[]}}')
    build(db, select=['+mart_day_history'], artifact_root=tmp_path)
    with duckdb.connect(str(db)) as conn:
        assert conn.execute('select count(*) from marts.mart_day_history').fetchone() == (0,)


@pytest.mark.parametrize('local_day, expected', [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)])
def test_dst_day_missing_one_interval_is_incomplete(tmp_path, local_day, expected):
    start = datetime.combine(local_day, datetime.min.time(), ZoneInfo('America/New_York')).astimezone(timezone.utc)
    # On the fall date this omits one of the repeated 01:00 endings. Twenty-four
    # usable intervals still cannot make a twenty-five-hour day complete.
    rows = [{'period': (start + timedelta(hours=i)).strftime('%Y-%m-%dT%H'),
             'respondent': 'PJM', 'type': 'D', 'value': 100, 'value-units': 'megawatthours'}
            for i in range(1, expected + 1) if i != 2]
    db = tmp_path / 'grid.duckdb'
    ingest(db, tmp_path, 'eia', 'electricity/rto/region-data',
           json.dumps({'response': {'data': rows}}).encode())
    build(db, select=['+mart_day_history'], artifact_root=tmp_path)
    with duckdb.connect(str(db)) as conn:
        assert conn.execute('select expected_hours, ok_hours, complete from marts.mart_day_history').fetchone() == (expected, expected - 1, False)


def test_malformed_pjm_value_fails_scoped_build(tmp_path):
    db = tmp_path / 'grid.duckdb'
    row = {'period': '2026-10-01T12', 'respondent': 'PJM', 'type': 'D',
           'value': 'provider format changed', 'value-units': 'megawatthours'}
    ingest(db, tmp_path, 'eia', 'electricity/rto/region-data',
           json.dumps({'response': {'data': [row]}}).encode())
    with pytest.raises(RuntimeError, match='mart_pjm_unparseable_input'):
        build(db, select=['+mart_day_history'], artifact_root=tmp_path)
