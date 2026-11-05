"""第 1 阶段移植测试:底部 5 按钮、语言三档、服务最终三项、规则页、新表。"""
import json
import os
import tempfile

if "YUNO_DB_PATH" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="yuno_stage1_")
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


def reg(c, email, name="用户", pw="TestPass123!"):
    r = c.post("/register", data={"email": email, "display_name": name,
                                  "password": pw})
    assert r.status_code == 200, r.status_code
    return c


def make_admin(email="admin1@yuno.local"):
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


BOTTOM = [("/", "marketplace"), ("/market", "market"), ("/trade", "trade"),
          ("/me#orders", "orders"), ("/me", "my_page")]


def test_no_top_nav_and_bottom_five_buttons():
    r = client().get("/")
    assert r.status_code == 200
    assert "<nav" not in r.text
    assert "bottom-nav" in r.text
    for href, _ in BOTTOM:
        assert f'href="{href}"' in r.text, href
    # 原顶部入口有去处:页脚含服务/客服/规则,个人中心含交易入口
    assert 'href="/services"' in r.text
    assert 'href="/support"' in r.text
    assert 'href="/rules"' in r.text


def test_bottom_targets_anon_and_logged():
    anon = client()
    assert anon.get("/").status_code == 200
    assert anon.get("/market").status_code == 200
    assert anon.get("/trade").status_code == 200
    assert anon.get("/me").status_code == 401
    assert anon.get("/orders").status_code == 401
    user = reg(client(), "b1@test.jp")
    assert user.get("/").status_code == 200
    assert user.get("/market").status_code == 200
    assert user.get("/trade").status_code == 200
    assert user.get("/me").status_code == 200
    assert user.get("/me#orders").status_code == 200
    assert user.get("/orders").status_code == 200
    # 订单按钮锚点确实落在个人中心订单区
    assert 'id="orders"' in user.get("/me").text


def test_trade_panel_entries_and_staff_only_admin():
    anon = client()
    r = anon.get("/trade")
    assert r.status_code == 200
    for href in ("/listings/new", "/oneclick", "/auctions", "/services",
                 "/support", "/me/messages"):
        assert f'href="{href}"' in r.text, href
    assert 'href="/admin"' not in r.text
    user = reg(client(), "b2@test.jp")
    assert 'href="/admin"' not in user.get("/trade").text
    assert 'href="/admin"' not in user.get("/me").text
    admin = make_admin()
    assert 'href="/admin"' in admin.get("/trade").text
    assert 'href="/admin"' in admin.get("/me").text


def test_follow_system_language_mapping():
    cases = [("zh-CN", "市场"), ("zh", "市场"), ("ja", "マーケット"),
             ("en", "マーケット")]
    for header, expect in cases:
        r = client().get("/", headers={"Accept-Language": header})
        assert r.status_code == 200
        assert expect in r.text, (header, expect)
    # 缺失 Accept-Language -> 日语默认
    r = client().get("/", headers={"Accept-Language": ""})
    assert "マーケット" in r.text


def test_manual_choice_cookie_beats_accept_language():
    c = client()
    r = c.get("/?lang=zh")
    assert "yuno_lang=zh" in r.headers.get("set-cookie", "")
    r2 = c.get("/", headers={"Accept-Language": "ja"})
    assert "市场" in r2.text  # 手动中文优先于 Accept-Language 日语
    # 跟随系统:清除手动选择后重新跟随 Accept-Language
    r3 = c.get("/?lang=system", headers={"Accept-Language": "ja"})
    assert "yuno_lang" in r3.headers.get("set-cookie", "")
    assert "マーケット" in c.get("/", headers={"Accept-Language": "ja"}).text
    # cookie 手动值同样优先
    c2 = client()
    c2.cookies.set("yuno_lang", "zh")
    assert "市场" in c2.get("/", headers={"Accept-Language": "ja"}).text


def test_language_selector_only_three_options():
    r = client().get("/")
    assert "?lang=zh" in r.text and "?lang=ja" in r.text
    assert "?lang=system" in r.text
    assert "?lang=en" not in r.text


def test_services_catalog_only_final_trio():
    r = client().get("/services")
    assert r.status_code == 200
    for name in ("ハウスクリーニング", "小口運搬", "地域配送予約"):
        assert name in r.text, name
    for price in ("¥1,500", "¥500", "¥150"):
        assert price in r.text, price
    assert "2,000" not in r.text
    for removed in ("商品クリーニング", "商品検品", "撮影・出品代行",
                    "出張査定", "委託販売"):
        assert removed not in r.text, removed
    r_zh = client().get("/services?lang=zh")
    for name in ("家居清洁", "小件搬运", "本地配送预约"):
        assert name in r_zh.text, name
    assert "10kg" in r_zh.text


def test_services_old_db_data_cannot_bias_prices():
    conn = d.connect()
    d.set_setting(conn, "service_prices", json.dumps({
        "cleaning_home": {"name_ja": "x", "name_zh": "x", "unit": "hour",
                          "price": 2000},
        "cleaning_item": {"name_ja": "y", "name_zh": "y", "unit": "item",
                          "price": 1000},
        "inspection": {"name_ja": "z", "name_zh": "z", "unit": "item",
                       "price": 1500},
    }, ensure_ascii=False))
    conn.close()
    r = client().get("/services")
    assert "¥1,500" in r.text and "¥2,000" not in r.text
    user = reg(client(), "sv1@test.jp")
    r = user.post("/services/new", data={"kind": "cleaning_home", "hours": "1",
                                         "qty": "1"})
    assert r.status_code == 200
    conn = d.connect()
    row = conn.execute("SELECT unit_price,amount FROM service_orders "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row["unit_price"] == 1500 and row["amount"] == 1500


def test_services_removed_kinds_rejected_and_trio_priced():
    user = reg(client(), "sv2@test.jp")
    for kind in ("cleaning_item", "inspection", "photo_listing",
                 "appraisal_visit", "consignment", "bogus"):
        assert user.post("/services/new", data={"kind": kind, "hours": "1",
                                                "qty": "1"}).status_code == 400, kind
    cases = [("cleaning_home", "2", "1", 3000),
             ("transport_small", "1", "2", 1000),
             ("local_delivery", "1", "1", 150)]
    for kind, hours, qty, amount in cases:
        assert user.post("/services/new", data={"kind": kind, "hours": hours,
                                                "qty": qty}).status_code == 200
        conn = d.connect()
        row = conn.execute("SELECT amount FROM service_orders "
                           "ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["amount"] == amount, (kind, row["amount"])


def test_rules_pages_bilingual_and_tax_and_mock_notes():
    for path in ("/rules", "/terms", "/privacy", "/returns", "/prohibited"):
        for header in ("ja", "zh"):
            r = client().get(path, headers={"Accept-Language": header})
            assert r.status_code == 200, (path, header)
            assert "日本語" in r.text and "中文" in r.text
            assert ("税込" in r.text and "含税" in r.text), path
            assert ("シミュレーション" in r.text and "模拟" in r.text), path
    # 页脚与个人中心可点达规则页
    assert 'href="/rules"' in client().get("/").text
    user = reg(client(), "rl@test.jp")
    assert 'href="/rules"' in user.get("/me").text
    # 订单页同样有模拟标注
    assert "シミュレーション" in user.get("/orders").text or \
        "模拟" in user.get("/orders").text


def test_orders_list_visibility():
    seller = reg(client(), "o1@test.jp")
    buyer = reg(client(), "o2@test.jp")
    other = reg(client(), "o3@test.jp")
    conn = d.connect()
    conn.execute("INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,"
                 "commission,delivery_fee,total,status,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (2, 1, 1, 1000, 100, 200, 1200, "pending_payment",
                  "2026-01-01T00:00:00+09:00", "2026-01-01T00:00:00+09:00"))
    conn.commit()
    conn.close()
    # buyer id=2, seller id=1 (注册顺序);other 不应看到
    assert "订单 #1" in buyer.get("/orders").text
    assert "订单 #1" in seller.get("/orders").text
    assert "订单 #1" not in other.get("/orders").text
    admin = make_admin()
    assert "订单 #1" in admin.get("/orders").text


def test_stage1_new_tables_exist():
    conn = d.connect()
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    cols_ai = {r[1] for r in conn.execute("PRAGMA table_info(ai_jobs)").fetchall()}
    cols_cc = {r[1] for r in conn.execute("PRAGMA table_info(comp_cache)").fetchall()}
    conn.close()
    assert "ai_jobs" in names and "comp_cache" in names
    assert {"id", "user_id", "kind", "status", "payload_json", "result_json",
            "created_at", "updated_at"} <= cols_ai
    assert {"id", "model_key", "source", "comps_json", "fetched_at"} <= cols_cc
