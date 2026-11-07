from contextlib import closing
import json
import sqlite3

import pytest

from app.remote_db import Connection
from deploy import backup, transfer
from test_backup import fixture_data


def test_transfer_real_libsql_roundtrip_and_refuse_nonempty_target(tmp_path, monkeypatch):
    import libsql
    source, photos = fixture_data(tmp_path)
    remote_file = tmp_path / 'isolated-libsql.db'
    monkeypatch.setattr(transfer.remote_db, 'configuration', lambda: ('libsql://example.turso.io', 'test-only'))
    monkeypatch.setattr(transfer.remote_db, 'connect', lambda _: Connection(libsql.connect(str(remote_file))))
    with closing(sqlite3.connect(source)) as conn:
        conn.execute("UPDATE sqlite_sequence SET seq=100 WHERE name='users'")
        conn.commit()
    # A cloud can enforce foreign keys despite a client's PRAGMA OFF request.
    monkeypatch.setattr(transfer.remote_db, 'connect', lambda _: enforced_connection(libsql, remote_file))
    transfer.import_to_remote(source, photos)
    with pytest.raises(ValueError, match='empty'):
        transfer.import_to_remote(source, photos)
    archive = tmp_path / 'remote.zip'
    manifest = transfer.export_remote(archive)
    assert manifest['counts']['users'] == 1
    assert manifest['counts']['orders'] == 1
    assert manifest['counts']['yuno_uploads'] == 2
    target = tmp_path / 'restored'
    backup.restore(archive.read_bytes(), target)
    assert (target / 'uploads/a.png').read_bytes() == (photos / 'a.png').read_bytes()
    with closing(sqlite3.connect(target / 'db/yuno.db')) as conn:
        assert conn.execute('SELECT id,pw_hash FROM users').fetchone() == (7, 'private-hash')
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name='users'").fetchone()[0] == 100
        assert json.loads(conn.execute('SELECT draft_json FROM oneclick_drafts').fetchone()[0])['photos'] == ['a.png', 'b.png']


def enforced_connection(driver, path):
    conn = Connection(driver.connect(str(path)))
    conn.execute('PRAGMA foreign_keys=ON')
    original = conn.execute
    conn.execute = lambda sql, params=(): original('SELECT 1') if sql == 'PRAGMA foreign_keys=OFF' else original(sql, params)
    return conn
