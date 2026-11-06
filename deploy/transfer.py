"""Copy a whole YUNO SQLite database without changing IDs or business schema.

Import refuses any existing user tables. Both directions use a transaction;
there is no overwrite/reset switch. Credentials come only from environment.
"""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

from app import remote_db, storage
from deploy import backup


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def copy_database(source, destination):
    existing = destination.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    if existing:
        raise ValueError("Destination database must be empty; refusing overwrite")
    schema = source.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,name").fetchall()
    destination.execute("PRAGMA foreign_keys=OFF")
    destination.execute("BEGIN IMMEDIATE")
    try:
        tables = []
        for kind, name, sql in schema:
            if kind == 'table':
                destination.execute(sql)
                tables.append(name)
        for name in tables:
            columns = source.execute('PRAGMA table_info(' + quoted(name) + ')').fetchall()
            fields = ','.join(quoted(column[1]) for column in columns)
            insert = 'INSERT INTO ' + quoted(name) + '(' + fields + ') VALUES(' + ','.join('?' for _ in columns) + ')'
            count = 0
            for row in source.execute('SELECT ' + fields + ' FROM ' + quoted(name)):
                destination.execute(insert, tuple(row))
                count += 1
            if destination.execute('SELECT COUNT(*) FROM ' + quoted(name)).fetchone()[0] != count:
                raise ValueError('Transferred row count mismatch')
        # Preserve AUTOINCREMENT high-water marks, including deleted old IDs.
        if source.execute("SELECT name FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
            destination.execute('DELETE FROM sqlite_sequence')
            for row in source.execute('SELECT name,seq FROM sqlite_sequence'):
                destination.execute('INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)', tuple(row))
        for kind, _, sql in schema:
            if kind != 'table':
                destination.execute(sql)
        if destination.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Transferred foreign key check failed')
        destination.commit()
    except BaseException:
        destination.rollback()
        raise


def import_to_remote(database, uploads):
    url, _ = remote_db.configuration()
    if not url:
        raise RuntimeError('Explicit Turso credentials required')
    database, uploads = Path(database), Path(uploads)
    if not database.is_file():
        raise ValueError('Existing restored database required')
    # Prepare a separate copy; never alter the source restore or live volume.
    with tempfile.TemporaryDirectory(prefix='yuno-import-') as directory:
        prepared = Path(directory) / 'prepared.db'
        with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(prepared)) as local:
                source.backup(local)
                backup.validate_db(local)
                local.executescript(storage.SCHEMA)
                for name in backup.references(local):
                    payload = (uploads / name).read_bytes()
                    if local.execute('SELECT name FROM yuno_uploads WHERE name=?', (name,)).fetchone():
                        # Already migrated backups contain the original chunks.
                        saved = b''.join(row[0] for row in local.execute(
                            'SELECT data FROM yuno_upload_chunks WHERE name=? ORDER BY part', (name,)))
                        if saved != payload:
                            raise ValueError('Existing photo chunks disagree with restored files')
                    else:
                        local.execute('INSERT INTO yuno_uploads(name,size,sha256) VALUES(?,?,?)',
                                      (name, len(payload), backup.digest(payload)))
                        if len(payload) > storage.MAX_PHOTO:
                            raise ValueError('Photo exceeds existing upload limit')
                        for part, offset in enumerate(range(0, len(payload), storage.CHUNK_SIZE)):
                            local.execute('INSERT INTO yuno_upload_chunks(name,part,data) VALUES(?,?,?)',
                                          (name, part, payload[offset:offset + storage.CHUNK_SIZE]))
                local.commit()
                with closing(remote_db.connect(None)) as target:
                    copy_database(local, target)


def export_remote(output):
    url, _ = remote_db.configuration()
    if not url:
        raise RuntimeError('Explicit Turso credentials required')
    if Path(output).exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='yuno-export-') as directory:
        root = Path(directory)
        photos = root / 'uploads'
        photos.mkdir()
        snapshot = root / 'snapshot.db'
        with closing(remote_db.connect(None)) as source:
            source.execute('BEGIN')
            try:
                with closing(sqlite3.connect(snapshot)) as local:
                    copy_database(source, local)
                    backup.validate_db(local)
                    for name in backup.references(local):
                        meta = local.execute('SELECT size,sha256 FROM yuno_uploads WHERE name=?', (name,)).fetchone()
                        rows = local.execute('SELECT part,data FROM yuno_upload_chunks WHERE name=? ORDER BY part', (name,)).fetchall()
                        payload = b''.join(row[1] for row in rows)
                        if (meta is None or meta[0] != len(payload) or meta[1] != backup.digest(payload)
                                or [row[0] for row in rows] != list(range(len(rows)))):
                            raise ValueError('Photo corruption: backup aborted')
                        (photos / name).write_bytes(payload)
            finally:
                source.rollback()
        return backup.create(snapshot, photos, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('import')
    command.add_argument('--database', required=True)
    command.add_argument('--uploads', required=True)
    command = sub.add_parser('export')
    command.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'import':
        import_to_remote(args.database, args.uploads)
    else:
        export_remote(args.output)
    print('YUNO transfer completed; private data and credentials omitted')


if __name__ == '__main__':
    main()
