"""第二/三阶段测试:拍卖、评价、配送、服务、退款争议、高价值审核、
行情真实数据、Agent、利润分析、新功能权限。全部本地运行,无外部调用。
"""
import os
import tempfile
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TOKYO = ZoneInfo("Asia/Tokyo")
except Exception:
    from datetime import timezone
    TOKYO = timezone(timedelta(hours=9))

if "YUNO_DB_PATH" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="yuno_test23_")
    os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
    os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.security import hash_password


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


def make_admin(email="admin@yuno.local"):
    conn = d.connect()
    salt, h = hash_password("TestAdmin123!")
    conn.execute("INSERT INTO users(email,pw_hash,salt,display_name,role,"
                 "created_at) VALUES(?,?,?,?,?,?)",
                 (email, h, salt, "管理员", "admin", "2026-01-01T00:00:00+09:00"))
    conn.commit()
    conn.close()
    c = client()
    r = c.post("/login", data={"email": email, "password": "TestAdmin123!"})
    assert r.status_code == 200
    return c


def user_id(email):
    conn = d.connect()
    uid = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]
    conn.close()
    return uid


def publish(c, price=10000, category="appliance", title_zh="二手商品",
            size="M", weight="12"):
    r = c.post("/listings/new", data={
        "category_slug": category, "title_ja": "中古品", "title_zh": title_zh,
        "desc_ja": "", "desc_zh": "", "price": str(price),
        "condition_grade": "good", "region": "sakado",
        "size_class": size, "weight_kg": weight})
    assert r.status_code == 200, r.status_code
    conn = d.connect()
    lid = conn.execute("SELECT MAX(id) FROM listings").fetchone()[0]
    conn.close()
    return lid


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


def future(hours=2):
    return (datetime.now(TOKYO) + timedelta(hours=hours)).isoformat(timespec="seconds")


def create_auction(seller, lid, start=5000, reserve=0, inc=500,
                   buy_now=0, ends=None, deposit=0, dep_amt=0):
    r = seller.post(f"/listings/{lid}/auction", data={
        "start_price": str(start), "reserve_price": str(reserve),
        "min_increment": str(inc), "buy_now_price": str(buy_now),
        "ends_at": ends or future(2),
        "deposit_required": "1" if deposit else "",
        "deposit_amount": str(dep_amt)})
    assert r.status_code == 200, r.status_code
    return dbrow("SELECT id FROM auctions ORDER BY id DESC LIMIT 1")[0]


def set_auction_past(aid):
    conn = d.connect()
    conn.execute("UPDATE auctions SET ends_at='2020-01-01T00:00:00+09:00' "
                 "WHERE id=?", (aid,))
    conn.commit()
    conn.close()


def complete_order(buyer, lid, key="pay-1"):
    buyer.post(f"/listings/{lid}/buy")
    oid = dbrow("SELECT id FROM orders ORDER BY id DESC LIMIT 1")[0]
    buyer.post(f"/orders/{oid}/pay", data={"idempotency_key": key})
    buyer.post(f"/orders/{oid}/complete")
    assert dbrow("SELECT status FROM orders WHERE id=?", (oid,))[0] == "completed"
    return oid


def test_auction_sold_flow_with_reserve_and_order():
    seller = reg(client(), "as@test.jp", "卖家")
    lid = publish(seller, price=10000)
    aid = create_auction(seller, lid, start=5000, reserve=6000, inc=500)
    b1 = reg(client(), "ab1@test.jp", "买家1")
    b2 = reg(client(), "ab2@test.jp", "买家2")
    assert b1.post(f"/auctions/{aid}/bid", data={"amount": "6000"}).status_code == 200
    assert b2.post(f"/auctions/{aid}/bid", data={"amount": "7000"}).status_code == 200
    # 代理逻辑:最高7000,次高6000 -> 当前价 6500
    assert dbrow("SELECT COUNT(*) FROM bids WHERE auction_id=?", (aid,))[0] == 2
    set_auction_past(aid)
    admin = make_admin()
    assert admin.post(f"/auctions/{aid}/settle").status_code == 200
    assert dbrow("SELECT status FROM auctions WHERE id=?", (aid,))[0] == "ended_sold"
    order = dbrow("SELECT goods_amount,commission,total,status FROM orders "
                  "ORDER BY id DESC LIMIT 1")
    assert tuple(order) == (6500, 650, 6700, "pending_payment")
    oid = dbrow("SELECT id FROM orders ORDER BY id DESC LIMIT 1")[0]
    b2.post(f"/orders/{oid}/pay", data={"idempotency_key": "auc-pay-1"})
    intent = dbrow("SELECT provider,seller_receivable,commission_amount FROM "
                   "payment_intents WHERE order_id=?", (oid,))
    assert tuple(intent) == ("mock", 5850, 650)


def test_auction_unsold_below_reserve_and_listing_stays_active():
    seller = reg(client(), "au@test.jp", "卖家")
    lid = publish(seller, price=10000)
    aid = create_auction(seller, lid, start=5000, reserve=8000, inc=500)
    b1 = reg(client(), "au1@test.jp", "买家")
    b1.post(f"/auctions/{aid}/bid", data={"amount": "6000"})
    set_auction_past(aid)
    admin = make_admin()
    admin.post(f"/auctions/{aid}/settle")
    assert dbrow("SELECT status FROM auctions WHERE id=?", (aid,))[0] == "ended_unsold"
    assert dbrow("SELECT status FROM listings WHERE id=?", (lid,))[0] == "active"
    assert dbrow("SELECT COUNT(*) FROM orders")[0] == 0


def test_proxy_bid_and_antisnipe_extension():
    seller = reg(client(), "ap@test.jp", "卖家")
    lid = publish(seller, price=20000)
    ends = (datetime.now(TOKYO) + timedelta(seconds=120)).isoformat(timespec="seconds")
    aid = create_auction(seller, lid, start=5000, reserve=0, inc=500, ends=ends)
    b1 = reg(client(), "ap1@test.jp", "买家1")
    b2 = reg(client(), "ap2@test.jp", "买家2")
    b1.post(f"/auctions/{aid}/bid", data={"amount": "6000", "proxy_max": "10000"})
    b2.post(f"/auctions/{aid}/bid", data={"amount": "7000"})
    # 结束前120秒内出价 -> 结束时间延长300秒
    from app.auctions import compute_price
    conn = d.connect()
    auc = conn.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
    bids = conn.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id",
                        (aid,)).fetchall()
    price, leader = compute_price(auc, bids)
    new_ends = conn.execute("SELECT ends_at FROM auctions WHERE id=?",
                            (aid,)).fetchone()[0]
    conn.close()
    assert price == 7500 and leader == user_id("ap1@test.jp")
    assert new_ends != ends
    assert b1.get(f"/auctions/{aid}").status_code == 200


def test_deposit_required_and_buy_now():
    seller = reg(client(), "ad@test.jp", "卖家")
    lid = publish(seller, price=20000)
    aid = create_auction(seller, lid, start=5000, deposit=1, dep_amt=1000)
    b1 = reg(client(), "ad1@test.jp", "买家")
    b1.post(f"/auctions/{aid}/bid", data={"amount": "6000"})
    assert dbrow("SELECT COUNT(*) FROM bids WHERE auction_id=?", (aid,))[0] == 0
    b1.post(f"/auctions/{aid}/deposit")
    assert dbrow("SELECT status FROM deposits WHERE auction_id=?",
                 (aid,))[0] == "held"
    b1.post(f"/auctions/{aid}/bid", data={"amount": "6000"})
    assert dbrow("SELECT COUNT(*) FROM bids WHERE auction_id=?", (aid,))[0] == 1
    lid2 = publish(seller, price=15000)
    aid2 = create_auction(seller, lid2, start=5000, buy_now=12000)
    b1.post(f"/auctions/{aid2}/buy-now")
    assert dbrow("SELECT status FROM auctions WHERE id=?", (aid2,))[0] == "ended_sold"
    assert dbrow("SELECT goods_amount FROM orders ORDER BY id DESC LIMIT 1")[0] == 12000


def test_reviews_and_reputation():
    seller = reg(client(), "rv@test.jp", "卖家")
    lid = publish(seller, price=6000)
    buyer = reg(client(), "rvb@test.jp", "买家")
    oid = complete_order(buyer, lid, key="rv-pay")
    assert buyer.post(f"/orders/{oid}/review",
                      data={"rating": "5", "comment": "很好"}).status_code == 200
    assert seller.post(f"/orders/{oid}/review",
                       data={"rating": "4", "comment": "爽快"}).status_code == 200
    buyer.post(f"/orders/{oid}/review", data={"rating": "5"})
    assert dbrow("SELECT COUNT(*) FROM reviews WHERE order_id=?", (oid,))[0] == 2
    sid = user_id("rv@test.jp")
    r = seller.get(f"/users/{sid}")
    assert r.status_code == 200 and "5.0" in r.text


def test_delivery_full_flow():
    seller = reg(client(), "dl@test.jp", "卖家")
    lid = publish(seller, price=6000)
    buyer = reg(client(), "dlb@test.jp", "买家")
    oid = complete_order(buyer, lid, key="dl-pay")
    r = buyer.post(f"/orders/{oid}/delivery-request",
                   data={"kind": "buyer_delivery", "scheduled_at": "2026-11-12 10:00"})
    assert r.status_code == 200
    did = dbrow("SELECT id FROM deliveries ORDER BY id DESC LIMIT 1")[0]
    admin = make_admin()
    courier = reg(client(), "courier@test.jp", "配送员")
    cid = user_id("courier@test.jp")
    admin.post(f"/admin/users/{cid}/role", data={"role": "courier"})
    assert courier.post(f"/deliveries/{did}/assign").status_code == 200
    assert courier.post(f"/deliveries/{did}/pickup", data={}).status_code == 200
    assert courier.post(f"/deliveries/{did}/deliver", data={}).status_code == 200
    assert buyer.post(f"/deliveries/{did}/confirm").status_code == 200
    assert dbrow("SELECT status FROM deliveries WHERE id=?", (did,))[0] == "confirmed"


def test_service_order_and_combined_settlement():
    admin = make_admin()
    user = reg(client(), "sv@test.jp", "用户")
    r = user.post("/services/new", data={"kind": "cleaning_home", "hours": "2",
                                         "qty": "1", "note": "打扫"})
    assert r.status_code == 200
    sid = dbrow("SELECT id,amount FROM service_orders ORDER BY id DESC LIMIT 1")
    assert sid[1] == 4000
    assert admin.post(f"/services/{sid[0]}/confirm").status_code == 200
    assert admin.post(f"/services/{sid[0]}/start").status_code == 200
    assert admin.post(f"/services/{sid[0]}/complete").status_code == 200
    assert dbrow("SELECT status FROM service_orders WHERE id=?", (sid[0],))[0] == "completed"
    # 与买断同笔结算:买断报价1000,服务4000 -> 净付 -3000(分项列示)
    seller = reg(client(), "svs@test.jp", "卖家")
    lid = publish(seller, price=10000)
    seller.post("/buyback/new", data={"listing_id": str(lid)})
    bid = dbrow("SELECT id FROM buybacks ORDER BY id DESC LIMIT 1")[0]
    admin.post(f"/buyback/{bid}/review")
    admin.post(f"/buyback/{bid}/quote", data={"quote": "1000"})
    seller.post("/services/new", data={"kind": "cleaning_item", "hours": "1",
                                       "qty": "1", "buyback_id": str(bid)})
    sid2 = dbrow("SELECT id FROM service_orders ORDER BY id DESC LIMIT 1")[0]
    r = seller.get(f"/services/{sid2}")
    assert "同一笔结算" in r.text and "净付" in r.text


def test_refund_and_dispute_flow_with_audit():
    seller = reg(client(), "rf@test.jp", "卖家")
    lid = publish(seller, price=6000)
    buyer = reg(client(), "rfb@test.jp", "买家")
    oid = complete_order(buyer, lid, key="rf-pay")
    r = buyer.post(f"/orders/{oid}/refund",
                   data={"reason": "商品损坏与描述不符", "evidence": "照片3张"})
    assert r.status_code == 200
    rid = dbrow("SELECT id FROM refunds ORDER BY id DESC LIMIT 1")[0]
    admin = make_admin()
    assert admin.post(f"/refunds/{rid}/decide",
                      data={"decision": "approved",
                            "decision_note": "证据充分,批准"}).status_code == 200
    assert dbrow("SELECT status FROM refunds WHERE id=?", (rid,))[0] == "decided"
    assert dbrow("SELECT status FROM orders WHERE id=?", (oid,))[0] == "refunded"
    assert dbrow("SELECT COUNT(*) FROM audit_log WHERE action='refund_decide'")[0] == 1
    lid2 = publish(seller, price=6000)
    oid2 = complete_order(buyer, lid2, key="rf-pay2")
    buyer.post(f"/orders/{oid2}/dispute", data={"reason": "未收到货"})
    did = dbrow("SELECT id FROM disputes ORDER BY id DESC LIMIT 1")[0]
    assert admin.post(f"/disputes/{did}/decide",
                      data={"decision": "卖家补发", "note": "核查物流后裁决"}).status_code == 200
    assert dbrow("SELECT status FROM disputes WHERE id=?", (did,))[0] == "decided"
    assert dbrow("SELECT COUNT(*) FROM audit_log WHERE action='dispute_decide'")[0] == 1


def test_high_value_review_blocks_trade_until_approved():
    seller = reg(client(), "hv@test.jp", "卖家")
    lid = publish(seller, price=150000, category="watch", title_zh="二手劳力士")
    assert dbrow("SELECT appraisal_status FROM hv_reviews WHERE listing_id=?",
                 (lid,))[0] == "pending"
    buyer = reg(client(), "hvb@test.jp", "买家")
    buyer.post(f"/listings/{lid}/buy")
    assert dbrow("SELECT COUNT(*) FROM orders")[0] == 0
    admin = make_admin()
    hid = dbrow("SELECT id FROM hv_reviews WHERE listing_id=?", (lid,))[0]
    assert admin.post(f"/admin/high-value/{hid}/review",
                      data={"appraisal_status": "approved",
                            "identity_verified": "1",
                            "appraisal_note": "鉴定通过"}).status_code == 200
    buyer.post(f"/listings/{lid}/buy")
    assert dbrow("SELECT COUNT(*) FROM orders")[0] == 1


def test_market_uses_real_orders_only_and_sample_notes():
    c = reg(client(), "mk@test.jp", "用户")
    r = c.get("/market")
    assert r.status_code == 200 and "暂无真实成交样本" in r.text
    seller = reg(client(), "mks@test.jp", "卖家")
    lid = publish(seller, price=6000)
    buyer = reg(client(), "mkb@test.jp", "买家")
    complete_order(buyer, lid, key="mk-pay")
    # 演示订单不得计入行情
    lid2 = publish(seller, price=99999, category="book", title_zh="演示书")
    conn = d.connect()
    conn.execute("INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,"
                 "commission,delivery_fee,total,status,demo,created_at,updated_at)"
                 " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (user_id("mkb@test.jp"), user_id("mks@test.jp"), lid2, 99999,
                  0, 0, 99999, "completed", 1,
                  "2026-11-01T00:00:00+09:00", "2026-11-02T00:00:00+09:00"))
    conn.commit()
    conn.close()
    from app.market import category_stats, top_listings
    conn = d.connect()
    stats = {s["slug"]: s for s in category_stats(conn)}
    tops = top_listings(conn, 10)
    conn.close()
    assert stats["appliance"]["completed"] == 1
    assert stats["book"]["completed"] == 0
    assert all(t["id"] != lid2 or t["sold_n"] == 0 for t in tops)


def test_agents_anomaly_pricing_profit_and_support():
    seller = reg(client(), "ag@test.jp", "卖家")
    lid = publish(seller, price=50000)
    buyer = reg(client(), "agb@test.jp", "买家")
    conn = d.connect()
    for i in range(3):
        conn.execute("INSERT INTO orders(buyer_id,seller_id,listing_id,"
                     "goods_amount,commission,delivery_fee,total,status,"
                     "idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (user_id("agb@test.jp"), user_id("ag@test.jp"), lid, 50000,
                      5000, 200, 50200, "pending_payment", f"dup-{i}",
                      "2026-11-01T00:00:00+09:00", "2026-11-01T00:00:00+09:00"))
    old = "2026-09-01T00:00:00+09:00"
    conn.execute("INSERT INTO listings(seller_id,category_id,title_ja,title_zh,"
                 "price,condition_grade,region,size_class,weight_kg,status,"
                 "is_platform_owned,created_at,updated_at) VALUES(NULL,"
                 "(SELECT id FROM categories WHERE slug='appliance'),"
                 "'自营旧货','自营旧货',60000,'good','sakado','M',12,'active',1,?,?)",
                 (old, old))
    plat_lid = conn.execute("SELECT MAX(id) FROM listings").fetchone()[0]
    conn.execute("INSERT INTO inventory(listing_id,cost,status,created_at)"
                 " VALUES(?,?, 'in_stock', ?)", (plat_lid, 10000, old))
    conn.commit()
    conn.close()
    admin = make_admin()
    assert admin.post("/admin/agents/run-anomalies").status_code == 200
    assert dbrow("SELECT COUNT(*) FROM alerts WHERE kind='duplicate_pending_orders'")[0] >= 1
    assert admin.post("/admin/agents/run-pricing").status_code == 200
    sugg = dbrow("SELECT id,listing_id,suggested_price FROM price_suggestions "
                 "WHERE status='pending' ORDER BY id DESC LIMIT 1")
    assert sugg is not None
    assert admin.post(f"/admin/suggestions/{sugg[0]}/approve").status_code == 200
    assert dbrow("SELECT price FROM listings WHERE id=?", (sugg[1],))[0] == sugg[2]
    assert dbrow("SELECT COUNT(*) FROM audit_log WHERE action='price_change'")[0] == 1
    r = admin.get("/admin/profit")
    assert r.status_code == 200 and "经营利润" in r.text
    r = buyer.post("/support", data={"question": "运费怎么算?"})
    assert r.status_code == 200 and "150" in r.text


def test_new_feature_permissions():
    seller = reg(client(), "pm@test.jp", "卖家")
    lid = publish(seller, price=10000)
    aid = create_auction(seller, lid, start=5000)
    other = reg(client(), "pmo@test.jp", "路人")
    assert other.get("/admin/auctions").status_code == 403
    assert other.post(f"/auctions/{aid}/settle").status_code == 403
    assert other.post(f"/admin/suggestions/1/approve").status_code == 403
    buyer = reg(client(), "pmb@test.jp", "买家")
    oid = complete_order(buyer, lid, key="pm-pay")
    buyer.post(f"/orders/{oid}/delivery-request",
               data={"kind": "buyer_delivery", "scheduled_at": "2026-11-12 10:00"})
    did = dbrow("SELECT id FROM deliveries ORDER BY id DESC LIMIT 1")[0]
    assert other.post(f"/deliveries/{did}/assign").status_code == 403
    user = reg(client(), "pmu@test.jp", "用户")
    user.post("/services/new", data={"kind": "inspection", "hours": "1", "qty": "1"})
    sid = dbrow("SELECT id FROM service_orders ORDER BY id DESC LIMIT 1")[0]
    assert other.get(f"/services/{sid}").status_code == 403
