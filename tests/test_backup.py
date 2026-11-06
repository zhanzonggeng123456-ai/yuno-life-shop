import io
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest
from cryptography.fernet import Fernet, InvalidToken

from deploy.backup import create, restore, seal


def fixture_data(tmp_path):
    from app.db import SCHEMA
    source = tmp_path / 'source.db'
    photos = tmp_path / 'photos'
    photos.mkdir()
    with sqlite3.connect(source) as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO users(id,email,pw_hash,salt,display_name) VALUES(7,'private@example.jp','private-hash','private-salt','Original')")
        conn.execute("INSERT INTO oneclick_drafts(id,user_id,photo,draft_json) VALUES(9,7,'a.png',?)",
                     (json.dumps({'photos': ['a.png', 'b.png']}),))
        conn.execute("INSERT INTO images(listing_id,filename) VALUES(12,'a.png')")
        conn.execute("INSERT INTO orders(id,listing_id,buyer_id,seller_id,goods_amount,total) VALUES(11,12,7,8,1234,1234)")
    (photos / 'a.png').write_bytes(b'first original image')
    (photos / 'b.png').write_bytes(b'second original image')
    return source, photos


def test_encrypted_independent_restore_preserves_ids_private_records_and_photos(tmp_path):
    source, photos = fixture_data(tmp_path)
    archive = tmp_path / 'snapshot.zip'
    create(source, photos, archive)
    key = tmp_path / 'separate.backup-key'
    encrypted = tmp_path / 'snapshot.yuno-backup'
    seal(archive, key, encrypted)
    assert b'private@example.jp' not in encrypted.read_bytes()
    with pytest.raises(InvalidToken):
        Fernet(Fernet.generate_key()).decrypt(encrypted.read_bytes())
    data = Fernet(key.read_bytes()).decrypt(encrypted.read_bytes())
    restored = tmp_path / 'restored'
    restore(data, restored)
    with sqlite3.connect(restored / 'db/yuno.db') as conn:
        assert conn.execute('SELECT id,email,pw_hash FROM users').fetchone() == (7, 'private@example.jp', 'private-hash')
        assert conn.execute('SELECT id,goods_amount FROM orders').fetchone() == (11, 1234)
        assert conn.execute('SELECT id,user_id FROM oneclick_drafts').fetchone() == (9, 7)
    assert (restored / 'uploads/a.png').read_bytes() == (photos / 'a.png').read_bytes()
    assert (restored / 'uploads/b.png').read_bytes() == (photos / 'b.png').read_bytes()
    with pytest.raises(FileExistsError):
        restore(data, restored)


def rewrite(data, name, payload):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(output, 'w') as altered:
        for entry in original.namelist():
            altered.writestr(entry, payload if entry == name else original.read(entry))
        if name not in original.namelist():
            altered.writestr(name, payload)
    return output.getvalue()


def test_corruption_traversal_and_missing_photos_never_publish_restore(tmp_path):
    source, photos = fixture_data(tmp_path)
    archive = tmp_path / 'snapshot.zip'
    create(source, photos, archive)
    data = archive.read_bytes()
    target = tmp_path / 'failed'
    for bad in (rewrite(data, 'uploads/a.png', b'corrupt'),
                rewrite(data, '../outside', b'unsafe')):
        with pytest.raises(ValueError):
            restore(bad, target)
        assert not target.exists()
    (photos / 'b.png').unlink()
    missing = tmp_path / 'missing.zip'
    with pytest.raises(ValueError, match='missing'):
        create(source, photos, missing)
    assert not missing.exists()


def test_missing_source_and_existing_archive_are_never_created_or_overwritten(tmp_path):
    source, photos = fixture_data(tmp_path)
    archive = tmp_path / 'existing.zip'
    archive.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        create(source, photos, archive)
    assert archive.read_bytes() == b'keep'
    with pytest.raises(ValueError):
        create(tmp_path / 'does-not-exist.db', photos, tmp_path / 'new.zip')
    assert not (tmp_path / 'does-not-exist.db').exists()

