"""第 2 阶段估价:接受同型号市场样本列表的区间计算(第 3 阶段接口)。

样本参数格式(供第 3 阶段市场搜索填充):
  comps: list[dict] 或 list[int],每项为同型号真实市场样本。
    dict 形式: {"price": int, "source": str, "date": str, "url": str}
      price 必填(日元整数);source/date/url 有则填,缺失不编造。
    int 形式: 直接视为价格,等价于 {"price": int}。
  condition: 成色等级 excellent/good/fair/poor(未知按 good)。
  new_price: 新品价(日元整数,仅用于启发式推算参考,不是市场价)。
  model_confirmed: 型号是否已由用户确认。未确认时一律走无报价分支,
    即使传入了样本或新品价也不出价(样本若无确认型号本就不应存在)。

分支(按优先级):
  1. model_confirmed=False -> kind="model_unconfirmed",low/high=None,
     不编型号、不编价格。
  2. comps 非空 -> kind="market",区间取样本价格的偏保守低位:
     low=样本价格的 25% 分位(下四分位附近),high=中位数。
     样本量再小也返回区间(1 个样本时 low=high=该价),不以"样本不足"
     为由返回空区间;但样本量、依据、置信度一律如实展示。
  3. comps 为空且 new_price 给出 -> kind="estimate_reference",
     启发式区间仅标注"推算参考",绝不冒充市场价,调用方绝不自动
     填入草稿价格。成色折扣随成色浮动(绝非单一固定比例):
     excellent 0.50 / good 0.45 / fair 0.35 / poor 0.20,
     区间为 [0.8*上限, 上限]。校准:新品 15000 时 excellent 上限 7500,
     good 上限 6750,均在"约 7500 的保守低位"口径内,绝不用新品价当二手价。
  4. 其余 -> kind="no_market_price",low/high=None,如实说明无同型号
     市场价,不编造。

平台自身的订单/挂牌数据绝不进入本函数:comps 只能是第 3 阶段从
公开市场(同型号挂牌/成交)取回的样本,平台数据不在此列。
免责(区间下方逐字展示,见 DISCLAIMER_ZH)。
"""
from statistics import median

DISCLAIMER_ZH = "此报价为AI根据现实数据做出的估价，用户可以根据自身另行填写"
DISCLAIMER_JA = "この価格はAIが実際のデータに基づいて算出した参考価格であり、ご自身で変更できます"

# 成色 -> 二手上限占新品价的比例(启发式推算参考专用,随成色浮动)
CONDITION_FACTOR = {
    "excellent": 0.50,
    "good": 0.45,
    "fair": 0.35,
    "poor": 0.20,
}


def _comp_prices(comps):
    prices = []
    for item in comps or []:
        if isinstance(item, dict):
            price = item.get("price")
        else:
            price = item
        try:
            price = int(price)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
    return sorted(prices)


def _percentile(sorted_prices, pct):
    if not sorted_prices:
        return None
    if len(sorted_prices) == 1:
        return sorted_prices[0]
    idx = int((len(sorted_prices) - 1) * pct)
    return sorted_prices[idx]


def valuation_interval(comps, condition, new_price=None, model_confirmed=True):
    """计算估价区间。返回 dict,字段见模块 docstring。

    关键字段:
      low/high: 市场区间(市场分支)或 None;启发式区间另见
        estimate_low/estimate_high,绝不混进 low/high。
      has_market_sample / sample_count / confidence / basis_zh / basis_ja
      kind: market | estimate_reference | model_unconfirmed | no_market_price
      is_market_price: 仅市场分支为 True,调用方只在 True 时自动填入草稿。
      suggested_price: 市场分支的中位数(即 high,因 high 取中位数),
        仅 is_market_price 时可用作自动填入值;其余分支为 None。
      disclaimer_zh: 逐字免责(有区间时展示)。
    """
    condition = condition if condition in CONDITION_FACTOR else "good"
    if not model_confirmed:
        return {
            "low": None, "high": None, "has_market_sample": False, "has_sample": False,
            "sample_count": 0, "confidence": "none",
            "kind": "model_unconfirmed", "is_market_price": False,
            "suggested_price": None, "estimate_low": None,
            "estimate_high": None, "condition": condition,
            "basis_zh": "型号未确认:请补细节照片(表背、刻字、序列号)或手动输入型号,"
                        "暂无市场报价,不编造型号与价格。",
            "basis_ja": "型番未確認のため市場価格を提示できません。詳細写真"
                        "(裏蓋・刻印・シリアル)または型番の手入力をお願いします。",
            "disclaimer_zh": DISCLAIMER_ZH, "disclaimer_ja": DISCLAIMER_JA,
            "comps": [],
        }
    prices = _comp_prices(comps)
    if prices:
        low = _percentile(prices, 0.25)
        high = int(median(prices))
        if low > high:
            low, high = high, low
        confidence = "high" if len(prices) >= 8 else (
            "medium" if len(prices) >= 3 else "low")
        return {
            "low": low, "high": high, "has_market_sample": True, "has_sample": True,
            "sample_count": len(prices), "confidence": confidence,
            "kind": "market", "is_market_price": True,
            "suggested_price": high, "estimate_low": None,
            "estimate_high": None, "condition": condition,
            "basis_zh": f"同型号市场样本 {len(prices)} 件的偏保守低位区间"
                        f"(低位约 25% 分位至中位数),不是成交价、不是平台收购承诺。",
            "basis_ja": f"同型番の市場サンプル {len(prices)} 件に基づく"
                        f"保守的な参考区間(成約価格でも買取約束でもありません)。",
            "disclaimer_zh": DISCLAIMER_ZH, "disclaimer_ja": DISCLAIMER_JA,
            "comps": [{"price": p} for p in prices],
        }
    if new_price is not None:
        try:
            new_price = int(new_price)
        except (TypeError, ValueError):
            new_price = None
    if new_price and new_price > 0:
        high = int(new_price * CONDITION_FACTOR[condition])
        low = int(high * 0.8)
        return {
            "low": None, "high": None, "has_market_sample": False, "has_sample": False,
            "sample_count": 0, "confidence": "low",
            "kind": "estimate_reference", "is_market_price": False,
            "suggested_price": None, "estimate_low": low,
            "estimate_high": high, "condition": condition,
            "basis_zh": "推算参考:暂无同型号市场样本,按新品价与成色做的启发式"
                        "推算,不是市场价,未自动填入草稿,仅供参考。",
            "basis_ja": "推算参考:同型番の市場サンプルがなく、新品価格と状態から"
                        "推算したもので、市場価格ではありません。",
            "disclaimer_zh": DISCLAIMER_ZH, "disclaimer_ja": DISCLAIMER_JA,
            "comps": [],
        }
    return {
        "low": None, "high": None, "has_market_sample": False, "has_sample": False,
        "sample_count": 0, "confidence": "none",
        "kind": "no_market_price", "is_market_price": False,
        "suggested_price": None, "estimate_low": None,
        "estimate_high": None, "condition": condition,
        "basis_zh": "暂无同型号市场价格样本,无法给出市场报价,请自行定价,"
                    "不编造价格。",
        "basis_ja": "同型番の市場価格サンプルがなく、市場価格を提示できません。",
        "disclaimer_zh": DISCLAIMER_ZH, "disclaimer_ja": DISCLAIMER_JA,
        "comps": [],
    }
