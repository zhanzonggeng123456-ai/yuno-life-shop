"""商业级优化阶段测试:安全 / 数据完整 / 合规展示 / 体验 / 生产数据干净。
只用测试专用口令,不碰 seed.py,不恢复旧演示口令。"""
import os
import re
import tempfile

if "YUNO_DB_PATH" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="yuno_optimize_")
    os.environ["YUNO_DB_PATH"] = os.path.join(_tmp, "test.db")
    os.environ["YUNO_UPLOAD_DIR"] = os.path.join(_tmp, "up")

import pytest
from fastapi.testclient import TestClient

from app import db as d
from app.business import stats
from app.market import category_stats, profit_report
from app.security import check_rate_limit, hash_password, reset_rate_limits


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(d.DB_PATH):
        os.remove(d.DB_PATH)
    d.init_db()
    reset_rate_limits()
    yield


def client():
    import app.main as m
    return TestClient(m.app)


def reg(c, email, name="用户", pw="TestPass123!"):
    r = c.post("/register", data={"email": email, "display_name": name,
                                  "password": pw})
    assert r.status_code == 200, r.status_code
    return c


def make_user_with_role(email, role, pw="TestAdmin123!"):
    conn = d.connect()
    salt, h = hash_password(pw)
    conn.execute("INSERT INTO users(email,pw_hash,salt,display_name,role,"
                 "created_at) VALUES(?,?,?,?,?,?)",
                 (email, h, salt, "职员", role, "2026-01-01T00:00:00+09:00"))
    conn.commit()
    conn.close()
    c = client()
    r = c.post("/login", data={"email": email, "password": pw})
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


def publish(c, price=6000, category="appliance", title_zh="二手微波炉"):
    r = c.post("/listings/new", data={
        "category_slug": category, "title_ja": "中古品", "title_zh": title_zh,
        "desc_ja": "", "desc_zh": "", "price": str(price),
        "condition_grade": "good", "region": "sakado",
        "size_class": "M", "weight_kg": "0"})
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM listings")


def buy_order(buyer, lid):
    r = buyer.post(f"/listings/{lid}/buy")
    assert r.status_code == 200, r.status_code
    return dbval("SELECT MAX(id) FROM orders")


def pay_order(buyer, oid, key="opt-key-1"):
    r = buyer.post(f"/orders/{oid}/pay", data={"idempotency_key": key})
    assert r.status_code == 200, r.status_code
    return r


# ---------------- 1. 安全:角色与越权 ----------------

def test_register_ignores_role_param_and_defaults_to_user():
    c = client()
    r = c.post("/register", data={"email": "noreole@test.jp",
                                  "display_name": "普通用户",
                                  "password": "TestPass123!",
                                  "role": "admin"})
    assert r.status_code == 200
    assert dbval("SELECT role FROM users WHERE email=?",
                 ("noreole@test.jp",)) == "user"


def test_register_validation_rejects_bad_input():
    c = client()
    assert c.post("/register", data={"email": "not-an-email",
                                     "display_name": "x",
                                     "password": "TestPass123!"}).status_code == 400
    assert c.post("/register", data={"email": "ok@test.jp",
                                     "display_name": "x",
                                     "password": "short"}).status_code == 400
    assert c.post("/register", data={"email": "ok2@test.jp",
                                     "display_name": "x" * 51,
                                     "password": "TestPass123!"}).status_code == 400


def test_admin_cannot_change_own_role_and_unknown_user_404():
    admin = make_user_with_role("opt-admin@test.jp", "admin")
    aid = dbval("SELECT id FROM users WHERE email=?", ("opt-admin@test.jp",))
    assert admin.post(f"/admin/users/{aid}/role",
                      data={"role": "user"}).status_code == 403
    assert dbval("SELECT role FROM users WHERE id=?", (aid,)) == "admin"
    assert admin.post("/admin/users/999999/role",
                      data={"role": "user"}).status_code == 404


def test_operator_cannot_change_role_but_admin_can_and_audits():
    op = make_user_with_role("opt-op@test.jp", "operator")
    target = reg(client(), "opt-target@test.jp")
    tid = dbval("SELECT id FROM users WHERE email=?", ("opt-target@test.jp",))
    assert op.post(f"/admin/users/{tid}/role",
                   data={"role": "operator"}).status_code == 403
    admin = make_user_with_role("opt-admin2@test.jp", "admin")
    assert admin.post(f"/admin/users/{tid}/role",
                      data={"role": "operator"}).status_code == 200
    assert dbval("SELECT role FROM users WHERE id=?", (tid,)) == "operator"
    row = dbrow("SELECT * FROM audit_log WHERE action='role_change' "
                "AND target_id=?", (tid,))
    assert row is not None and "user->operator" in row["note"]


def test_admin_ops_write_audit_log():
    admin = make_user_with_role("opt-admin3@test.jp", "admin")
    seller = reg(client(), "opt-seller@test.jp")
    lid = publish(seller)
    assert admin.post(f"/admin/listings/{lid}/toggle").status_code == 200
    assert dbrow("SELECT * FROM audit_log WHERE action='listing_toggle' "
                 "AND target_id=?", (lid,)) is not None
    assert admin.post("/admin/settings", data={
        "commission_rate": "0.09", "regions": "[]",
        "buyback_params": "{}"}).status_code == 200
    assert dbrow("SELECT * FROM audit_log WHERE action='settings_change'") is not None
    assert admin.post("/admin/expenses", data={
        "kind": "耗材", "amount": "100", "note": ""}).status_code == 200
    assert dbrow("SELECT * FROM audit_log WHERE action='expense_add'") is not None


def test_cross_user_order_and_service_and_message_forbidden():
    seller = reg(client(), "opt-s1@test.jp")
    buyer = reg(client(), "opt-b1@test.jp")
    stranger = reg(client(), "opt-str@test.jp")
    lid = publish(seller)
    oid = buy_order(buyer, lid)
    assert stranger.post(f"/orders/{oid}/complete").status_code == 403
    assert stranger.post(f"/orders/{oid}/cancel").status_code == 403
    assert stranger.post(f"/orders/{oid}/pay",
                         data={"idempotency_key": "x"}).status_code == 403
    assert stranger.post(f"/orders/{oid}/review",
                         data={"rating": "5"}).status_code == 403
    assert stranger.post(f"/orders/{oid}/refund",
                         data={"reason": "坏了"}).status_code == 403
    assert stranger.post(f"/orders/{oid}/dispute",
                         data={"reason": "纠纷"}).status_code == 403
    assert stranger.get(f"/orders/{oid}").status_code == 403
    # 消息收件人改参数:买家不得把消息发给无关第三方
    third = dbval("SELECT id FROM users WHERE email=?", ("opt-str@test.jp",))
    before = dbval("SELECT COUNT(*) FROM messages")
    assert buyer.post(f"/messages/{lid}/{dbval('SELECT id FROM users WHERE email=?', ('opt-b1@test.jp',))}",
                      data={"body": "hi", "receiver_id": str(third)}).status_code == 403
    assert dbval("SELECT COUNT(*) FROM messages") == before
    # 服务单他人取消被拒
    buyer.post("/services/new", data={"kind": "cleaning_home", "hours": "1",
                                      "qty": "1", "note": ""})
    sid = dbval("SELECT MAX(id) FROM service_orders")
    assert stranger.post(f"/services/{sid}/cancel").status_code == 403
    assert stranger.get(f"/services/{sid}").status_code == 403
    # 商品照片他人删除被拒
    assert stranger.post(f"/listings/{lid}/photos/999999/delete").status_code in (403, 404)


def test_offer_missing_id_returns_404_not_500():
    seller = reg(client(), "opt-s2@test.jp")
    assert seller.post("/offers/999999/accept").status_code == 404
    assert seller.post("/offers/999999/reject").status_code == 404
    assert seller.post("/offers/999999/counter",
                       data={"counter_amount": "100"}).status_code == 404
    assert seller.post("/offers/999999/accept-counter").status_code == 404


def test_origin_mismatch_rejected_and_same_host_allowed():
    c = client()
    r = c.post("/register", data={"email": "evil@test.jp",
                                  "display_name": "x",
                                  "password": "TestPass123!"},
               headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    r2 = c.post("/register", data={"email": "samehost@test.jp",
                                   "display_name": "x",
                                   "password": "TestPass123!"},
                headers={"Origin": "http://testserver"})
    assert r2.status_code == 200
    # 无 Origin 头的请求放行(全部旧测试均属此类)
    assert client().post("/register", data={
        "email": "noorigin@test.jp", "display_name": "x",
        "password": "TestPass123!"}).status_code == 200


def test_session_cookie_samesite_lax():
    c = client()
    r = c.post("/register", data={"email": "cookie@test.jp",
                                  "display_name": "x",
                                  "password": "TestPass123!"},
               follow_redirects=False)
    assert r.status_code in (200, 303)
    assert "SameSite=lax" in r.headers.get("set-cookie", "") or \
        any("SameSite=lax" in v for v in r.headers.get_list("set-cookie", []))


def test_rate_limit_login_register_role_429():
    # 登录:同一账号连续失败 10 次后第 11 次 429
    c = client()
    for _ in range(10):
        assert c.post("/login", data={"email": "ghost@test.jp",
                                      "password": "WrongPass123!"}).status_code == 200
    assert c.post("/login", data={"email": "ghost@test.jp",
                                  "password": "WrongPass123!"}).status_code == 429
    # 注册:同一邮箱重复提交 10 次后第 11 次 429
    c2 = client()
    for _ in range(10):
        c2.post("/register", data={"email": "rl@test.jp",
                                   "display_name": "x",
                                   "password": "TestPass123!"})
    assert c2.post("/register", data={"email": "rl@test.jp",
                                      "display_name": "x",
                                      "password": "TestPass123!"}).status_code == 429
    # 改角色:同一管理员 20 次后第 21 次 429
    admin = make_user_with_role("opt-admin4@test.jp", "admin")
    reg(client(), "opt-rl-target@test.jp")
    tid = dbval("SELECT id FROM users WHERE email=?", ("opt-rl-target@test.jp",))
    for i in range(20):
        assert admin.post(f"/admin/users/{tid}/role",
                          data={"role": "user" if i % 2 else "operator"}).status_code == 200
    assert admin.post(f"/admin/users/{tid}/role",
                      data={"role": "user"}).status_code == 429
    # 限流函数本身:limit=3 时前 3 次放行,第 4 次拒绝
    assert [check_rate_limit("unit-key", 3, 60) for _ in range(4)] == \
        [True, True, True, False]


# ---------------- 1b. 输入校验 ----------------

def test_input_validation_400_not_500():
    seller = reg(client(), "opt-v1@test.jp")
    base = {"category_slug": "appliance", "title_ja": "中古品",
            "title_zh": "二手微波炉", "desc_ja": "", "desc_zh": "",
            "condition_grade": "good", "region": "sakado",
            "size_class": "M", "weight_kg": "0"}
    assert seller.post("/listings/new",
                       data={**base, "price": "-5"}).status_code == 400
    assert seller.post("/listings/new",
                       data={**base, "price": "abc"}).status_code == 400
    assert seller.post("/listings/new",
                       data={**base, "price": "100",
                             "title_ja": "x" * 201}).status_code == 400
    assert seller.post("/listings/new",
                       data={**base, "price": "100",
                             "condition_grade": "bogus"}).status_code == 400
    lid = publish(seller)
    buyer = reg(client(), "opt-v2@test.jp")
    assert buyer.post(f"/listings/{lid}/offer",
                      data={"amount": "-100"}).status_code == 400
    assert buyer.post("/services/new", data={
        "kind": "cleaning_home", "hours": "-1",
        "qty": "1", "note": ""}).status_code == 400
    assert buyer.post("/services/new", data={
        "kind": "cleaning_home", "hours": "1",
        "qty": "0", "note": ""}).status_code == 400
    assert buyer.post("/services/new", data={
        "kind": "removed_kind", "hours": "1",
        "qty": "1", "note": ""}).status_code == 400
    assert seller.post(f"/listings/{lid}/auction", data={
        "start_price": "-1", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "0", "ends_at": "2027-01-01T00:00:00+09:00",
        "deposit_amount": "0"}).status_code == 400
    assert buyer.post("/support", data={"question": ""}).status_code == 400
    assert buyer.post("/support", data={"question": "x" * 2001}).status_code == 400


# ---------------- 2. 数据完整 ----------------

def test_duplicate_pay_is_idempotent_no_double_audit():
    seller = reg(client(), "opt-p1@test.jp")
    buyer = reg(client(), "opt-p2@test.jp")
    lid = publish(seller)
    oid = buy_order(buyer, lid)
    pay_order(buyer, oid, key="dup-key-9")
    pay_order(buyer, oid, key="dup-key-9")
    pay_order(buyer, oid, key="other-key-9")
    assert dbval("SELECT COUNT(*) FROM order_audit WHERE order_id=? "
                 "AND event='mock_payment'", (oid,)) == 1
    assert dbval("SELECT COUNT(*) FROM payment_intents WHERE order_id=?",
                 (oid,)) == 1
    assert dbval("SELECT status FROM orders WHERE id=?", (oid,)) == "paid"


def test_duplicate_buy_creates_no_duplicate_order():
    seller = reg(client(), "opt-p3@test.jp")
    buyer = reg(client(), "opt-p4@test.jp")
    lid = publish(seller)
    buy_order(buyer, lid)
    buyer.post(f"/listings/{lid}/buy")
    assert dbval("SELECT COUNT(*) FROM orders WHERE listing_id=?",
                 (lid,)) == 1


def test_terminal_states_are_irreversible():
    seller = reg(client(), "opt-t1@test.jp")
    buyer = reg(client(), "opt-t2@test.jp")
    lid = publish(seller)
    oid = buy_order(buyer, lid)
    pay_order(buyer, oid)
    buyer.post(f"/orders/{oid}/complete")
    assert dbval("SELECT status FROM orders WHERE id=?", (oid,)) == "completed"
    buyer.post(f"/orders/{oid}/cancel")
    buyer.post(f"/orders/{oid}/complete")
    assert dbval("SELECT status FROM orders WHERE id=?", (oid,)) == "completed"
    assert dbrow("SELECT * FROM audit_log WHERE action='order_complete' "
                 "AND target_id=?", (oid,)) is not None
    # 已取消订单不可再支付
    lid2 = publish(seller)
    oid2 = buy_order(buyer, lid2)
    buyer.post(f"/orders/{oid2}/cancel")
    assert dbval("SELECT status FROM orders WHERE id=?", (oid2,)) == "cancelled"
    buyer.post(f"/orders/{oid2}/pay", data={"idempotency_key": "late-key"})
    assert dbval("SELECT status FROM orders WHERE id=?", (oid2,)) == "cancelled"
    # 已退款订单不可再完成
    lid3 = publish(seller)
    oid3 = buy_order(buyer, lid3)
    pay_order(buyer, oid3, key="refund-key")
    buyer.post(f"/orders/{oid3}/refund", data={"reason": "坏了", "evidence": ""})
    rid = dbval("SELECT MAX(id) FROM refunds")
    op = make_user_with_role("opt-t-op@test.jp", "operator")
    assert op.post(f"/refunds/{rid}/decide", data={
        "decision": "approved", "decision_note": "同意退款"}).status_code == 200
    assert dbval("SELECT status FROM orders WHERE id=?", (oid3,)) == "refunded"
    buyer.post(f"/orders/{oid3}/complete")
    assert dbval("SELECT status FROM orders WHERE id=?", (oid3,)) == "refunded"
    assert dbrow("SELECT * FROM audit_log WHERE action='refund_decide' "
                 "AND target_id=?", (rid,)) is not None


def test_auction_settled_and_buyback_rejected_are_terminal():
    seller = reg(client(), "opt-t3@test.jp")
    lid = publish(seller)
    seller.post(f"/listings/{lid}/auction", data={
        "start_price": "1000", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "0", "ends_at": "2020-01-01T00:00:00+09:00",
        "deposit_amount": "0"})
    aid = dbval("SELECT MAX(id) FROM auctions")
    op = make_user_with_role("opt-t-op2@test.jp", "operator")
    op.post(f"/auctions/{aid}/settle")
    assert dbval("SELECT status FROM auctions WHERE id=?", (aid,)) == "ended_unsold"
    op.post(f"/auctions/{aid}/settle")
    assert dbval("SELECT status FROM auctions WHERE id=?", (aid,)) == "ended_unsold"
    # 买断被拒后不可再流转
    lid2 = publish(seller)
    seller.post("/buyback/new", data={"listing_id": str(lid2)})
    bid = dbval("SELECT MAX(id) FROM buybacks")
    op.post(f"/buyback/{bid}/reject")
    assert dbval("SELECT status FROM buybacks WHERE id=?", (bid,)) == "rejected"
    op.post(f"/buyback/{bid}/review")
    assert dbval("SELECT status FROM buybacks WHERE id=?", (bid,)) == "rejected"
    assert dbrow("SELECT * FROM audit_log WHERE action='buyback_transition' "
                 "AND target_id=?", (bid,)) is not None


def test_duplicate_deposit_not_charged_twice():
    seller = reg(client(), "opt-d1@test.jp")
    buyer = reg(client(), "opt-d2@test.jp")
    lid = publish(seller)
    seller.post(f"/listings/{lid}/auction", data={
        "start_price": "1000", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "0", "ends_at": "2027-01-01T00:00:00+09:00",
        "deposit_required": "1", "deposit_amount": "500"})
    aid = dbval("SELECT MAX(id) FROM auctions")
    buyer.post(f"/auctions/{aid}/deposit")
    buyer.post(f"/auctions/{aid}/deposit")
    assert dbval("SELECT COUNT(*) FROM deposits WHERE auction_id=? "
                 "AND bidder_id=? AND status='held'",
                 (aid, dbval("SELECT id FROM users WHERE email=?",
                             ("opt-d2@test.jp",)))) == 1


# ---------------- 3. 合规展示 ----------------

def test_mock_and_tax_labels_on_money_pages():
    seller = reg(client(), "opt-m1@test.jp")
    buyer = reg(client(), "opt-m2@test.jp")
    lid = publish(seller)
    oid = buy_order(buyer, lid)
    for url in (f"/listings/{lid}?lang=zh", f"/orders/{oid}?lang=zh",
                "/services?lang=zh"):
        txt = buyer.get(url).text
        assert "所有价格均为含税价" in txt, url
        assert "模拟" in txt, url
    seller.post(f"/listings/{lid}/auction", data={
        "start_price": "1000", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "0", "ends_at": "2027-01-01T00:00:00+09:00",
        "deposit_amount": "0"})
    aid = dbval("SELECT MAX(id) FROM auctions")
    txt = buyer.get(f"/auctions/{aid}?lang=zh").text
    assert "所有价格均为含税价" in txt and "模拟" in txt
    seller.post("/buyback/new", data={"listing_id": str(lid)})
    # 买断页需卖家本人或运营;卖家视角含税标注
    bid = dbval("SELECT MAX(id) FROM buybacks")
    if bid:
        assert "所有价格均为含税价" in seller.get(f"/buyback/{bid}?lang=zh").text


def test_rules_links_reachable_and_bilingual():
    c = client()
    home = c.get("/").text
    for href in ("/rules", "/terms", "/privacy", "/returns", "/prohibited"):
        assert f'href="{href}"' in home, href
        r = c.get(href)
        assert r.status_code == 200
        assert "日本語" in r.text and "中文" in r.text
    user = reg(client(), "opt-m3@test.jp")
    assert 'href="/rules"' in user.get("/me").text


def test_no_placeholder_copy_on_key_pages():
    c = client()
    for url in ("/", "/market", "/services", "/rules", "/terms", "/trade"):
        txt = c.get(url).text
        assert "TODO" not in txt and "lorem" not in txt.lower()
        assert "敬请期待" not in txt and "建设中" not in txt


def test_admin_users_page_never_leaks_password_hash():
    admin = make_user_with_role("opt-m4@test.jp", "admin")
    reg(client(), "opt-m5@test.jp")
    h = dbval("SELECT pw_hash FROM users WHERE email=?", ("opt-m5@test.jp",))
    assert h not in admin.get("/admin/users").text
    assert "pw_hash" not in admin.get("/admin/users").text


# ---------------- 4. 体验 ----------------

def test_empty_states_and_friendly_error_pages():
    user = reg(client(), "opt-e1@test.jp")
    assert "暂无数据" in user.get("/orders?lang=zh").text
    assert "暂无数据" in user.get("/market?lang=zh").text
    assert "暂无" in user.get("/me/extra").text
    r = client().get("/no-such-page-xyz")
    assert r.status_code == 404 and "返回首页" in r.text
    r = client().get("/listings/999999")
    assert r.status_code == 404 and "返回首页" in r.text
    r = client().get("/admin")
    assert r.status_code == 401 and "返回首页" in r.text
    r = user.get("/admin")
    assert r.status_code == 403 and "返回首页" in r.text
    r = client().get("/me")
    assert r.status_code == 401 and "返回首页" in r.text


def test_ai_job_poll_states_include_failed():
    user = reg(client(), "opt-e2@test.jp")
    r = user.post("/ai-jobs", data={"kind": "nope_kind"})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    import time as _t
    last = None
    for _ in range(80):
        last = user.get(f"/ai-jobs/{jid}").json()
        if last["status"] in ("done", "failed"):
            break
        _t.sleep(0.1)
    assert last["status"] == "failed"
    assert "unknown kind" in last["result"]["error"]


def test_crawl_no_dead_links():
    seller = reg(client(), "opt-c1@test.jp")
    buyer = reg(client(), "opt-c2@test.jp")
    lid = publish(seller)
    op = make_user_with_role("opt-c-op@test.jp", "operator")
    seller.post(f"/listings/{lid}/auction", data={
        "start_price": "1000", "reserve_price": "0", "min_increment": "100",
        "buy_now_price": "0", "ends_at": "2027-01-01T00:00:00+09:00",
        "deposit_amount": "0"})
    aid = dbval("SELECT MAX(id) FROM auctions")
    seeds = {
        client(): ["/", "/market", "/trade", "/services", "/rules",
                   "/terms", "/privacy", "/returns", "/prohibited",
                   "/support", "/auctions", f"/listings/{lid}",
                   f"/auctions/{aid}", "/healthz"],
        seller: ["/", "/me", "/me/messages", "/me/extra", "/orders",
                 "/deliveries", f"/listings/{lid}"],
        buyer: ["/", "/me", "/orders", f"/listings/{lid}",
                f"/auctions/{aid}"],
        op: ["/admin", "/admin/users", "/admin/listings", "/admin/buybacks",
             "/admin/orders", "/admin/inventory", "/admin/auctions",
             "/admin/deliveries", "/admin/services", "/admin/refunds",
             "/admin/disputes", "/admin/high-value", "/admin/alerts",
             "/admin/profit", "/admin/agents", "/admin/settings",
             "/admin/expenses"],
    }
    href_re = re.compile(r'href="([^"]+)"')
    for cli, pages in seeds.items():
        hrefs = set()
        for pg in pages:
            r = cli.get(pg)
            assert r.status_code != 404 and r.status_code < 500, (pg, r.status_code)
            assert len(r.text) > 50, pg
            for h in href_re.findall(r.text):
                if h.startswith("/") and not h.startswith("//"):
                    hrefs.add(h.split("#")[0].split("?")[0])
        for h in hrefs:
            if h in ("/logout",):
                continue
            r = cli.get(h)
            assert r.status_code != 404, h
            assert r.status_code < 500, (h, r.status_code)


def test_mobile_css_guards_present():
    txt = client().get("/").text
    assert "max-width:100%" in txt
    assert "overflow-x:auto" in txt
    assert "overflow-wrap:break-word" in txt or "word-break:break-word" in txt
    assert 'name="viewport"' in txt


# ---------------- 5. 生产数据干净 ----------------

def test_init_db_creates_no_users_or_demo_data():
    assert dbval("SELECT COUNT(*) FROM users") == 0
    assert dbval("SELECT COUNT(*) FROM listings") == 0
    assert dbval("SELECT COUNT(*) FROM orders") == 0
    assert dbval("SELECT COUNT(*) FROM listings WHERE demo=1") == 0


def test_demo_data_excluded_from_stats_and_profit():
    conn = d.connect()
    cat_id = conn.execute("SELECT id FROM categories WHERE slug='appliance'"
                          ).fetchone()[0]
    conn.execute("INSERT INTO listings(seller_id,category_id,title_ja,price,"
                 "demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                 (None, cat_id, "演示商品", 100, 1, "2026-01-01", "2026-01-01"))
    demo_lid = conn.execute("SELECT MAX(id) FROM listings").fetchone()[0]
    conn.execute("INSERT INTO listings(seller_id,category_id,title_ja,price,"
                 "demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                 (None, cat_id, "真实商品", 100, 0, "2026-01-01", "2026-01-01"))
    real_lid = conn.execute("SELECT MAX(id) FROM listings").fetchone()[0]
    conn.execute("INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,"
                 "commission,total,status,demo,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (1, None, demo_lid, 999999, 0, 999999, "paid", 1,
                  "2026-01-02", "2026-01-02"))
    conn.execute("INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,"
                 "commission,total,status,demo,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (1, None, real_lid, 1000, 0, 1000, "paid", 0,
                  "2026-01-02", "2026-01-02"))
    real_oid = conn.execute("SELECT MAX(id) FROM orders").fetchone()[0]
    conn.execute("INSERT INTO refunds(order_id,applicant_id,reason,status,"
                 "decision,created_at) VALUES(?,?,?,?,?,?)",
                 (real_oid, 1, "退货", "decided", "approved", "2026-01-03"))
    conn.commit()
    s = stats(conn)
    assert s["gmv"] == 1000, s
    cats = category_stats(conn)
    app = next(x for x in cats if x["slug"] == "appliance")
    assert app["listed"] == 1 and app["completed"] == 1 \
        and app["volume"] == 1000
    pr = profit_report(conn)
    assert pr["refunded_total"] == 1000, pr
    conn.close()
