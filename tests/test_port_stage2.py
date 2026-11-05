"""第 2 阶段移植测试:多图 + 相机优先、鉴定两轴、估价区间与型号确认流。"""
import json
import os
import re
import tempfile

if "YUNO_DB_PATH" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="yuno_stage2_")
    os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
    os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.oneclick import (DETAIL_CHECKLISTS, appraise_two_axis,
                          detail_checklist_for, is_sensitive_category)
from app.valuation import DISCLAIMER_ZH, valuation_interval


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(d.DB_PATH):
        os.remove(d.DB_PATH)
    d.init_db()
    yield


def client():
    import app.main as m
    return TestClient(m.app)


def reg(c, email, name="用户", pw="TestPass123!"):
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


def dball(sql, args=()):
    conn = d.connect()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return rows


def img_file(name):
    return ("images", (name, b"fake-image-bytes-" + name.encode(), "image/jpeg"))


def publish(c, n=1, category="appliance", price=6000, title_zh="二手微波炉"):
    files = [img_file(f"p{i}.jpg") for i in range(n)]
    r = c.post("/listings/new", data={
        "category_slug": category, "title_ja": "中古品", "title_zh": title_zh,
        "desc_ja": "", "desc_zh": "", "price": str(price),
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"}, files=files)
    return r


def publish_ok(c, n=1, **kw):
    r = publish(c, n=n, **kw)
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM listings")


def upload_multi(c, name="ロレックス 腕時計", text="ステンレス", n=3,
                 price_hint="150000"):
    files = [("photos", (f"w{i}.jpg", b"fake-image-bytes", "image/jpeg"))
             for i in range(n)]
    r = c.post("/oneclick/upload",
               data={"name": name, "text": text, "condition": "good",
                     "price_hint": price_hint}, files=files)
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM oneclick_drafts")


def recognize(c, did):
    r = c.post(f"/oneclick/{did}/recognize")
    assert r.status_code == 200, r.status_code
    return r


# ---------------- 1. 多图 + 相机优先 ----------------

def test_publish_ten_photos_ok_eleventh_rejected():
    c = reg(client(), "s2a@test.jp")
    lid = publish_ok(c, n=10)
    assert dbval("SELECT COUNT(*) FROM images WHERE listing_id=?", (lid,)) == 10
    before = dbval("SELECT COUNT(*) FROM listings")
    r = publish(c, n=11)
    assert r.status_code == 400
    assert "10" in r.text
    assert dbval("SELECT COUNT(*) FROM listings") == before


def test_cover_switch_changes_detail_first_image_and_non_owner_403():
    owner = reg(client(), "s2b@test.jp", "卖家")
    lid = publish_ok(owner, n=3)
    rows = dball("SELECT id, filename FROM images WHERE listing_id=? "
                 "ORDER BY sort, id", (lid,))
    assert len(rows) == 3
    first_before = rows[0]["filename"]
    target_id, target_file = rows[1]["id"], rows[1]["filename"]
    assert target_file != first_before
    r = owner.post(f"/listings/{lid}/photos/{target_id}/cover")
    assert r.status_code == 200
    assert dbval("SELECT filename FROM images WHERE listing_id=? "
                 "ORDER BY sort, id LIMIT 1", (lid,)) == target_file
    detail = owner.get(f"/listings/{lid}").text
    uploads = re.findall(r'/uploads/([^"]+)', detail)
    assert uploads and uploads[0] == target_file
    # 非所有者操作一律 403,封面不变
    other = reg(client(), "s2c@test.jp", "路人")
    assert other.post(f"/listings/{lid}/photos/{rows[2]['id']}/cover").status_code == 403
    assert other.post(f"/listings/{lid}/photos/{target_id}/delete").status_code == 403
    assert other.post(f"/listings/{lid}/photos/add",
                      files=[img_file("x.jpg")]).status_code == 403
    assert dbval("SELECT filename FROM images WHERE listing_id=? "
                 "ORDER BY sort, id LIMIT 1", (lid,)) == target_file


def test_delete_and_replace_photo_take_effect():
    owner = reg(client(), "s2d@test.jp", "卖家")
    lid = publish_ok(owner, n=3)
    rows = dball("SELECT id, filename FROM images WHERE listing_id=? "
                 "ORDER BY sort, id", (lid,))
    r = owner.post(f"/listings/{lid}/photos/{rows[0]['id']}/delete")
    assert r.status_code == 200
    assert dbval("SELECT COUNT(*) FROM images WHERE listing_id=?", (lid,)) == 2
    rows = dball("SELECT id, filename FROM images WHERE listing_id=? "
                 "ORDER BY sort, id", (lid,))
    old_file = rows[0]["filename"]
    r = owner.post(f"/listings/{lid}/photos/{rows[0]['id']}/replace",
                   files={"photo": ("new.jpg", b"new-bytes", "image/jpeg")})
    assert r.status_code == 200
    assert dbval("SELECT filename FROM images WHERE id=?",
                 (rows[0]["id"],)) != old_file
    # 详情页展示全部照片(删除后 2 张)
    detail = owner.get(f"/listings/{lid}").text
    assert len(re.findall(r'/uploads/[^"]+', detail)) >= 2


def test_publish_page_camera_first_and_album_and_disabled_valuation():
    c = reg(client(), "s2e@test.jp")
    html = c.get("/listings/new").text
    assert 'capture="environment"' in html
    assert "相册" in html
    assert "photo-preview" in html
    assert "最多10张" in html
    assert 'id="oneclick-valuation-btn" disabled' in html
    assert "请先拍照/上传照片" in html


def test_listing_photo_add_respects_ten_limit():
    owner = reg(client(), "s2f@test.jp", "卖家")
    lid = publish_ok(owner, n=10)
    r = owner.post(f"/listings/{lid}/photos/add",
                   files=[("photos", ("x.jpg", b"fake-image-bytes",
                                      "image/jpeg"))])
    assert r.status_code == 400
    assert dbval("SELECT COUNT(*) FROM images WHERE listing_id=?", (lid,)) == 10


# ---------------- oneclick 草稿多照片 ----------------

def test_oneclick_draft_multi_photos_and_analysis_counts_all():
    c = reg(client(), "s2g@test.jp")
    did = upload_multi(c, n=3)
    row = dbrow("SELECT photo, draft_json FROM oneclick_drafts WHERE id=?", (did,))
    dr = json.loads(row["draft_json"])
    assert len(dr["photos"]) == 3
    assert row["photo"] == dr["photos"][0]  # 原 photo 字段作封面兼容
    recognize(c, did)
    rec = json.loads(dbval("SELECT recognition_json FROM oneclick_drafts "
                           "WHERE id=?", (did,)))
    assert rec["photo_count"] == 3 and len(rec["photos"]) == 3
    dr = json.loads(dbval("SELECT draft_json FROM oneclick_drafts WHERE id=?",
                          (did,)))
    assert dr["photo_count"] == 3 and len(dr["photos"]) == 3
    page = c.get(f"/oneclick/{did}").text
    assert "3 张" in page
    # 发布后商品带全部 3 张照片,首张为封面
    r = c.post(f"/oneclick/{did}/publish", data={
        "category_slug": "watch", "title_ja": "中古時計", "title_zh": "二手表",
        "desc_ja": "", "desc_zh": "", "price": "80000",
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"})
    assert r.status_code == 200
    lid = dbval("SELECT MAX(id) FROM listings")
    assert dbval("SELECT COUNT(*) FROM images WHERE listing_id=?", (lid,)) == 3


# ---------------- 2. 鉴定两轴 ----------------

def test_sensitive_category_map_and_checklists():
    assert is_sensitive_category("watch") is True
    assert is_sensitive_category("coin") is True
    assert is_sensitive_category("antique") is True
    assert is_sensitive_category("fashion") is True
    assert is_sensitive_category("figure") is True
    for slug in ("furniture", "appliance", "digital", "camera",
                 "instrument", "book", "tool", "other"):
        assert is_sensitive_category(slug) is False
    assert detail_checklist_for("watch") == DETAIL_CHECKLISTS["watch"]
    for item in ("表盘", "表背机芯", "刻字", "序列号", "表扣", "表带", "盒证"):
        assert item in detail_checklist_for("watch")
    assert detail_checklist_for("appliance") == []


def test_sensitive_appraisal_full_verdict_and_low_confidence_when_detail_short():
    ap = appraise_two_axis("watch", 150000, "good", {}, photo_count=1)
    assert ap["condition_grade"] == "good"
    assert "authenticity" in ap
    assert ap["authenticity"]["verdict"] in ("likely_genuine", "unconfirmed")
    assert ap["authenticity"]["is_guess"] is True
    assert "AI 推测" in ap["authenticity"]["note"]
    assert ap["confidence"] == "low"
    assert ap["detail_insufficient"] is True
    assert "细节不足、低置信度" in ap["detail_note"]
    assert ap["requires_manual_review"] is True  # 高价值进复核
    ap2 = appraise_two_axis("watch", 8000, "good", {}, photo_count=5)
    assert ap2["confidence"] == "medium"
    assert ap2["detail_insufficient"] is False
    assert ap2["requires_manual_review"] is False
    # 路由页面同样展示成色 + 真伪 + 低置信度注明
    c = reg(client(), "s2h@test.jp")
    did = upload_multi(c, n=1)
    recognize(c, did)
    page = c.get(f"/oneclick/{did}").text
    assert "真伪结论" in page and "AI 推测" in page
    assert "细节不足、低置信度" in page
    assert "表盘" in page


def test_ordinary_appraisal_has_no_authenticity_field():
    ap = appraise_two_axis("appliance", 6000, "good", {}, photo_count=1)
    assert ap["condition_grade"] == "good"
    assert "authenticity" not in ap
    assert "verdict" not in ap
    assert "authenticity_risk" not in ap
    assert ap["requires_manual_review"] is False
    c = reg(client(), "s2i@test.jp")
    did = upload_multi(c, name="電子レンジ", text="微波炉,良好", n=2,
                       price_hint="6000")
    recognize(c, did)
    page = c.get(f"/oneclick/{did}").text
    assert "真伪结论" not in page
    assert "成色等级" in page


# ---------------- 3. 估价 ----------------

def test_valuation_market_interval_and_disclaimer_verbatim():
    assert DISCLAIMER_ZH == "此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写"
    comps = [{"price": 200000, "source": "Chrono24", "date": "2026-11-01"},
             {"price": 240000, "source": "Mercari", "date": "2026-11-02"},
             {"price": 260000, "source": "Yahoo", "date": "2026-11-03"},
             {"price": 300000, "source": "eBay", "date": "2026-11-04"}]
    val = valuation_interval(comps, "good")
    assert val["kind"] == "market" and val["is_market_price"] is True
    assert val["low"] is not None and val["high"] is not None
    assert val["low"] <= val["high"]
    assert val["sample_count"] == 4
    assert val["suggested_price"] == val["high"]
    assert val["disclaimer_zh"] == DISCLAIMER_ZH
    # 1 个样本也不返回空区间
    val1 = valuation_interval([{"price": 100000}], "good")
    assert val1["low"] == 100000 and val1["high"] == 100000


def test_valuation_conservative_calibration_new_15000():
    val = valuation_interval([], "excellent", new_price=15000)
    assert val["kind"] == "estimate_reference"
    assert val["estimate_high"] == 7500
    assert val["estimate_low"] == 6000
    assert val["is_market_price"] is False
    assert val["suggested_price"] is None
    assert "推算参考" in val["basis_zh"]
    # 成色越差上限越低,绝非固定比例、绝不用新品价当二手价
    good = valuation_interval([], "good", new_price=15000)
    fair = valuation_interval([], "fair", new_price=15000)
    assert good["estimate_high"] == 6750
    assert fair["estimate_high"] == 5250
    assert fair["estimate_high"] < good["estimate_high"] < 7500


def test_valuation_market_median_auto_filled_and_estimate_not():
    c = reg(client(), "s2j@test.jp")
    did = upload_multi(c, name="電子レンジ", text="微波炉", n=1,
                       price_hint="12345")
    recognize(c, did)
    # 模拟第 3 阶段填入同型号市场样本后的估价:中位数自动填入可编辑价格框
    market = valuation_interval(
        [{"price": 8000}, {"price": 10000}, {"price": 12000}], "good")
    conn = d.connect()
    conn.execute("UPDATE oneclick_drafts SET valuation_json=? WHERE id=?",
                 (json.dumps(market, ensure_ascii=False), did))
    conn.commit()
    conn.close()
    page = c.get(f"/oneclick/{did}").text
    assert f'value="{market["suggested_price"]}"' in page
    assert DISCLAIMER_ZH in page
    assert "不是成交价、不是平台收购承诺" in page
    # 启发式推算参考绝不自动填入:价格框仍是用户期望价,且注明未自动填入
    est = valuation_interval([], "good", new_price=15000)
    conn = d.connect()
    conn.execute("UPDATE oneclick_drafts SET valuation_json=? WHERE id=?",
                 (json.dumps(est, ensure_ascii=False), did))
    conn.commit()
    conn.close()
    page = c.get(f"/oneclick/{did}").text
    assert 'value="12345"' in page
    assert "未自动填入" in page
    assert "推算参考" in page


def test_publish_requires_user_confirmation_and_price_editable():
    c = reg(client(), "s2k@test.jp")
    did = upload_multi(c, n=1, price_hint="6000")
    recognize(c, did)
    assert dbval("SELECT status FROM oneclick_drafts WHERE id=?", (did,)) == "recognized"
    assert dbval("SELECT COUNT(*) FROM listings") == 0
    # 用户把价格改成自己的才发布,发布后以修改为准
    r = c.post(f"/oneclick/{did}/publish", data={
        "category_slug": "watch", "title_ja": "中古時計", "title_zh": "二手表",
        "desc_ja": "", "desc_zh": "", "price": "77777",
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"})
    assert r.status_code == 200
    lid = dbval("SELECT MAX(id) FROM listings")
    assert dbval("SELECT price FROM listings WHERE id=?", (lid,)) == 77777


def test_model_unconfirmed_honest_no_quote_and_confirm_flow():
    val = valuation_interval([], "good", model_confirmed=False)
    assert val["low"] is None and val["high"] is None
    assert val["kind"] == "model_unconfirmed"
    assert val["suggested_price"] is None
    c = reg(client(), "s2l@test.jp")
    did = upload_multi(c, n=1)
    recognize(c, did)
    stored = json.loads(dbval("SELECT valuation_json FROM oneclick_drafts "
                              "WHERE id=?", (did,)))
    assert stored["low"] is None and stored["kind"] == "model_unconfirmed"
    page = c.get(f"/oneclick/{did}").text
    assert "型号未确认" in page
    assert "表背、刻字、序列号" in page
    assert "未确认" in page
    # 手动输入型号确认后仍不编价格(无同型号市场样本时如实无报价)
    r = c.post(f"/oneclick/{did}/model",
               data={"brand": "Seiko", "model": "SBGX263"})
    assert r.status_code == 200
    dr = json.loads(dbval("SELECT draft_json FROM oneclick_drafts WHERE id=?",
                          (did,)))
    assert dr["model_confirmed"] is True and dr["model"] == "SBGX263"
    stored = json.loads(dbval("SELECT valuation_json FROM oneclick_drafts "
                              "WHERE id=?", (did,)))
    assert stored["low"] is None and stored["kind"] == "no_market_price"
    page = c.get(f"/oneclick/{did}").text
    assert "已确认" in page
