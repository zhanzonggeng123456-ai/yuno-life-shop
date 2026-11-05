"""AI运营Agent(第三阶段)。全部本地启发式实现,零API成本,不调用任何付费模型。
所有Agent输出均为建议,高风险操作(收购付款、封禁、争议裁决)只记录建议与审计,
须人工审批才生效。
"""
import re
from datetime import datetime

from .business import guess_category, price_reference
from .market import profit_report

BANNED_WORDS = ["伪物", "假货", "盗品", "赃物", "武器", "麻药", "毒品", "伪造", "假冒"]
SUPPORT_FAQ = [
    (r"运费|配送|送料", "配送:轻小件150日元起按尺寸分档(S150/M200/L250),"
     "XL大件单独报价,未开放地区不承诺配送。配送预约请在订单页申请。"),
    (r"佣金", "佣金:成交价的7%~10%,后台可调,默认10%,由卖家侧承担;"
     "自营商品不收佣金。买家合计 = 商品价 + 运费。"),
    (r"买断|收购|卖给平台", "买断:提交申请后平台审核报价,可拒绝收购,不承诺全收;"
     "AI估价只是参考区间,不是最终收购承诺。接受报价后预约取货、验货、付款入库。"),
    (r"退款|退货|争议", "退款与争议:在订单页提交申请并附证据,运营审核后裁决;"
     "裁决结果与审计记录会保留在订单与争议记录中。"),
    (r"拍卖|竞价|出价", "拍卖:起拍价、保留价、最小加价、一口价均可设置;"
     "结束前5分钟内出价自动延时5分钟;达到保留价才成交,否则流拍。"),
    (r"支付|付款", "支付:当前为模拟支付,不会真实扣款。正式收款需平台"
     "签约日本持牌支付服务商后切换,届时会在页面明确告知。"),
]


def review_agent(conn, listing):
    flags = []
    blob = "%s %s %s %s" % (listing["title_ja"] or "", listing["title_zh"] or "",
                            listing["desc_ja"] or "", listing["desc_zh"] or "")
    for w in BANNED_WORDS:
        if w in blob:
            flags.append("疑似违禁词:" + w)
    imgs = conn.execute("SELECT COUNT(*) FROM images WHERE listing_id=?",
                        (listing["id"],)).fetchone()[0]
    if imgs == 0:
        flags.append("无商品图片,建议补拍")
    cat = conn.execute("SELECT slug FROM categories WHERE id=?",
                       (listing["category_id"],)).fetchone()
    if cat:
        low, high, conf, basis = price_reference(conn, cat["slug"])
        if low and listing["price"] > high * 3:
            flags.append("价格远高于平台订单参考区间,建议复核定价")
        if low and listing["price"] < low * 0.3:
            flags.append("价格远低于平台订单参考区间,建议复核是否为误标")
    verdict = "需人工复核" if flags else "通过(本地启发式,非最终结论)"
    return {"listing_id": listing["id"], "flags": flags, "verdict": verdict}


def pricing_agent(conn, listing):
    cat = conn.execute("SELECT slug FROM categories WHERE id=?",
                       (listing["category_id"],)).fetchone()
    slug = cat["slug"] if cat else None
    low, high, conf, basis = price_reference(conn, slug)
    if low is None:
        return {"listing_id": listing["id"], "suggestion": None,
                "note": "暂无样本,无法给出定价建议,请勿编造参考价"}
    return {"listing_id": listing["id"], "suggestion": (low, high),
            "confidence": conf, "basis": basis,
            # 第 3 阶段收口:price_reference 只统计平台订单/挂牌,此处
            # 明确标注为平台订单参考,绝不说成市场价。
            "note": "平台订单参考区间(平台订单/挂牌统计,不是市场价),"
                    "最终定价由卖家/运营决定"}


def classify_agent(name, text):
    slug, conf = guess_category("%s %s" % (name or "", text or ""))
    return {"category_slug": slug, "confidence": conf,
            "note": "本地关键词建议,须人工确认"}


def support_agent(question):
    for pat, ans in SUPPORT_FAQ:
        if re.search(pat, question or ""):
            return {"answer": ans, "note": "规则问答(本地);复杂问题请转人工客服"}
    return {"answer": "已收到您的问题,规则库暂无匹配答案,已转人工客服处理。"
            "常见问题:运费、佣金、买断、退款争议、拍卖、支付。",
            "note": "规则问答(本地);复杂问题请转人工客服"}


def anomaly_agent(conn):
    alerts = []
    rows = conn.execute(
        "SELECT buyer_id, listing_id, COUNT(*) c FROM orders "
        "WHERE status='pending_payment' GROUP BY buyer_id, listing_id "
        "HAVING c >= 3").fetchall()
    for r in rows:
        alerts.append(("duplicate_pending_orders", "order", r["listing_id"],
                       "买家 %s 对商品 %s 有 %s 笔待付款订单"
                       % (r["buyer_id"], r["listing_id"], r["c"]), "medium"))
    rows = conn.execute(
        "SELECT b.auction_id, b.bidder_id, b.amount, a.start_price FROM bids b "
        "JOIN auctions a ON a.id=b.auction_id ORDER BY b.id").fetchall()
    seen = {}
    for b in rows:
        prev = seen.get(b["auction_id"], b["start_price"])
        if prev and b["amount"] > prev * 3:
            alerts.append(("bid_jump", "auction", b["auction_id"],
                           "出价人 %s 出价 %s 日元,远高于前价 %s 日元,疑似恶意竞价"
                           % (b["bidder_id"], b["amount"], prev), "high"))
        seen[b["auction_id"]] = max(prev, b["amount"])
    rows = conn.execute(
        "SELECT order_id, COUNT(*) c FROM order_audit WHERE event='mock_payment'"
        " GROUP BY order_id HAVING c > 1").fetchall()
    for r in rows:
        alerts.append(("duplicate_payment", "order", r["order_id"],
                       "订单 %s 有 %s 笔模拟支付审计记录"
                       % (r["order_id"], r["c"]), "high"))
    rows = conn.execute(
        "SELECT buyer_id, COUNT(*) c FROM orders WHERE status='cancelled' "
        "GROUP BY buyer_id HAVING c >= 5").fetchall()
    for r in rows:
        alerts.append(("frequent_cancels", "user", r["buyer_id"],
                       "用户 %s 累计取消 %s 笔订单" % (r["buyer_id"], r["c"]), "low"))
    return alerts


def dispute_agent(refund_or_dispute):
    reason = refund_or_dispute["reason"] or ""
    if re.search(r"假货|损坏|与描述不符|描述不符|未到货|未收到", reason):
        suggestion = "建议运营优先核查证据照片与物流记录,必要时安排鉴定"
    elif re.search(r"延迟|太慢", reason):
        suggestion = "建议核查配送任务时间线,再决定是否补偿运费"
    else:
        suggestion = "建议运营按证据与交易记录人工裁决"
    return {"suggestion": suggestion,
            "note": "仅为辅助建议,裁决须运营人工确认并写入审计记录"}


def inventory_agent(conn):
    from statistics import median
    out = []
    rows = conn.execute(
        "SELECT i.*, l.price, l.category_id, l.created_at"
        " FROM inventory i JOIN listings l ON l.id=i.listing_id "
        "WHERE i.status='in_stock'").fetchall()
    for inv in rows:
        try:
            from datetime import timezone
            now_aware = datetime.now(timezone.utc)
            dt = datetime.fromisoformat(inv["created_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days = max(0, (now_aware - dt).days)
        except Exception:
            days = 0
        follows = conn.execute(
            "SELECT COUNT(*) FROM listing_follows WHERE listing_id=?",
            (inv["listing_id"],)).fetchone()[0]
        peers = conn.execute(
            "SELECT price FROM listings WHERE category_id=? AND status='active'"
            " AND demo=0", (inv["category_id"],)).fetchall()
        peer_prices = [r[0] for r in peers]
        peer_med = int(median(peer_prices)) if peer_prices else None
        suggestion, reason = None, ""
        if days >= 30 and follows < 3 and peer_med:
            suggestion = min(inv["price"], peer_med)
            reason = "库存 %s 天、关注仅 %s 人,建议向同类挂牌中位数靠拢" % (days, follows)
        elif days >= 60:
            suggestion = int(inv["price"] * 0.9)
            reason = "库存 %s 天未售出,建议降价10%%试销" % days
        if suggestion and suggestion != inv["price"]:
            out.append({"listing_id": inv["listing_id"],
                        "current_price": inv["price"],
                        "suggested_price": suggestion, "reason": reason})
    return out


def ops_agent(conn):
    rep = profit_report(conn)
    return {
        "gmv": rep["gmv"], "platform_sales": rep["platform_sales"],
        "commission_income": rep["commission_income"],
        "gross_profit": rep["gross_profit"],
        "service_income": rep["service_income"],
        "refunded_total": rep["refunded_total"],
        "expenses": rep["expenses"],
        "operating_profit": rep["operating_profit_full"],
        "net_profit": rep["net_profit_full"],
        "note": "GMV不是收入;佣金收入 + 自营毛利 + 服务收入 - 退款 - 费用 = 经营利润",
    }
