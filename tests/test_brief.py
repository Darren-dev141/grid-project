from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline import ledger
from grid_pipeline.brief import BriefFacts, _fmt_time, _warehouse_facts, render, render_brief
from grid_pipeline.model import Forecast


UTC = timezone.utc
NEW_YORK = ZoneInfo('America/New_York')
EIA_DATASET = 'electricity/rto/region-data'
NCEI_DATASET = 'daily-summaries'
NWS_DATASET = 'forecast_bwi'


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


def add_batch(path, source, dataset, digest, loaded_at, rows, *, observed_at=None):
    with duckdb.connect(str(path)) as connection:
        connection.execute('INSERT INTO raw.batches VALUES (?, ?, ?, ?, ?, ?, ?)',
                           [source, dataset, digest, '', loaded_at, True, observed_at])
        if rows:
            connection.executemany('INSERT INTO raw.records VALUES (?, ?, ?, ?, ?)', [
                (source, dataset, digest, number, json.dumps(row))
                for number, row in enumerate(rows)
            ])


def hourly_rows(day, base):
    start = datetime.combine(day, time.min, NEW_YORK).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, NEW_YORK).astimezone(UTC)
    hours = int((end - start).total_seconds() // 3600)
    return [{'period': (start + timedelta(hours=hour)).strftime('%Y-%m-%dT%H'),
             'respondent': 'PJM', 'type': 'D', 'value': str(base + hour),
             'value-units': 'megawatthours'}
            for hour in range(1, hours + 1)]


def temperature_row(day, high='70', low='40'):
    return {'DATE': day.isoformat(), 'STATION': 'USW00093721', 'TMAX': high,
            'TMIN': low, 'TMAX_ATTRIBUTES': ',,W', 'TMIN_ATTRIBUTES': ',,W'}


def make_ledger_root(tmp_path):
    root = tmp_path / 'ledger'
    (root / 'definitions').mkdir(parents=True)
    raw = ledger.read_definition(
        Path(__file__).resolve().parents[1] / 'ledger/definitions/stress-index-v1.toml')
    (root / 'definitions/stress-index-v1.toml').write_bytes(raw)
    return root


def test_rendered_brief_from_built_warehouse_has_real_scored_content(tmp_path):
    database = tmp_path / 'grid.duckdb'
    make_database(database)
    index = 0
    for year in (2023, 2024, 2025, 2026):
        days = [date(year, 6, 24) + timedelta(days=offset) for offset in range(21)]
        loaded = datetime(year, 7, 16, 12, tzinfo=UTC)
        load_rows = []
        for day in days:
            load_rows += hourly_rows(day, 90000 + (index * 137) % 5000)
            index += 1
        add_batch(database, 'eia', EIA_DATASET, f'eia-{year}', loaded,
                  load_rows, observed_at=loaded)
        add_batch(database, 'ncei', NCEI_DATASET, f'ncei-{year}', loaded,
                  [temperature_row(day, str(82 + i % 8), str(58 + i % 4))
                   for i, day in enumerate(days)], observed_at=loaded)
    add_batch(database, 'nws', NWS_DATASET, 'nws-2026',
              datetime(2026, 7, 15, 10, tzinfo=UTC),
              [{'properties': {'updateTime': '2026-07-15T05:00:00Z',
                               'generatedAt': '2026-07-15T05:00:00Z',
                               'periods': [
                                   {'number': 1, 'startTime': '2026-07-15T01:00:00-04:00',
                                    'endTime': '2026-07-15T06:00:00-04:00',
                                    'isDaytime': False, 'temperature': 62,
                                    'temperatureUnit': 'F'},
                                   {'number': 2, 'startTime': '2026-07-15T06:00:00-04:00',
                                    'endTime': '2026-07-15T18:00:00-04:00',
                                    'isDaytime': True, 'temperature': 88,
                                    'temperatureUnit': 'F'}]}}],
              observed_at=datetime(2026, 7, 15, 10, tzinfo=UTC))
    out = tmp_path / 'site'
    rendered = render_brief(database, make_ledger_root(tmp_path), out,
                            target_date=date(2026, 7, 15),
                            generated_at=datetime(2026, 7, 15, 11, tzinfo=UTC))
    assert rendered.forecast.no_call_reason is None
    assert rendered.forecast.level in {'calm', 'watch', 'strained', 'severe'}
    assert rendered.forecast.peak_mw is not None
    page = rendered.index_path.read_text(encoding='utf-8')
    assert '2026-07-15' in page
    assert f'Stress level: {rendered.forecast.level}' in page
    assert 'Peak demand:' in page
    assert 'Peak hour ending:' in page
    assert 'Load: fresh' in page and 'Weather: fresh' in page
    assert 'Data as of: 2026-07-14' in page
    assert 'tile.openstreetmap.org' in page
    assert page.index('map.addLayer(renderer)') < page.index('L.geoJSON')
    comment = rendered.comment_path.read_text(encoding='utf-8')
    assert '2026-07-15' in comment
    assert 'No receipts in the ledger for this target date.' in comment


def test_no_call_brief_from_tiny_warehouse_shows_reason_and_no_claims(tmp_path):
    database = tmp_path / 'grid.duckdb'
    make_database(database)
    day = date(2026, 10, 1)
    loaded = datetime(2026, 10, 3, 12, tzinfo=UTC)
    add_batch(database, 'eia', EIA_DATASET, 'eia', loaded, hourly_rows(day, 90000),
              observed_at=loaded)
    add_batch(database, 'ncei', NCEI_DATASET, 'ncei', loaded, [temperature_row(day)],
              observed_at=loaded)
    out = tmp_path / 'site'
    rendered = render_brief(database, make_ledger_root(tmp_path), out,
                            target_date=date(2026, 10, 20),
                            generated_at=datetime(2026, 10, 20, 11, tzinfo=UTC))
    assert rendered.forecast.no_call_reason == 'stale_load'
    page = rendered.index_path.read_text(encoding='utf-8')
    assert '2026-10-20' in page
    assert 'No call — stale_load' in page
    assert 'No peak demand, peak hour, or stress level is claimed' in page
    assert 'Load: stale' in page
    comment = rendered.comment_path.read_text(encoding='utf-8')
    assert '**No call** — `stale_load`' in comment


def test_warehouse_naive_hour_is_utc_regardless_of_host_timezone(tmp_path):
    database = tmp_path / 'grid.duckdb'
    with duckdb.connect(str(database)) as connection:
        connection.execute('CREATE SCHEMA cleaned')
        connection.execute('CREATE TABLE cleaned.eia_pjm_hourly_demand (hour_utc TIMESTAMP)')
        connection.execute("INSERT INTO cleaned.eia_pjm_hourly_demand VALUES ('2026-11-08 22:00:00')")
    _, hour = _warehouse_facts(database)
    assert hour == datetime(2026, 11, 8, 22, tzinfo=UTC)
    assert _fmt_time(hour) == '2026-11-08 22:00 UTC'


def test_pure_render_no_call_and_receipt_listing():
    forecast = Forecast(date(2026, 11, 6), 'stress-index-v1', 'a' * 64,
                        None, None, None, None, 'stale_weather', ())
    facts = BriefFacts(load_fresh=True, weather_fresh=False,
                       latest_completed_peak=date(2026, 11, 4),
                       latest_completed_present=True, history_days=84,
                       history_last_date=date(2026, 11, 4),
                       data_as_of=date(2026, 11, 4), load_last_hour_utc=None,
                       weather_update_time=None, target_high_f=None,
                       target_morning_low_f=None)
    digest = 'b' * 64
    path = f'ledger/forecasts/ours/2026-11-06/{digest}.json'
    brief = render(forecast, facts, [(path, digest)],
                   generated_at=datetime(2026, 11, 6, 12, tzinfo=UTC))
    assert 'No call — stale_weather' in brief.html
    assert 'Weather: stale' in brief.html
    assert f'`{path}` — sha256: `{digest}`' in brief.comment_md


def test_comment_lists_receipt_path_and_full_sha256_from_ledger(tmp_path):
    database = tmp_path / 'grid.duckdb'
    make_database(database)
    day = date(2026, 10, 1)
    loaded = datetime(2026, 10, 3, 12, tzinfo=UTC)
    add_batch(database, 'eia', EIA_DATASET, 'eia', loaded, hourly_rows(day, 90000),
              observed_at=loaded)
    add_batch(database, 'ncei', NCEI_DATASET, 'ncei', loaded, [temperature_row(day)],
              observed_at=loaded)
    root = make_ledger_root(tmp_path)
    raw = (json.dumps({'target_date': '2026-10-20', 'forecaster_id': 'ours'}) + '\n').encode()
    digest = sha256(raw).hexdigest()
    receipt = root / 'forecasts/ours/2026-10-20' / f'{digest}.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes(raw)
    rendered = render_brief(database, root, tmp_path / 'site',
                            target_date=date(2026, 10, 20),
                            generated_at=datetime(2026, 10, 20, 11, tzinfo=UTC))
    comment = rendered.comment_path.read_text(encoding='utf-8')
    assert f'ledger/forecasts/ours/2026-10-20/{digest}.json' in comment
    assert f'sha256: `{digest}`' in comment
