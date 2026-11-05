"""核心业务规则。全部本地计算,无外部调用、无按量计费。
外部服务占位(默认关闭,接了才花钱,不接也能跑):
真实 AI 模型仅当 YUNO_AI_ENABLED=1 且 YUNO_AI_API_KEY 已设置时才允许调用,
MVP 流程永远不调用它,只走本地启发式。支付/短信/对象存储/物流见 docs/PENDING.md。
"""
import json
import os
import re
from statistics import median

from .db import get_setting

COMMISSION_MIN, COMMISSION_MAX, COMMISSION_DEFAULT = 0.07, 0.10, 0.10


def commission_rate(conn):
    try:
        v = float(get_setting(conn, "commission_rate") or COMMISSION_DEFAULT)
    except ValueError:
        v = COMMISSION_DEFAULT
    return min(max(v, COMMISSION_MIN), COMMISSION_MAX)


def commission_for(conn, goods_amount, is_platform_sale):
    if is_platform_sale:
        return 0
    return round(goods_amount * commission_rate(conn))


def delivery_fee(conn, size_class, weight_kg, region_code):
    """返回 (fee_or_None, needs_quote, note)。
    S=150 / M=200 / L=250;重量>20kg 升一档;XL 或 >30kg 单独报价;
    未开放地区不承诺配送。"""
    rules = json.loads(get_setting(conn, "delivery_rules") or "{}")
    base = (rules.get("base") or {"S": 150, "M": 200, "L": 250})
    regions = json.loads(get_setting(conn, "regions") or "[]")
    region = next((r for r in regions if r["code"] == region_code), None)
    if region is not None and not region.get("active"):
        return None, True, "region_inactive"
    if size_class == "XL" or (weight_kg or 0) > 30:
        return None, True, "xl_quote"
    cls = size_class or "M"
    if (weight_kg or 0) > 20 and cls in ("S", "M"):
        cls = {"S": "M", "M": "L"}[cls]
    fee = int(base.get(cls, 200))
    if region:
        fee += int(region.get("distance_surcharge", 0))
    return fee, False, ""


def size_class_for(weight_kg, explicit):
    if explicit in ("S", "M", "L", "XL"):
        return explicit
    w = weight_kg or 0
    if w <= 2:
        return "S"
    if w <= 10:
        return "M"
    if w <= 30:
        return "L"
    return "XL"


ORDER_TRANSITIONS = {
    "pending_payment": ("paid", "cancelled"),
    "paid": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}
BUYBACK_TRANSITIONS = {
    # 无样本时提交状态为 submitted,运营可直接进入审核(此前 submitted 只能
    # 先到 estimated 但无对应入口,属于死状态,本次修复)
    "submitted": ("estimated", "reviewing", "rejected"),
    "estimated": ("reviewing", "rejected"),
    "reviewing": ("quoted", "rejected"),
    "quoted": ("accepted", "rejected"),
    "accepted": ("pickup_scheduled",),
    "pickup_scheduled": ("inspected",),
    "inspected": ("paid",),
    "paid": ("completed",),
    "completed": (),
    "rejected": (),
}


def can_transition(mapping, cur, nxt):
    return nxt in mapping.get(cur, ())


KEYWORD_CATEGORY = [
    (r"腕時計|手表|時計|watch|rolex|ロレックス|セイコー|カシオ", "watch"),
    (r"硬貨|古銭|钱币|コイン|coin|記念硬貨|紙幣", "coin"),
    (r"フィギュア|手办|模型|figure|プラモデル|ガンプラ", "figure"),
    (r"カメラ|相机|镜头|レンズ|leica|ニコン|キャノン", "camera"),
    (r"冷蔵庫|冰箱|洗濯機|洗衣机|電子レンジ|微波炉|エアコン|空调|テレビ|电视|掃除機", "appliance"),
    (r"ソファ|沙发|テーブル|桌|椅子|ベッド|床|家具|タンス|本棚", "furniture"),
    (r"スマホ|手机|iphone|パソコン|电脑|ノートパソコン|タブレット|ipad", "digital"),
    (r"ギター|吉他|ピアノ|钢琴|バイオリン|スピーカー|音箱|アンプ", "instrument"),
    (r"本|書籍|漫画|マンガ|cd|dvd|レコード|黑胶", "book"),
    (r"バッグ|包|財布|钱包|ジャケット|衣服|スニーカー|鞋", "fashion"),
    (r"工具|ドライバー|キャンプ|釣り|ゴルフ|自転車|自行车", "tool"),
    (r"骨董|古董|壺|花瓶|絵画|茶碗|アンティーク", "antique"),
]

CONDITION_TEXT = {
    "excellent": ("美品", "近乎全新"),
    "good": ("良好", "良好"),
    "fair": ("使用感あり", "有使用痕迹"),
    "poor": ("ジャンク・要修理", "需维修/故障品"),
}



def guess_category(blob):
    for pat, slug in KEYWORD_CATEGORY:
        if re.search(pat, blob, re.IGNORECASE):
            return slug, "high"
    return None, "low"


def price_reference(conn, category_slug):
    """返回 (low, high, confidence, basis)。
    >=3 笔真实成交 -> 中位数 ±20%;否则在售挂牌价范围(标注非成交);
    皆无 -> (None, None, 'none', '').绝不编造."""
    if not category_slug:
        return None, None, "none", ""
    rows = conn.execute(
        "SELECT goods_amount FROM orders WHERE status IN ('paid','completed') "
        "AND listing_id IN (SELECT id FROM listings WHERE category_id="
        "(SELECT id FROM categories WHERE slug=?))",
        (category_slug,)).fetchall()
    amounts = [r[0] for r in rows]
    if len(amounts) >= 3:
        med = median(amounts)
        return int(med * 0.8), int(med * 1.2), "medium", \
            f"based_on_completed:{len(amounts)}"
    act = conn.execute(
        "SELECT price FROM listings WHERE status='active' AND category_id="
        "(SELECT id FROM categories WHERE slug=?)",
        (category_slug,)).fetchall()
    prices = [r[0] for r in act]
    if prices:
        return min(prices), max(prices), "low", \
            f"based_on_active_listings:{len(prices)}"
    return None, None, "none", ""


def local_ai_assist(conn, name, text, condition, price_hint):
    """本地启发式建议:分类猜测 + 日/中标题与介绍草稿 + 价格参考区间。
    所有推测均为草稿,须用户确认修改后才能发布;AI 估价不是收购承诺。"""
    blob = f"{name or ''} {text or ''}"
    category_slug, cat_conf = guess_category(blob)
    cond_ja, cond_zh = CONDITION_TEXT.get(condition or "good", ("良好", "良好"))
    title_ja = f"中古 {name}({cond_ja})" if name else ""
    title_zh = f"二手{name}({cond_zh})" if name else ""
    desc_ja = f"{name}です。状態:{cond_ja}。補足:{text or '—'}"
    desc_zh = f"{name},成色:{cond_zh}。补充:{text or '—'}"
    keywords = sorted({w for w in re.split(r"[\s、，。,]+", blob)
    if 2 <= len(w) <= 20})[:10]
    low, high, conf, basis = price_reference(conn, category_slug)
    return {"category_slug": category_slug, "category_confidence": cat_conf,
    "title_ja": title_ja, "title_zh": title_zh,
    "desc_ja": desc_ja, "desc_zh": desc_zh, "keywords": keywords,
    "price_low": low, "price_high": high,
    "price_confidence": conf, "price_basis": basis,
    "price_hint": price_hint}


def real_ai_assist(*args, **kwargs):
    """真实 AI 模型可替换接口占位,默认关闭。
    仅当 YUNO_AI_ENABLED=1 且 YUNO_AI_API_KEY 已设置时才允许外部实现调用;
    MVP 流程不调用本函数。接了才花钱,不接也能跑。"""
    if os.environ.get("YUNO_AI_ENABLED")!= "1":
        return None
    if not os.environ.get("YUNO_AI_API_KEY"):
        return None
    raise NotImplementedError("Real AI provider not configured. See docs/PENDING.md.")


def stats(conn):
    """经营统计:GMV / 销售额 / 毛利 / 费用 / 利润严格区分,绝不混算。"""
    def one(sql, args=()):
        r = conn.execute(sql, args).fetchone()
        return r[0] if r and r[0] is not None else 0
    gmv = one("SELECT SUM(goods_amount) FROM orders "
              "WHERE status IN ('paid','completed')")
    platform_sales = one("SELECT SUM(goods_amount) FROM orders "
                         "WHERE status IN ('paid','completed') AND is_platform_sale=1")
    commission_income = one("SELECT SUM(commission) FROM orders "
                            "WHERE status IN ('paid','completed') AND is_platform_sale=0")
    sold_cost = one("SELECT SUM(cost) FROM inventory WHERE status='sold'")
    buyback_cost = one("SELECT SUM(acquisition_cost) FROM buybacks "
                       "WHERE status='completed'")
    expenses = one("SELECT SUM(amount) FROM expenses")
    gross_profit = platform_sales - sold_cost
    operating_profit = commission_income + gross_profit - expenses
    return {"gmv": gmv, "platform_sales": platform_sales,
            "c2c_sales": gmv - platform_sales,
            "commission_income": commission_income,
            "sold_inventory_cost": sold_cost,
            "buyback_cost_total": buyback_cost, "expenses": expenses,
            "gross_profit": gross_profit,
            "operating_profit": operating_profit,
            "net_profit": operating_profit}
