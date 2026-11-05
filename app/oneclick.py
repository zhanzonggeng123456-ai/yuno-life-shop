"""AI 一键链路:拍照/上传 -> 一键识别 -> 一键上架。

全部本地启发式,零付费 API、零外部调用:
- 识别依据只有三样:用户输入的商品名/补充描述、品类属性模式、
  本地历史数据(真实订单与在售挂牌)。没有任何视觉模型参与。
- 所有识别结果一律标注为"推测",全部可人工修改;识别结论、
  鉴定结论、估价区间都不是确定事实,更不是收购承诺。
- 真实视觉模型只留可替换接口 real_vision_assist() 与环境变量占位,
  默认关闭,见 docs/PENDING.md。接了才花钱,不接也能跑。
"""
import os
import re

from .business import (CONDITION_TEXT, guess_category, local_ai_assist,
                       price_reference)

HIGH_VALUE_CATEGORIES = ("watch", "coin", "antique")
HIGH_VALUE_THRESHOLD = 100000

GUESS_NOTE_JA = "推測(ローカルヒューリスティックによる提案であり、確定事実ではありません)"
GUESS_NOTE_ZH = "推测(本地启发式建议,不是确定事实)"


def is_high_value(category_slug, price):
    """高价值商品:手表/钱币/古董且 >=100000 日元,须人工复核后方可交易。"""
    try:
        return category_slug in HIGH_VALUE_CATEGORIES and int(price) >= HIGH_VALUE_THRESHOLD
    except (TypeError, ValueError):
        return False


# 品牌关键词 -> 建议品牌(全部为"推测",命中即 low/high 之分见 recognize)
BRAND_PATTERNS = [
    (r"ロレックス|rolex", "Rolex"),
    (r"セイコー|seiko", "Seiko"),
    (r"カシオ|casio", "Casio"),
    (r"オメガ|omega", "Omega"),
    (r"アップル|apple|iphone|ipad", "Apple"),
    (r"ソニー|sony", "Sony"),
    (r"ニコン|nikon", "Nikon"),
    (r"キャノン|canon", "Canon"),
    (r"ライカ|leica", "Leica"),
    (r"任天堂|nintendo|switch", "Nintendo"),
    (r"ルイ・ヴィトン|ルイヴィトン|vuitton", "Louis Vuitton"),
    (r"グッチ|gucci", "Gucci"),
    (r"シャネル|chanel", "Chanel"),
    (r"エルメス|hermes", "Hermes"),
    (r"ナイキ|nike", "Nike"),
    (r"アディダス|adidas", "Adidas"),
    (r"ダイソン|dyson", "Dyson"),
    (r"パナソニック|panasonic", "Panasonic"),
    (r"シャープ|sharp", "Sharp"),
]

MATERIAL_PATTERNS = [
    (r"皮革|レザー|leather|牛皮|羊皮", "皮革"),
    (r"金属|メタル|metal|ステンレス", "金属"),
    (r"木製|木材|ウッド|wood|实木", "木材"),
    (r"プラスチック|树脂|塑料", "塑料"),
    (r"ガラス|玻璃", "玻璃"),
    (r"布|ファブリック|fabric|棉|麻", "布料"),
    (r"セラミック|陶器|陶瓷", "陶瓷"),
]

CONDITION_PATTERNS = [
    (r"美品|新品同様|ほぼ新品|全新|九成新|近乎全新", "excellent"),
    (r"ジャンク|故障|壊れ|要修理|需维修", "poor"),
    (r"使用感|傷あり|有使用痕迹|划痕|磨损", "fair"),
]

MODEL_PATTERN = re.compile(r"\b[A-Z]{1,4}[- ]?\d{3,4}[A-Z]?\b")


def _first_match(patterns, blob):
    for pat, value in patterns:
        if re.search(pat, blob, re.IGNORECASE):
            return value
    return ""


def recognize(conn, name, text, condition, price_hint):
    """一键识别:返回全部标注为推测的建议字段。

    每个建议项都是 {"field","value","confidence","basis","is_guess": True}。
    调用方必须把 is_guess 原样展示给用户,且全部字段可人工修改。
    """
    blob = f"{name or ''} {text or ''}"
    category_slug, cat_conf = guess_category(blob)
    brand = _first_match(BRAND_PATTERNS, blob)
    material = _first_match(MATERIAL_PATTERNS, blob)
    m = MODEL_PATTERN.search(blob.upper())
    model = m.group(0).strip() if m else ""
    cond_guess, cond_basis = condition, "user_input"
    for pat, grade in CONDITION_PATTERNS:
        if re.search(pat, blob, re.IGNORECASE):
            cond_guess, cond_basis = grade, "keyword"
            break
    suggestions = []
    if category_slug:
        suggestions.append({"field": "category_slug", "value": category_slug,
                            "confidence": cat_conf, "basis": "keyword",
                            "is_guess": True})
    if brand:
        suggestions.append({"field": "brand", "value": brand,
                            "confidence": "high", "basis": "keyword",
                            "is_guess": True})
    if model:
        suggestions.append({"field": "model", "value": model,
                            "confidence": "low", "basis": "pattern",
                            "is_guess": True})
    if material:
        suggestions.append({"field": "material", "value": material,
                            "confidence": "medium", "basis": "keyword",
                            "is_guess": True})
    suggestions.append({"field": "condition_grade", "value": cond_guess,
                        "confidence": "medium" if cond_basis == "keyword" else "low",
                        "basis": cond_basis, "is_guess": True})
    return {"category_slug": category_slug, "category_confidence": cat_conf,
            "brand": brand, "model": model, "material": material,
            "condition_guess": cond_guess, "condition_basis": cond_basis,
            "suggestions": suggestions, "is_guess": True,
            "guess_note_ja": GUESS_NOTE_JA, "guess_note_zh": GUESS_NOTE_ZH}


def appraise(category_slug, price, condition_grade, attrs):
    """AI 鉴定(启发式风险提示,绝非真伪判定)。

    返回成色等级、真伪风险等级与风险因素、高价值人工复核标记。
    risk 只是"需要人工多看一眼"的程度,不是"真/假"的结论。
    """
    attrs = attrs or {}
    factors = []
    if category_slug == "watch" and not attrs.get("accessories"):
        factors.append("watch_no_accessories")
    if category_slug == "coin" and not attrs.get("grading_org"):
        factors.append("coin_no_grading_org")
    if category_slug == "coin" and not attrs.get("authenticity"):
        factors.append("coin_authenticity_unknown")
    if category_slug == "antique" and not attrs.get("provenance"):
        factors.append("antique_no_provenance")
    if category_slug in HIGH_VALUE_CATEGORIES and not attrs.get("brand"):
        factors.append("high_value_brand_unconfirmed")
    risk = "low" if not factors else ("medium" if len(factors) == 1 else "high")
    requires_review = is_high_value(category_slug, price)
    note_ja = ("鑑定はローカルヒューリスティックによるリスク提示であり、"
               "真贋の判定ではありません。")
    note_zh = "鉴定为本地启发式风险提示,不是真伪判定,仅供人工复核参考。"
    if requires_review:
        note_ja += "高額品のため、鑑定承認前は取引できません。"
        note_zh += "高价值商品,鉴定通过前不可交易。"
    return {"condition_grade": condition_grade or "good",
            "authenticity_risk": risk, "risk_factors": factors,
            "requires_manual_review": requires_review,
            "is_determination": False, "note_ja": note_ja, "note_zh": note_zh}


def valuation_for(conn, category_slug):
    """AI 估价:只用本地真实订单与挂牌数据,无样本时不编价。"""
    low, high, conf, basis = price_reference(conn, category_slug)
    if low is None:
        basis_ja = ("サンプル不足:同カテゴリの実際の成約・出品データがなく、"
                    "参考価格を提示できません。ご自身で価格を設定してください。")
        basis_zh = ("缺少可靠成交样本:平台暂无同类真实成交与在售挂牌可供参考,"
                    "无法给出参考价,请自行定价。")
    elif basis.startswith("based_on_completed"):
        n = basis.split(":")[1]
        basis_ja = f"プラットフォームの実際の成約 {n} 件の中央値 ±20%"
        basis_zh = f"基于平台真实成交 {n} 件的中位数 ±20%"
    else:
        n = basis.split(":")[1]
        basis_ja = f"出品中の価格 {n} 件(成約価格ではなく、信頼度は低)"
        basis_zh = f"基于在售挂牌价 {n} 件(挂牌价,不是成交价,可信度低)"
    return {"low": low, "high": high, "confidence": conf, "basis": basis,
            "has_sample": low is not None,
            "basis_ja": basis_ja, "basis_zh": basis_zh}


def build_draft(conn, name, text, condition, price_hint, rec):
    """识别 + 估价结果 inline 生成可编辑草稿(日/中标题、介绍、规格、成色描述、关键词)。

    草稿只是预填,发布前用户可全部修改;点"一键上架"才是用户确认。
    """
    base = local_ai_assist(conn, name, text, condition, price_hint)
    cond_ja, cond_zh = CONDITION_TEXT.get(
        rec.get("condition_guess") or condition or "good", ("良好", "良好"))
    spec_parts_ja, spec_parts_zh = [], []
    if rec.get("brand"):
        spec_parts_ja.append(f"ブランド(推測):{rec['brand']}")
        spec_parts_zh.append(f"品牌(推测):{rec['brand']}")
    if rec.get("model"):
        spec_parts_ja.append(f"型番(推測):{rec['model']}")
        spec_parts_zh.append(f"型号(推测):{rec['model']}")
    if rec.get("material"):
        spec_parts_ja.append(f"素材(推測):{rec['material']}")
        spec_parts_zh.append(f"材质(推测):{rec['material']}")
    return {"category_slug": rec.get("category_slug"),
            "title_ja": base["title_ja"], "title_zh": base["title_zh"],
            "desc_ja": base["desc_ja"], "desc_zh": base["desc_zh"],
            "keywords": base["keywords"],
            "condition_grade": rec.get("condition_guess") or condition or "good",
            "condition_desc_ja": cond_ja, "condition_desc_zh": cond_zh,
            "spec_ja": " / ".join(spec_parts_ja),
            "spec_zh": " / ".join(spec_parts_zh),
            "attrs": {k: rec[k] for k in ("brand", "model", "material")
                      if rec.get(k)}}


def real_vision_assist(*args, **kwargs):
    """真实视觉模型可替换接口占位,默认关闭。

    仅当 YUNO_VISION_ENABLED=1 且 YUNO_VISION_API_KEY 已设置时才允许
    外部实现调用;一键链路永远不调用本函数,只走本地启发式。
    接了才花钱,不接也能跑。见 docs/PENDING.md。
    """
    if os.environ.get("YUNO_VISION_ENABLED") != "1":
        return None
    if not os.environ.get("YUNO_VISION_API_KEY"):
        return None
    raise NotImplementedError("Real vision provider not configured. See docs/PENDING.md.")
