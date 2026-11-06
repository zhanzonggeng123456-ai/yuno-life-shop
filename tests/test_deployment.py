import secrets

import pytest
from fastapi.testclient import TestClient

from test_app import fresh_db
from deploy.gateway import app
from deploy.serve import configure_storage


def test_public_ingress_keeps_native_auth_and_blocks_legacy_cookie_routes():
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    config = client.get("/api/v1/config")
    assert config.status_code == 200
    assert config.headers["x-content-type-options"] == "nosniff"
    assert config.headers["cache-control"] == "no-store"
    assert len(config.json()["services"]) == 3
    assert client.get("/").json()["payment"] == "simulated"
    for path in ("/docs", "/openapi.json", "/admin", "/api/v1x/config"):
        assert client.get(path).status_code == 404
    assert client.post("/register", data={}).status_code == 404
    result = client.post("/api/v1/actions/register", json={
        "email": secrets.token_hex(8) + "@example.jp", "display_name": "Cloud QA",
        "password": secrets.token_urlsafe(20)})
    assert result.status_code == 200
    token = result.json()["token"]
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer " + token}).status_code == 200
    client.cookies.set("yuno_session", token)
    assert client.get("/api/v1/me").status_code == 401


def test_cloud_start_refuses_ephemeral_or_escaped_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("YUNO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("YUNO_REQUIRE_PERSISTENT_VOLUME", "1")
    with pytest.raises(RuntimeError, match="persistent volume"):
        configure_storage()
    monkeypatch.setenv("YUNO_REQUIRE_PERSISTENT_VOLUME", "0")
    monkeypatch.setenv("YUNO_DB_PATH", str(tmp_path.parent / "unrelated.db"))
    with pytest.raises(RuntimeError, match="inside"):
        configure_storage()


def test_cloud_storage_preserves_existing_database_and_photos(tmp_path, monkeypatch):
    monkeypatch.setenv("YUNO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("YUNO_REQUIRE_PERSISTENT_VOLUME", "0")
    monkeypatch.delenv("YUNO_DB_PATH", raising=False)
    monkeypatch.delenv("YUNO_UPLOAD_DIR", raising=False)
    configure_storage()
    database = tmp_path / "db" / "yuno.db"
    photo = tmp_path / "uploads" / "retained.jpg"
    database.write_bytes(b"existing database")
    photo.write_bytes(b"existing photo")
    configure_storage()
    assert database.read_bytes() == b"existing database"
    assert photo.read_bytes() == b"existing photo"


def test_fresh_process_initializes_database_only_after_storage_configuration(tmp_path):
    import os
    import subprocess
    import sys
    environment = os.environ.copy()
    for key in ('YUNO_DB_PATH', 'YUNO_UPLOAD_DIR', 'TURSO_DATABASE_URL', 'TURSO_AUTH_TOKEN', 'YUNO_STORAGE_MODE'):
        environment.pop(key, None)
    environment.update(YUNO_DATA_DIR=str(tmp_path), YUNO_REQUIRE_PERSISTENT_VOLUME='0')
    code = ('from deploy.serve import configure_storage; root=configure_storage(); '
            'from app import db; assert db.DB_PATH == root/"db"/"yuno.db"; '
            'assert db.UPLOAD_DIR == root/"uploads"; db.init_db(); '
            'assert (root/"db"/"yuno.db").is_file()')
    subprocess.run([sys.executable, '-c', code], env=environment, check=True, timeout=20)
