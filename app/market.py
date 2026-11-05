"""交易行情与经营利润分析(第三阶段)。全部基于平台真实订单/商品数据,
演示订单(demo=1)一律排除,绝不编造。数据不足时返回样本量与提示,
调用方须把提示展示出来。

行情口径:
- 成交价:status 为 paid/completed 的真实订单商品金额。
- 挂牌价:在售商品价格,与成交价严格分开展示。
- 成交周期:订单 created_at -> completed 时的 updated_at 天数均值。
"""
import json
from datetime import datetime, timedelta
from statistics import median

try:
    from zoneinfo import ZoneInfo
    TOKYO = ZoneInfo("Asia/Tokyo")
except Exception:
    from datetime import timezone
    TOKYO = timezone(timedelta(hours=9))


def _completed_orders(conn, category_slug=None):
    sql = ("SELECT o.* FROM orders o JOIN listings l ON l.id=o.listing_id "
           "JOIN categories c ON c.id=l.category_id "
           "WHERE o.status IN ('paid','completed') AND o.demo=0")
    args = []
    if category_slug:
        sql += " AND c.slug=?"
        args.append(category_slug)
    return conn.execute(sql, args).fetchall()


def _days_between(a, b):
    try:
        da = datetime.fromisoformat(a)
        db = datetime.fromisoformat(b)
        return max(0, (db - da).days)
    except Exception:
        return None


def category_stats(conn):
    """每类:挂牌数、在售数、成交数、成交总额、成交均价/中位数/区间、
    关注数、成交周期均值、样本量与可信度。"""
    out = []
    cats = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    for cat in cats:
        listed = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE category_id=? AND demo=0",
            (cat["id"],)).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE category_id=? AND status='active'"
            " AND demo=0", (cat["id"],)).fetchone()[0]
        orders = _completed_orders(conn, cat["slug"])
        amounts = [o["goods_amount"] for o in orders]
        cycles = [d for d in (
            _days_between(o["created_at"], o["updated_at"]) for o in orders)
            if d is not None]
        follows = conn.execute(
            "SELECT COUNT(*) FROM listing_follows f JOIN listings l "
            "ON l.id=f.listing_id WHERE l.category_id=? AND l.demo=0",
            (cat["id"],)).fetchone()[0]
        out.append({
            "slug": cat["slug"], "name_ja": cat["name_ja"],
            "name_zh": cat["name_zh"], "listed": listed, "active": active,
            "completed": len(amounts), "volume": sum(amounts),
            "avg": int(sum(amounts) / len(amounts)) if amounts else None,
            "median": int(median(amounts)) if amounts else None,
            "low": min(amounts) if amounts else None,
            "high": max(amounts) if amounts else None,
            "follows": follows,
            "avg_cycle_days": round(sum(cycles) / len(cycles), 1) if cycles else None,
            "sample_note": ("样本充足" if len(amounts) >= 10 else
                            "样本较少,仅供参考" if amounts else "暂无真实成交样本"),
        })
    return out


def top_listings(conn, limit=10):
    """热门交易榜 TOP10:按真实成交数、再按关注数排序,全部真实数据。"""
    rows = conn.execute(
        "SELECT l.id, l.title_ja, l.title_zh, l.price, c.slug AS cat_slug,"
        " (SELECT COUNT(*) FROM orders o WHERE o.listing_id=l.id "
        "  AND o.status IN ('paid','completed') AND o.demo=0) AS sold_n,"
        " (SELECT COUNT(*) FROM listing_follows f WHERE f.listing_id=l.id) "
        "  AS follow_n FROM listings l JOIN categories c ON c.id=l.category_id "
        "WHERE l.demo=0 ORDER BY sold_n DESC, follow_n DESC, l.id DESC "
        "LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def weekly_curve(conn, category_slug=None, weeks=12):
    """最近 N 周每周成交均价与成交数(按订单 created_at 周桶)。"""
    orders = _completed_orders(conn, category_slug)
    now = datetime.now(TOKYO)
    buckets = {}
    for i in range(weeks):
        start = now - timedelta(days=7 * (i + 1))
        key = start.strftime("%Y-W%W")
        buckets[key] = []
    for o in orders:
        try:
            d = datetime.fromisoformat(o["created_at"])
        except Exception:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=TOKYO)
        key = d.strftime("%Y-W%W")
        if key in buckets:
            buckets[key].append(o["goods_amount"])
    return [{"week": k, "count": len(v),
             "avg": int(sum(v) / len(v)) if v else None}
            for k, v in sorted(buckets.items())]


def collectible_trend(conn):
    """收藏品价格变化:手表/钱币/古董三类的成交均价与在售挂牌均价对照。"""
    out = []
    for slug in ("watch", "coin", "antique"):
        orders = _completed_orders(conn, slug)
        amounts = [o["goods_amount"] for o in orders]
        act = conn.execute(
            "SELECT price FROM listings WHERE status='active' AND demo=0 "
            "AND category_id=(SELECT id FROM categories WHERE slug=?)",
            (slug,)).fetchall()
        prices = [r[0] for r in act]
        out.append({
            "slug": slug,
            "completed_n": len(amounts),
            "completed_avg": int(sum(amounts) / len(amounts)) if amounts else None,
            "active_n": len(prices),
            "active_avg": int(sum(prices) / len(prices)) if prices else None,
        })
    return out


def listing_price_moves(conn):
    """第 3 阶段行情双榜:按单个商品(不按品类)算涨跌。

    依据(必须明码标注,调用方须展示):
      有 >=2 笔真实订单(已支付/已完成,演示订单排除)的商品,
      涨跌 = 最近真实成交价 vs 首次成交价,样本量 = 该商品真实订单数。
      不足 2 笔、首价 <=0 的商品不入榜,计入 insufficient/flat 说明,
      绝不编造。挂牌价不计入涨跌;估价绝不走此数据(行情页展示平台
      真实订单统计是允许的,但必须标注依据是平台订单)。
    返回 {gainers(涨幅 pct 降序), losers(跌幅 pct 升序,即跌得最深在前),
      up_count, down_count, flat_count, insufficient,
      top_gainer, top_loser}。
    """
    listings = conn.execute(
        "SELECT l.id, l.title_ja, l.title_zh, c.slug AS cat_slug, "
        "c.name_zh AS cat_zh FROM listings l "
        "JOIN categories c ON c.id=l.category_id "
        "WHERE l.demo=0 ORDER BY l.id").fetchall()
    gainers, losers = [], []
    flat, insufficient = 0, 0
    for row in listings:
        orders = conn.execute(
            "SELECT goods_amount FROM orders WHERE listing_id=? "
            "AND status IN ('paid','completed') AND demo=0 "
            "ORDER BY created_at, id", (row["id"],)).fetchall()
        amounts = [o[0] for o in orders]
        if len(amounts) < 2:
            insufficient += 1
            continue
        first, latest = amounts[0], amounts[-1]
        if first <= 0:
            insufficient += 1
            continue
        change = latest - first
        pct = round(change / first * 100, 1)
        entry = {"listing_id": row["id"],
                 "title_zh": row["title_zh"], "title_ja": row["title_ja"],
                 "cat_slug": row["cat_slug"], "cat_zh": row["cat_zh"],
                 "first": first, "latest": latest, "change": change,
                 "pct": pct, "orders": len(amounts)}
        if change > 0:
            gainers.append(entry)
        elif change < 0:
            losers.append(entry)
        else:
            flat += 1
    gainers.sort(key=lambda x: -x["pct"])
    losers.sort(key=lambda x: x["pct"])
    return {"gainers": gainers, "losers": losers,
            "up_count": len(gainers), "down_count": len(losers),
            "flat_count": flat, "insufficient": insufficient,
            "top_gainer": gainers[0] if gainers else None,
            "top_loser": losers[0] if losers else None}


def profit_report(conn):
    """经营利润分析:营业额/GMV/商品销售额/毛利/费用/经营利润/净利润
    严格区分,服务收入与退款单独列示,绝不把代收交易额算成收入。"""
    from .business import stats
    s = stats(conn)
    service_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM service_orders "
        "WHERE status='completed'").fetchone()[0]
    refunded = conn.execute(
        "SELECT COALESCE(SUM(o.total),0) FROM refunds r JOIN orders o "
        "ON o.id=r.order_id WHERE r.status='decided' "
        "AND r.decision='approved'").fetchone()[0]
    turnover = s["gmv"] + service_income
    operating = s["operating_profit"] + service_income - refunded
    return {
        **s,
        "turnover": turnover,
        "service_income": service_income,
        "refunded_total": refunded,
        "operating_profit_full": operating,
        "net_profit_full": operating,
    }
