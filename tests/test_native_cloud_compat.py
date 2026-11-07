"""Both native contracts share durable storage without changing v1 responses."""
import secrets

from fastapi.testclient import TestClient
from app import db, storage
from deploy.gateway import app
from test_app import fresh_db


def test_v2_registration_login_and_database_photo_replacement(fresh_db, monkeypatch):
    monkeypatch.setenv('YUNO_PHOTO_STORAGE', 'database')
    db.init_db()
    c = TestClient(app)
    email = 'cloud-' + secrets.token_hex(6) + '@example.test'
    password = secrets.token_urlsafe(24)
    r = c.post('/api/v2/register', json={
        'email': email, 'password': password, 'display_name': 'Cloud acceptance'})
    assert r.status_code == 200, r.text
    auth = {'Authorization': 'Bearer ' + r.json()['access_token']}
    identity = c.get('/api/v2/me', headers=auth).json()
    # The pre-existing client retains its own response envelope.
    assert c.get('/api/v1/me', headers=auth).json()['user']['id'] == identity['id']
    r = c.post('/api/v2/oneclick/upload', headers=auth,
               data={'name': 'Cloud test'}, files={'photo': ('test.png', b'first', 'image/png')})
    assert r.status_code == 200, r.text
    did = int(r.json()['next'].split('/')[-1])
    r = c.post(f'/api/v2/oneclick/{did}/photos/0/replace', headers=auth,
               files={'photo': ('replace.png', b'replacement', 'image/png')})
    assert r.status_code == 200, r.text
    draft = c.get(f'/api/v2/oneclick/{did}', headers=auth).json()
    name = draft['photos'][0]['filename']
    assert storage.read(name) == b'replacement'
    assert not (db.UPLOAD_DIR / name).exists()
    restarted = TestClient(app)
    assert restarted.get(draft['photos'][0]['url']).content == b'replacement'
    assert c.post('/api/v2/logout', headers=auth, json={}).status_code == 200
    assert c.get('/api/v2/me', headers=auth).status_code == 401
    r = c.post('/api/v2/login', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    assert c.post('/api/v2/login', json={'email': email, 'password': 'wrong'}).status_code == 401
    assert c.get('/api/v1/config').status_code == 200
    assert c.get('/api/v2/config').status_code == 200


def test_v2_public_gateway_does_not_expose_business_html_routes(fresh_db):
    client = TestClient(app)
    result = client.get('/api/v2/config')
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'
    for path in ('/api/v2x/config', '/api/v2/../admin', '/admin', '/openapi.json'):
        assert client.get(path).status_code == 404
    assert client.post('/api/v2/login', json={}).status_code in (400, 422)
    assert client.post('/register', data={}).status_code == 404
