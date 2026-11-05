"""拍卖业务逻辑(第二阶段)。全部本地计算,与固定价交易共用商品/用户/
支付/订单体系:结算时复用主程序的 create_order。

规则:
- 出价必须 >= 当前价 + 最小加价幅度(首次出价 >= 起拍价)。
- 代理出价:bidder 报 proxy_max,当前价 = 第二高 proxy_max + 最小加价,
  上限为最高 proxy_max;平局先出价者领先。
- 防压线:结束前 300 秒内出价,结束时间自动延长 300 秒。
- 保证金(模拟):deposit_required 时,未交保证金的出价被拒绝;
  保证金只做模拟托管记录,绝不宣称为真实收款。
- 结算:最高价 >= 保留价 -> 生成待付款订单;否则流拍。
"""
from .security import now_tokyo

ANTI_SNIPE_SECONDS = 300


def _parse_ts(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def auction_bids(conn, auction_id):
    return conn.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id",
                        (auction_id,)).fetchall()


def effective_max(bid):
    return bid["proxy_max"] if bid["proxy_max"] else bid["amount"]


def compute_price(auction, bids):
    """返回 (current_price, leader_id)。无出价时为起拍价,无领先者。"""
    start = auction["start_price"]
    inc = auction["min_increment"] or 100
    if not bids:
        return start, None
    ranked = sorted(bids, key=lambda b: (-effective_max(b), b["id"]))
    top = ranked[0]
    if len(ranked) == 1:
        return start, top["bidder_id"]
    second = effective_max(ranked[1])
    price = min(effective_max(top), second + inc)
    return max(price, start), top["bidder_id"]


def min_next_bid(auction, bids):
    current, _ = compute_price(auction, bids)
    if not bids:
        return current
    return current + (auction["min_increment"] or 100)


def place_bid(conn, auction, bidder_id, amount, proxy_max=None):
    """返回 (ok, message, bid_id)。调用方负责提交与防压线处理。"""
    from datetime import timedelta
    now = now_tokyo()
    if auction["status"] != "active":
        return False, "auction_not_active", None
    ends = _parse_ts(auction["ends_at"])
    starts = _parse_ts(auction["starts_at"])
    now_dt = _parse_ts(now)
    if starts and now_dt < starts:
        return False, "auction_not_started", None
    if ends and now_dt >= ends:
        return False, "auction_ended", None
    if auction["deposit_required"]:
        dep = conn.execute(
            "SELECT id FROM deposits WHERE auction_id=? AND bidder_id=? "
            "AND status='held'", (auction["id"], bidder_id)).fetchone()
        if not dep:
            return False, "deposit_required", None
    bids = auction_bids(conn, auction["id"])
    need = min_next_bid(auction, bids)
    if amount < need:
        return False, f"bid_too_low:{need}", None
    if proxy_max is not None and proxy_max < amount:
        return False, "proxy_below_bid", None
    cur = conn.execute(
        "INSERT INTO bids(auction_id,bidder_id,amount,proxy_max,created_at)"
        " VALUES(?,?,?,?,?)",
        (auction["id"], bidder_id, amount, proxy_max, now))
    bid_id = cur.lastrowid
    if ends and (ends - now_dt).total_seconds() <= ANTI_SNIPE_SECONDS:
        new_end = (ends + timedelta(seconds=ANTI_SNIPE_SECONDS)).isoformat(
            timespec="seconds")
        conn.execute("UPDATE auctions SET ends_at=? WHERE id=?",
                     (new_end, auction["id"]))
    return True, "bid_placed", bid_id


def settle_auction(conn, auction, create_order_fn):
    """结算拍卖。返回 (outcome, order_id_or_None, final_price_or_None)。
    outcome: sold / unsold / not_ended / already_settled。
    调用方负责提交。"""
    if auction["status"] != "active":
        return "already_settled", None, None
    now_dt = _parse_ts(now_tokyo())
    ends = _parse_ts(auction["ends_at"])
    if ends and now_dt < ends:
        return "not_ended", None, None
    bids = auction_bids(conn, auction["id"])
    listing = conn.execute("SELECT * FROM listings WHERE id=?",
                           (auction["listing_id"],)).fetchone()
    if not bids:
        conn.execute("UPDATE auctions SET status='ended_unsold' WHERE id=?",
                     (auction["id"],))
        return "unsold", None, None
    price, leader = compute_price(auction, bids)
    reserve = auction["reserve_price"] or 0
    if price < reserve:
        conn.execute("UPDATE auctions SET status='ended_unsold' WHERE id=?",
                     (auction["id"],))
        if listing is not None and listing["status"] == "reserved":
            conn.execute("UPDATE listings SET status='active' WHERE id=?",
                         (listing["id"],))
        return "unsold", None, price
    if listing is None or listing["status"] != "active":
        return "already_settled", None, None
    oid, err = create_order_fn(conn, leader, listing, price)
    if err:
        return "needs_quote", None, price
    conn.execute("UPDATE auctions SET status='ended_sold' WHERE id=?",
                 (auction["id"],))
    return "sold", oid, price
