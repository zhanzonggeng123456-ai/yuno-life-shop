import secrets
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from test_app import fresh_db
from app import db as d
from app.main import app
from app.security import reset_rate_limits


@pytest.fixture
def api():
    reset_rate_limits()
    return TestClient(app)


def account(api):
    result = api.post("/api/v1/actions/register", json={
        "email": secrets.token_hex(8) + "@example.jp",
        "display_name": "Native test", "password": secrets.token_urlsafe(18)})
    assert result.status_code == 200, result.text
    payload = result.json()
    assert "pw_hash" not in payload["user"] and "salt" not in payload["user"]
    return {"Authorization": "Bearer " + payload["token"]}


def publish(api, auth):
    result = api.post("/api/v1/actions/listing_create", headers=auth, data={
        "category_slug": "appliance", "title_ja": "電子レンジ",
        "title_zh": "微波炉", "price": "4000",
    }, files=[("images", ("one.png", b"image", "image/png")),
              ("images", ("two.png", b"image", "image/png"))])
    assert result.status_code == 200, result.text
    return result.json()["id"]


def test_native_auth_revocation_and_cookie_rejection(api):
    auth = account(api)
    assert api.get("/api/v1/me", headers=auth).status_code == 200
    assert api.get("/api/v1/me").status_code == 401
    assert api.post("/api/v1/actions/logout", headers=auth, json={}).status_code == 200
    assert api.get("/api/v1/me", headers=auth).status_code == 401


def test_native_market_and_rules_are_json(api):
    for path in ("config", "market", "rules/terms", "rules/privacy", "rules/returns", "rules/prohibited"):
        result = api.get("/api/v1/" + path)
        assert result.status_code == 200, result.text
        assert "application/json" in result.headers["content-type"]
    assert "模拟" in api.get("/api/v1/rules/terms").json()["text"]
    assert len(api.get("/api/v1/config").json()["services"]) == 3


def test_native_order_retry_and_private_resources(api):
    seller, buyer, stranger = account(api), account(api), account(api)
    lid = publish(api, seller)
    result = api.get(f"/api/v1/listings/{lid}")
    assert len(result.json()["item"]["photos"]) == 2
    order = api.post("/api/v1/actions/buy", headers=buyer, json={"lid": lid}).json()["id"]
    assert api.get(f"/api/v1/orders/{order}", headers=stranger).status_code == 404
    args = {"oid": order, "idempotency_key": secrets.token_hex(16)}
    for _ in range(2):
        assert api.post("/api/v1/actions/order_pay", headers=buyer, json=args).status_code == 200
    assert api.get(f"/api/v1/orders/{order}", headers=buyer).json()["item"]["status"] == "paid"
    assert api.post("/api/v1/actions/order_complete", headers=buyer, json={"oid": order}).status_code == 200
    assert api.post("/api/v1/actions/order_cancel", headers=buyer, json={"oid": order}).status_code == 409
    assert api.get("/api/v1/admin/users", headers=stranger).status_code == 403
    assert api.post("/api/v1/actions/unknown", headers=buyer, json={}).status_code == 404


def test_native_draft_photos_jobs_and_ownership(api):
    seller, stranger = account(api), account(api)
    response = api.post("/api/v1/actions/oneclick_upload", headers=seller,
                        data={"name": "微波炉"}, files={"photo": ("one.png", b"image", "image/png")})
    assert response.status_code == 200, response.text
    did = response.json()["id"]
    assert api.get(f"/api/v1/drafts/{did}", headers=stranger).status_code == 404
    assert api.post("/api/v1/actions/oneclick_recognize", headers=stranger, json={"did": did}).status_code == 403
    job = api.post("/api/v1/actions/ai_job_create", headers=seller,
                   json={"kind": "oneclick_recognize", "draft_id": str(did)}).json()["job_id"]
    for _ in range(100):
        status = api.get(f"/api/v1/jobs/{job}", headers=seller).json()["item"]["status"]
        if status in ("done", "failed"):
            break
        time.sleep(.02)
    assert status == "done"
    draft = api.get(f"/api/v1/drafts/{did}", headers=seller).json()["item"]
    assert draft["valuation"]["suggested_price"] is None
    assert len(draft["photos"]) == 1
    assert api.get(f"/api/v1/jobs/{job}", headers=stranger).status_code == 404
    assert api.post("/api/v1/actions/oneclick_upload", headers=seller,
                    data={"name": "test"}, files=[
                        ("photos", (f"{i}.png", b"image", "image/png")) for i in range(11)
                    ]).status_code in (400, 413)


def test_native_validation_and_no_secret_disclosure(api):
    auth = account(api)
    result = api.post("/api/v1/actions/listing_create", headers=auth,
                      json={"category_slug": "appliance", "title_ja": "test", "price": "no"})
    assert result.status_code == 400
    result = api.post("/api/v1/actions/register", json={})
    assert result.status_code == 400
    with d.connect() as c:
        c.execute("UPDATE sessions SET expires_at='2000-01-01'")
        c.commit()
    assert api.get("/api/v1/me", headers=auth).status_code == 401


def test_native_photo_editing_keeps_cover_count_and_audit(api):
    auth, stranger = account(api), account(api)
    result = api.post("/api/v1/actions/oneclick_upload", headers=auth,
                      data={"name": "photo test"}, files=[
                          ("photos", ("one.png", b"one", "image/png")),
                          ("photos", ("two.png", b"two", "image/png"))])
    did = result.json()["id"]
    before = api.get(f"/api/v1/drafts/{did}", headers=auth).json()["item"]["photos"]
    args = {"did": did, "idx": 1}
    assert api.post("/api/v1/actions/draft_photo_cover", headers=stranger, json=args).status_code == 403
    assert api.post("/api/v1/actions/draft_photo_cover", headers=auth, json=args).status_code == 200
    after = api.get(f"/api/v1/drafts/{did}", headers=auth).json()["item"]["photos"]
    assert after[0] == before[1] and len(after) == 2
    assert api.post("/api/v1/actions/draft_photo_replace", headers=auth, json=args).status_code == 400
    result = api.post("/api/v1/actions/draft_photo_replace", headers=auth, data=args,
                      files={"photo": ("new.png", b"new", "image/png")})
    assert result.status_code == 200, result.text
    draft = api.get(f"/api/v1/drafts/{did}", headers=auth).json()["item"]
    assert draft["status"] == "uploaded" and len(draft["photos"]) == 2
    with closing(d.connect()) as c:
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action LIKE 'draft_photo_%'").fetchone()[0] == 2


def test_native_public_profile_and_appraiser_permissions(api):
    auth = account(api)
    user = api.get("/api/v1/me", headers=auth).json()["user"]
    public = api.get(f"/api/v1/profiles/{user['id']}").json()["item"]
    assert "email" not in public and "phone" not in public and public["count"] == 0
    with closing(d.connect()) as c:
        c.execute("UPDATE users SET role='appraiser' WHERE id=?", (user["id"],))
        c.commit()
    assert api.get("/api/v1/admin/high-value", headers=auth).status_code == 200
    assert api.get("/api/v1/admin/users", headers=auth).status_code == 403
    assert api.post("/api/v1/actions/admin_run_anomalies", headers=auth, json={}).status_code == 403


def test_native_auction_proxy_is_private_and_low_bids_fail(api):
    seller, buyer = account(api), account(api)
    lid = publish(api, seller)
    result = api.post("/api/v1/actions/auction_create", headers=seller, json={
        "lid": lid, "start_price": 1000, "min_increment": 100,
        "ends_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    aid = result.json()["id"]
    result = api.post("/api/v1/actions/auction_bid", headers=buyer,
                      json={"aid": aid, "amount": 1000, "proxy_max": 2000})
    assert result.status_code == 200, result.text
    result = api.get(f"/api/v1/auctions/{aid}").json()
    assert result["item"]["current_price"] == 1000
    assert "proxy_max" not in result["related"]["bids"][0]
    assert api.post("/api/v1/actions/auction_bid", headers=buyer,
                    json={"aid": aid, "amount": 1}).status_code == 409
