"""Run dbt with serialized Windows ThreadPool notifier writes.

CPython's Windows multiprocessing SimpleQueue has no writer lock. dbt's
ThreadPool notifier has several sending threads, so overlapping sends can fail.
Only the dbt child process receives this context; no dependency files change.
"""
import sys
import threading


class SerializedNotifierContext:
    def __init__(self, context):
        self._context = context

    def __getattr__(self, name):
        return getattr(self._context, name)

    def SimpleQueue(self):
        queue = self._context.SimpleQueue()
        if queue._wlock is None:
            queue._wlock = threading.Lock()
        return queue


def main():
    if sys.platform == 'win32':
        import dbt.graph.thread_pool as pools

        class SerializedDbtThreadPool(pools.DbtThreadPool):
            def _setup_queues(self):
                # Pool.__init__ sets _ctx, calls this method, then creates the
                # notifier. Install the context before any pool thread starts.
                self._ctx = SerializedNotifierContext(self._ctx)
                super()._setup_queues()

        pools.DbtThreadPool = SerializedDbtThreadPool
    from dbt.cli.main import cli
    cli()


if __name__ == '__main__':
    main()
