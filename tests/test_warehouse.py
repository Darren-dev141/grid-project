"""Check dbt invocation and failure handling without running a subprocess."""
from unittest.mock import Mock
import subprocess
import sys

import pytest

from grid_pipeline import warehouse


def test_build_uses_current_python_and_isolates_artifacts(tmp_path, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, 'ok', ''))
    monkeypatch.setattr(warehouse.subprocess, 'run', run)
    warehouse.build(tmp_path / 'grid.duckdb', select=['+mart_day_history'], artifact_root=tmp_path)
    args = run.call_args.args[0]
    assert args[:3] == [sys.executable, '-m', 'grid_pipeline.dbt_runner']
    assert args[-2:] == ['--select', '+mart_day_history']
    assert str(tmp_path / 'target') in args
    assert str(tmp_path / 'logs') in args
    env = run.call_args.kwargs['env']
    assert env['GRID_DATABASE'] == str(tmp_path / 'grid.duckdb')
    assert env['DBT_SEND_ANONYMOUS_USAGE_STATS'] == 'false'
    assert run.call_count == 1


def test_build_does_not_retry_transport_failure(tmp_path, monkeypatch):
    run = Mock(side_effect=[
        subprocess.CompletedProcess([], 1, '', 'concurrent send_bytes() calls are not supported'),
        subprocess.CompletedProcess([], 0, '', '')])
    monkeypatch.setattr(warehouse.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='concurrent send_bytes'):
        warehouse.build(tmp_path / 'grid.duckdb')
    assert run.call_count == 1


@pytest.mark.parametrize('message, attempts', [('SQL compilation failed', 1),
    ('concurrent send_bytes() calls are not supported', 1)])
def test_build_fails_loudly_and_bounds_attempts(tmp_path, monkeypatch, message, attempts):
    run = Mock(return_value=subprocess.CompletedProcess([], 1, message, ''))
    monkeypatch.setattr(warehouse.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='dbt build failed'):
        warehouse.build(tmp_path / 'grid.duckdb')
    assert run.call_count == attempts


def test_build_propagates_timeout(tmp_path, monkeypatch):
    run = Mock(side_effect=subprocess.TimeoutExpired('dbt', 180))
    monkeypatch.setattr(warehouse.subprocess, 'run', run)
    with pytest.raises(subprocess.TimeoutExpired):
        warehouse.build(tmp_path / 'grid.duckdb')
    assert run.call_count == 1
