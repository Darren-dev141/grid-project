from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from grid_pipeline import ledger
from grid_pipeline.model import Forecast, ForecastReceipt


def git(repo, *args, ok=True):
    result = subprocess.run(['git', '-c', f'safe.directory={repo.as_posix()}',
                             '-C', str(repo), *args], cwd=repo, capture_output=True, text=True)
    if ok:
        assert result.returncode == 0, result.stderr
    return result


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, 'init')
    git(tmp_path, 'config', 'user.name', 'Ledger Test')
    git(tmp_path, 'config', 'user.email', 'ledger@example.invalid')
    (tmp_path / 'README').write_text('fixture')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-m', 'initial')
    root = tmp_path / 'ledger'
    (root / 'definitions').mkdir(parents=True)
    (root / 'definitions/stress-index-v1.toml').write_bytes(b'version = "v1"\n')
    return tmp_path


def call():
    issued = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=2)
    target = (issued + timedelta(days=3)).date()
    forecast = Forecast(target, 'stress-index-v1', sha256(b'version = "v1"\n').hexdigest(),
                        None, None, None, None, 'stale_weather', (),
                        receipt=ForecastReceipt('prospective', 'verified', issued))
    return forecast, issued


def test_hash_multiple_receipts_and_exclusive_create(repository):
    forecast, issued = call()
    root = repository / 'ledger'
    first = ledger.append_forecast(root, 'stress', forecast, issued)
    assert first.stem == sha256(first.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        ledger.append_forecast(root, 'stress', forecast, issued)
    changed = replace(forecast, no_call_reason='stale_load')
    second = ledger.append_forecast(root, 'stress', changed, issued)
    assert second != first
    assert ledger.verify(repository, integrity_only=True)['receipts'] == 2
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'receipts')
    assert ledger.verify(repository, integrity_only=True)['historical_receipt_additions'] == 2


def test_hash_mismatch_and_readdressed_back_edit_fail(repository):
    forecast, issued = call()
    path = ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'receipt')
    raw = path.read_bytes().replace(b'stale_weather', b'stale_load')
    path.write_bytes(raw)
    with pytest.raises(ledger.LedgerError, match='hash'):
        ledger.verify(repository)
    path.unlink()
    path.with_name(sha256(raw).hexdigest() + '.json').write_bytes(raw)
    with pytest.raises(ledger.LedgerError, match='changed or deleted'):
        ledger.verify(repository)


def test_committed_definition_back_edit_fails_full_history(repository):
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'definition')
    (repository / 'ledger/definitions/stress-index-v1.toml').write_bytes(b'changed')
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'back edit')
    with pytest.raises(ledger.LedgerError, match='history'):
        ledger.verify(repository)


def test_late_git_commit_and_staged_working_mismatch_fail(repository, monkeypatch):
    forecast, issued = call()
    root = repository / 'ledger'
    path = ledger.append_forecast(root, 'stress', forecast, issued)
    git(repository, 'add', 'ledger')
    original = path.read_bytes()
    path.write_bytes(original + b' ')
    with pytest.raises(ledger.LedgerError):
        ledger.verify(repository)
    path.write_bytes(original)
    monkeypatch.setenv('GIT_COMMITTER_DATE', (issued + timedelta(days=5)).isoformat())
    git(repository, 'commit', '-m', 'late receipt')
    with pytest.raises(ledger.LedgerError, match='committed'):
        ledger.verify(repository)


def test_reject_retrospective_late_future_and_naive_issue(repository):
    forecast, issued = call()
    root = repository / 'ledger'
    with pytest.raises(ledger.LedgerError, match='prospective'):
        ledger.append_forecast(root, 'stress', replace(forecast, receipt=None), issued)
    for bad in [issued.replace(tzinfo=None), issued + timedelta(days=1)]:
        with pytest.raises(ledger.LedgerError, match='issue time'):
            ledger.append_forecast(root, 'stress', forecast, bad)
    with pytest.raises(ledger.LedgerError, match='target day'):
        ledger.append_forecast(root, 'stress', replace(forecast, target_date=issued.astimezone(ledger.ET).date()), issued)


def test_frozen_thresholds_and_late_commit_are_verified(repository):
    forecast, issued = call()
    root = repository / 'ledger'
    path = ledger.append_forecast(root, 'stress', forecast, issued)
    payload = json.loads(path.read_bytes())
    payload['definition']['thresholds_mw'] = [1, 2, 3]
    raw = ledger._encode(payload)
    relative = path.relative_to(root).with_name(sha256(raw).hexdigest() + '.json')
    with pytest.raises(ledger.LedgerError, match='thresholds'):
        ledger._validate(raw, relative, root)
    with pytest.raises(ledger.LedgerError, match='committed'):
        ledger._validate(path.read_bytes(), path.relative_to(root), root,
                         issued + timedelta(days=5))


def test_renamed_retrospective_and_definitionless_receipts_fail(repository):
    forecast, issued = call()
    root = repository / 'ledger'
    path = ledger.append_forecast(root, 'stress', forecast, issued)
    original = json.loads(path.read_bytes())
    for field in ['mode', 'definition']:
        payload = json.loads(json.dumps(original))
        if field == 'mode':
            payload['forecast']['receipt']['mode'] = 'retrospective'
        else:
            payload['definition'] = None
        raw = ledger._encode(payload)
        relative = path.relative_to(root).with_name(sha256(raw).hexdigest() + '.json')
        with pytest.raises(ledger.LedgerError):
            ledger._validate(raw, relative, root)


def test_guard_blocks_non_owner_and_allows_owner():
    root = Path(__file__).resolve().parents[1] / 'ledger'
    assert ledger.read_definition(root / 'definitions/stress-index-v1.toml')
    with pytest.raises(PermissionError, match='through grid_pipeline.ledger'):
        (root / 'definitions/stress-index-v1.toml').open('rb')
