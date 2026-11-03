"""Synthetic protocol tests; these fixtures are never acceptance evidence."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from grid_pipeline import ledger
from test_ledger import repository, call, git


def establish(repo):
    (repo / 'acceptance-source').write_text('reviewed test source, not real acceptance')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'synthetic acceptance code')
    commit = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    git(repo, 'tag', '-a', 's4-acceptance', '-m', 'synthetic boundary')
    tag = git(repo, 'rev-parse', 'refs/tags/s4-acceptance').stdout.strip()
    ledger.establish_boundary(repo, commit, tag, 123)
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'synthetic boundary record')
    return commit, tag


def test_receipt_free_ci_can_bootstrap_without_claiming_acceptance(repository, monkeypatch):
    monkeypatch.setattr(ledger, '_remote_acceptance_tag', lambda repo: None, raising=False)
    result = ledger.verify(repository, witness=True)
    assert result['acceptance'] == 'bootstrap_no_receipts'
    assert result['witnessed_receipts'] == 0


def test_remote_anchor_prevents_missing_policy_bootstrap(repository, monkeypatch):
    monkeypatch.setattr(ledger, '_remote_acceptance_tag',
                        lambda repo: {'object': {'type': 'tag', 'sha': '1' * 40}}, raising=False)
    with pytest.raises(ledger.LedgerError, match='boundary|anchor'):
        ledger.verify(repository, witness=True)


def test_future_issue_on_other_reachable_ref_fails(repository, monkeypatch):
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'definition baseline')
    base = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    git(repository, 'checkout', '-b', 'other-receipt-ref')
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'receipt on other ref')
    git(repository, 'checkout', '--detach', base)

    class Earlier(datetime):
        @classmethod
        def now(cls, tz=None):
            return (issued - timedelta(days=1)).astimezone(tz)

    monkeypatch.setattr(ledger, 'datetime', Earlier)
    with pytest.raises(ledger.LedgerError, match='future'):
        ledger.verify(repository)


def test_historical_selection_is_offline_and_labeled(repository, monkeypatch):
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'historical receipt')
    establish(repository)
    def no_network(*args):
        raise AssertionError('local selection must not require network')
    monkeypatch.setattr(ledger, '_push_witnesses', no_network)
    selected = ledger.select_receipt(repository, 'stress', forecast.target_date)
    assert selected['witness_status'] == 'historical_not_required'
    assert ledger.verify(repository)['historical_receipts'] == 1


def test_post_boundary_requires_real_provider_in_ci(repository, monkeypatch):
    establish(repository)
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'post-boundary receipt')
    monkeypatch.setattr(ledger, '_verify_boundary_remote', lambda *args: None)
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [])
    assert ledger.verify(repository)['prospective_receipts'] == 1
    with pytest.raises(ledger.LedgerError, match='witness'):
        ledger.verify(repository, witness=True)
    commit = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [(commit, datetime.now(timezone.utc))])
    assert ledger.verify(repository, witness=True)['witnessed_receipts'] == 1


def test_boundary_retag_is_detected_locally(repository):
    establish(repository)
    git(repository, 'tag', '-d', 's4-acceptance')
    git(repository, 'tag', '-a', 's4-acceptance', '-m', 'changed tag object')
    with pytest.raises(ledger.LedgerError, match='boundary|tag'):
        ledger.verify(repository)


def test_boundary_record_is_exclusive_and_append_only(repository):
    commit, tag = establish(repository)
    with pytest.raises(FileExistsError):
        ledger.establish_boundary(repository, commit, tag, 123)


def test_unanchored_receipts_cannot_pass_ci_witness_gate(repository):
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'unanchored receipt')
    assert ledger.verify(repository)['acceptance'] == 'unanchored'
    with pytest.raises(ledger.LedgerError, match='boundary'):
        ledger.verify(repository, witness=True)


def test_receipt_on_acceptance_commit_is_prospective(repository):
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'receipt on synthetic boundary')
    commit = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    git(repository, 'tag', '-a', 's4-acceptance', '-m', 'synthetic inclusive boundary')
    tag = git(repository, 'rev-parse', 'refs/tags/s4-acceptance').stdout.strip()
    ledger.establish_boundary(repository, commit, tag, 123)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'boundary record')
    result = ledger.verify(repository)
    assert result['historical_receipts'] == 0
    assert result['prospective_receipts'] == 1


def test_committed_boundary_cannot_be_changed(repository):
    establish(repository)
    path = repository / ledger.BOUNDARY_PATH
    original = ledger.read_definition(path)
    # Deliberate corruption in this isolated test repository, never real ledger data.
    path.write_bytes(original + b' ')
    with pytest.raises(ledger.LedgerError):
        ledger.verify(repository)


def test_remote_boundary_mismatch_fails_closed(repository, monkeypatch):
    establish(repository)
    record = json.loads(ledger.read_definition(repository / ledger.BOUNDARY_PATH))
    def evidence(repo, suffix):
        if suffix.startswith('git/ref/'):
            return {'object': {'type': 'tag', 'sha': '0' * 40}}
        if suffix.startswith('git/tags/'):
            return {'object': {'type': 'commit', 'sha': record['acceptance_commit']}}
        return {'head_sha': record['acceptance_commit'], 'event': 'push',
                'conclusion': 'success', 'path': '.github/workflows/ci.yml'}
    monkeypatch.setattr(ledger, '_github_json', evidence)
    with pytest.raises(ledger.LedgerError, match='remote acceptance'):
        ledger.verify(repository, witness=True)


def test_incomparable_origin_of_historical_content_requires_its_own_witness(repository, monkeypatch):
    base = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'original historical content')
    historical_commit = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    historical_tree = git(repository, 'rev-parse', 'HEAD^{tree}').stdout.strip()
    establish(repository)
    boundary_head = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    side = git(repository, 'commit-tree', historical_tree, '-p', base, '-m', 'same content on side').stdout.strip()
    merged = git(repository, 'commit-tree', 'HEAD^{tree}', '-p', boundary_head,
                 '-p', side, '-m', 'merge identical historical receipt').stdout.strip()
    git(repository, 'checkout', '--detach', merged)
    monkeypatch.setattr(ledger, '_verify_boundary_remote', lambda *args: None)
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [(historical_commit, datetime.now(timezone.utc))])
    with pytest.raises(ledger.LedgerError, match='witness'):
        ledger.verify(repository, witness=True)
    result = ledger.verify(repository)
    assert result['historical_receipts'] == 0
    assert result['prospective_receipts'] == 1
    assert result['historical_origins'] == 1
    assert result['prospective_origins'] == 1


def test_every_incomparable_prospective_origin_needs_witness_coverage(repository, monkeypatch):
    establish(repository)
    base = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'first prospective origin')
    first = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    second = git(repository, 'commit-tree', 'HEAD^{tree}', '-p', base, '-m', 'incomparable second origin').stdout.strip()
    merged = git(repository, 'commit-tree', 'HEAD^{tree}', '-p', first, '-p', second, '-m', 'merge origins').stdout.strip()
    git(repository, 'checkout', '--detach', merged)
    monkeypatch.setattr(ledger, '_verify_boundary_remote', lambda *args: None)
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [(first, datetime.now(timezone.utc))])
    with pytest.raises(ledger.LedgerError, match='witness'):
        ledger.verify(repository, witness=True)
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [(merged, datetime.now(timezone.utc))])
    result = ledger.verify(repository, witness=True)
    assert result['prospective_origins'] == 2
    assert result['witnessed_origins'] == 2
    assert result['witnessed_receipts'] == 1


def test_git_verification_passes_blob_ids_not_ledger_specs(repository, monkeypatch):
    import subprocess
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'object-content fixture')
    original = subprocess.run
    calls = []

    def checked(command, **kwargs):
        calls.append(command)
        assert all('ledger/' not in str(arg).replace('\\', '/') and not str(arg).startswith(':')
                   for arg in command)
        return original(command, **kwargs)

    monkeypatch.setattr(ledger.subprocess, 'run', checked)
    assert ledger.verify(repository)['receipts'] == 1
    assert any('cat-file' in command and 'blob' in command for command in calls)
    with pytest.raises(ledger.LedgerError, match='object ID'):
        ledger.read_object(repository, 'HEAD:ledger/definitions/stress-index-v1.toml')


@pytest.mark.parametrize('status', [403, 500])
def test_missing_anchor_lookup_does_not_treat_api_failure_as_absence(repository, monkeypatch, status):
    from urllib.error import HTTPError
    monkeypatch.setattr(ledger, '_git', lambda *args: 'https://github.com/' + ledger.IDENTITY)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)

    def unavailable(*args, **kwargs):
        raise HTTPError('https://api.github.com/', status, 'unavailable', None, None)

    monkeypatch.setattr(ledger, 'urlopen', unavailable)
    with pytest.raises(ledger.LedgerError, match='unavailable'):
        ledger._github_json(repository, 'git/ref/tags/s4-acceptance', missing_ok=True)


def test_remote_absence_is_explicit_and_requires_readable_public_identity(repository, monkeypatch):
    calls = []

    def absent(repo, suffix, **kwargs):
        calls.append((suffix, kwargs))
        return {'full_name': ledger.IDENTITY, 'private': False} if suffix == '' else None

    monkeypatch.setattr(ledger, '_github_json', absent)
    assert ledger._remote_acceptance_tag(repository) is None
    assert calls[-1] == ('git/ref/tags/s4-acceptance', {'missing_ok': True})
