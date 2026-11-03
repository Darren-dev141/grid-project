"""Independent-review counterexamples, using isolated Git repositories."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from grid_pipeline import ledger
from test_ledger import repository, call, git


@pytest.mark.parametrize('staged', [False, True])
def test_backdated_uncommitted_receipt_fails_after_target(repository, monkeypatch, staged):
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    if staged:
        git(repository, 'add', 'ledger')

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return (issued + timedelta(days=6)).astimezone(tz)

    monkeypatch.setattr(ledger, 'datetime', Later)
    with pytest.raises(ledger.LedgerError, match='uncommitted|target'):
        ledger.verify(repository)


def test_committed_receipt_without_public_witness_is_not_verified(repository, monkeypatch):
    from test_s4_boundary import establish
    establish(repository)
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'receipt without external witness')
    def unavailable(repo):
        raise ledger.LedgerError('independent push witnesses unavailable')
    monkeypatch.setattr(ledger, '_push_witnesses', unavailable)
    monkeypatch.setattr(ledger, '_verify_boundary_remote', lambda *args: None)
    with pytest.raises(ledger.LedgerError, match='witness|timing'):
        ledger.verify(repository, witness=True)


@pytest.mark.parametrize('observed_days, expected', [(0, True), (6, False)])
def test_push_witness_cutoff_is_not_committer_date(repository, monkeypatch, observed_days, expected):
    from test_s4_boundary import establish
    establish(repository)
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'receipt')
    commit = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    monkeypatch.setattr(ledger, '_push_witnesses',
                        lambda repo: [(commit, issued + timedelta(days=observed_days, seconds=1))])
    monkeypatch.setattr(ledger, '_verify_boundary_remote', lambda *args: None)
    if expected:
        assert ledger.verify(repository, witness=True)['witnessed_receipts'] == 1
    else:
        with pytest.raises(ledger.LedgerError, match='witness'):
            ledger.verify(repository, witness=True)
    assert ledger.verify(repository, integrity_only=True)['timing'] == 'unverified_integrity_only'


def test_merge_deletion_survives_removed_branch_ref(repository):
    # One parent contains the definition; the other parent and merge omit it.
    # The merge tree matches the second parent, triggering default simplification.
    base = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'add definition')
    with_definition = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    git(repository, 'checkout', '-b', 'without-ledger', base)
    (repository / 'other').write_text('independent branch')
    git(repository, 'add', 'other')
    git(repository, 'commit', '-m', 'other parent')
    tree = git(repository, 'rev-parse', 'HEAD^{tree}').stdout.strip()
    other = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    merged = git(repository, 'commit-tree', tree, '-p', with_definition,
                 '-p', other, '-m', 'merge drops definition').stdout.strip()
    git(repository, 'checkout', '--detach', merged)
    for branch in git(repository, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').stdout.splitlines():
        git(repository, 'branch', '-D', branch)
    with pytest.raises(ledger.LedgerError, match='history|back-edit'):
        ledger.verify(repository)


def test_definition_added_after_receipt_cannot_validate_history(repository):
    forecast, issued = call()
    ledger.append_forecast(repository / 'ledger', 'stress', forecast, issued)
    git(repository, 'add', 'ledger/forecasts')
    git(repository, 'commit', '-m', 'receipt before definition')
    git(repository, 'add', 'ledger/definitions')
    git(repository, 'commit', '-m', 'definition too late')
    with pytest.raises(ledger.LedgerError, match='definition.*commit|commit.*definition'):
        ledger.verify(repository)


def test_selection_uses_latest_issuance_including_no_call(repository, monkeypatch):
    forecast, issued = call()
    root = repository / 'ledger'
    ledger.append_forecast(root, 'stress', forecast, issued)
    later = issued + timedelta(seconds=1)
    updated = replace(forecast, no_call_reason='stale_load',
                      receipt=replace(forecast.receipt, issued_at=later))
    ledger.append_forecast(root, 'stress', updated, later)
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'multiple issues')
    commit = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    monkeypatch.setattr(ledger, '_push_witnesses', lambda repo: [(commit, datetime.now(timezone.utc))], raising=False)
    selected = ledger.select_receipt(repository, 'stress', forecast.target_date)
    assert selected['forecast']['no_call_reason'] == 'stale_load'
    assert selected['issued_at'] == later.isoformat()


def test_partial_staging_rejected_before_hook_checks(repository):
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'clean baseline')
    (repository / 'source.py').write_text('staged bad source\n')
    git(repository, 'add', 'source.py')
    (repository / 'source.py').write_text('different passing source\n')
    from grid_pipeline.precommit import check_snapshot
    with pytest.raises(ValueError, match='staged|snapshot'):
        check_snapshot(repository)
    git(repository, 'add', 'source.py')
    assert check_snapshot(repository)


def test_untracked_source_rejected_before_hook_checks(repository):
    git(repository, 'add', 'ledger')
    git(repository, 'commit', '-m', 'clean baseline')
    from grid_pipeline.precommit import check_snapshot
    assert check_snapshot(repository)
    (repository / 'untracked.py').write_text('source absent from index\n')
    with pytest.raises(ValueError, match='snapshot'):
        check_snapshot(repository)
