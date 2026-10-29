import json

import duckdb
import httpx
import pytest

from grid_pipeline.fetch import LoadError, fetch, utc_hour


START = utc_hour('2026-10-01T00:00Z')
END = utc_hour('2026-10-01T02:00Z')


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv('EIA_API_KEY', 'synthetic-eia-secret')


def page(source, rows, total):
    defaults = {'period': '2026-10-01T00', 'respondent': 'PJM'}
    rows = [defaults | row for row in rows]
    return {'response': {'data': rows, 'total': str(total)}}


def checkpoint(root):
    with duckdb.connect(str(root / 'grid.duckdb')) as conn:
        return conn.execute('SELECT completed_until FROM ops.checkpoints').fetchall()


def test_pagination_and_checkpoint(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=page('eia', [{'value': len(requests)}], 2))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client)
        assert result['indexed'] == 2
        assert result['pages'] == 2
        assert checkpoint(tmp_path) == [(END,)]
        assert fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, client=client)['status'] == 'already_complete'
    assert len(requests) == 2
    assert [r.url.params['offset'] for r in requests] == ['0', '1']
    assert requests[0].url.params['end'] == '2026-10-01T01'


def test_failure_then_recovery_reuses_raw_without_advancing(tmp_path):
    calls = []

    def failed(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json=page('eia', [{'value': 1}], 2))
        return httpx.Response(403, text='synthetic-eia-secret')

    with httpx.Client(transport=httpx.MockTransport(failed)) as client:
        with pytest.raises(LoadError, match='HTTP 403'):
            fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client)
    assert checkpoint(tmp_path) == []
    assert len(list((tmp_path / 'raw/eia').glob('*.json'))) == 1

    def recovered(request):
        return httpx.Response(200, json=page('eia', [{'value': int(request.url.params['offset']) + 1}], 2))

    with httpx.Client(transport=httpx.MockTransport(recovered)) as client:
        assert fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client)['indexed'] == 2
    assert checkpoint(tmp_path) == [(END,)]
    assert len(list((tmp_path / 'raw/eia').glob('*.json'))) == 2


def test_retry_after_and_network_error_are_bounded(tmp_path):
    calls, delays = [], []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError('authenticated URL must not be logged', request=request)
        if len(calls) == 2:
            return httpx.Response(429, headers={'Retry-After': '3'})
        return httpx.Response(200, json=page('eia', [{'value': 1}], 1))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, client=client, sleep=delays.append)
    assert delays == [1, 3]
    assert len(calls) == 3


@pytest.mark.parametrize('case', ['repeat', 'changed_total', 'empty', 'malformed', 'credential', 'redirect', 'exhausted'])
def test_invalid_pages_never_advance(tmp_path, case):
    calls = []

    def handler(request):
        calls.append(request)
        if case == 'credential':
            return httpx.Response(200, text='synthetic-eia-secret')
        if case == 'redirect':
            return httpx.Response(302, headers={'Location': 'https://example.com'})
        if case == 'exhausted':
            return httpx.Response(503)
        if case == 'malformed':
            return httpx.Response(200, text='not JSON')
        if case == 'empty':
            return httpx.Response(200, json=page('eia', [], 0))
        total = 3 if case == 'changed_total' and len(calls) > 1 else 2
        return httpx.Response(200, json=page('eia', [{'value': 1}], total))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LoadError) as error:
            fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client, sleep=lambda _: None)
    assert 'synthetic-eia-secret' not in str(error.value)
    assert checkpoint(tmp_path) == []
    if case == 'credential':
        assert not (tmp_path / 'raw').exists()
    if case == 'exhausted':
        assert len(calls) == 4


def test_overlap_and_gap_protection(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=page('eia', [{'value': len(requests), 'period': request.url.params['start']}], 1))

    later = utc_hour('2026-10-01T04:00Z')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch(tmp_path, 'fuel-mix', START, END, client=client)
        fetch(tmp_path, 'fuel-mix', START, later, overlap_hours=1, client=client)
        assert requests[1].url.params['start'] == '2026-10-01T01'
        with pytest.raises(LoadError, match='skip a gap'):
            fetch(tmp_path, 'fuel-mix', utc_hour('2026-10-02T00:00Z'), utc_hour('2026-10-03T00:00Z'), client=client)
    assert checkpoint(tmp_path) == [(later,)]


@pytest.mark.parametrize('value', ['2026-10-01T00:00', '2026-10-01T00:01Z', '2026-10-01T00:00-04:00'])
def test_requires_explicit_utc_hour(value):
    with pytest.raises(ValueError):
        utc_hour(value)


def test_missing_credentials_fails_before_network_or_storage(tmp_path, monkeypatch):
    monkeypatch.delenv('EIA_API_KEY')
    with pytest.raises(LoadError, match='missing EIA_API_KEY'):
        fetch(tmp_path, 'fuel-mix', START, END)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('source,row', [
    ('fuel-mix', {'period': '2026-09-30T23'}),
    ('fuel-mix', {'period': '2026-10-01T02'}),
    ('fuel-mix', {'respondent': 'OTHER'}),
])
def test_wrong_interval_or_geography_fails_closed(tmp_path, source, row):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=page(source, [row], 1))
    )) as client:
        with pytest.raises(LoadError, match='interval or geography'):
            fetch(tmp_path, source, START, END, overlap_hours=0, client=client)
    assert checkpoint(tmp_path) == []


def test_interrupted_indexing_leaves_batches_uncommitted(tmp_path, monkeypatch):
    from grid_pipeline import fetch as fetch_module
    original = fetch_module.ingest
    calls = []

    def interrupted(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise OSError('simulated disk failure')
        return original(*args, **kwargs)

    def handler(request):
        return httpx.Response(200, json=page('eia', [{'value': request.url.params['offset']}], 2))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(fetch_module, 'ingest', interrupted)
        with pytest.raises(OSError, match='disk failure'):
            fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client)
        assert checkpoint(tmp_path) == []
        with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
            assert conn.execute('SELECT committed, observed_at FROM raw.batches').fetchall() == [(False, None)]
        monkeypatch.setattr(fetch_module, 'ingest', original)
        result = fetch(tmp_path, 'fuel-mix', START, END, overlap_hours=0, page_size=1, client=client)
    assert result['indexed'] == 1  # The first staged page was reused.
    assert checkpoint(tmp_path) == [(END,)]
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('SELECT count(*) FROM raw.batches WHERE committed AND observed_at IS NOT NULL').fetchone() == (2,)


# New EIA-930 registry and backfill contract.
EIA_ROWS = {
    'fuel-mix': {'period': '2026-10-01T00', 'respondent': 'PJM', 'fueltype': 'NG', 'value': '1'},
    'pjm-demand': {'period': '2026-10-01T00', 'respondent': 'PJM', 'respondent-name': 'PJM Interconnection, LLC', 'type': 'D', 'type-name': 'Demand', 'value': '94016', 'value-units': 'megawatthours'},
    'bge-demand': {'period': '2026-10-01T00', 'subba': 'BC', 'subba-name': 'Baltimore Gas & Electric zone', 'parent': 'PJM', 'parent-name': 'PJM Interconnection, LLC', 'value': '3987', 'value-units': 'megawatthours'},
}
EIA_CONTRACT = {
    'fuel-mix': ('electricity/rto/fuel-type-data', {'facets[respondent][]': 'PJM'}, 'eia:electricity/rto/fuel-type-data:PJM'),
    'pjm-demand': ('electricity/rto/region-data', {'facets[respondent][]': 'PJM', 'facets[type][]': 'D'}, 'eia:electricity/rto/region-data:PJM:D'),
    'bge-demand': ('electricity/rto/region-sub-ba-data', {'facets[parent][]': 'PJM', 'facets[subba][]': 'BC'}, 'eia:electricity/rto/region-sub-ba-data:PJM:BC'),
}


@pytest.mark.parametrize('dataset', EIA_CONTRACT)
def test_named_dataset_routes_facets_stream_and_raw_route(tmp_path, dataset):
    route, facets, stream = EIA_CONTRACT[dataset]
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'response': {'data': [EIA_ROWS[dataset]], 'total': '1'}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch(tmp_path, dataset, START, END, overlap_hours=0, client=client)['status'] == 'complete'
    request = seen[0]
    assert request.url.path.endswith('/' + route + '/data/')
    assert {key: request.url.params[key] for key in facets} == facets
    with duckdb.connect(str(tmp_path / 'grid.duckdb')) as conn:
        assert conn.execute('SELECT stream FROM ops.checkpoints').fetchone() == (stream,)
        assert conn.execute('SELECT DISTINCT dataset FROM raw.batches').fetchone() == (route,)


@pytest.mark.parametrize('dataset,row', [
    ('fuel-mix', {'respondent': 'MISO'}),
    ('pjm-demand', {'type': 'DF'}),
    ('bge-demand', {'subba': 'PE'}),
])
def test_named_dataset_wrong_scope_fails_closed(tmp_path, dataset, row):
    bad = EIA_ROWS[dataset] | row
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, json={'response': {'data': [bad], 'total': '1'}}
    ))) as client:
        with pytest.raises(LoadError, match='interval or geography'):
            fetch(tmp_path, dataset, START, END, overlap_hours=0, client=client)
    assert checkpoint(tmp_path) == []


def test_backfill_exact_windows_and_completion_is_noop(tmp_path):
    from grid_pipeline.fetch_cli import backfill
    seen = []

    def handler(request):
        seen.append((request.url.params['start'], request.url.params['end']))
        row = EIA_ROWS['pjm-demand'] | {'period': request.url.params['start']}
        return httpx.Response(200, json={'response': {'data': [row], 'total': '1'}})

    start = utc_hour('2026-10-01T00:00Z')
    end = utc_hour('2026-10-11T00:00Z')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backfill(tmp_path, 'pjm-demand', start, end, window_days=4, client=client)
        backfill(tmp_path, 'pjm-demand', start, end, window_days=4, client=client)
    assert seen == [('2026-10-01T00', '2026-10-04T23'),
                    ('2026-10-05T00', '2026-10-08T23'),
                    ('2026-10-09T00', '2026-10-10T23')]


def test_backfill_resumes_after_failed_window_without_refetching_completed(tmp_path):
    from grid_pipeline.fetch_cli import backfill
    seen = []
    fail_window = True

    def handler(request):
        nonlocal fail_window
        start = request.url.params['start']
        seen.append(start)
        if start == '2026-10-05T00' and fail_window:
            return httpx.Response(503)
        dataset = 'pjm-demand'
        row = EIA_ROWS[dataset] | {'period': start}
        return httpx.Response(200, json={'response': {'data': [row], 'total': '1'}})

    start = utc_hour('2026-10-01T00:00Z')
    end = utc_hour('2026-10-09T00:00Z')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LoadError):
            backfill(tmp_path, 'pjm-demand', start, end, window_days=4, client=client, sleep=lambda _: None)
        fail_window = False
        backfill(tmp_path, 'pjm-demand', start, end, window_days=4, client=client)
    assert seen == ['2026-10-01T00'] + ['2026-10-05T00'] * 5
