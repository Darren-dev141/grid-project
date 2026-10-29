import json
import httpx
import pytest
from grid_pipeline.storage import ingest


def forecast():
    return {'properties': {'updateTime': '2026-10-28T12:00:00Z', 'generatedAt': '2026-10-28T12:01:00Z', 'periods': [{'number': 1, 'startTime': '2026-10-28T08:00:00-04:00', 'endTime': '2026-10-28T18:00:00-04:00', 'isDaytime': True, 'temperature': 70, 'temperatureUnit': 'F'}]}}


def test_storage(tmp_path):
    body=json.dumps(forecast()).encode()
    assert ingest(tmp_path/'grid.duckdb',tmp_path,'nws','forecast',body)==1
    assert ingest(tmp_path/'grid.duckdb',tmp_path,'nws','forecast',body)==0
    assert next((tmp_path/'raw/nws').glob('*.json')).read_bytes()==body
    assert ingest(tmp_path/'grid.duckdb',tmp_path,'nws','alerts',b'{"features": []}')==0


def test_missing_ua(tmp_path,monkeypatch):
    from grid_pipeline.nws import fetch
    monkeypatch.delenv('NWS_USER_AGENT',raising=False)
    with pytest.raises(RuntimeError,match='NWS_USER_AGENT'):
        fetch(tmp_path)


@pytest.mark.parametrize('mode', ['ok','retry','mismatch','malformed','network','forbidden'])
def test_fetch(tmp_path,monkeypatch,mode):
    from grid_pipeline.nws import fetch
    monkeypatch.setenv('NWS_USER_AGENT','synthetic-agent')
    calls=[]; delays=[]
    def handler(request):
        calls.append(request)
        assert request.headers['Accept']=='application/geo+json'
        assert request.headers['User-Agent']=='synthetic-agent'
        if mode=='network': raise httpx.ConnectError('sensitive',request=request)
        if mode=='retry': return httpx.Response(503,text='sensitive')
        if mode=='forbidden': return httpx.Response(403,text='sensitive')
        if '/points/' in request.url.path:
            return httpx.Response(200,json={'properties':{'gridId':'LWX','gridX':0 if mode=='mismatch' else 100,'gridY':98}})
        if mode=='malformed': return httpx.Response(200,content=b'{bad')
        return httpx.Response(200,json=forecast() if 'forecast' in request.url.path else {'features':[]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        if mode=='ok':
            assert fetch(tmp_path,client=client,sleep=delays.append)=={'forecast':1,'alerts':0}
            assert fetch(tmp_path,client=client,sleep=delays.append)=={'forecast':0,'alerts':0}
        else:
            with pytest.raises(RuntimeError) as exc: fetch(tmp_path,client=client,sleep=delays.append)
            assert 'sensitive' not in str(exc.value)
    if mode in {'retry','network'}: assert len(calls)==3 and delays==[1,2]
    if mode in {'forbidden','mismatch'}: assert len(calls)==1
    if mode=='malformed':
        assert any(p.read_bytes()==b'{bad' for p in (tmp_path/'raw/nws').glob('*'))
        assert not (tmp_path/'grid.duckdb').exists()


def test_cli_failure(tmp_path,monkeypatch,capsys):
    from grid_pipeline.nws import main
    monkeypatch.delenv('NWS_USER_AGENT',raising=False)
    assert main(['--root',str(tmp_path)])==1
    assert 'NWS_USER_AGENT' in capsys.readouterr().err

@pytest.mark.parametrize('payload,dataset', [
    ({'properties': {'periods': [{}], 'updateTime':'2026-10-28T12:00:00Z','generatedAt':'2026-10-28T12:01:00Z'}},'forecast'),
    ({'features': [{}]}, 'alerts'),
])
def test_incomplete_records_land_without_index(tmp_path,payload,dataset):
    body=json.dumps(payload).encode()
    with pytest.raises(ValueError,match='invalid NWS'):
        ingest(tmp_path/'grid.duckdb',tmp_path,'nws',dataset,body)
    assert next((tmp_path/'raw/nws').glob('*')).read_bytes()==body
    assert not (tmp_path/'grid.duckdb').exists()


def test_console_registration():
    import tomllib
    from pathlib import Path
    config=tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())
    assert config['project']['scripts']['grid-weather']=='grid_pipeline.nws:main'

@pytest.mark.parametrize('status', [403,429,503])
def test_http_error_body_retained(tmp_path,monkeypatch,status):
    from grid_pipeline.nws import fetch
    monkeypatch.setenv('NWS_USER_AGENT','synthetic-agent')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status,content=b'upstream error bytes'))) as client:
        with pytest.raises(RuntimeError): fetch(tmp_path,client=client,sleep=lambda _:None)
    assert any(p.read_bytes()==b'upstream error bytes' for p in (tmp_path/'raw/nws').glob('*'))


def test_cli_success_and_safe_storage_failure(tmp_path,monkeypatch,capsys):
    from grid_pipeline import nws
    monkeypatch.setattr(nws,'fetch',lambda root:{'forecast':1,'alerts':0})
    assert nws.main(['--root',str(tmp_path)])==0
    assert json.loads(capsys.readouterr().out)=={'forecast':1,'alerts':0}
    def broken(root): raise OSError('private path secret')
    monkeypatch.setattr(nws,'fetch',broken)
    assert nws.main(['--root',str(tmp_path)])==1
    output=capsys.readouterr().err
    assert 'private' not in output and 'failed' in output


def test_retry_after_does_not_retry_early(tmp_path,monkeypatch):
    from grid_pipeline.nws import fetch
    monkeypatch.setenv('NWS_USER_AGENT','synthetic-agent')
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,headers={'Retry-After':'120'},content=b'throttled')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError,match='later retry'):
            fetch(tmp_path,client=client,sleep=lambda _:None)
    assert len(calls)==1
