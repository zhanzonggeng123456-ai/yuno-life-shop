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
from .valuation import valuation_interval as _valuation_interval  # noqa: F401  (stage-3 entry, re-exported)

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


# ---- 第 2 阶段:鉴定两轴(成色等级 + 真伪)的品类映射 ----
# 敏感品类(有假货市场,照片直接给成色 + 真伪 verdict,细节照片只是建议):
#   watch 手表、coin 钱币/收藏品、antique 古董/艺术、
#   fashion 品牌包袋配饰(含服装/箱包及配饰)、figure 模型/手办/玩具/绝版收藏。
# 普通品类(无假货市场,只给成色,不做任何真伪判断):
#   furniture 家具家居、appliance 家电、digital 手机/电脑/数码、
#   camera 相机镜头、instrument 乐器音响、book 书籍影音、
#   tool 工具/运动户外、other 其他合法中古商品。
# 13 个 db.py 分类 slug 全覆盖,无遗漏、无重叠。
SENSITIVE_CATEGORIES = ("watch", "coin", "antique", "fashion", "figure")
ORDINARY_CATEGORIES = ("furniture", "appliance", "digital", "camera",
                        "instrument", "book", "tool", "other")

# 细节拍摄清单(建议,不是硬性前置条件)。数据结构: slug -> list[str],
# 供页面展示与第 3 阶段复用;清单缺失的品类返回空列表。
DETAIL_CHECKLISTS = {
    "watch": ["表盘", "表背机芯", "刻字", "序列号", "表扣", "表带", "盒证"],
    "coin": ["正面", "背面", "边缘", "铭文/年份", "评级封装", "证书"],
    "antique": ["整体", "落款/款识", "底部/胎釉", "细节纹饰", "来源凭证"],
    "fashion": ["品牌标识/Logo", "五金刻字", "序列号/内标", "走线/材质细节",
                "盒证/购物凭证"],
    "figure": ["盒装正面", "本体正面", "本体背面", "版权标识/编号", "配件齐全情况"],
}

# 细节不足的判定(启发式,本地无视觉模型,不得假装"看"出了内容):
# 敏感品类照片少于 3 张即视为细节不足 -> 低置信度 + 注明,不硬说无法确认。
DETAIL_SUFFICIENT_PHOTO_COUNT = 3


def is_sensitive_category(category_slug):
    return category_slug in SENSITIVE_CATEGORIES


def detail_checklist_for(category_slug):
    """返回该品类的细节拍摄建议清单(敏感品类才有,普通品类为空列表)。"""
    return list(DETAIL_CHECKLISTS.get(category_slug or "", []))


def appraise_two_axis(category_slug, price, condition_grade, attrs=None,
                      photo_count=1, red_flags=None):
    """第 2 阶段鉴定两轴。本地启发式 + 用户确认,结论一律标注推测性质。

    敏感品类返回成色 + 真伪 verdict(直接给结论,细节照片只是建议):
      {"condition_grade", "authenticity": {"verdict", "verdict_zh",
       "confidence", "is_guess", "note"}, "confidence",
       "detail_insufficient", "detail_note", "detail_checklist",
       "requires_manual_review", "is_determination": False, ...}
      verdict 取值 likely_genuine / suspect(仅 red_flags 明确时) /
      unconfirmed(细节不足时仍给结论倾向,但置信度 low)。
      细节不足 -> confidence="low" + detail_note 含"细节不足、低置信度",
      不硬说无法确认;明确红旗/高风险/高价值 -> requires_manual_review。
      真伪结论一律标注"AI 推测,须人工复核确认"。
    普通品类返回只有成色的 dict,绝不含 authenticity/verdict/
    authenticity_risk 等任何真伪字段,也不触发真伪复核。
    本地无视觉模型、无 OCR:结论依据只是照片数量与用户输入的
    属性/红旗,绝不声称逐张"看"出了真伪内容。
    """
    attrs = attrs or {}
    red_flags = list(red_flags or [])
    if attrs.get("red_flag"):
        red_flags.append(str(attrs.get("red_flag")))
    grade = condition_grade or "good"
    if is_sensitive_category(category_slug):
        try:
            count = int(photo_count or 0)
        except (TypeError, ValueError):
            count = 0
        insufficient = count < DETAIL_SUFFICIENT_PHOTO_COUNT
        if red_flags:
            verdict, verdict_zh = "suspect", "存疑(有明确红旗)"
        elif insufficient:
            verdict, verdict_zh = "likely_genuine", "倾向正品(细节不足,低置信度)"
        else:
            verdict, verdict_zh = "likely_genuine", "倾向正品"
        confidence = "low" if (insufficient or red_flags) else "medium"
        requires_review = bool(red_flags) or is_high_value(category_slug, price)
        detail_note = ("细节不足、低置信度:细节照片不足,结论置信度低,"
                       "建议补拍细节照片以提高准确度;不是无法确认。"
                       if insufficient else "")
        return {
            "condition_grade": grade,
            "authenticity": {
                "verdict": verdict, "verdict_zh": verdict_zh,
                "confidence": confidence, "is_guess": True,
                "note": "AI 推测,须人工复核确认,不是确定结论。",
            },
            "confidence": confidence,
            "detail_insufficient": insufficient,
            "detail_note": detail_note,
            "detail_checklist": detail_checklist_for(category_slug),
            "photo_count": count,
            "red_flags": red_flags,
            "requires_manual_review": requires_review,
            "is_determination": False,
            "note_zh": "鉴定为本地启发式推测(照片数量与用户输入,无视觉模型),"
                       "真伪结论是 AI 推测,须人工复核确认。",
            "note_ja": "鑑定はローカルヒューリスティックによる推測であり、"
                       "真贋の結論は AI の推測で、人の確認が必要です。",
        }
    return {
        "condition_grade": grade,
        "confidence": "medium",
        "is_guess": True,
        "photo_count": photo_count,
        "requires_manual_review": False,
        "is_determination": False,
        "note_zh": "普通品类只做成色评估,不做真伪判断。",
        "note_ja": "通常カテゴリは状態評価のみで、真贋判定は行いません。",
    }


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
