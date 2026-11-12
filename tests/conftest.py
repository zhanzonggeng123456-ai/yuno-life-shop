"""Collect abandoned SQLite handles before Windows database reset fixtures."""
import gc
import threading
import pytest


@pytest.fixture(autouse=True)
def a_collect_sqlite_handles(tmp_path, monkeypatch):
    # A completed job can be visible before its worker closes SQLite. Do not
    # unlink the next fixture's DB while that last journal handle is still open.
    for worker in threading.enumerate():
        if worker.name.endswith('(run_job)'):
            worker.join(timeout=10)
            if worker.is_alive():
                pytest.fail('YUNO AI worker must finish before resetting test storage')
    gc.collect()

    # Each test owns its filename. A late-closing connection from a previous
    # test must never unlink or journal the next test's database (Linux CI).
    from app import db
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'yuno.db')
    monkeypatch.setattr(db, 'UPLOAD_DIR', tmp_path / 'uploads')
