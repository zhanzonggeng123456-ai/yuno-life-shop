"""Independent SQLite + photo backup. Never imports/initializes the application.

Run create on the storage host during a maintenance window. The SQLite write
reservation prevents database mutations; missing/changing photos abort export.
Run seal locally before retaining/transferring archives. Keep the key separately.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
from datetime import datetime, timezone
import zipfile
from contextlib import closing

MAX_BYTES = 256 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    if not isinstance(name, str) or not name or name in (".", "..") or any(
            c in name for c in ("/", "\\", ":", "\x00")):
        raise ValueError("Unsafe photo name")
    return name


def references(conn):
    result = set()
    for row in conn.execute("SELECT filename FROM images"):
        result.add(safe_name(row[0]))
    for photo, encoded in conn.execute("SELECT photo, draft_json FROM oneclick_drafts"):
        if photo:
            result.add(safe_name(photo))
        for name in json.loads(encoded or "{}").get("photos", []):
            result.add(safe_name(name))
    for row in conn.execute("SELECT pickup_photo, delivery_photo FROM deliveries"):
        for name in row:
            if name:
                result.add(safe_name(name))
    return result


def validate_db(conn):
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("Database integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Database foreign key check failed")


def create(database, uploads, output):
    database, uploads, output = map(Path, (database, uploads, output))
    if not database.is_file() or database.is_symlink() or not uploads.is_dir():
        raise ValueError("Existing database and uploads directory required")
    if output.exists():
        raise FileExistsError(output)
    # mode=rw deliberately refuses to silently create an empty source database.
    lock = sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
    try:
        lock.execute("BEGIN IMMEDIATE")
        with tempfile.TemporaryDirectory(prefix="yuno-snapshot-") as directory:
            snapshot = Path(directory) / "yuno.db"
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
                    validate_db(target)
                    required = references(target)
                    counts = {name: target.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0]
                              for (name,) in target.execute(
                                  "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            files = {"db/yuno.db": snapshot.read_bytes()}
            if len(files["db/yuno.db"]) > MAX_BYTES:
                raise ValueError("Backup exceeds 256 MiB safety limit; use streaming export")
            for name in sorted(required):
                photo = uploads / name
                if photo.is_symlink() or not photo.is_file():
                    raise ValueError("Referenced photo missing or unsafe; backup aborted")
                before = photo.stat()
                if sum(map(len, files.values())) + before.st_size > MAX_BYTES:
                    raise ValueError("Backup exceeds 256 MiB safety limit; use streaming export")
                data = photo.read_bytes()
                after = photo.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Photo changed; retry during maintenance")
                files["uploads/" + name] = data
                if sum(map(len, files.values())) > MAX_BYTES:
                    raise ValueError("Backup exceeds 256 MiB safety limit; use streaming export")
            manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                        "counts": counts, "files": {name: {"sha256": digest(data), "size": len(data)}
                                                   for name, data in files.items()}}
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=output.parent) as spool:
                with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as archive:
                    for name, data in files.items():
                        archive.writestr(name, data)
                    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
                spool.seek(0)
                with output.open("xb") as destination:
                    shutil.copyfileobj(spool, destination)
            return manifest
    finally:
        lock.rollback()
        lock.close()


def checked_archive(data):
    if len(data) > MAX_BYTES:
        raise ValueError("Archive exceeds safety limit")
    archive = zipfile.ZipFile(io.BytesIO(data))
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)) or sum(info.file_size for info in infos) > MAX_BYTES:
        raise ValueError("Duplicate entries or expanded archive exceeds safety limit")
    for info in infos:
        path = PurePosixPath(info.filename)
        if (path.is_absolute() or ".." in path.parts or "\\" in info.filename or ":" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir()):
            raise ValueError("Unsafe archive entry")
    manifest = json.loads(archive.read("manifest.json"))
    if manifest.get("format") != 1 or set(names) != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Invalid backup manifest")
    if "db/yuno.db" not in names:
        raise ValueError("Missing database")
    for name, expected in manifest["files"].items():
        if name != "db/yuno.db" and not (name.startswith("uploads/") and safe_name(name[8:])):
            raise ValueError("Unexpected backup entry")
        payload = archive.read(name)
        if len(payload) != expected["size"] or digest(payload) != expected["sha256"]:
            raise ValueError("Backup checksum mismatch")
    return archive, manifest


def restore(data, destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Restore requires a new, nonexistent directory")
    archive, manifest = checked_archive(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="yuno-restore-", dir=destination.parent) as directory:
        stage = Path(directory) / "data"
        (stage / "db").mkdir(parents=True)
        (stage / "uploads").mkdir()
        for name in manifest["files"]:
            (stage / name).write_bytes(archive.read(name))
        with closing(sqlite3.connect(stage / "db" / "yuno.db")) as conn:
            validate_db(conn)
            if references(conn) != {name[8:] for name in manifest["files"] if name.startswith("uploads/")}:
                raise ValueError("Database/photo references disagree")
            for table, count in manifest["counts"].items():
                # Identifiers must be an actual SQLite table; quote embedded quotes.
                actual = conn.execute('SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]
                if actual != count:
                    raise ValueError("Database row count mismatch")
        # Atomic publication only after all checks. Never merge into live data.
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
    return manifest


def seal(source, key_file, destination):
    from cryptography.fernet import Fernet
    data = Path(source).read_bytes()
    checked_archive(data)
    key_file = Path(key_file)
    if not key_file.exists():
        key_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(Fernet.generate_key())
    encrypted = Fernet(key_file.read_bytes().strip()).encrypt(data)
    with Path(destination).open("xb") as stream:
        stream.write(encrypted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("create")
    command.add_argument("--database", required=True)
    command.add_argument("--uploads", required=True)
    command.add_argument("--output", required=True)
    command = sub.add_parser("seal")
    command.add_argument("--archive", required=True)
    command.add_argument("--key-file", required=True)
    command.add_argument("--output", required=True)
    command = sub.add_parser("restore")
    command.add_argument("--archive", required=True)
    command.add_argument("--key-file", required=True)
    command.add_argument("--destination", required=True)
    args = parser.parse_args()
    if args.command == "create":
        result = create(args.database, args.uploads, args.output)
        print(json.dumps({"ok": True, "counts": result["counts"], "files": len(result["files"])}))
    elif args.command == "seal":
        seal(args.archive, args.key_file, args.output)
        print('{"ok":true,"encrypted":true}')
    else:
        from cryptography.fernet import Fernet
        data = Fernet(Path(args.key_file).read_bytes().strip()).decrypt(Path(args.archive).read_bytes())
        result = restore(data, args.destination)
        print(json.dumps({"ok": True, "counts": result["counts"]}))


if __name__ == "__main__":
    main()
