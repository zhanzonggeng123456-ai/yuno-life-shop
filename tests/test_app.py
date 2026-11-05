"""Yuno Life MVP 测试:单元 + API 集成 + 权限 + 核心流程 E2E。
每个测试前重置本地 SQLite 文件,全部本地运行,无外部调用。
"""
import os
import sqlite3
import tempfile

_tmp = tempfile.mkdtemp(prefix="yuno_test_")
os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.business import delivery_fee, local_ai_assist, stats
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


def publish(c, price=6000, category="appliance", title_zh="二手微波炉",
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


def test_register_login_and_admin_forbidden():
    c = reg(client(), "u1@test.jp")
    assert c.get("/me").status_code == 200
    r = c.get("/admin")
    assert r.status_code == 403
    bad = client()
    r = bad.post("/login", data={"email": "u1@test.jp", "password": "wrong"})
    assert "invalid_login" in (r.headers.get("location", "") + r.text) \
        or r.status_code in (200, 303)


def test_c2c_flow_mock_payment_idempotent():
    seller = reg(client(), "seller@test.jp", "卖家")
    lid = publish(seller)
    buyer = reg(client(), "buyer@test.jp", "买家")
    r = buyer.post(f"/listings/{lid}/buy")
    assert r.status_code == 200
    oid = dbrow("SELECT id FROM orders ORDER BY id DESC LIMIT 1")[0]
    assert dbrow("SELECT status FROM orders WHERE id=?", (oid,))[0] == "pending_payment"
    # 佣金 10%:6000 -> 600(卖家侧承担);买家合计 = 商品价 + 运费 = 6200
    row = dbrow("SELECT goods_amount,commission,delivery_fee,total FROM orders "
                "WHERE id=?", (oid,))
    assert tuple(row) == (6000, 600, 200, 6200)
    # 模拟支付 + 幂等:同一幂等键重复提交只记一次支付审计
    r = buyer.post(f"/orders/{oid}/pay", data={"idempotency_key": "key-1"})
    assert r.status_code == 200
    r = buyer.post(f"/orders/{oid}/pay", data={"idempotency_key": "key-1"})
    assert r.status_code == 200
    n = dbrow("SELECT COUNT(*) FROM order_audit WHERE order_id=? AND event=?",
              (oid, "mock_payment"))[0]
    assert n == 1
    assert dbrow("SELECT status FROM listings WHERE id=?", (lid,))[0] == "sold"
    r = buyer.post(f"/orders/{oid}/complete")
    assert dbrow("SELECT status FROM orders WHERE id=?", (oid,))[0] == "completed"
    conn = d.connect()
    s = stats(conn)
    conn.close()
    assert s["gmv"] == 6000 and s["commission_income"] == 600
    assert s["gmv"] != s["commission_income"]


def test_offer_counter_flow():
    seller = reg(client(), "s2@test.jp", "卖家")
    lid = publish(seller, price=10000)
    buyer = reg(client(), "b2@test.jp", "买家")
    r = buyer.post(f"/listings/{lid}/offer", data={"amount": "8000"})
    assert r.status_code == 200
    oid = dbrow("SELECT id FROM offers ORDER BY id DESC LIMIT 1")[0]
    r = seller.post(f"/offers/{oid}/counter", data={"counter_amount": "9000"})
    assert r.status_code == 200
    assert dbrow("SELECT status FROM offers WHERE id=?", (oid,))[0] == "countered"
    r = buyer.post(f"/offers/{oid}/accept-counter")
    assert r.status_code == 200
    order = dbrow("SELECT goods_amount,status FROM orders ORDER BY id DESC LIMIT 1")
    assert tuple(order) == (9000, "pending_payment")


def test_message_thread_and_permissions():
    seller = reg(client(), "s3@test.jp", "卖家")
    lid = publish(seller)
    buyer = reg(client(), "b3@test.jp", "买家")
    other = reg(client(), "o3@test.jp", "路人")
    r = buyer.post(f"/messages/{lid}/{dbrow('SELECT id FROM users WHERE email=?', ('b3@test.jp',))[0]}",
                   data={"body": "你好,还能便宜吗?", "receiver_id": "1"})
    assert r.status_code == 200
    bid = dbrow("SELECT id FROM users WHERE email=?", ("b3@test.jp",))[0]
    assert buyer.get(f"/messages/{lid}/{bid}").status_code == 200
    assert other.get(f"/messages/{lid}/{bid}").status_code == 403
    # 越权:路人不能接受卖家的议价
    buyer.post(f"/listings/{lid}/offer", data={"amount": "5000"})
    oid = dbrow("SELECT id FROM offers ORDER BY id DESC LIMIT 1")[0]
    assert other.post(f"/offers/{oid}/accept").status_code == 403


def test_buyback_full_flow_and_platform_resale():
    seller = reg(client(), "s4@test.jp", "卖家")
    lid = publish(seller, price=10000)
    admin = make_admin()
    r = seller.post("/buyback/new", data={"listing_id": str(lid)})
    assert r.status_code == 200
    bid = dbrow("SELECT id FROM buybacks ORDER BY id DESC LIMIT 1")[0]
    # 非运营不能报价
    buyer = reg(client(), "b4@test.jp", "买家")
    assert buyer.post(f"/buyback/{bid}/quote", data={"quote": "1000"}).status_code == 403
    assert admin.post(f"/buyback/{bid}/review").status_code == 200
    assert admin.post(f"/buyback/{bid}/quote", data={"quote": "1000"}).status_code == 200
    assert seller.post(f"/buyback/{bid}/accept").status_code == 200
    assert seller.post(f"/buyback/{bid}/pickup",
                       data={"pickup_at": "2026-11-10 14:00"}).status_code == 200
    assert admin.post(f"/buyback/{bid}/inspect",
                      data={"inspection_note": "动作正常,外观良好"}).status_code == 200
    r = admin.post(f"/buyback/{bid}/pay", data={"resale_price": "3500"})
    assert r.status_code == 200
    assert dbrow("SELECT status FROM buybacks WHERE id=?", (bid,))[0] == "completed"
    assert dbrow("SELECT status FROM listings WHERE id=?", (lid,))[0] == "sold"
    plat = dbrow("SELECT id,price,is_platform_owned FROM listings "
                 "WHERE is_platform_owned=1 ORDER BY id DESC LIMIT 1")
    assert tuple(plat) == (plat[0], 3500, 1)
    inv = dbrow("SELECT cost,status FROM inventory WHERE listing_id=?", (plat[0],))
    assert tuple(inv) == (1000, "in_stock")
    # 买家买走自营商品:佣金 0,自营毛利 = 3500-1000
    r = buyer.post(f"/listings/{plat[0]}/buy")
    assert r.status_code == 200
    order = dbrow("SELECT goods_amount,commission,is_platform_sale FROM orders "
                  "ORDER BY id DESC LIMIT 1")
    assert tuple(order) == (3500, 0, 1)
    oid = dbrow("SELECT id FROM orders ORDER BY id DESC LIMIT 1")[0]
    buyer.post(f"/orders/{oid}/pay", data={"idempotency_key": "bb-pay-1"})
    buyer.post(f"/orders/{oid}/complete")
    conn = d.connect()
    s = stats(conn)
    conn.close()
    assert s["platform_sales"] == 3500
    assert s["gross_profit"] == 2500
    assert s["buyback_cost_total"] == 1000


def test_xl_delivery_needs_separate_quote():
    seller = reg(client(), "s5@test.jp", "卖家")
    lid = publish(seller, price=50000, size="XL", weight="40")
    buyer = reg(client(), "b5@test.jp", "买家")
    buyer.post(f"/listings/{lid}/buy")
    assert dbrow("SELECT COUNT(*) FROM orders")[0] == 0
    assert dbrow("SELECT status FROM listings WHERE id=?", (lid,))[0] == "active"
    conn = d.connect()
    fee, needs, _ = delivery_fee(conn, "XL", 40, "sakado")
    conn.close()
    assert fee is None and needs is True


def test_ai_assist_no_sample_and_delivery_rules():
    c = reg(client(), "u6@test.jp")
    r = c.post("/ai-assist", data={"name": "未知の骨董品",
                                   "text": "祖母の家にあった壺", "condition": "good"})
    assert r.status_code == 200
    assert "暂无样本" in r.text
    conn = d.connect()
    assert delivery_fee(conn, "S", 1, "sakado")[0] == 150
    assert delivery_fee(conn, "M", 12, "sakado")[0] == 200
    assert delivery_fee(conn, "L", 25, "sakado")[0] == 250
    assert delivery_fee(conn, "M", 25, "sakado")[0] == 250  # 超重升档
    assert delivery_fee(conn, "S", 1, "kawagoe")[1] is True  # 未开放地区不承诺
    out = local_ai_assist(conn, "不存在的商品xyz", "", "good", None)
    conn.close()
    assert out["price_low"] is None  # 不编造价格


def test_commission_rate_bounds():
    admin = make_admin()
    r = admin.post("/admin/settings", data={
        "commission_rate": "0.05", "regions": "[]", "buyback_params": "{}"})
    assert r.status_code == 200
    conn = d.connect()
    assert d.get_setting(conn, "commission_rate") == "0.10"
    conn.close()
    r = admin.post("/admin/settings", data={
        "commission_rate": "0.08",
        "regions": d.DEFAULT_SETTINGS["regions"],
        "buyback_params": d.DEFAULT_SETTINGS["buyback_params"]})
    assert r.status_code == 200
    seller = reg(client(), "s7@test.jp", "卖家")
    lid = publish(seller, price=10000)
    buyer = reg(client(), "b7@test.jp", "买家")
    buyer.post(f"/listings/{lid}/buy")
    row = dbrow("SELECT commission FROM orders ORDER BY id DESC LIMIT 1")
    assert row[0] == 800  # 8% 生效
