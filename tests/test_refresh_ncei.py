"""NCEI catch-up wrapper: window derivation, dry run, and delegation to ncei.fetch; no network."""
from datetime import date
import json

import httpx
import pytest

from grid_pipeline import ncei
from grid_pipeline.storage import ingest
from scripts import refresh_ncei


def _row(day):
    return {'DATE': day, 'STATION': ncei.STATION, 'TMAX': '70', 'TMIN': '45',
            'TMAX_ATTRIBUTES': ',,1', 'TMIN_ATTRIBUTES': ',,1'}


def _archive(root, *days, committed=True):
    body = json.dumps([_row(day) for day in days]).encode()
    ingest(root / 'grid.duckdb', root, 'ncei', ncei.DATASET, body, committed=committed)


def _no_network(*args, **kwargs):
    raise AssertionError('network path must not run')


@pytest.mark.parametrize(('latest', 'today', 'overlap', 'expected'), [
    (date(2026, 10, 24), date(2026, 11, 5), 3, (date(2026, 10, 21), date(2026, 11, 5))),
    (date(2026, 10, 24), date(2026, 11, 5), 0, (date(2026, 10, 24), date(2026, 11, 5))),
    (date(2026, 11, 3), date(2026, 11, 5), 3, (date(2026, 10, 31), date(2026, 11, 5))),
    (date(2026, 11, 4), date(2026, 11, 5), 3, None),
    (date(2026, 11, 5), date(2026, 11, 5), 3, None),
])
def test_window_ends_today_exclusive_and_is_none_when_current(latest, today, overlap, expected):
    assert refresh_ncei.plan_window(latest, today, overlap) == expected


def test_latest_recorded_date_ignores_uncommitted_and_missing_archives(tmp_path):
    assert refresh_ncei.latest_recorded_date(tmp_path) is None
    _archive(tmp_path, '2026-10-20', '2026-10-24')
    _archive(tmp_path, '2026-10-30', committed=False)
    assert refresh_ncei.latest_recorded_date(tmp_path) == date(2026, 10, 24)


def test_dry_run_prints_the_window_and_the_grid_temps_command_without_network(
        tmp_path, monkeypatch, capsys):
    _archive(tmp_path, '2026-10-24')
    monkeypatch.setattr(ncei, 'fetch', _no_network)
    code = refresh_ncei.main(['--root', str(tmp_path), '--dry-run'], today=date(2026, 11, 5))
    printed = json.loads(capsys.readouterr().out)
    assert code == 0
    assert (printed['status'], printed['start'], printed['end']) == (
        'dry_run', '2026-10-21', '2026-11-05')
    assert printed['equivalent_command'] == (
        f'grid-temps --root {tmp_path} --start 2026-10-21 --end 2026-11-05')


def test_current_archive_is_a_no_op(tmp_path, monkeypatch, capsys):
    _archive(tmp_path, '2026-11-04')
    monkeypatch.setattr(ncei, 'fetch', _no_network)
    assert refresh_ncei.main(['--root', str(tmp_path)], today=date(2026, 11, 5)) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'current'


def test_catch_up_requests_exactly_the_window_and_lands_the_rows(tmp_path, capsys):
    _archive(tmp_path, '2026-10-24')
    seen = []

    def handler(request):
        seen.append((request.url.params['startDate'], request.url.params['endDate']))
        return httpx.Response(200, content=json.dumps(
            [_row('2026-10-25'), _row('2026-11-03'), _row('2026-11-04')]).encode())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        code = refresh_ncei.main(['--root', str(tmp_path)], client=client, today=date(2026, 11, 5))
    assert code == 0
    assert seen == [('2026-10-21', '2026-11-04')]       # endDate is inclusive in the NCEI API
    assert json.loads(capsys.readouterr().out)['status'] == 'fetched'
    assert refresh_ncei.latest_recorded_date(tmp_path) == date(2026, 11, 4)


def test_failure_exits_nonzero_without_a_traceback(tmp_path, capsys):
    _archive(tmp_path, '2026-10-24')
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as client:
        assert refresh_ncei.main(['--root', str(tmp_path)], client=client,
                                 today=date(2026, 11, 5)) == 1
    assert 'NCEI HTTP 403' in capsys.readouterr().err


def test_missing_archive_asks_for_an_explicit_start(tmp_path, capsys):
    assert refresh_ncei.main(['--root', str(tmp_path)], today=date(2026, 11, 5)) == 1
    assert 'explicit --start' in capsys.readouterr().err
