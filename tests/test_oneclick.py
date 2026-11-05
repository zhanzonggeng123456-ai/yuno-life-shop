"""AI 一键链路测试:上传 -> 一键识别 -> 一键上架。
每个测试前重置本地 SQLite 文件,全部本地运行,无外部调用。
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="yuno_oneclick_")
os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.oneclick import (appraise, is_high_value, real_vision_assist,
                          valuation_for)


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(d.DB_PATH):
        os.remove(d.DB_PATH)
    d.init_db()
    yield


def client():
    import app.main as m
    return TestClient(m.app)


def reg(c, email, name="用户", pw="Pass1234!"):
    r = c.post("/register", data={"email": email, "display_name": name,
                                  "password": pw})
    assert r.status_code == 200, r.status_code
    return c


def dbval(sql, args=()):
    conn = d.connect()
    row = conn.execute(sql, args).fetchone()
    conn.close()
    return row[0] if row else None


def dbrow(sql, args=()):
    conn = d.connect()
    row = conn.execute(sql, args).fetchone()
    conn.close()
    return row


def upload_draft(c, name="ロレックス 腕時計", text="ステンレス、付属品あり",
                 price_hint="150000", photo=True):
    files = {"photo": ("watch.jpg", b"fake-image-bytes", "image/jpeg")} \
        if photo else None
    r = c.post("/oneclick/upload",
               data={"name": name, "text": text, "condition": "good",
                     "price_hint": price_hint},
               files=files)
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM oneclick_drafts")


def recognize(c, did):
    r = c.post(f"/oneclick/{did}/recognize")
    assert r.status_code == 200, r.status_code
    return r


def publish_draft(c, did, category="watch", title_zh="二手表", price="80000",
                  title_ja="中古時計"):
    r = c.post(f"/oneclick/{did}/publish", data={
        "category_slug": category, "title_ja": title_ja, "title_zh": title_zh,
        "desc_ja": "", "desc_zh": "", "price": price,
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"})
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM listings")


def test_recognize_suggestions_are_guesses_and_editable():
    c = reg(client(), "oc1@test.jp")
    did = upload_draft(c)
    r = recognize(c, did)
    # 识别结果标注为推测,且品牌建议来自关键词(ロレックス -> Rolex)
    assert "推测" in r.text or "推測" in r.text
    assert "Rolex" in r.text
    # 用户把标题改成自己的,发布后以修改为准,不以建议为准
    lid = publish_draft(c, did, title_zh="我改过的标题")
    assert dbval("SELECT title_zh FROM listings WHERE id=?", (lid,)) == "我改过的标题"
    assert dbval("SELECT status FROM oneclick_drafts WHERE id=?", (did,)) == "published"
    assert dbval("SELECT listing_id FROM oneclick_drafts WHERE id=?", (did,)) == lid


def test_valuation_no_sample_never_fabricates():
    c = reg(client(), "oc2@test.jp")
    conn = d.connect()
    val = valuation_for(conn, "watch")
    conn.close()
    assert val["low"] is None and val["high"] is None
    assert val["has_sample"] is False and val["confidence"] == "none"
    did = upload_draft(c, price_hint="")
    recognize(c, did)
    row = dbrow("SELECT valuation_json FROM oneclick_drafts WHERE id=?", (did,))
    import json
    val = json.loads(row[0])
    assert val["low"] is None and val["has_sample"] is False
    r = c.get(f"/oneclick/{did}")
    assert "サンプル不足" in r.text or "缺少可靠成交样本" in r.text


def test_high_value_auto_review_blocks_trade_and_audits():
    seller = reg(client(), "oc3s@test.jp", "卖家")
    did = upload_draft(seller)
    recognize(seller, did)
    lid = publish_draft(seller, did, price="150000")
    hv = dbrow("SELECT appraisal_status FROM hv_reviews WHERE listing_id=?", (lid,))
    assert hv is not None and hv[0] == "pending"
    assert dbval("SELECT COUNT(*) FROM audit_log WHERE action='appraisal_queued'"
                 " AND target_id=?", (lid,)) == 1
    buyer = reg(client(), "oc3b@test.jp", "买家")
    buyer.post(f"/listings/{lid}/buy")
    assert dbval("SELECT COUNT(*) FROM orders WHERE listing_id=?", (lid,)) == 0


def test_oneclick_publish_creates_listing_with_photo():
    c = reg(client(), "oc4@test.jp")
    did = upload_draft(c, name="電子レンジ", text="微波炉,良好",
                       price_hint="6000")
    recognize(c, did)
    lid = publish_draft(c, did, category="appliance", title_zh="二手微波炉",
                        price="6000", title_ja="中古電子レンジ")
    assert dbval("SELECT category_id FROM listings WHERE id=?", (lid,)) == \
        dbval("SELECT id FROM categories WHERE slug='appliance'")
    photo = dbval("SELECT photo FROM oneclick_drafts WHERE id=?", (did,))
    assert photo
    assert dbval("SELECT COUNT(*) FROM images WHERE listing_id=? AND filename=?",
                 (lid, photo)) == 1
    assert c.get(f"/listings/{lid}").status_code == 200


def test_unauthorized_draft_rejected():
    owner = reg(client(), "oc5a@test.jp", "卖家")
    did = upload_draft(owner)
    other = reg(client(), "oc5b@test.jp", "路人")
    assert other.get(f"/oneclick/{did}").status_code == 403
    assert other.post(f"/oneclick/{did}/recognize").status_code == 403
    r = other.post(f"/oneclick/{did}/publish", data={
        "category_slug": "appliance", "title_ja": "x", "title_zh": "x",
        "desc_ja": "", "desc_zh": "", "price": "100",
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"})
    assert r.status_code == 403
    assert dbval("SELECT status FROM oneclick_drafts WHERE id=?", (did,)) == "uploaded"


def test_appraisal_rules_and_high_value_threshold():
    assert is_high_value("watch", 100000) is True
    assert is_high_value("watch", 99999) is False
    assert is_high_value("furniture", 200000) is False
    ap = appraise("watch", 150000, "good", {})
    assert ap["requires_manual_review"] is True
    assert ap["is_determination"] is False
    # 无附件、无品牌确认 -> 两个风险因素 -> high
    assert ap["authenticity_risk"] == "high"
    ap2 = appraise("appliance", 6000, "good", {})
    assert ap2["requires_manual_review"] is False
    assert ap2["authenticity_risk"] == "low"


def test_real_vision_disabled_by_default(monkeypatch):
    assert real_vision_assist() is None
    monkeypatch.setenv("YUNO_VISION_ENABLED", "1")
    monkeypatch.setenv("YUNO_VISION_API_KEY", "test-key")
    with pytest.raises(NotImplementedError):
        real_vision_assist()
