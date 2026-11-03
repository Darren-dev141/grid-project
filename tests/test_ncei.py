"""NCEI contract, raw retention, replay and bounded retry tests; no network."""
from datetime import date
import json

import duckdb
import httpx
import pytest

from grid_pipeline import ncei
from grid_pipeline.fetch import LoadError
from grid_pipeline.storage import ingest

START, END = date(2026, 10, 20), date(2026, 10, 23)


def row(day='2026-10-20', high='72', low='44'):
    return {'DATE': day, 'STATION': ncei.STATION, 'TMAX': high, 'TMIN': low,
            'TMAX_ATTRIBUTES': ',,1', 'TMIN_ATTRIBUTES': ',,1'}


def test_fetch_contract_and_identical_replay(tmp_path):
    body = json.dumps([row()]).encode()
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.params['startDate'] == '2026-10-20'
        assert request.url.params['endDate'] == '2026-10-22'
        assert request.url.params['units'] == 'standard'
        assert request.url.params['stations'] == ncei.STATION
        assert request.url.params['includeAttributes'] == 'true'
        assert 'token' not in request.headers and 'api_key' not in request.url.params
        return httpx.Response(200, content=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert ncei.fetch(tmp_path, START, END, client=client)['indexed'] == 1
        assert ncei.fetch(tmp_path, START, END, client=client)['indexed'] == 0
    assert len(calls) == 2
    assert next((tmp_path / 'raw/ncei').glob('*.json')).read_bytes() == body
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('select count(*) from raw.records').fetchone() == (1,)
        assert conn.execute('select committed, observed_at is not null from raw.batches').fetchone() == (True, True)


@pytest.mark.parametrize('body', [b'{bad', b'{}', b'[{}]',
    json.dumps([dict(row(), STATION='wrong')]).encode(),
    json.dumps([row('2026-10-23')]).encode(),
    json.dumps([row(), row()]).encode(),
    json.dumps([row('20261020')]).encode()])
def test_invalid_scope_lands_without_index(tmp_path, body):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
        with pytest.raises(LoadError, match='raw body retained'):
            ncei.fetch(tmp_path, START, END, client=client)
    assert next((tmp_path / 'raw/ncei').glob('*.json')).read_bytes() == body
    assert not (tmp_path / 'grid.duckdb').exists()


@pytest.mark.parametrize('status,headers,attempts', [(403, {}, 1), (503, {}, 3), (429, {'Retry-After': '120'}, 1)])
def test_bounded_http_failures(tmp_path, status, headers, attempts):
    calls, delays = [], []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers=headers, content=b'private upstream message')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LoadError) as exc:
            ncei.fetch(tmp_path, START, END, client=client, sleep=delays.append)
    assert 'private' not in str(exc.value)
    assert len(calls) == attempts
    assert delays == ([1, 2] if attempts == 3 else [])
    assert next((tmp_path / 'raw/ncei').glob('*.json')).read_bytes() == b'private upstream message'


def test_network_retry_then_success(tmp_path):
    calls, delays = [], []
    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError('private', request=request)
        return httpx.Response(200, json=[])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert ncei.fetch(tmp_path, START, END, client=client, sleep=delays.append)['days'] == 0
    assert delays == [1, 2]


def test_network_exhaustion(tmp_path):
    def handler(request):
        raise httpx.ConnectError('private', request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LoadError, match='after 3 attempts'):
            ncei.fetch(tmp_path, START, END, client=client, sleep=lambda _: None)


@pytest.mark.parametrize('start,end', [(END, START), (START, START), (START, date(2028, 1, 1))])
def test_invalid_interval_has_no_side_effects(tmp_path, start, end):
    with pytest.raises(LoadError, match='1 to 366'):
        ncei.fetch(tmp_path, start, end)
    assert list(tmp_path.iterdir()) == []


def test_replay_validates_dataset(tmp_path):
    with pytest.raises(ValueError, match='unsupported NCEI'):
        ingest(tmp_path / 'grid.duckdb', tmp_path, 'ncei', 'other', b'[]')


def test_cli_success_and_safe_failure(tmp_path, monkeypatch, capsys):
    args = ['--root', str(tmp_path), '--start', START.isoformat(), '--end', END.isoformat()]
    monkeypatch.setattr(ncei, 'fetch', lambda *args: {'days': 1})
    assert ncei.main(args) == 0
    assert json.loads(capsys.readouterr().out) == {'days': 1}
    def broken(*args):
        raise OSError('private path')
    monkeypatch.setattr(ncei, 'fetch', broken)
    assert ncei.main(args) == 1
    assert 'private' not in capsys.readouterr().err
