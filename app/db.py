"""SQLite 数据层。标准库 sqlite3,无外部依赖,本地文件数据库。

环境变量:
  YUNO_DB_PATH:数据库文件路径,默认 <项目>/data/yuno.db
  YUNO_UPLOAD_DIR:图片存储目录,默认 <项目>/uploads
"""
import json
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("YUNO_DB_PATH", BASE / "data" / "yuno.db"))
UPLOAD_DIR = Path(os.environ.get("YUNO_UPLOAD_DIR", BASE / "uploads"))

# 13 大类:slug -> (日文名, 中文名, 英文名, 属性定义)
# 属性定义: key / label_ja / label_zh / label_en / type(text|number|select)
CATEGORIES = [
    ("furniture", "家具・家居用品", "家具家居用品", "Furniture & Home", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("material", "素材", "材质", "Material", "text"),
        ("size", "サイズ", "尺寸", "Size", "text"),
        ("color", "色", "颜色", "Color", "text"),
    ]),
    ("appliance", "家電・キッチン家電", "家用电器/厨房电器", "Appliances", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("model", "型番", "型号", "Model", "text"),
        ("year", "製造年", "制造年份", "Year", "number"),
        ("working_status", "動作状態", "工作状态", "Working status", "text"),
        ("size", "サイズ", "尺寸", "Size", "text"),
        ("weight", "重量(kg)", "重量(kg)", "Weight (kg)", "number"),
    ]),
    ("digital", "スマホ・PC・デジタル機器", "手机/电脑/数码设备", "Digital Devices", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("model", "型番", "型号", "Model", "text"),
        ("storage", "容量", "存储容量", "Storage", "text"),
        ("battery", "バッテリー状態", "电池状态", "Battery", "text"),
        ("year", "製造年", "制造年份", "Year", "number"),
    ]),
    ("watch", "中古時計", "中古机械表/石英表/怀表", "Watches", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("model", "型番", "型号", "Model", "text"),
        ("movement", "ムーブメント", "机芯", "Movement", "text"),
        ("year", "製造年", "年份", "Year", "number"),
        ("diameter", "ケース径(mm)", "表径(mm)", "Diameter (mm)", "number"),
        ("accessories", "付属品", "附件", "Accessories", "text"),
        ("repair_history", "修理履歴", "维修记录", "Repair history", "text"),
    ]),
    ("coin", "古銭・記念貨幣", "古钱币/纪念币/纸币", "Coins & Currency", [
        ("country", "国", "国家", "Country", "text"),
        ("era", "年代", "年代", "Era", "text"),
        ("denomination", "額面", "面额", "Denomination", "text"),
        ("material", "材質", "材质", "Material", "text"),
        ("grading_org", "鑑定機関", "评级机构", "Grading org", "text"),
        ("grade_score", "グレード", "评级分数", "Grade score", "text"),
        ("authenticity", "真贋状態", "真伪状态", "Authenticity", "text"),
    ]),
    ("figure", "模型・フィギュア・玩具", "模型/手办/玩具/绝版收藏", "Figures & Toys", [
        ("maker", "メーカー", "厂商", "Maker", "text"),
        ("work", "作品", "作品", "Work", "text"),
        ("scale", "スケール", "比例", "Scale", "text"),
        ("version", "バージョン", "版本", "Version", "text"),
        ("box_condition", "箱の状態", "盒装状态", "Box condition", "text"),
        ("missing_parts", "欠品", "缺件情况", "Missing parts", "text"),
    ]),
    ("camera", "カメラ・レンズ", "老相机/镜头/摄影设备", "Cameras", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("model", "型番", "型号", "Model", "text"),
        ("lens", "レンズ", "镜头", "Lens", "text"),
        ("year", "製造年", "年份", "Year", "number"),
        ("shutter_status", "シャッター状態", "快门状态", "Shutter status", "text"),
    ]),
    ("antique", "骨董・美術品", "古董/艺术品/老物件", "Antiques & Art", [
        ("era", "時代", "年代", "Era", "text"),
        ("origin", "産地", "产地", "Origin", "text"),
        ("material", "材質", "材质", "Material", "text"),
        ("provenance", "来歴", "来源", "Provenance", "text"),
        ("appraisal_status", "鑑定状態", "鉴定状态", "Appraisal status", "text"),
    ]),
    ("instrument", "楽器・オーディオ", "乐器及音响设备", "Instruments & Audio", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("model", "型番", "型号", "Model", "text"),
        ("year", "製造年", "年份", "Year", "number"),
        ("condition_note", "状態", "成色说明", "Condition", "text"),
    ]),
    ("book", "書籍・映像ソフト", "书籍/影音制品", "Books & Media", [
        ("author", "著者", "作者", "Author", "text"),
        ("publisher", "出版社", "出版社", "Publisher", "text"),
        ("year", "出版年", "出版年份", "Year", "number"),
        ("language", "言語", "语言", "Language", "text"),
    ]),
    ("fashion", "衣類・バッグ・小物", "服装/箱包及配饰", "Fashion", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("size", "サイズ", "尺码", "Size", "text"),
        ("material", "素材", "材质", "Material", "text"),
        ("color", "色", "颜色", "Color", "text"),
    ]),
    ("tool", "工具・スポーツ・アウトドア", "工具/运动及户外设备", "Tools & Outdoors", [
        ("brand", "ブランド", "品牌", "Brand", "text"),
        ("type", "種類", "类型", "Type", "text"),
        ("condition_note", "状態", "成色说明", "Condition", "text"),
    ]),
    ("other", "その他合法中古品", "其他合法中古商品", "Other", [
        ("note", "備考", "备注", "Note", "text"),
    ]),
]

DEFAULT_SETTINGS = {
    # 佣金率:需求书 7%~10%,后台可调,默认 10%
    "commission_rate": "0.10",
    # 首期只开放坂户市;鹤岛/川越/东松山在列表里但默认关闭,后续可开
    "regions": json.dumps([
        {"code": "sakado", "name_ja": "坂戸市", "name_zh": "坂户市", "name_en": "Sakado",
         "active": True, "distance_surcharge": 0},
        {"code": "tsurugashima", "name_ja": "鶴ヶ島市", "name_zh": "鹤岛市",
         "name_en": "Tsurugashima", "active": False, "distance_surcharge": 50},
        {"code": "kawagoe", "name_ja": "川越市", "name_zh": "川越市", "name_en": "Kawagoe",
         "active": False, "distance_surcharge": 100},
        {"code": "higashimatsuyama", "name_ja": "東松山市", "name_zh": "东松山市",
         "name_en": "Higashimatsuyama", "active": False, "distance_surcharge": 100},
    ], ensure_ascii=False),
    # 买断报价参数:只是建议区间的输入,最终报价由运营人工输入,绝非固定比例
    "buyback_params": json.dumps({
        "note_ja": "AI参考区间与建议报价的计算参数,最终报价须人工确认",
        "note_zh": "AI参考区间与建议报价的计算参数,最终报价须人工确认",
        "by_category": {"appliance": 0.15, "furniture": 0.15, "digital": 0.20,
                        "watch": 0.35, "coin": 0.40, "figure": 0.25,
                        "camera": 0.25, "antique": 0.30, "instrument": 0.20,
                        "book": 0.10, "fashion": 0.15, "tool": 0.15,
                        "other": 0.10},
        "inventory_penalty_per_unit": 0.02,
        "max_inventory_penalty": 0.10,
    }, ensure_ascii=False),
    # 增值服务目录:家居清洁 2000 日元/小时(可配置),其余按件计价
    "service_prices": json.dumps({
        "cleaning_home": {"name_ja": "ハウスクリーニング", "name_zh": "家居清洁",
                          "unit": "hour", "price": 2000},
        "cleaning_item": {"name_ja": "商品クリーニング", "name_zh": "商品清洁整理",
                          "unit": "item", "price": 1000},
        "inspection": {"name_ja": "商品検品", "name_zh": "商品检测",
                       "unit": "item", "price": 1500},
        "photo_listing": {"name_ja": "撮影・出品代行", "name_zh": "商品拍摄及代上架",
                          "unit": "item", "price": 2000},
        "appraisal_visit": {"name_ja": "出張査定", "name_zh": "上门估价",
                            "unit": "item", "price": 3000},
        "transport_small": {"name_ja": "小口運搬", "name_zh": "小件搬运",
                            "unit": "item", "price": 2500},
        "consignment": {"name_ja": "委託販売", "name_zh": "商品代售",
                        "unit": "item", "price": 0},
    }, ensure_ascii=False),
    # 配送规则:轻小件 150 日元起,按尺寸分档;XL(大型家具/冰箱/洗衣机等)单独报价
    "delivery_rules": json.dumps({
        "base": {"S": 150, "M": 200, "L": 250},
        "express_extra": 100,
        "xl_note_ja": "大型商品は別途見積もり。統一料金は適用されません。",
        "xl_note_zh": "大型商品单独报价,不适用统一低价。",
    }, ensure_ascii=False),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL, salt TEXT NOT NULL, display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user', phone TEXT DEFAULT '',
  region TEXT DEFAULT 'sakado', is_active INTEGER DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL,
  name_ja TEXT, name_zh TEXT, name_en TEXT, attrs_json TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS listings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER,
  category_id INTEGER NOT NULL, title_ja TEXT, title_zh TEXT,
  desc_ja TEXT, desc_zh TEXT, price INTEGER NOT NULL,
  condition_grade TEXT DEFAULT '', attrs_json TEXT DEFAULT '{}',
  status TEXT DEFAULT 'active', is_platform_owned INTEGER DEFAULT 0,
  is_today_deal INTEGER DEFAULT 0, discount_price INTEGER,
  discount_until TEXT, is_featured INTEGER DEFAULT 0,
  inspection_record TEXT DEFAULT '', region TEXT DEFAULT 'sakado',
  size_class TEXT DEFAULT 'M', weight_kg REAL DEFAULT 0,
  demo INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS images(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  filename TEXT NOT NULL, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS oneclick_drafts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
  photo TEXT DEFAULT '', name TEXT DEFAULT '', text TEXT DEFAULT '',
  condition_grade TEXT DEFAULT 'good', price_hint INTEGER,
  recognition_json TEXT DEFAULT '{}', draft_json TEXT DEFAULT '{}',
  appraisal_json TEXT DEFAULT '{}', valuation_json TEXT DEFAULT '{}',
  status TEXT DEFAULT 'uploaded', listing_id INTEGER,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS offers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  buyer_id INTEGER NOT NULL, amount INTEGER NOT NULL,
  status TEXT DEFAULT 'pending', counter_amount INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  buyer_id INTEGER NOT NULL, sender_id INTEGER NOT NULL,
  receiver_id INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER NOT NULL,
  seller_id INTEGER, listing_id INTEGER NOT NULL, goods_amount INTEGER NOT NULL,
  commission INTEGER NOT NULL DEFAULT 0, delivery_fee INTEGER,
  total INTEGER NOT NULL, status TEXT DEFAULT 'pending_payment',
  payment_ref TEXT, idempotency_key TEXT UNIQUE, is_platform_sale INTEGER DEFAULT 0,
  demo INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS order_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  event TEXT NOT NULL, amount_delta INTEGER DEFAULT 0, note TEXT DEFAULT '',
  created_at TEXT);
CREATE TABLE IF NOT EXISTS buybacks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  seller_id INTEGER NOT NULL, status TEXT DEFAULT 'submitted',
  ai_low INTEGER, ai_high INTEGER, ai_confidence TEXT DEFAULT '',
  ai_basis TEXT DEFAULT '', quote INTEGER, pickup_at TEXT DEFAULT '',
  inspection_note TEXT DEFAULT '', acquisition_cost INTEGER,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS inventory(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  buyback_id INTEGER, cost INTEGER NOT NULL, fees INTEGER DEFAULT 0,
  status TEXT DEFAULT 'in_stock', created_at TEXT);
CREATE TABLE IF NOT EXISTS expenses(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
  amount INTEGER NOT NULL, note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS auctions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL UNIQUE,
  start_price INTEGER NOT NULL, reserve_price INTEGER DEFAULT 0,
  min_increment INTEGER NOT NULL DEFAULT 100, buy_now_price INTEGER,
  starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
  deposit_required INTEGER DEFAULT 0, deposit_amount INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active', created_at TEXT);
CREATE TABLE IF NOT EXISTS bids(
  id INTEGER PRIMARY KEY AUTOINCREMENT, auction_id INTEGER NOT NULL,
  bidder_id INTEGER NOT NULL, amount INTEGER NOT NULL,
  proxy_max INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS deposits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, auction_id INTEGER NOT NULL,
  bidder_id INTEGER NOT NULL, amount INTEGER NOT NULL,
  status TEXT DEFAULT 'held', created_at TEXT);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  reviewer_id INTEGER NOT NULL, reviewee_id INTEGER NOT NULL,
  rating INTEGER NOT NULL, comment TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS listing_follows(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
  listing_id INTEGER NOT NULL, created_at TEXT,
  UNIQUE(user_id, listing_id));
CREATE TABLE IF NOT EXISTS deliveries(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  kind TEXT NOT NULL, courier_id INTEGER, scheduled_at TEXT DEFAULT '',
  status TEXT DEFAULT 'requested', pickup_photo TEXT DEFAULT '',
  delivery_photo TEXT DEFAULT '', note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS service_orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
  listing_id INTEGER, buyback_id INTEGER, kind TEXT NOT NULL,
  hours REAL DEFAULT 0, qty INTEGER DEFAULT 1, unit_price INTEGER NOT NULL,
  amount INTEGER NOT NULL, status TEXT DEFAULT 'requested',
  note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS refunds(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  applicant_id INTEGER NOT NULL, reason TEXT NOT NULL,
  evidence TEXT DEFAULT '', status TEXT DEFAULT 'requested',
  decision TEXT DEFAULT '', decision_by INTEGER, decision_note TEXT DEFAULT '',
  created_at TEXT);
CREATE TABLE IF NOT EXISTS disputes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  reporter_id INTEGER NOT NULL, reason TEXT NOT NULL,
  status TEXT DEFAULT 'open', decision TEXT DEFAULT '',
  decided_by INTEGER, note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS hv_reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL UNIQUE,
  identity_verified INTEGER DEFAULT 0, appraisal_status TEXT DEFAULT 'pending',
  appraisal_note TEXT DEFAULT '', reviewer_id INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS payment_intents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
  provider TEXT NOT NULL, intent_ref TEXT NOT NULL,
  seller_receivable INTEGER DEFAULT 0, commission_amount INTEGER DEFAULT 0,
  delivery_amount INTEGER DEFAULT 0, status TEXT DEFAULT 'simulated',
  idempotency_key TEXT UNIQUE, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER,
  action TEXT NOT NULL, target_type TEXT NOT NULL, target_id INTEGER,
  note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
  target_type TEXT NOT NULL, target_id INTEGER, detail TEXT DEFAULT '',
  severity TEXT DEFAULT 'medium', status TEXT DEFAULT 'open', created_at TEXT);
CREATE TABLE IF NOT EXISTS price_suggestions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id INTEGER NOT NULL,
  suggested_price INTEGER NOT NULL, reason TEXT DEFAULT '',
  status TEXT DEFAULT 'pending', decided_by INTEGER, created_at TEXT);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        for slug, nja, nzh, nen, attrs in CATEGORIES:
            attrs_json = json.dumps([
                {"key": k, "label_ja": lj, "label_zh": lz, "label_en": le, "type": t}
                for k, lj, lz, le, t in attrs], ensure_ascii=False)
            conn.execute(
                """INSERT INTO categories(slug,name_ja,name_zh,name_en,attrs_json)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(slug) DO UPDATE SET
                     name_ja=excluded.name_ja, name_zh=excluded.name_zh,
                     name_en=excluded.name_en, attrs_json=excluded.attrs_json""",
                (slug, nja, nzh, nen, attrs_json))
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        conn.commit()
    finally:
        conn.close()


def get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()


def category_by_slug(conn, slug):
    return conn.execute("SELECT * FROM categories WHERE slug=?", (slug,)).fetchone()


def category_by_id(conn, cid):
    return conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()


def user_by_id(conn, uid):
    if uid is None:
        return None
    return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
