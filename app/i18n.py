"""i18n: ja/zh complete, en keys reserved. Default ja.

Language selection (stage 1, three options only):
  - manual: ?lang=ja | ?lang=zh (also legacy ?lang=en / cookie en) writes
    cookie yuno_lang and wins over Accept-Language afterwards.
  - follow-system: no manual cookie, or ?lang=system (which clears the
    cookie): parse Accept-Language, zh* -> zh, ja* -> ja, anything else
    (including missing header) -> ja.
"""
STRINGS = {
    "site_name": {"ja": "Yuno Life", "zh": "Yuno Life", "en": "Yuno Life"},
    "tagline": {"ja": "坂戸市から始まる、AI搭載の総合中古取引プラットフォーム",
                "zh": "从坂户市开始的 AI 综合中古交易平台",
                "en": "An AI-powered secondhand marketplace starting in Sakado"},
    "home": {"ja": "ホーム", "zh": "首页", "en": "Home"},
    "marketplace": {"ja": "マーケット", "zh": "市场", "en": "Market"},
    "market": {"ja": "成約相場", "zh": "成交行情", "en": "Market trends"},
    "trade": {"ja": "取引", "zh": "交易", "en": "Trade"},
    "publish": {"ja": "出品する", "zh": "发布商品", "en": "Sell an item"},
    "oneclick": {"ja": "AI一括出品", "zh": "AI一键发布", "en": "AI one-click listing"},
    "auction": {"ja": "オークション", "zh": "拍卖", "en": "Auction"},
    "services": {"ja": "サービス", "zh": "服务", "en": "Services"},
    "support": {"ja": "サポート", "zh": "客服", "en": "Support"},
    "my_page": {"ja": "マイページ", "zh": "个人中心", "en": "My page"},
    "admin": {"ja": "管理画面", "zh": "管理后台", "en": "Admin"},
    "login": {"ja": "ログイン", "zh": "登录", "en": "Log in"},
    "register": {"ja": "新規登録", "zh": "注册", "en": "Register"},
    "logout": {"ja": "ログアウト", "zh": "退出登录", "en": "Log out"},
    "email": {"ja": "メールアドレス", "zh": "邮箱", "en": "Email"},
    "password": {"ja": "パスワード", "zh": "密码", "en": "Password"},
    "display_name": {"ja": "表示名", "zh": "昵称", "en": "Display name"},
    "search": {"ja": "検索", "zh": "搜索", "en": "Search"},
    "category": {"ja": "カテゴリー", "zh": "分类", "en": "Category"},
    "all": {"ja": "すべて", "zh": "全部", "en": "All"},
    "price": {"ja": "価格", "zh": "价格", "en": "Price"},
    "buy_now": {"ja": "今すぐ購入", "zh": "立即购买", "en": "Buy now"},
    "make_offer": {"ja": "価格交渉する", "zh": "出价议价", "en": "Make an offer"},
    "sell_to_platform": {"ja": "プラットフォームに売却申請", "zh": "申请卖给平台",
                         "en": "Request platform buyout"},
    "platform_owned": {"ja": "プラットフォーム自営", "zh": "平台自营", "en": "Platform-owned"},
    "today_deal": {"ja": "今日の特価", "zh": "今日特价", "en": "Today's deal"},
    "mock_payment_note": {
        "ja": "※本決済はシミュレーションです。実際の請求は発生しません。",
        "zh": "※本次支付为模拟支付，不会产生真实扣款。",
        "en": "※ This payment is simulated. No real charge occurs."},
    "mock_badge": {"ja": "", "zh": "", "en": "[SIMULATED]"},
    "no_data": {"ja": "まだデータがありません", "zh": "暂无数据", "en": "No data yet"},
    "region": {"ja": "地域", "zh": "地区", "en": "Region"},
    "condition": {"ja": "状態", "zh": "成色", "en": "Condition"},
    "commission": {"ja": "手数料", "zh": "佣金", "en": "Commission"},
    "delivery_fee": {"ja": "配送料", "zh": "运费", "en": "Delivery fee"},
    "total": {"ja": "合計", "zh": "合计", "en": "Total"},
    "orders": {"ja": "注文", "zh": "订单", "en": "Orders"},
    "messages": {"ja": "メッセージ", "zh": "站内消息", "en": "Messages"},
    "offers": {"ja": "価格交渉", "zh": "议价", "en": "Offers"},
    "buyback": {"ja": "買取申請", "zh": "买断申请", "en": "Buyout request"},
    "inventory": {"ja": "在庫", "zh": "库存", "en": "Inventory"},
    "submit": {"ja": "送信", "zh": "提交", "en": "Submit"},
    "back": {"ja": "戻る", "zh": "返回", "en": "Back"},
    "browse": {"ja": "商品を探す", "zh": "浏览商品", "en": "Browse"},
    # --- stage 1 additions ---
    "language": {"ja": "言語", "zh": "语言", "en": "Language"},
    "lang_zh": {"ja": "中国語", "zh": "中文", "en": "Chinese"},
    "lang_ja": {"ja": "日本語", "zh": "日本語", "en": "Japanese"},
    "lang_system": {"ja": "システムに従う", "zh": "跟随系统", "en": "Follow system"},
    "rules": {"ja": "規約・ルール", "zh": "规则与说明", "en": "Rules"},
    "terms": {"ja": "利用規約", "zh": "条款", "en": "Terms"},
    "privacy": {"ja": "プライバシーポリシー", "zh": "隐私", "en": "Privacy"},
    "returns": {"ja": "返品・紛争", "zh": "退货争议", "en": "Returns & disputes"},
    "prohibited": {"ja": "出品禁止物", "zh": "禁售规则", "en": "Prohibited items"},
    "tax_inclusive": {"ja": "表示価格はすべて税込です。",
                      "zh": "所有价格均为含税价。",
                      "en": "All prices include tax."},
    "overview": {"ja": "概要", "zh": "概览", "en": "Overview"},
    "users": {"ja": "ユーザー", "zh": "用户", "en": "Users"},
    "listings": {"ja": "商品", "zh": "商品", "en": "Listings"},
    "deliveries": {"ja": "配送", "zh": "配送", "en": "Deliveries"},
    "refunds": {"ja": "返金", "zh": "退款", "en": "Refunds"},
    "disputes": {"ja": "紛争", "zh": "争议", "en": "Disputes"},
    "high_value": {"ja": "高額商品審査", "zh": "高价值审核", "en": "High-value review"},
    "alerts": {"ja": "アラート", "zh": "预警", "en": "Alerts"},
    "profit": {"ja": "利益分析", "zh": "利润分析", "en": "Profit analysis"},
    "agents": {"ja": "AI運営", "zh": "AI 运营", "en": "AI operations"},
    "settings": {"ja": "設定", "zh": "参数设置", "en": "Settings"},
    "expenses": {"ja": "費用", "zh": "费用", "en": "Expenses"},
    "trade_panel": {"ja": "取引パネル", "zh": "交易面板", "en": "Trade panel"},
    "my_listings": {"ja": "自分の商品", "zh": "我的商品", "en": "My listings"},
    "my_orders": {"ja": "自分の注文", "zh": "我的订单", "en": "My orders"},
    "offers_in": {"ja": "受けた価格交渉", "zh": "收到的议价", "en": "Offers received"},
    "offers_out": {"ja": "送った価格交渉", "zh": "我发出的议价", "en": "Offers sent"},
    "my_buybacks": {"ja": "自分の買取申請", "zh": "我的买断申请", "en": "My buyout requests"},
    "service_order": {"ja": "サービス注文", "zh": "服务订单", "en": "Service order"},
    "place_service_order": {"ja": "サービスを注文する", "zh": "下服务订单",
                            "en": "Place a service order"},
    "login_required": {"ja": "ログインが必要です", "zh": "需要登录后使用",
                       "en": "Login required"},
}


def t(lang, key):
    d = STRINGS.get(key, {})
    return d.get(lang) or d.get("ja") or key


def accept_language_lang(request):
    """Follow-system mapping: zh* -> zh, ja* -> ja, else (incl. missing) -> ja."""
    raw = request.headers.get("accept-language", "") or ""
    for part in raw.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        primary = tag.split("-")[0]
        if primary == "zh":
            return "zh"
        if primary == "ja":
            return "ja"
        # First explicit language wins; anything else falls back to ja.
        return "ja"
    return "ja"


def lang_from(request):
    q = request.query_params.get("lang")
    if q in ("ja", "zh", "en"):
        return q
    if q == "system":
        return accept_language_lang(request)
    c = request.cookies.get("yuno_lang")
    if c in ("ja", "zh", "en"):
        return c
    if c == "system":
        return accept_language_lang(request)
    return accept_language_lang(request)
