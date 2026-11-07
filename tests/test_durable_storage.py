from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import db, storage
from deploy.serve import configure_storage
from test_app import fresh_db


def test_remote_boot_refuses_partial_configuration_and_ephemeral_fallback(monkeypatch):
    monkeypatch.setenv('YUNO_STORAGE_MODE', 'remote')
    monkeypatch.delenv('TURSO_DATABASE_URL', raising=False)
    monkeypatch.delenv('TURSO_AUTH_TOKEN', raising=False)
    with pytest.raises(RuntimeError, match='requires Turso'):
        configure_storage()
    monkeypatch.setenv('TURSO_DATABASE_URL', 'libsql://yuno-example.turso.io')
    with pytest.raises(RuntimeError, match='Both'):
        configure_storage()
    monkeypatch.setenv('TURSO_AUTH_TOKEN', 'disposable-test-placeholder')
    monkeypatch.setenv('YUNO_PHOTO_STORAGE', 'files')
    with pytest.raises(RuntimeError, match='durable'):
        configure_storage()
    monkeypatch.setenv('TURSO_DATABASE_URL', 'https://unrelated.example')
    with pytest.raises(RuntimeError, match='official'):
        configure_storage()


def test_database_photos_roundtrip_chunks_transaction_rollback_and_corruption(monkeypatch):
    monkeypatch.setenv('YUNO_PHOTO_STORAGE', 'database')
    monkeypatch.setenv('YUNO_DB_DRIVER', 'libsql')
    db.init_db()
    data = b'original-bytes' * 50000
    with closing(db.connect()) as conn:
        storage.save('rollback.png', data, conn)
        conn.rollback()
    with pytest.raises(FileNotFoundError):
        storage.read('rollback.png')
    storage.save('retained.png', data)
    assert storage.read('retained.png') == data
    assert not (db.UPLOAD_DIR / 'retained.png').exists()
    with closing(db.connect()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM yuno_upload_chunks').fetchone()[0] == 3
        conn.execute('DELETE FROM yuno_upload_chunks WHERE part=1')
        conn.commit()
    with pytest.raises(ValueError, match='incomplete'):
        storage.read('retained.png')
    storage.delete('retained.png')
    with pytest.raises(FileNotFoundError):
        storage.read('retained.png')


def test_libsql_mapping_and_transaction_behavior(tmp_path):
    from app.remote_db import Connection
    import libsql
    with closing(Connection(libsql.connect(str(tmp_path / 'adapter.db')))) as conn:
        conn.execute('CREATE TABLE example(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT)')
        inserted = conn.execute('INSERT INTO example(title) VALUES(?)', ('kept',))
        assert inserted.lastrowid == 1
        conn.commit()
        row = conn.execute('SELECT id,title FROM example').fetchone()
        assert row[0] == row['id'] == 1
        assert dict(row) == {'id': 1, 'title': 'kept'}
        assert tuple(row) == (1, 'kept')
        conn.execute('INSERT INTO example(title) VALUES(?)', ('rolled back',))
        conn.rollback()
        assert len(conn.execute('SELECT * FROM example').fetchall()) == 1
        with pytest.raises(ValueError, match='syntax'):
            conn.executescript('INVALID SQL')


def test_native_private_draft_upload_and_media_survive_new_connections(monkeypatch):
    import secrets
    from deploy.gateway import app
    monkeypatch.setenv('YUNO_PHOTO_STORAGE', 'database')
    monkeypatch.setenv('YUNO_DB_DRIVER', 'libsql')
    db.init_db()
    client = TestClient(app)
    registered = client.post('/api/v1/actions/register', json={
        'email': secrets.token_hex(8)+'@example.jp', 'display_name': 'Durability QA',
        'password': secrets.token_urlsafe(24)})
    assert registered.status_code == 200
    auth = {'Authorization': 'Bearer '+registered.json()['token']}
    result = client.post('/api/v1/actions/oneclick_upload', headers=auth,
                         data={'name': 'Private durability draft'},
                         files=[('photos', ('one.png', b'first original', 'image/png')),
                                ('photos', ('two.png', b'second original', 'image/png'))])
    assert result.status_code == 200
    did = result.json()['id']
    # A new client and every new DB connection see durable original bytes.
    restarted = TestClient(app)
    draft = restarted.get(f'/api/v1/drafts/{did}', headers=auth)
    assert draft.status_code == 200
    photos = draft.json()['item']['photos']
    assert [restarted.get(p['url']).content for p in photos] == [b'first original', b'second original']
    assert restarted.get(f'/api/v1/drafts/{did}').status_code == 401
