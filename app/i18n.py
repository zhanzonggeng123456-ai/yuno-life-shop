"""i18n: ja/zh complete, en keys reserved. Default ja."""
STRINGS = {
    "site_name": {"ja": "Yuno Life", "zh": "Yuno Life", "en": "Yuno Life"},
    "tagline": {"ja": "坂戸市から始まる、AI搭載の総合中古取引プラットフォーム",
                "zh": "从坂户市开始的 AI 综合中古交易平台",
                "en": "An AI-powered secondhand marketplace starting in Sakado"},
    "home": {"ja": "ホーム", "zh": "首页", "en": "Home"},
    "publish": {"ja": "出品する", "zh": "发布商品", "en": "Sell an item"},
    "oneclick": {"ja": "AI一括出品", "zh": "AI一键发布", "en": "AI one-click listing"},
    "my_page": {"ja": "マイページ", "zh": "我的主页", "en": "My page"},
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
}


def t(lang, key):
    d = STRINGS.get(key, {})
    return d.get(lang) or d.get("ja") or key


def lang_from(request):
    q = request.query_params.get("lang")
    if q in ("ja", "zh", "en"):
        return q
    c = request.cookies.get("yuno_lang")
    if c in ("ja", "zh", "en"):
        return c
    return "ja"
