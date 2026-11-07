"""Collect abandoned SQLite handles before Windows database reset fixtures."""
import gc
import threading
import pytest


@pytest.fixture(autouse=True)
def a_collect_sqlite_handles():
    # A completed job can be visible before its worker closes SQLite. Do not
    # unlink the next fixture's DB while that last journal handle is still open.
    for worker in threading.enumerate():
        if worker.name.endswith('(run_job)'):
            worker.join(timeout=10)
            if worker.is_alive():
                pytest.fail('YUNO AI worker must finish before resetting test storage')
    gc.collect()
