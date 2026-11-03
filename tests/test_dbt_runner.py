"""Exercise serialized Windows notifier sends without installing dbt."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import threading
import time
from types import SimpleNamespace
from types import ModuleType
import sys
from unittest.mock import Mock
import subprocess

import pytest


class Notifier:
    def __init__(self):
        self._wlock = None
        self.sending = threading.Lock()

    def put(self, value):
        with self._wlock if self._wlock is not None else nullcontext():
            if not self.sending.acquire(blocking=False):
                raise ValueError('concurrent send_bytes() calls are not supported')
            try:
                time.sleep(.001)
            finally:
                self.sending.release()


def test_notifier_serializes_overlapping_sends():
    from grid_pipeline.dbt_runner import SerializedNotifierContext
    context = SerializedNotifierContext(SimpleNamespace(SimpleQueue=Notifier))
    queue = context.SimpleQueue()
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(queue.put, range(30)))


def test_existing_process_lock_is_preserved():
    from grid_pipeline.dbt_runner import SerializedNotifierContext
    notifier = Notifier()
    existing = threading.Lock()
    notifier._wlock = existing
    context = SerializedNotifierContext(SimpleNamespace(SimpleQueue=lambda: notifier))
    assert context.SimpleQueue()._wlock is existing


def test_unlocked_notifier_reproduces_transport_error():
    queue = Notifier()
    with ThreadPoolExecutor(max_workers=6) as pool:
        with pytest.raises(ValueError, match='concurrent send_bytes'):
            list(pool.map(queue.put, range(30)))


def test_transport_failure_is_not_retried_into_a_pass(tmp_path, monkeypatch):
    from grid_pipeline import warehouse
    run = Mock(side_effect=[
        subprocess.CompletedProcess([], 1, '', 'concurrent send_bytes() calls are not supported'),
        subprocess.CompletedProcess([], 0, '', '')])
    monkeypatch.setattr(warehouse.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='dbt build failed'):
        warehouse.build(tmp_path / 'grid.duckdb')
    assert run.call_count == 1


@pytest.mark.parametrize('outcome', ['success', 'exit', 'exception'])
def test_runner_serializes_close_and_preserves_cli_failure(monkeypatch, outcome):
    from grid_pipeline import dbt_runner
    closed = []

    class Pool:
        def __init__(self):
            self._ctx = SimpleNamespace(SimpleQueue=Notifier)
            self._setup_queues()
            self.notifier = self._ctx.SimpleQueue()

        def _setup_queues(self):
            pass

        def close(self):
            with ThreadPoolExecutor(max_workers=6) as senders:
                list(senders.map(self.notifier.put, [None] * 30))
            closed.append(True)

    modules = {name: ModuleType(name) for name in
               ['dbt', 'dbt.graph', 'dbt.graph.thread_pool', 'dbt.cli', 'dbt.cli.main']}
    modules['dbt.graph.thread_pool'].DbtThreadPool = Pool
    modules['dbt'].graph = modules['dbt.graph']
    modules['dbt.graph'].thread_pool = modules['dbt.graph.thread_pool']
    modules['dbt'].cli = modules['dbt.cli']
    modules['dbt.cli'].main = modules['dbt.cli.main']

    def cli():
        pool = modules['dbt.graph.thread_pool'].DbtThreadPool()
        try:
            if outcome == 'exit':
                raise SystemExit(3)
            if outcome == 'exception':
                raise RuntimeError('query failed')
        finally:
            pool.close()

    modules['dbt.cli.main'].cli = cli
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, 'platform', 'win32')
    if outcome == 'exit':
        with pytest.raises(SystemExit) as raised:
            dbt_runner.main()
        assert raised.value.code == 3
    elif outcome == 'exception':
        with pytest.raises(RuntimeError, match='query failed'):
            dbt_runner.main()
    else:
        dbt_runner.main()
    assert closed == [True]
