"""Collect abandoned SQLite handles before Windows database reset fixtures."""
import gc
import pytest


@pytest.fixture(autouse=True)
def a_collect_sqlite_handles():
    gc.collect()
