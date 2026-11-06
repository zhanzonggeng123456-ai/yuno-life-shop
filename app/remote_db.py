"""Small DB-API compatibility boundary for the official libSQL Python driver."""
import os
from urllib.parse import urlsplit


class Row:
    def __init__(self, names, values):
        self.names, self.values = names, values

    def keys(self):
        return self.names

    def __getitem__(self, key):
        return self.values[self.names.index(key)] if isinstance(key, str) else self.values[key]

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.names = tuple(item[0] for item in (cursor.description or ()))

    def fetchone(self):
        values = self.cursor.fetchone()
        return Row(self.names, values) if values is not None else None

    def fetchall(self):
        return [Row(self.names, values) for values in self.cursor.fetchall()]

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row

    @property
    def lastrowid(self):
        return self.cursor.lastrowid


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        return Cursor(self.connection.execute(sql, tuple(params)))

    def executescript(self, sql):
        return self.connection.executescript(sql)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if error_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def configuration():
    url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if bool(url) != bool(token):
        raise RuntimeError("Both Turso database URL and token are required")
    if url:
        parsed = urlsplit(url)
        if (parsed.scheme not in ("libsql", "https") or not parsed.hostname
                or not parsed.hostname.endswith(".turso.io") or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise RuntimeError("Use an official libSQL Turso database URL")
    return url, token


def connect(database):
    import libsql
    url, token = configuration()
    raw = libsql.connect(database=url, auth_token=token) if url else libsql.connect(str(database))
    return Connection(raw)
