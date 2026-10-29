from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from grid_pipeline.freshness import check, main
from grid_pipeline.publish import publish
from test_publish import PROJECT, load


NOW = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)


def test_recent_publication_is_fresh(tmp_path):
    root, output = tmp_path / 'data', tmp_path / 'export'
    load(root)
    publish(root / 'grid.duckdb', output, PROJECT, 999, data_kind='synthetic')
    report = check(output, NOW, max_lag_hours=36)
    assert report['fresh'] is True
    # Lag runs from the end of the last usable hour: price 06:00-07:00, mix 05:00-06:00.
    assert report['sources']['price']['lag_hours'] == 1.0
    assert report['sources']['generation']['lag_hours'] == 2.0


def write_publication(output, **fields):
    snapshot_id = 'a' * 32
    (output / 'snapshots' / snapshot_id).mkdir(parents=True)
    (output / 'snapshots' / snapshot_id / 'manifest.json').write_text(json.dumps(fields))
    (output / 'current.json').write_text(json.dumps({'snapshot_id': snapshot_id}))


def test_source_without_usable_hours_is_missing_not_fresh(tmp_path):
    write_publication(tmp_path, price_last_hour_utc='2026-11-01T06:00:00+00:00',
                      renewable_share_last_hour_utc=None)
    report = check(tmp_path, NOW, max_lag_hours=36)
    assert report['fresh'] is False
    assert report['sources']['generation'] == {'status': 'missing'}
    assert report['sources']['price']['status'] == 'fresh'


def test_source_older_than_max_lag_is_stale(tmp_path):
    write_publication(tmp_path, price_last_hour_utc='2026-11-01T06:00:00+00:00',
                      renewable_share_last_hour_utc='2026-10-30T17:00:00+00:00')
    report = check(tmp_path, NOW, max_lag_hours=36)
    assert report['fresh'] is False
    assert report['sources']['generation']['status'] == 'stale'
    assert report['sources']['generation']['lag_hours'] == 38.0
    assert report['sources']['price']['status'] == 'fresh'


def test_hour_ending_after_now_is_rejected_as_future(tmp_path):
    # A local-time value mislabeled as UTC lands hours ahead; it must not look fresh.
    write_publication(tmp_path, price_last_hour_utc='2026-11-01T11:00:00+00:00',
                      renewable_share_last_hour_utc='2026-11-01T06:00:00+00:00')
    report = check(tmp_path, NOW, max_lag_hours=36)
    assert report['fresh'] is False
    assert report['sources']['price']['status'] == 'future'


def test_command_without_publication_fails_cleanly(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(['--output', str(tmp_path)])
    assert exit_info.value.code == 1
    assert 'no readable current publication' in capsys.readouterr().err


def test_command_exits_nonzero_for_stale_publication(tmp_path, capsys):
    write_publication(tmp_path, price_last_hour_utc='2000-01-01T00:00:00+00:00',
                      renewable_share_last_hour_utc='2000-01-01T00:00:00+00:00')
    with pytest.raises(SystemExit) as exit_info:
        main(['--output', str(tmp_path)])
    assert exit_info.value.code == 1
    assert json.loads(capsys.readouterr().out)['sources']['price']['status'] == 'stale'
