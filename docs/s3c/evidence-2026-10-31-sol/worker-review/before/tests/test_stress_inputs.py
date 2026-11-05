from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

import duckdb
import pytest

from grid_pipeline.model import Alert
from grid_pipeline.stress_inputs import annotate_alert_interval, load_first_recorded_history


EIA_DATASET = 'electricity/rto/region-data'
NCEI_DATASET = 'daily-summaries'
NEW_YORK = ZoneInfo('America/New_York')
UTC = timezone.utc


def make_database(path):
    with duckdb.connect(str(path)) as connection:
        connection.execute('CREATE SCHEMA raw')
        connection.execute('''CREATE TABLE raw.batches (
            source VARCHAR, dataset VARCHAR, digest VARCHAR, path VARCHAR,
            loaded_at TIMESTAMPTZ, committed BOOLEAN, observed_at TIMESTAMPTZ,
            PRIMARY KEY (source, dataset, digest))''')
        connection.execute('''CREATE TABLE raw.records (
            source VARCHAR, dataset VARCHAR, digest VARCHAR, row_number INTEGER,
            payload JSON, PRIMARY KEY (source, dataset, digest, row_number))''')


def add_batch(path, source, dataset, digest, loaded_at, rows, *, observed_at=None,
              committed=True):
    with duckdb.connect(str(path)) as connection:
        connection.execute('INSERT INTO raw.batches VALUES (?, ?, ?, ?, ?, ?, ?)',
                           [source, dataset, digest, '', loaded_at, committed, observed_at])
        if rows:
            connection.executemany('INSERT INTO raw.records VALUES (?, ?, ?, ?, ?)', [
                (source, dataset, digest, number, json.dumps(row))
                for number, row in enumerate(rows)
            ])


def hourly_rows(day):
    start = datetime.combine(day, time.min, NEW_YORK).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, NEW_YORK).astimezone(UTC)
    hours = int((end - start).total_seconds() // 3600)
    return [{'period': (start + timedelta(hours=hour)).strftime('%Y-%m-%dT%H'),
             'respondent': 'PJM', 'type': 'D', 'value': 100,
             'value-units': 'megawatthours'}
            for hour in range(1, hours + 1)]


def temperature_row(day, high='70', low='40', high_attributes=',,W'):
    return {'DATE': day.isoformat(), 'STATION': 'USW00093721', 'TMAX': high,
            'TMIN': low, 'TMAX_ATTRIBUTES': high_attributes, 'TMIN_ATTRIBUTES': ',,W'}


@pytest.fixture
def databases(tmp_path):
    load_database = tmp_path / 'load.duckdb'
    temperature_database = tmp_path / 'temperature.duckdb'
    make_database(load_database)
    make_database(temperature_database)
    return load_database, temperature_database


def test_first_recorded_revisions_neighbor_availability_and_read_only(databases):
    load_database, temperature_database = databases
    day = date(2026, 3, 8)
    rows = hourly_rows(day)
    rows[0]['value'] = 105
    rows[1]['value'] = 105
    first_load = datetime(2026, 3, 10, 12, tzinfo=UTC)
    revision_load = datetime(2026, 3, 11, 12, tzinfo=UTC)
    neighbor_load = datetime(2026, 3, 12, 12, tzinfo=UTC)
    add_batch(load_database, 'eia', EIA_DATASET, 'a', first_load, rows,
              observed_at=datetime(2026, 3, 9, tzinfo=UTC))
    add_batch(load_database, 'eia', EIA_DATASET, 'b', revision_load,
              [dict(rows[0], value=180)], observed_at=revision_load)
    add_batch(load_database, 'eia', EIA_DATASET, 'uncommitted',
              datetime(2026, 3, 1, tzinfo=UTC), [dict(rows[0], value=1)], committed=False)
    add_batch(load_database, 'eia', EIA_DATASET, 'other',
              datetime(2026, 3, 1, tzinfo=UTC),
              [dict(rows[0], respondent='BGE', value=999)])
    add_batch(load_database, 'eia', EIA_DATASET, 'neighbor', neighbor_load,
              hourly_rows(day + timedelta(days=1))[:1])
    first_temperature = datetime(2026, 3, 10, 13, tzinfo=UTC)
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', first_temperature,
              [temperature_row(day), temperature_row(day + timedelta(days=1),
                                                     high_attributes=',X,W'),
               temperature_row(day + timedelta(days=2), low=None)],
              observed_at=datetime(2026, 3, 9, tzinfo=UTC))
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'b', revision_load,
              [temperature_row(day, high='90'), temperature_row(day + timedelta(days=1)),
               temperature_row(day + timedelta(days=2))], observed_at=revision_load)
    before = tuple(sha256(path.read_bytes()).digest() for path in databases)

    history = {item.date: item for item in
               load_first_recorded_history(load_database, temperature_database)}

    assert tuple(sha256(path.read_bytes()).digest() for path in databases) == before
    assert history[day].peak_mw == 105
    assert history[day].peak_hour_ending == 1
    assert history[day].complete is True
    assert (history[day].high_f, history[day].morning_low_f) == (70, 40)
    assert history[day].load_first_recorded is True
    assert history[day].temperature_first_recorded is True
    assert history[day].load_available_at == neighbor_load
    assert history[day].temperature_available_at == first_temperature
    assert (history[day + timedelta(days=1)].high_f,
            history[day + timedelta(days=1)].morning_low_f) == (None, None)
    assert history[day + timedelta(days=1)].temperature_first_recorded is True
    assert history[day + timedelta(days=1)].temperature_available_at == first_temperature
    assert (history[day + timedelta(days=2)].high_f,
            history[day + timedelta(days=2)].morning_low_f) == (None, None)
    assert history[day + timedelta(days=2)].load_first_recorded is None
    assert history[day + timedelta(days=2)].load_available_at is None


@pytest.mark.parametrize(('start', 'end', 'expected'), [
    ('2026-03-08T04:59:59+00:00', '2026-03-09T04:00:00+00:00',
     (date(2026, 3, 7), date(2026, 3, 8))),
    ('2026-11-01T03:59:59+00:00', '2026-11-02T05:00:00+00:00',
     (date(2026, 10, 31), date(2026, 11, 1))),
    ('2026-07-01T16:00:00+00:00', '2026-07-01T16:00:01+00:00',
     (date(2026, 7, 1),)),
])
def test_alert_annotations_include_every_overlapped_local_date(start, end, expected):
    alerts = annotate_alert_interval(datetime.fromisoformat(start), datetime.fromisoformat(end),
                                     'synthetic warning', date(2026, 1, 1), date(2026, 12, 31))
    assert alerts == tuple(Alert(day, 'synthetic warning') for day in expected)
