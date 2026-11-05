"""第 3 阶段移植测试:市场比价搜索、行情双榜、AI 任务、/ai-assist 收口、
所有权与自购核查。网络相关测试一律用 mock 传输/注入样本/缓存,
不做真实联网。"""
import json
import os
import tempfile
import time
from urllib.parse import unquote

if "YUNO_DB_PATH" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="yuno_stage3_")
    os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
    os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.agents import pricing_agent
from app.market import listing_price_moves
from app.market_search import (normalize_model_key, read_cache,
                               search_market_comps, sources_for_category,
                               write_cache)
from app.security import hash_password
from app.valuation import valuation_interval


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


def dbexec(sql, args=()):
    conn = d.connect()
    conn.execute(sql, args)
    conn.commit()
    conn.close()


def user_id(email):
    return dbval("SELECT id FROM users WHERE email=?", (email,))


def publish(c, price=6000, category="appliance", title_zh="二手微波炉"):
    r = c.post("/listings/new", data={
        "category_slug": category, "title_ja": "中古品", "title_zh": title_zh,
        "desc_ja": "", "desc_zh": "", "price": str(price),
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"},
        files=[("images", ("p.jpg", b"fake-image-bytes", "image/jpeg"))])
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM listings")


def upload_draft(c, name="ロレックス 腕時計", text="ステンレス"):
    files = [("photos", ("w0.jpg", b"fake-image-bytes", "image/jpeg"))]
    r = c.post("/oneclick/upload",
               data={"name": name, "text": text, "condition": "good",
                     "price_hint": "150000"}, files=files)
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM oneclick_drafts")


def poll_job(c, jid, timeout=8.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = c.get(f"/ai-jobs/{jid}")
        assert r.status_code == 200, r.status_code
        last = r.json()
        if last["status"] in ("done", "failed"):
            return last
        time.sleep(0.1)
    return last


def seed_cache(brand, model, slugs, comps):
    conn = d.connect()
    key = normalize_model_key(brand, model)
    for slug in slugs:
        write_cache(conn, key, slug, comps)
    conn.close()
    return key


# ---------------- 1. 市场比价搜索 ----------------

def test_sources_by_category_and_cache_key_rule():
    assert sources_for_category("book") == ["amazon_used", "bookoff"]
    assert sources_for_category("watch")[0] == "chrono24"
    assert sources_for_category("watch")[1:] == [
        "mercari", "yahoo", "rakuma", "paypay", "ebay"]
    assert sources_for_category("appliance") == [
        "mercari", "yahoo", "rakuma", "paypay", "ebay"]
    # 缓存键:品牌 + 型号归一化(小写、只留字母数字,空格/连字符不区分)
    assert normalize_model_key("Grand Seiko", "SBGX-263") == \
        normalize_model_key("grandseiko", "SBGX263") == "grandseikosbgx263"


def test_search_parallel_mock_only_mock_prices():
    def mercari(q):
        return [{"price": 100000, "source": "Mercari", "date": "2026-11-01",
                 "url": "https://example.jp/m1"},
                {"price": 110000, "date": "2026-11-02"}]
    def yahoo(q):
        return [{"price": 120000, "date": "2026-11-03"}]
    def rakuma(q):
        return []
    r = search_market_comps("Seiko", "SBGX261", "watch", providers={
        "mercari": mercari, "yahoo": yahoo, "rakuma": rakuma},
        source_slugs=["mercari", "yahoo", "rakuma"], timeout_total=10)
    prices = sorted(c["price"] for c in r["comps"])
    # 绝不编造:样本价格集合 exactly 等于 mock 给出的价格
    assert prices == [100000, 110000, 120000]
    assert r["statuses"] == {"mercari": "ok", "yahoo": "ok",
                             "rakuma": "无结果"}
    assert r["sample_count"] == 3 and r["from_cache"] is False
    assert r["comps"][0]["url"] == "https://example.jp/m1"
    # 样本可喂给 valuation_interval 得市场区间
    val = valuation_interval(r["comps"], "good")
    assert val["kind"] == "market" and val["is_market_price"] is True


def test_search_slow_source_hard_cap_returns_best_effort():
    def fast(q):
        return [{"price": 50000}, {"price": 60000}]
    def slow(q):
        time.sleep(5)
        return [{"price": 999999}]
    t0 = time.monotonic()
    r = search_market_comps("BrandX", "SlowModel1", "appliance", providers={
        "mercari": fast, "yahoo": slow},
        source_slugs=["mercari", "yahoo"], timeout_total=2,
        per_source_timeout=10)
    elapsed = time.monotonic() - t0
    assert elapsed < 4, elapsed  # 60 秒是截止线:2 秒上限内即返回,不等慢源
    assert r["timed_out"] is True
    assert sorted(c["price"] for c in r["comps"]) == [50000, 60000]
    assert 999999 not in [c["price"] for c in r["comps"]]
    assert r["statuses"]["yahoo"] == "超时"
    assert "60 秒内获 2 个样本" in r["search_note"]


def test_search_early_exit_at_ten_and_background_continues():
    def five(q):
        return [{"price": p} for p in (10000, 11000, 12000, 13000, 14000)]
    def slow(q):
        time.sleep(5)
        return [{"price": 777777}]
    t0 = time.monotonic()
    r = search_market_comps("BrandX", "EarlyModel1", "appliance", providers={
        "mercari": five, "yahoo": five, "rakuma": slow},
        source_slugs=["mercari", "yahoo", "rakuma"], timeout_total=30)
    elapsed = time.monotonic() - t0
    assert elapsed < 3, elapsed
    assert r["sample_count"] == 10  # 8~10 样本提前结束,取上限 10
    assert r["statuses"]["rakuma"] == "后台继续"


def test_search_per_source_timeout_label_and_unreachable_and_no_result():
    def slow(q):
        time.sleep(3)
        return [{"price": 111111}]
    def broken(q):
        raise RuntimeError("boom")
    def empty(q):
        return []
    t0 = time.monotonic()
    r = search_market_comps("BrandX", "TimeoutModel1", "appliance", providers={
        "mercari": slow, "yahoo": broken, "rakuma": empty},
        source_slugs=["mercari", "yahoo", "rakuma"], timeout_total=10,
        per_source_timeout=1)
    elapsed = time.monotonic() - t0
    assert elapsed < 6, elapsed
    assert r["statuses"]["mercari"] == "超时"
    assert r["statuses"]["yahoo"] == "不可达"
    assert r["statuses"]["rakuma"] == "无结果"
    assert r["comps"] == []  # 超时源的样本不计入前台结果


def test_search_mock_transport_snippet_only():
    import httpx

    def handler(request):
        url = str(request.url)
        if "mercari" in url:
            return httpx.Response(200, text="<html>¥120,000 … ¥150,000</html>")
        return httpx.Response(403, text="blocked")
    transport = httpx.MockTransport(handler)
    r = search_market_comps("Seiko", "TransModel1", "watch",
                            transport=transport,
                            source_slugs=["mercari", "yahoo"],
                            timeout_total=10)
    assert sorted(c["price"] for c in r["comps"]) == [120000, 150000]
    assert r["statuses"]["mercari"] == "ok"
    assert r["statuses"]["yahoo"] == "不可达"  # 被挡按不可达标注,不编造


def test_search_cache_hit_and_expiry():
    called = []
    def provider(q):
        called.append(q)
        return [{"price": 424242}]
    seed_cache("CacheBrand", "CacheModel1", ["mercari"],
               [{"price": 88000, "source": "Mercari", "date": "2026-11-01"}])
    conn = d.connect()
    try:
        r = search_market_comps("CacheBrand", "CacheModel1", "appliance",
                                conn=conn, providers={"mercari": provider},
                                source_slugs=["mercari"], timeout_total=5)
    finally:
        conn.close()
    assert r["from_cache"] is True
    assert [c["price"] for c in r["comps"]] == [88000]
    assert called == []  # 缓存命中不调用 provider、不联网
    assert r["statuses"] == {"mercari": "来自缓存"}
    # 24 小时过期:把 fetched_at 改旧,再次搜索必须重新抓取
    dbexec("UPDATE comp_cache SET fetched_at='2020-01-01T00:00:00+09:00' "
           "WHERE model_key=?", (normalize_model_key("CacheBrand",
                                                     "CacheModel1"),))
    conn = d.connect()
    try:
        r2 = search_market_comps("CacheBrand", "CacheModel1", "appliance",
                                 conn=conn, providers={"mercari": provider},
                                 source_slugs=["mercari"], timeout_total=5)
    finally:
        conn.close()
    assert r2["from_cache"] is False and called != []
    assert [c["price"] for c in r2["comps"]] == [424242]


def test_search_background_continues_writes_cache():
    def slow(q):
        time.sleep(1.5)
        return [{"price": 313131}]
    r = search_market_comps("BrandX", "BgModel1", "appliance",
                            providers={"mercari": slow},
                            source_slugs=["mercari"], timeout_total=0.5,
                            per_source_timeout=10)
    assert r["timed_out"] is True and r["comps"] == []
    # 后台续跑:慢源跑完后结果写入缓存,供下次查询使用
    key = normalize_model_key("BrandX", "BgModel1")
    found = None
    for _ in range(50):
        found = read_cache(d.connect(), key)
        if found.get("mercari"):
            break
        time.sleep(0.1)
    assert found and [c["price"] for c in found["mercari"]] == [313131]


# ---------------- 2. 行情双榜 ----------------

def _insert_listing_with_orders(seller_id, buyer_id, cat_slug, title, amounts):
    cat_id = dbval("SELECT id FROM categories WHERE slug=?", (cat_slug,))
    conn = d.connect()
    cur = conn.execute(
        "INSERT INTO listings(seller_id,category_id,title_ja,title_zh,price,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (seller_id, cat_id, title, title, amounts[-1],
         "2026-10-01T00:00:00+09:00", "2026-10-01T00:00:00+09:00"))
    lid = cur.lastrowid
    for i, amt in enumerate(amounts):
        conn.execute(
            "INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,"
            "commission,total,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (buyer_id, seller_id, lid, amt, 0, amt, "completed",
             f"2026-10-0{i + 1}T00:00:00+09:00",
             f"2026-10-0{i + 1}T00:00:00+09:00"))
    conn.commit()
    conn.close()
    return lid


def test_dual_board_same_screen_per_listing_not_category():
    seller = reg(client(), "s3m1@test.jp", "卖家")
    buyer = reg(client(), "s3m2@test.jp", "买家")
    sid, bid = user_id("s3m1@test.jp"), user_id("s3m2@test.jp")
    _insert_listing_with_orders(sid, bid, "appliance", "涨价微波炉",
                                [10000, 12000])   # +20%,同一品类
    _insert_listing_with_orders(sid, bid, "appliance", "跌价微波炉",
                                [20000, 15000])   # -25%,同一品类
    _insert_listing_with_orders(sid, bid, "appliance", "仅一单商品", [9000])
    moves = listing_price_moves(d.connect())
    assert moves["up_count"] == 1 and moves["down_count"] == 1
    assert moves["top_gainer"]["title_zh"] == "涨价微波炉"
    assert moves["top_gainer"]["pct"] == 20.0
    assert moves["top_loser"]["title_zh"] == "跌价微波炉"
    assert moves["top_loser"]["pct"] == -25.0
    assert moves["insufficient"] == 1  # 仅一单的商品排除、不编造
    html = seller.get("/market").text
    assert "上涨 1 件" in html and "下跌 1 件" in html
    assert "▲" in html and "▼" in html
    assert "最高涨幅" in html and "最高跌幅" in html
    assert "涨价微波炉" in html and "跌价微波炉" in html
    assert "vs 首次成交价" in html
    assert "样本量 2 笔" in html
    assert "未列入涨跌榜" in html
    # 依据标注:平台真实订单统计,且与估价数据区分
    assert "平台真实订单统计" in html


# ---------------- 3. AI 任务 ----------------

def test_job_dispatch_poll_done_and_owner_only():
    c = reg(client(), "s3j1@test.jp")
    did = upload_draft(c)
    r = c.post("/ai-jobs", data={"kind": "oneclick_recognize",
                                 "draft_id": str(did)})
    assert r.status_code == 200, r.status_code
    job = r.json()
    assert job["status"] == "queued" and job["poll_url"] == f"/ai-jobs/{job['job_id']}"
    done = poll_job(c, job["job_id"])
    assert done["status"] == "done"
    assert done["result"]["draft_id"] == did
    assert done["result"]["category_slug"] == "watch"
    assert dbval("SELECT status FROM oneclick_drafts WHERE id=?",
                 (did,)) == "recognized"
    # 他人任务 403;运营可见(改角色后可查)
    other = reg(client(), "s3j2@test.jp", "路人")
    assert other.get(f"/ai-jobs/{job['job_id']}").status_code == 403
    dbexec("UPDATE users SET role='operator' WHERE email=?", ("s3j2@test.jp",))
    assert other.get(f"/ai-jobs/{job['job_id']}").status_code == 200
    assert c.get("/ai-jobs/999999").status_code == 404


def test_job_failure_unknown_kind():
    c = reg(client(), "s3j3@test.jp")
    r = c.post("/ai-jobs", data={"kind": "nope_kind"})
    jid = r.json()["job_id"]
    done = poll_job(c, jid)
    assert done["status"] == "failed"
    assert "unknown kind" in done["result"]["error"]
    # 未登录派发 401
    anon = client()
    assert anon.post("/ai-jobs", data={"kind": "market_search"}).status_code == 401


def test_job_valuation_with_cached_market_comps_auto_fills_draft():
    c = reg(client(), "s3j4@test.jp")
    did = upload_draft(c)
    assert c.post(f"/oneclick/{did}/recognize").status_code == 200
    # 型号确认 + 全源缓存样本(6 个手表源,各 2 个样本)
    seed_cache("Seiko", "SBGX263", sources_for_category("watch"),
               [{"price": 200000, "source": "Mercari", "date": "2026-11-01"},
                {"price": 240000, "source": "Mercari", "date": "2026-11-02"}])
    assert c.post(f"/oneclick/{did}/model",
                  data={"brand": "Seiko", "model": "SBGX263"}).status_code == 200
    r = c.post("/ai-jobs", data={"kind": "oneclick_valuation",
                                 "draft_id": str(did)})
    done = poll_job(c, r.json()["job_id"])
    assert done["status"] == "done"
    assert done["result"]["valuation_kind"] == "market"
    assert done["result"]["from_cache"] is True
    val = json.loads(dbval("SELECT valuation_json FROM oneclick_drafts "
                           "WHERE id=?", (did,)))
    assert val["kind"] == "market" and val["is_market_price"] is True
    # 区间取样本偏保守低位:前 10 个样本(5×200000 + 5×240000),
    # low=25% 分位 200000,high=中位数 220000,中位数自动填入草稿
    assert val["low"] == 200000 and val["high"] == 220000
    assert val["suggested_price"] == 220000
    dr = json.loads(dbval("SELECT draft_json FROM oneclick_drafts "
                          "WHERE id=?", (did,)))
    assert dr["suggested_price"] == 220000 and dr["price_source"] == "market"
    page = c.get(f"/oneclick/{did}").text
    assert 'value="220000"' in page
    assert "Mercari" in page and "来自缓存" in page


def test_job_valuation_unconfirmed_honest_no_quote():
    c = reg(client(), "s3j5@test.jp")
    did = upload_draft(c)
    assert c.post(f"/oneclick/{did}/recognize").status_code == 200
    r = c.post("/ai-jobs", data={"kind": "oneclick_valuation",
                                 "draft_id": str(did)})
    done = poll_job(c, r.json()["job_id"])
    assert done["status"] == "done"
    assert done["result"]["valuation_kind"] == "model_unconfirmed"
    val = json.loads(dbval("SELECT valuation_json FROM oneclick_drafts "
                           "WHERE id=?", (did,)))
    assert val["kind"] == "model_unconfirmed" and val["low"] is None


# ---------------- 4. /ai-assist 平台参考收口 ----------------

def test_ai_assist_labels_platform_reference_not_market_price():
    seller = reg(client(), "s3a1@test.jp", "卖家")
    publish(seller, price=6000, category="appliance", title_zh="二手微波炉")
    r = seller.post("/ai-assist",
                    data={"name": "電子レンジ", "text": "微波炉",
                          "condition": "good", "price_hint": ""},
                    follow_redirects=False)
    assert r.status_code == 303
    note = unquote(r.headers["location"])
    assert "平台订单参考" in note
    assert "不是市场价" in note
    assert "基于平台在售挂牌价" in note
    # 页面同样展示平台口径(跟随重定向后)
    page = seller.post("/ai-assist",
                       data={"name": "電子レンジ", "text": "微波炉",
                             "condition": "good", "price_hint": ""}).text
    assert "平台订单参考" in page and "不是市场价" in page
    # Agent 侧同样收口:定价建议注明平台订单参考,不是市场价
    conn = d.connect()
    listing = conn.execute("SELECT * FROM listings LIMIT 1").fetchone()
    conn.close()
    sugg = pricing_agent(d.connect(), listing)
    assert "平台订单参考" in sugg["note"] and "不是市场价" in sugg["note"]


# ---------------- 5. 所有权与自购 ----------------

def _order_via_route(buyer, lid, key="s3-pay-1"):
    assert buyer.post(f"/listings/{lid}/buy").status_code == 200
    oid = dbval("SELECT MAX(id) FROM orders")
    assert buyer.post(f"/orders/{oid}/pay",
                      data={"idempotency_key": key}).status_code == 200
    return oid


def test_non_owner_order_and_photo_ops_forbidden():
    seller = reg(client(), "s3o1@test.jp", "卖家")
    buyer = reg(client(), "s3o2@test.jp", "买家")
    stranger = reg(client(), "s3o3@test.jp", "路人")
    lid = publish(seller, price=6000)
    oid = _order_via_route(buyer, lid)
    # 陌生人订单操作一律 403,卖家(非买家非运营)支付也 403
    for who in (stranger, seller):
        assert who.post(f"/orders/{oid}/pay",
                        data={"idempotency_key": "x"}).status_code == 403
    assert stranger.post(f"/orders/{oid}/complete").status_code == 403
    assert stranger.post(f"/orders/{oid}/cancel").status_code == 403
    assert stranger.post(f"/orders/{oid}/review",
                         data={"rating": "5"}).status_code == 403
    assert stranger.post(f"/orders/{oid}/refund",
                         data={"reason": "坏了"}).status_code == 403
    assert dbval("SELECT status FROM orders WHERE id=?", (oid,)) == "paid"
    # 陌生人照片管理 403(设封面/删除/替换),草稿照片删除 403
    rows = dbrow("SELECT id FROM images WHERE listing_id=?", (lid,))
    assert stranger.post(f"/listings/{lid}/photos/{rows[0]}/cover").status_code == 403
    assert stranger.post(f"/listings/{lid}/photos/{rows[0]}/delete").status_code == 403
    assert stranger.post(f"/listings/{lid}/photos/{rows[0]}/replace",
                         files={"photo": ("n.jpg", b"bytes", "image/jpeg")}
                         ).status_code == 403
    did = upload_draft(seller)
    assert stranger.post(f"/oneclick/{did}/photos/0/delete").status_code == 403
    assert stranger.get(f"/oneclick/{did}").status_code == 403


def test_offer_ownership_matrix():
    seller = reg(client(), "s3f1@test.jp", "卖家")
    buyer = reg(client(), "s3f2@test.jp", "买家")
    other = reg(client(), "s3f3@test.jp", "路人")
    lid = publish(seller, price=6000)
    assert buyer.post(f"/listings/{lid}/offer",
                      data={"amount": "5000"}).status_code == 200
    oid = dbval("SELECT MAX(id) FROM offers")
    assert other.post(f"/offers/{oid}/accept").status_code == 403
    assert other.post(f"/offers/{oid}/reject").status_code == 403
    assert other.post(f"/offers/{oid}/counter",
                      data={"counter_amount": "5500"}).status_code == 403
    assert seller.post(f"/offers/{oid}/accept-counter").status_code == 403
    assert dbval("SELECT status FROM offers WHERE id=?", (oid,)) == "pending"
    # 卖家还价、买家接受还价的正常路径仍可用
    assert seller.post(f"/offers/{oid}/counter",
                       data={"counter_amount": "5500"}).status_code == 200
    assert buyer.post(f"/offers/{oid}/accept-counter").status_code == 200


def test_self_purchase_and_self_bid_and_self_deposit_rejected():
    seller = reg(client(), "s3s1@test.jp", "卖家")
    buyer = reg(client(), "s3s2@test.jp", "买家")
    lid = publish(seller, price=6000)
    assert dbval("SELECT COUNT(*) FROM orders") == 0
    seller.post(f"/listings/{lid}/buy")
    assert dbval("SELECT COUNT(*) FROM orders") == 0  # 自购拒绝
    seller.post(f"/listings/{lid}/offer", data={"amount": "5000"})
    assert dbval("SELECT COUNT(*) FROM offers") == 0  # 自己不能议价
    # 拍卖:卖家出价/一口价/保证金均拒绝,买家出价成功作对照
    r = seller.post(f"/listings/{lid}/auction", data={
        "start_price": "1000", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "9000", "ends_at": "2030-01-01T00:00:00+09:00",
        "deposit_required": "1", "deposit_amount": "500"})
    assert r.status_code == 200
    aid = dbval("SELECT MAX(id) FROM auctions")
    seller.post(f"/auctions/{aid}/bid", data={"amount": "1500"})
    assert dbval("SELECT COUNT(*) FROM bids") == 0
    seller.post(f"/auctions/{aid}/buy-now")
    assert dbval("SELECT COUNT(*) FROM orders") == 0
    seller.post(f"/auctions/{aid}/deposit")
    assert dbval("SELECT COUNT(*) FROM deposits") == 0  # 卖家不得自交保证金
    # 对照:买家先交保证金(本拍卖要求保证金)再出价,正常成功
    assert buyer.post(f"/auctions/{aid}/deposit").status_code == 200
    assert dbval("SELECT COUNT(*) FROM deposits") == 1
    assert buyer.post(f"/auctions/{aid}/bid",
                      data={"amount": "1500"}).status_code == 200
    assert dbval("SELECT COUNT(*) FROM bids") == 1


def test_buyback_and_service_and_delivery_ownership_spot_checks():
    seller = reg(client(), "s3b1@test.jp", "卖家")
    other = reg(client(), "s3b2@test.jp", "路人")
    lid = publish(seller, price=6000)
    # 他人不能替卖家提交买断
    assert other.post("/buyback/new",
                      data={"listing_id": str(lid)}).status_code == 403
    assert seller.post("/buyback/new",
                       data={"listing_id": str(lid)}).status_code == 200
    bid = dbval("SELECT MAX(id) FROM buybacks")
    assert other.post(f"/buyback/{bid}/accept").status_code == 403
    assert other.get(f"/buyback/{bid}").status_code == 403
    # 服务单:他人查看 403,他人取消 403
    r = seller.post("/services/new", data={
        "kind": "cleaning_home", "hours": "2", "qty": "1", "note": ""})
    assert r.status_code == 200
    sid = dbval("SELECT MAX(id) FROM service_orders")
    assert other.get(f"/services/{sid}").status_code == 403
    assert other.post(f"/services/{sid}/cancel").status_code == 403
    assert dbval("SELECT status FROM service_orders WHERE id=?",
                 (sid,)) == "requested"
