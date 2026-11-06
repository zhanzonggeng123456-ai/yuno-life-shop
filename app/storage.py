"""Photo storage: existing local files or opt-in durable SQLite chunks.

Chunks stay below common HTTP row-size limits. Original bytes and existing
filenames are preserved; no image generation, transformation or paid API.
"""
import hashlib
import os
from contextlib import closing

from . import db

CHUNK_SIZE = 256 * 1024
MAX_PHOTO = 5 * 1024 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS yuno_uploads(
  name TEXT PRIMARY KEY, size INTEGER NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS yuno_upload_chunks(
  name TEXT NOT NULL REFERENCES yuno_uploads(name) ON DELETE CASCADE,
  part INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(name,part));
"""


def in_database():
    mode = os.environ.get("YUNO_PHOTO_STORAGE", "files")
    if mode not in ("files", "database"):
        raise RuntimeError("Invalid YUNO_PHOTO_STORAGE")
    return mode == "database"


def name_only(name):
    if not isinstance(name, str) or not name or name in (".", "..") or any(
            value in name for value in ("/", "\\", ":", "\x00")):
        raise ValueError("Invalid photo filename")
    return name


def save(name, data, connection=None):
    name = name_only(name)
    if len(data) > MAX_PHOTO:
        raise ValueError("Photo exceeds 5 MiB")
    if not in_database():
        (db.UPLOAD_DIR / name).write_bytes(data)
        return
    if connection is None:
        with closing(db.connect()) as conn:
            save(name, data, conn)
            conn.commit()
        return
    connection.execute("INSERT INTO yuno_uploads(name,size,sha256) VALUES(?,?,?)",
                       (name, len(data), hashlib.sha256(data).hexdigest()))
    for part, offset in enumerate(range(0, len(data), CHUNK_SIZE)):
        connection.execute("INSERT INTO yuno_upload_chunks(name,part,data) VALUES(?,?,?)",
                           (name, part, data[offset:offset + CHUNK_SIZE]))


def read(name, connection=None):
    name = name_only(name)
    if not in_database():
        return (db.UPLOAD_DIR / name).read_bytes()
    if connection is None:
        with closing(db.connect()) as conn:
            return read(name, conn)
    meta = connection.execute("SELECT size,sha256 FROM yuno_uploads WHERE name=?", (name,)).fetchone()
    if meta is None:
        raise FileNotFoundError(name)
    if meta[0] > MAX_PHOTO:
        raise ValueError("Invalid stored photo size")
    rows = connection.execute("SELECT part,data FROM yuno_upload_chunks WHERE name=? ORDER BY part", (name,)).fetchall()
    if [row[0] for row in rows] != list(range(len(rows))):
        raise ValueError("Stored photo chunks incomplete")
    data = b"".join(row[1] for row in rows)
    if len(data) != meta[0] or hashlib.sha256(data).hexdigest() != meta[1]:
        raise ValueError("Stored photo integrity check failed")
    return data


def delete(name):
    name = name_only(name)
    if not in_database():
        (db.UPLOAD_DIR / name).unlink(missing_ok=True)
        return
    with closing(db.connect()) as conn:
        # Explicit chunk delete also works with hosts that don't enable FK cascades.
        conn.execute("DELETE FROM yuno_upload_chunks WHERE name=?", (name,))
        conn.execute("DELETE FROM yuno_uploads WHERE name=?", (name,))
        conn.commit()
