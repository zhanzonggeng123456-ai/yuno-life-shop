"""Yuno Life MVP — FastAPI + SQLite + 后端直出响应式网页。
无前端构建步骤,手机浏览器可直接用。一条命令启动: ./start.sh
"""
import html
import json
import os
import secrets
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

from . import db as d
from .auctions import compute_price, min_next_bid, place_bid, settle_auction
from .agents import (anomaly_agent, dispute_agent, inventory_agent,
                     ops_agent, review_agent, support_agent)
from .business import (BUYBACK_TRANSITIONS, ORDER_TRANSITIONS,
                       can_transition, commission_for, commission_rate,
                       delivery_fee, local_ai_assist, size_class_for, stats)
from .market import (category_stats, collectible_trend, profit_report,
                     top_listings, weekly_curve)
from .oneclick import (appraise, build_draft, is_high_value, recognize,
                       valuation_for)
from .payments import get_provider
from .i18n import lang_from, t
from .security import (can_admin, can_appraise, can_operate, hash_password,
                       new_session_token, now_tokyo, session_expiry,
                       verify_password)

app = FastAPI(title="Yuno Life")
d.init_db()

ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ---------------- helpers ----------------
def esc(s):
    return html.escape(str(s if s is not None else ""))


def yen(n):
    if n is None:
        return "—"
    return f"¥{int(n):,}"


def conn():
    return d.connect()


def current_user(request):
    token = request.cookies.get("yuno_session")
    if not token:
        return None
    c = conn()
    try:
        row = c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if not row or row["expires_at"] < now_tokyo():
            return None
        return d.user_by_id(c, row["user_id"])
    finally:
        c.close()


def require_user(request):
    u = current_user(request)
    if not u:
        raise HTTPException(401, "login required")
    return u


def page(request, lang, user, title, body, msg=""):
    nav_user = ""
    if user:
        nav_user = (f'<a href="/me">{esc(user["display_name"])}</a> '
                    f'<a href="/me/messages">{t(lang,"messages")}</a> '
                    f'<a href="/admin">{t(lang,"admin")}</a> ' if can_operate(user) else
                    f'<a href="/me">{esc(user["display_name"])}</a> '
                    f'<a href="/me/messages">{t(lang,"messages")}</a> ')
        nav_user += ('<form method="post" action="/logout" style="display:inline">'
                     '<button>' + t(lang, "logout") + '</button></form>')
    else:
        nav_user = (f'<a href="/login">{t(lang,"login")}</a> '
                    f'<a href="/register">{t(lang,"register")}</a>')
    flash = f'<p class="flash">{esc(msg)}</p>' if msg else ""
    lang_links = ' | '.join(
        f'<a href="?lang={l}">{l}</a>' for l in ("ja", "zh", "en"))
    html_doc = f"""<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} - Yuno Life</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;
padding:12px}}nav a,nav button{{margin-right:10px}}.card{{border:1px solid #ccc;
border-radius:8px;padding:12px;margin:10px 0}}input,select,textarea{{width:100%;
padding:8px;margin:4px 0;box-sizing:border-box}}button{{padding:8px 14px;
cursor:pointer}}.flash{{background:#ffeeba;padding:10px}}table{{width:100%;
border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:6px;text-align:left}}
.badge{{background:#222;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px}}
.warn{{background:#fff3cd;padding:10px;border:1px solid #e6c200}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
</style></head><body>
<nav><a href="/"><b>Yuno Life</b></a> <a href="/">{t(lang,"home")}</a>
<a href="/listings/new">{t(lang,"publish")}</a>
<a href="/oneclick">{t(lang,"oneclick")}</a>
<a href="/auctions">拍卖</a> <a href="/market">行情</a>
<a href="/services">服务</a> <a href="/support">客服</a> {nav_user}
<span style="float:right">{lang_links}</span></nav>
<p>{t(lang,"tagline")}</p>{flash}{body}
<hr><p><small>Yuno Life MVP · 坂戸市先行 · 支払いは模擬表示 / 支付均为模拟标注 ·
<a href="/healthz">health</a></small></p></body></html>"""
    resp = HTMLResponse(html_doc)
    q = request.query_params.get("lang")
    if q in ("ja", "zh", "en"):
        resp.set_cookie("yuno_lang", q, max_age=365 * 86400)
    return resp


def redirect(url, msg=""):
    sep = "&" if "?" in url else "?"
    r = RedirectResponse(f"{url}{sep}msg={msg}" if msg else url, status_code=303)
    return r


def listing_title(row, lang):
    return row["title_ja"] if lang == "ja" else (row["title_zh"] or row["title_ja"])


def listing_desc(row, lang):
    return row["desc_ja"] if lang == "ja" else (row["desc_zh"] or row["desc_ja"])


def effective_price(row):
    if row["is_today_deal"] and row["discount_price"] and row["discount_until"] \
            and row["discount_until"] >= now_tokyo():
        return row["discount_price"]
    return row["price"]


def region_name(conn_, code, lang):
    regions = json.loads(d.get_setting(conn_, "regions") or "[]")
    r = next((x for x in regions if x["code"] == code), None)
    if not r:
        return code
    return r.get(f"name_{lang}") or r.get("name_ja") or code


def active_regions(conn_):
    return [r for r in json.loads(d.get_setting(conn_, "regions") or "[]")
            if r.get("active")]


# ---------------- public ----------------
@app.get("/healthz")
def healthz():
    return {"ok": True, "app": "yuno-life", "phase": "1-2-3-complete"}


@app.get("/")
def home(request: Request, q: str = "", category: str = "", region: str = "",
         price_min: str = "", price_max: str = "", only_platform: str = ""):
    lang = lang_from(request)
    c = conn()
    try:
        cats = c.execute("SELECT * FROM categories ORDER BY id").fetchall()
        sql = ("SELECT l.*, cat.slug AS cat_slug FROM listings l "
               "JOIN categories cat ON cat.id=l.category_id "
               "WHERE l.status='active'")
        args = []
        if q:
            sql += " AND (l.title_ja LIKE ? OR l.title_zh LIKE ? OR l.desc_ja LIKE ?)"
            args += [f"%{q}%"] * 3
        if category:
            sql += " AND cat.slug=?"; args.append(category)
        if region:
            sql += " AND l.region=?"; args.append(region)
        if price_min.isdigit():
            sql += " AND l.price>=?"; args.append(int(price_min))
        if price_max.isdigit():
            sql += " AND l.price<=?"; args.append(int(price_max))
        if only_platform:
            sql += " AND l.is_platform_owned=1"
        sql += " ORDER BY l.is_featured DESC, l.id DESC"
        rows = c.execute(sql, args).fetchall()
        cat_opts = "".join(
            f'<option value="{r["slug"]}"{" selected" if category == r["slug"] else ""}>'
            f'{esc(r[f"name_{lang}"] or r["name_ja"])}</option>' for r in cats)
        reg_opts = "".join(
            f'<option value="{r["code"]}"{" selected" if region == r["code"] else ""}>'
            f'{esc(r.get(f"name_{lang}") or r["name_ja"])}</option>'
            for r in active_regions(c))
        cards = ""
        for r in rows:
            img = c.execute("SELECT filename FROM images WHERE listing_id=? "
                            "ORDER BY sort LIMIT 1", (r["id"],)).fetchone()
            img_tag = (f'<img src="/uploads/{img["filename"]}" style="width:100%;'
                       f'max-height:160px;object-fit:cover">' if img else "")
            badges = ""
            if r["is_platform_owned"]:
                badges += f' <span class="badge">{t(lang,"platform_owned")}</span>'
            if r["is_today_deal"]:
                badges += f' <span class="badge">{t(lang,"today_deal")}</span>'
            if r["demo"]:
                badges += ' <span class="badge">DEMO</span>'
            cards += (f'<div class="card"><a href="/listings/{r["id"]}">{img_tag}'
                      f'<h3>{esc(listing_title(r, lang))}{badges}</h3></a>'
                      f'<p>{yen(effective_price(r))}'
                      f'{" <s>" + yen(r["price"]) + "</s>" if r["is_today_deal"] and effective_price(r) != r["price"] else ""}'
                      f' · {esc(region_name(c, r["region"], lang))}</p></div>')
        if not cards:
            cards = f'<p>{t(lang,"no_data")}</p>'
        body = f"""<h1>Yuno Life</h1>
<form method="get"><input name="q" value="{esc(q)}" placeholder="{t(lang,"search")}">
<select name="category"><option value="">{t(lang,"category")}:{t(lang,"all")}</option>
{cat_opts}</select>
<select name="region"><option value="">{t(lang,"region")}:{t(lang,"all")}</option>
{reg_opts}</select>
<input name="price_min" value="{esc(price_min)}" placeholder="min ¥">
<input name="price_max" value="{esc(price_max)}" placeholder="max ¥">
<label><input type="checkbox" name="only_platform" value="1"
{" checked" if only_platform else ""}> {t(lang,"platform_owned")}</label>
<button>{t(lang,"search")}</button></form>
<p><small>※ <a href="/market">交易行情</a>全部基于平台真实订单,演示订单已排除;
本页只显示在售商品与挂牌价,挂牌价与成交价严格区分,绝不编造。</small></p>
<div class="grid">{cards}</div>"""
        return page(request, lang, current_user(request), "Yuno Life", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


# ---------------- auth ----------------
@app.get("/register")
def register_form(request: Request):
    lang = lang_from(request)
    body = f"""<h2>{t(lang,"register")}</h2><form method="post">
<input name="email" type="email" required placeholder="{t(lang,"email")}">
<input name="display_name" required placeholder="{t(lang,"display_name")}">
<input name="password" type="password" required placeholder="{t(lang,"password")}">
<input name="phone" placeholder="電話番号 / 手机号(可选)">
<button>{t(lang,"submit")}</button></form>
<p><small>同一账号可同时买卖,无需注册两个账户。短信验证为二阶段待接入,
本阶段仅邮箱注册。</small></p>"""
    return page(request, lang, None, t(lang, "register"), body,
                request.query_params.get("msg", ""))


@app.post("/register")
def register(request: Request, email: str = Form(...), display_name: str = Form(...),
             password: str = Form(...), phone: str = Form("")):
    c = conn()
    try:
        if c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            return redirect("/register", "email_exists")
        salt, h = hash_password(password)
        cur = c.execute("INSERT INTO users(email,pw_hash,salt,display_name,role,"
                        "phone,created_at) VALUES(?,?,?,?,?,?,?)",
                        (email, h, salt, display_name, "user", phone, now_tokyo()))
        c.commit()
        tok = new_session_token()
        c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
                  (tok, cur.lastrowid, session_expiry()))
        c.commit()
        r = redirect("/me", "registered")
        r.set_cookie("yuno_session", tok, httponly=True, max_age=30 * 86400)
        return r
    finally:
        c.close()


@app.get("/login")
def login_form(request: Request):
    lang = lang_from(request)
    body = f"""<h2>{t(lang,"login")}</h2><form method="post">
<input name="email" type="email" required placeholder="{t(lang,"email")}">
<input name="password" type="password" required placeholder="{t(lang,"password")}">
<button>{t(lang,"submit")}</button></form>"""
    return page(request, lang, None, t(lang, "login"), body,
                request.query_params.get("msg", ""))


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    c = conn()
    try:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u or not verify_password(password, u["salt"], u["pw_hash"]):
            return redirect("/login", "invalid_login")
        tok = new_session_token()
        c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
                  (tok, u["id"], session_expiry()))
        c.commit()
        r = redirect("/me", "logged_in")
        r.set_cookie("yuno_session", tok, httponly=True, max_age=30 * 86400)
        return r
    finally:
        c.close()


@app.post("/logout")
def logout(request: Request):
    tok = request.cookies.get("yuno_session")
    if tok:
        c = conn()
        try:
            c.execute("DELETE FROM sessions WHERE token=?", (tok,)); c.commit()
        finally:
            c.close()
    r = redirect("/", "logged_out")
    r.delete_cookie("yuno_session")
    return r


# ---------------- listing create + AI assist ----------------
def category_fields_html(cat, lang, attrs=None, prefix=""):
    attrs = attrs or {}
    out = ""
    for a in json.loads(cat["attrs_json"]):
        key = a["key"]
        label = a.get(f"label_{lang}") or a.get("label_ja") or key
        out += (f'<label>{esc(label)}<input name="attr_{key}" '
                f'value="{esc(attrs.get(key, ""))}"></label>')
    return out


@app.get("/listings/new")
def listing_new(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        cats = c.execute("SELECT * FROM categories ORDER BY id").fetchall()
        opts = "".join(f'<option value="{r["slug"]}">{esc(r[f"name_{lang}"] or r["name_ja"])}</option>'
                       for r in cats)
        regs = "".join(f'<option value="{r["code"]}">{esc(r.get(f"name_{lang}") or r["name_ja"])}</option>'
                       for r in active_regions(c))
        # AI 辅助预填(来自 /ai-assist 的重定向参数)
        q = request.query_params
        assist = ""
        if q.get("ai_title_ja"):
            assist = (f'<div class="warn"><b>AI 辅助草稿(本地启发式,非模型推测定论):</b><br>'
                      f'分类建议: {esc(q.get("ai_category", ""))} '
                      f'(可信度 {esc(q.get("ai_cat_conf", ""))})<br>'
                      f'价格参考: {esc(q.get("ai_price_note", ""))}<br>'
                      f'请确认并修改后再发布。</div>')
        body = f"""{assist}<h2>{t(lang,"publish")}</h2>
<form method="post" enctype="multipart/form-data">
<label>分类<select name="category_slug" id="cat">{opts}</select></label>
<label>日文标题<input name="title_ja" required value="{esc(q.get("ai_title_ja", ""))}"></label>
<label>中文标题<input name="title_zh" value="{esc(q.get("ai_title_zh", ""))}"></label>
<label>日文介绍<textarea name="desc_ja">{esc(q.get("ai_desc_ja", ""))}</textarea></label>
<label>中文介绍<textarea name="desc_zh">{esc(q.get("ai_desc_zh", ""))}</textarea></label>
<label>价格(¥)<input name="price" type="number" min="1" required></label>
<label>成色<select name="condition_grade">
<option value="excellent">美品 / 近乎全新</option><option value="good" selected>良好</option>
<option value="fair">使用感あり / 有使用痕迹</option><option value="poor">要修理 / 需维修</option>
</select></label>
<label>地区<select name="region">{regs}</select></label>
<label>尺寸档<select name="size_class"><option value="S">S(轻小件)</option>
<option value="M" selected>M</option><option value="L">L</option>
<option value="XL">XL(大型家具/冰箱/洗衣机等,单独报价)</option></select></label>
<label>重量(kg)<input name="weight_kg" type="number" step="0.1" value="0"></label>
<label>商品图片<input type="file" name="image" accept="image/*"></label>
<div id="attrs"></div>
<button>{t(lang,"submit")}</button></form>
<h3>AI 辅助(本地启发式,免费)</h3>
<form method="post" action="/ai-assist">
<input name="name" required placeholder="商品名,如:微波炉 / 電子レンジ">
<input name="text" placeholder="补充描述,如:品牌、年份、状态">
<input name="condition" value="good" placeholder="成色 excellent/good/fair/poor">
<input name="price_hint" placeholder="你的期望价(可选)">
<button>生成草稿并预填</button></form>
<p><small>AI 辅助只做本地建议,识别结果可人工修改;估价不是最终收购承诺,
数据不足时会明确提示暂无样本,不会编造市场成交价。真实大模型 API
默认关闭,见 README 零成本章节。</small></p>
"""
        return page(request, lang, user, t(lang, "publish"), body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/ai-assist")
def ai_assist(request: Request, name: str = Form(...), text: str = Form(""),
              condition: str = Form("good"), price_hint: str = Form("")):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        r = local_ai_assist(c, name, text, condition,
                            int(price_hint) if price_hint.isdigit() else None)
        if r["price_low"] is None:
            note = ("暂无样本:平台暂无同类真实成交与在售挂牌可供参考,无法给出参考价。"
                    "请自行定价。/ サンプル不足のため参考価格を提示できません。")
        elif r["price_basis"].startswith("based_on_completed"):
            n = r["price_basis"].split(":")[1]
            note = (f"基于平台真实成交 {n} 件的中位数 ±20%(可信度:{r['price_confidence']})。"
                    f"这是参考区间,不是收购承诺。")
        else:
            n = r["price_basis"].split(":")[1]
            note = (f"基于在售挂牌价 {n} 件(挂牌价,不是成交价,可信度低)。"
                    f"这是参考区间,不是收购承诺。")
        url = (f"/listings/new?ai_title_ja={r['title_ja']}&ai_title_zh={r['title_zh']}"
               f"&ai_desc_ja={r['desc_ja']}&ai_desc_zh={r['desc_zh']}"
               f"&ai_category={r['category_slug'] or ''}"
               f"&ai_cat_conf={r['category_confidence']}"
               f"&ai_price_note={note}")
        # URL 参数需转义;RedirectResponse 会原样处理,标题含中文时由浏览器编码
        from urllib.parse import quote
        url = (f"/listings/new?ai_title_ja={quote(r['title_ja'])}"
               f"&ai_title_zh={quote(r['title_zh'])}"
               f"&ai_desc_ja={quote(r['desc_ja'])}&ai_desc_zh={quote(r['desc_zh'])}"
               f"&ai_category={r['category_slug'] or ''}"
               f"&ai_cat_conf={r['category_confidence']}&ai_price_note={quote(note)}")
        return RedirectResponse(url, status_code=303)
    finally:
        c.close()


@app.post("/listings/new")
async def listing_create(request: Request, category_slug: str = Form(...),
                         title_ja: str = Form(...), title_zh: str = Form(""),
                         desc_ja: str = Form(""), desc_zh: str = Form(""),
                         price: int = Form(...), condition_grade: str = Form("good"),
                         region: str = Form("sakado"), size_class: str = Form("M"),
                         weight_kg: float = Form(0),
                         image: UploadFile = File(None)):
    user = require_user(request)
    c = conn()
    try:
        cat = d.category_by_slug(c, category_slug)
        if not cat:
            raise HTTPException(400, "bad category")
        if region not in [r["code"] for r in active_regions(c)]:
            raise HTTPException(400, "region not open yet")
        attrs = {}
        form = await request.form()
        for a in json.loads(cat["attrs_json"]):
            v = form.get(f"attr_{a['key']}", "")
            if v:
                attrs[a["key"]] = v
        size = size_class_for(weight_kg, size_class)
        cur = c.execute(
            "INSERT INTO listings(seller_id,category_id,title_ja,title_zh,desc_ja,"
            "desc_zh,price,condition_grade,attrs_json,region,size_class,weight_kg,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], cat["id"], title_ja, title_zh, desc_ja, desc_zh, price,
             condition_grade, json.dumps(attrs, ensure_ascii=False), region, size,
             weight_kg, now_tokyo(), now_tokyo()))
        lid = cur.lastrowid
        # 高价值收藏品(手表/钱币/古董且 >=100000 日元)自动进入人工审核队列,
        # 鉴定通过前不可交易;其余商品不受影响。
        if category_slug in ("watch", "coin", "antique") and price >= 100000:
            c.execute("INSERT OR IGNORE INTO hv_reviews(listing_id,created_at)"
                      " VALUES(?,?)", (lid, now_tokyo()))
        if image is not None and getattr(image, "filename", ""):
            data = await image.read()
            ext = Path(image.filename).suffix.lower()
            if ext not in ALLOWED_IMG or len(data) > 5 * 1024 * 1024:
                raise HTTPException(400, "bad image")
            fname = f"{uuid.uuid4().hex}{ext}"
            (d.UPLOAD_DIR / fname).write_bytes(data)
            c.execute("INSERT INTO images(listing_id,filename,sort) VALUES(?,?,0)",
                      (lid, fname))
        c.commit()
        return redirect(f"/listings/{lid}", "published")
    finally:
        c.close()


# ---------------- AI 一键链路:上传 -> 一键识别 -> 一键上架 ----------------
# 三步,每步一个主按钮,移动端可用。识别/鉴定/估价全部是本地启发式推测,
# 草稿全部可改;点"一键上架"才是用户确认,发布后走正常商品/订单/库存流程。
def _steps_html(current):
    steps = ["1 上传照片", "2 一键识别", "3 一键上架"]
    out = []
    for i, s in enumerate(steps, 1):
        out.append(f"<b>{s}</b>" if i == current else s)
    return "<p>" + " → ".join(out) + "</p>"


def _draft_or_403(c, did, user):
    row = c.execute("SELECT * FROM oneclick_drafts WHERE id=?", (did,)).fetchone()
    if not row:
        raise HTTPException(404, "draft not found")
    if row["user_id"] != user["id"]:
        raise HTTPException(403, "not your draft")
    return row


def _guess_panel(rec, lang):
    if not rec:
        return ""
    items = "".join(
        f"<li>{esc(s['field'])}: {esc(s['value'])} "
        f"(推测·可修改, 可信度 {esc(s['confidence'])})</li>"
        for s in rec.get("suggestions", []))
    note = rec.get("guess_note_zh") if lang != "ja" else rec.get("guess_note_ja")
    return (f'<div class="warn"><b>一键识别结果 — 全部是推测,全部可修改:</b><br>'
            f'{esc(note)}<ul>{items}</ul></div>')


def _appraisal_panel(ap, lang):
    if not ap:
        return ""
    factors = ", ".join(ap.get("risk_factors", [])) or "无"
    note = ap.get("note_zh") if lang != "ja" else ap.get("note_ja")
    warn = ""
    if ap.get("requires_manual_review"):
        warn = ("<br><b>高价值商品:已自动进入人工复核队列,"
                "鉴定通过前不可交易。</b>")
    return (f'<div class="card"><b>AI 鉴定(启发式风险提示,不是真伪判定)</b><br>'
            f'成色等级: {esc(ap.get("condition_grade", ""))}<br>'
            f'真伪风险: {esc(ap.get("authenticity_risk", ""))} '
            f'(风险因素: {esc(factors)})<br>{esc(note)}{warn}</div>')


def _valuation_panel(val, lang):
    if not val:
        return ""
    if not val.get("has_sample"):
        basis = val.get("basis_zh") if lang != "ja" else val.get("basis_ja")
        return (f'<div class="warn"><b>AI 估价:</b> {esc(basis)}'
                f'不会编造价格,请自行定价。</div>')
    basis = val.get("basis_zh") if lang != "ja" else val.get("basis_ja")
    return (f'<div class="card"><b>AI 估价参考区间:</b> '
            f'{yen(val.get("low"))} 〜 {yen(val.get("high"))} '
            f'(可信度 {esc(val.get("confidence", ""))}, {esc(basis)});'
            f'这只是参考,不是收购承诺。</div>')


@app.get("/oneclick")
def oneclick_start(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    body = f"""{_steps_html(1)}
<h2>{t(lang, "oneclick")}</h2>
<p>第 1 步:拍一张照片、写上商品名,点主按钮上传。照片本地存储,
不调用任何付费视觉模型。</p>
<form method="post" action="/oneclick/upload" enctype="multipart/form-data">
<label>商品照片<input type="file" name="photo" accept="image/*"></label>
<label>商品名<input name="name" required
placeholder="如:ロレックス 腕時計 / 微波炉"></label>
<label>补充描述<textarea name="text"
placeholder="品牌、年份、状态、附件等,写得越多识别建议越准"></textarea></label>
<label>成色<select name="condition">
<option value="excellent">美品 / 近乎全新</option><option value="good" selected>良好</option>
<option value="fair">使用感あり / 有使用痕迹</option><option value="poor">要修理 / 需维修</option>
</select></label>
<label>期望价(¥,可选)<input name="price_hint" type="number" min="1"></label>
<button style="font-size:18px;padding:12px 24px">第 1 步:上传照片</button></form>
<p><small>下一步点"一键识别"才会生成建议;所有建议都标注为推测,
发布前你都可以改。</small></p>"""
    return page(request, lang, user, t(lang, "oneclick"), body,
                request.query_params.get("msg", ""))


@app.post("/oneclick/upload")
async def oneclick_upload(request: Request, name: str = Form(...),
                          text: str = Form(""), condition: str = Form("good"),
                          price_hint: str = Form(""),
                          photo: UploadFile = File(None)):
    user = require_user(request)
    c = conn()
    try:
        fname = ""
        if photo is not None and getattr(photo, "filename", ""):
            data = await photo.read()
            ext = Path(photo.filename).suffix.lower()
            if ext not in ALLOWED_IMG or len(data) > 5 * 1024 * 1024:
                raise HTTPException(400, "bad image")
            fname = f"{uuid.uuid4().hex}{ext}"
            (d.UPLOAD_DIR / fname).write_bytes(data)
        cur = c.execute(
            "INSERT INTO oneclick_drafts(user_id,photo,name,text,condition_grade,"
            "price_hint,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (user["id"], fname, name, text, condition,
             int(price_hint) if price_hint.isdigit() else None,
             "uploaded", now_tokyo(), now_tokyo()))
        c.commit()
        return redirect(f"/oneclick/{cur.lastrowid}")
    finally:
        c.close()


@app.get("/oneclick/{did}")
def oneclick_detail(request: Request, did: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        draft = _draft_or_403(c, did, user)
        if draft["status"] == "published" and draft["listing_id"]:
            return redirect(f"/listings/{draft['listing_id']}")
        img = (f'<img src="/uploads/{esc(draft["photo"])}" style="max-width:100%">'
               if draft["photo"] else "<p>未上传照片(纯文字流程也可继续)。</p>")
        if draft["status"] == "uploaded":
            body = f"""{_steps_html(2)}{img}
<p>商品名: {esc(draft["name"])}<br>补充: {esc(draft["text"])}</p>
<form method="post" action="/oneclick/{did}/recognize">
<button style="font-size:18px;padding:12px 24px">第 2 步:一键识别</button></form>
<p><small>识别只用你输入的文字、品类属性模式与本地历史数据,
不调用视觉模型;结果全部是推测,下一步可改。</small></p>"""
            return page(request, lang, user, t(lang, "oneclick"), body,
                        request.query_params.get("msg", ""))
        rec = json.loads(draft["recognition_json"] or "{}")
        ap = json.loads(draft["appraisal_json"] or "{}")
        val = json.loads(draft["valuation_json"] or "{}")
        dr = json.loads(draft["draft_json"] or "{}")
        cats = c.execute("SELECT * FROM categories ORDER BY id").fetchall()
        opts = "".join(
            f'<option value="{r["slug"]}"'
            f'{" selected" if r["slug"] == dr.get("category_slug") else ""}>'
            f'{esc(r[f"name_{lang}"] or r["name_ja"])}</option>' for r in cats)
        regs = "".join(
            f'<option value="{r["code"]}">{esc(r.get(f"name_{lang}") or r["name_ja"])}</option>'
            for r in active_regions(c))
        cat = d.category_by_slug(c, dr.get("category_slug") or "") if dr.get("category_slug") else None
        attrs_html = category_fields_html(cat, lang, dr.get("attrs", {})) if cat else \
            "<p>请先在上面选好分类,专属属性字段会随分类出现(发布时仍可改)。</p>"
        cond = dr.get("condition_grade") or draft["condition_grade"] or "good"
        cond_opts = "".join(
            f'<option value="{v}"{" selected" if v == cond else ""}>{label}</option>'
            for v, label in [("excellent", "美品 / 近乎全新"), ("good", "良好"),
                             ("fair", "使用感あり / 有使用痕迹"),
                             ("poor", "要修理 / 需维修")])
        price_val = draft["price_hint"] or ""
        body = f"""{_steps_html(3)}{img}
{_guess_panel(rec, lang)}
{_appraisal_panel(ap, lang)}
{_valuation_panel(val, lang)}
<p>草稿规格: {esc(dr.get("spec_zh") or dr.get("spec_ja", ""))}<br>
关键词: {esc(", ".join(dr.get("keywords", [])))}<br>
成色描述: {esc(dr.get("condition_desc_zh") or dr.get("condition_desc_ja", ""))}</p>
<h3>确认并修改草稿,点主按钮即发布</h3>
<form method="post" action="/oneclick/{did}/publish">
<label>分类<select name="category_slug">{opts}</select></label>
<label>日文标题<input name="title_ja" required value="{esc(dr.get("title_ja", ""))}"></label>
<label>中文标题<input name="title_zh" value="{esc(dr.get("title_zh", ""))}"></label>
<label>日文介绍<textarea name="desc_ja">{esc(dr.get("desc_ja", ""))}</textarea></label>
<label>中文介绍<textarea name="desc_zh">{esc(dr.get("desc_zh", ""))}</textarea></label>
<label>价格(¥)<input name="price" type="number" min="1" required value="{price_val}"></label>
<label>成色<select name="condition_grade">{cond_opts}</select></label>
<label>地区<select name="region">{regs}</select></label>
<label>尺寸档<select name="size_class"><option value="S">S(轻小件)</option>
<option value="M" selected>M</option><option value="L">L</option>
<option value="XL">XL(大型家具/冰箱/洗衣机等,单独报价)</option></select></label>
<label>重量(kg)<input name="weight_kg" type="number" step="0.1" value="0"></label>
{attrs_html}
<button style="font-size:18px;padding:12px 24px">第 3 步:一键上架</button></form>
<p><small>点"一键上架"就是你的确认,商品将按上面修改后的内容发布;
高价值商品会自动进入人工复核队列,通过前不可交易。</small></p>"""
        return page(request, lang, user, t(lang, "oneclick"), body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/oneclick/{did}/recognize")
def oneclick_recognize(request: Request, did: int):
    user = require_user(request)
    c = conn()
    try:
        draft = _draft_or_403(c, did, user)
        if draft["status"] == "published":
            return redirect(f"/listings/{draft['listing_id']}")
        rec = recognize(c, draft["name"], draft["text"],
                        draft["condition_grade"], draft["price_hint"])
        ap = appraise(rec.get("category_slug"), draft["price_hint"],
                      rec.get("condition_guess"), rec)
        val = valuation_for(c, rec.get("category_slug"))
        dr = build_draft(c, draft["name"], draft["text"],
                         draft["condition_grade"], draft["price_hint"], rec)
        c.execute("UPDATE oneclick_drafts SET recognition_json=?,draft_json=?,"
                  "appraisal_json=?,valuation_json=?,status='recognized',"
                  "updated_at=? WHERE id=?",
                  (json.dumps(rec, ensure_ascii=False),
                   json.dumps(dr, ensure_ascii=False),
                   json.dumps(ap, ensure_ascii=False),
                   json.dumps(val, ensure_ascii=False),
                   now_tokyo(), did))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "oneclick_recognize", "oneclick_draft", did,
                   f"category={rec.get('category_slug')};"
                   f"risk={ap.get('authenticity_risk')}", now_tokyo()))
        c.commit()
        return redirect(f"/oneclick/{did}")
    finally:
        c.close()


@app.post("/oneclick/{did}/publish")
async def oneclick_publish(request: Request, did: int,
                           category_slug: str = Form(...),
                           title_ja: str = Form(...), title_zh: str = Form(""),
                           desc_ja: str = Form(""), desc_zh: str = Form(""),
                           price: int = Form(...),
                           condition_grade: str = Form("good"),
                           region: str = Form("sakado"),
                           size_class: str = Form("M"),
                           weight_kg: float = Form(0)):
    user = require_user(request)
    c = conn()
    try:
        draft = _draft_or_403(c, did, user)
        if draft["status"] != "recognized":
            return redirect(f"/oneclick/{did}", "recognize_first")
        cat = d.category_by_slug(c, category_slug)
        if not cat:
            raise HTTPException(400, "bad category")
        if region not in [r["code"] for r in active_regions(c)]:
            raise HTTPException(400, "region not open yet")
        attrs = {}
        form = await request.form()
        for a in json.loads(cat["attrs_json"]):
            v = form.get(f"attr_{a['key']}", "")
            if v:
                attrs[a["key"]] = v
        size = size_class_for(weight_kg, size_class)
        cur = c.execute(
            "INSERT INTO listings(seller_id,category_id,title_ja,title_zh,desc_ja,"
            "desc_zh,price,condition_grade,attrs_json,region,size_class,weight_kg,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], cat["id"], title_ja, title_zh, desc_ja, desc_zh, price,
             condition_grade, json.dumps(attrs, ensure_ascii=False), region, size,
             weight_kg, now_tokyo(), now_tokyo()))
        lid = cur.lastrowid
        hv = is_high_value(category_slug, price)
        if hv:
            c.execute("INSERT OR IGNORE INTO hv_reviews(listing_id,created_at)"
                      " VALUES(?,?)", (lid, now_tokyo()))
            c.execute("INSERT INTO audit_log(actor_id,action,target_type,"
                      "target_id,note,created_at) VALUES(?,?,?,?,?,?)",
                      (user["id"], "appraisal_queued", "listing", lid,
                       "high_value_auto_review", now_tokyo()))
        if draft["photo"]:
            c.execute("INSERT INTO images(listing_id,filename,sort) VALUES(?,?,0)",
                      (lid, draft["photo"]))
        c.execute("UPDATE oneclick_drafts SET status='published',listing_id=?,"
                  "updated_at=? WHERE id=?", (lid, now_tokyo(), did))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "oneclick_publish", "listing", lid,
                   f"from_draft={did}", now_tokyo()))
        c.commit()
        return redirect(f"/listings/{lid}", "published")
    finally:
        c.close()


@app.get("/uploads/{name}")
def serve_upload(name: str):
    p = d.UPLOAD_DIR / Path(name).name
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p)


# ---------------- listing detail / buy / offer ----------------
@app.get("/listings/{lid}")
def listing_detail(request: Request, lid: int):
    lang = lang_from(request)
    user = current_user(request)
    c = conn()
    try:
        r = c.execute("SELECT l.*, cat.slug AS cat_slug, cat.name_ja AS cat_ja, "
                      "cat.name_zh AS cat_zh FROM listings l JOIN categories cat "
                      "ON cat.id=l.category_id WHERE l.id=?", (lid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        seller = d.user_by_id(c, r["seller_id"]) if r["seller_id"] else None
        imgs = c.execute("SELECT filename FROM images WHERE listing_id=? ORDER BY sort",
                         (lid,)).fetchall()
        img_html = "".join(f'<img src="/uploads/{i["filename"]}" '
                           f'style="max-width:100%;max-height:320px">' for i in imgs)
        attrs_html = ""
        for k, v in json.loads(r["attrs_json"] or "{}").items():
            attrs_html += f"<li>{esc(k)}: {esc(v)}</li>"
        fee, needs_quote, fee_note = delivery_fee(c, r["size_class"], r["weight_kg"],
                                                  r["region"])
        fee_html = (f'<p class="warn">大型商品单独报价,不适用统一低价,请联系平台确认。'
                    f'</p>' if needs_quote else
                    f'<p>{t(lang,"delivery_fee")}: {yen(fee)} '
                    f'(尺寸档 {esc(r["size_class"])})</p>')
        hv = c.execute("SELECT * FROM hv_reviews WHERE listing_id=?",
                       (lid,)).fetchone()
        hv_html = ""
        if hv:
            hv_html = (f'<p class="warn">高价值收藏品审核:身份验证 '
                       f'{"已验证" if hv["identity_verified"] else "未验证"} · '
                       f'鉴定状态 {esc(hv["appraisal_status"])}'
                       f'{" · " + esc(hv["appraisal_note"]) if hv["appraisal_note"] else ""}'
                       f'。鉴定通过前不可交易。</p>')
        auc = c.execute("SELECT * FROM auctions WHERE listing_id=?",
                        (lid,)).fetchone()
        auc_html = ""
        if auc:
            bids = c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id",
                             (auc["id"],)).fetchall()
            cur_price, leader = compute_price(auc, bids)
            auc_html = (f'<p>拍卖:当前价 {yen(cur_price)} · 出价 {len(bids)} 笔 · '
                        f'保留价 {yen(auc["reserve_price"])} · '
                        f'结束 {esc(auc["ends_at"])} · 状态 {esc(auc["status"])} '
                        f'<a href="/auctions/{auc["id"]}">进入拍卖</a></p>')
        follow_n = c.execute("SELECT COUNT(*) FROM listing_follows WHERE listing_id=?",
                             (lid,)).fetchone()[0]
        follow_html = f'<p>关注人数: {follow_n}</p>'
        if user:
            followed = c.execute("SELECT id FROM listing_follows WHERE user_id=? "
                                 "AND listing_id=?", (user["id"], lid)).fetchone()
            act = "unfollow" if followed else "follow"
            lbl = "取消关注" if followed else "关注商品"
            follow_html += (f'<form method="post" action="/listings/{lid}/{act}">'
                            f'<button>{lbl}</button></form>')
        actions = ""
        if user and r["status"] == "active":
            if not r["is_platform_owned"] and user["id"] != r["seller_id"]:
                actions += f"""<form method="post" action="/listings/{lid}/buy">
<button>{t(lang,"buy_now")} {yen(effective_price(r))}</button></form>
<form method="post" action="/listings/{lid}/offer">
<input name="amount" type="number" min="1" required placeholder="出价 ¥">
<button>{t(lang,"make_offer")}</button></form>
<a href="/messages/{lid}/{user['id']}">{t(lang,"messages")}</a>"""
            elif r["is_platform_owned"]:
                actions += f"""<form method="post" action="/listings/{lid}/buy">
<button>{t(lang,"buy_now")} {yen(effective_price(r))}</button></form>"""
            if user["id"] == r["seller_id"] and not r["is_platform_owned"]:
                actions += f"""<form method="post" action="/buyback/new">
<input type="hidden" name="listing_id" value="{lid}">
<button>{t(lang,"sell_to_platform")}</button></form>"""
                if not auc:
                    actions += f"""<h3>发起拍卖(任何商品均可拍卖)</h3>
<form method="post" action="/listings/{lid}/auction">
<input name="start_price" type="number" min="1" required placeholder="起拍价 ¥">
<input name="reserve_price" type="number" min="0" value="0" placeholder="保留价 ¥(0=无)">
<input name="min_increment" type="number" min="1" value="100" placeholder="最小加价 ¥">
<input name="buy_now_price" type="number" min="0" placeholder="一口价 ¥(可选)">
<input name="ends_at" required placeholder="结束时间,如 2026-12-31T23:59:59+09:00">
<label><input type="checkbox" name="deposit_required" value="1"> 需要保证金(模拟)</label>
<input name="deposit_amount" type="number" min="0" value="0" placeholder="保证金 ¥">
<button>发起拍卖</button></form>"""
        badges = ""
        if r["is_platform_owned"]:
            badges = f' <span class="badge">{t(lang,"platform_owned")}</span>'
        if r["is_today_deal"]:
            badges += f' <span class="badge">{t(lang,"today_deal")}</span>'
        if r["demo"]:
            badges += ' <span class="badge">DEMO</span>'
        body = f"""<div class="card">{img_html}<h2>{esc(listing_title(r, lang))}{badges}</h2>
<p>{yen(effective_price(r))}
{" <s>" + yen(r["price"]) + "</s>" if effective_price(r) != r["price"] else ""}
· {esc(r[f"cat_{lang}"] if lang in ("ja", "zh") else r["cat_ja"])}
· {esc(region_name(c, r["region"], lang))} · 状态:{esc(r["status"])}
· 卖家:{esc(seller["display_name"]) if seller else t(lang,"platform_owned")}</p>
<p>{esc(listing_desc(r, lang))}</p><ul>{attrs_html}</ul>
<p>成色:{esc(r["condition_grade"])} · 检测记录:{esc(r["inspection_record"] or "—")}</p>
{fee_html}{hv_html}{auc_html}{follow_html}{actions}</div>
<p><a href="/">{t(lang,"back")}</a></p>"""
        return page(request, lang, user, listing_title(r, lang), body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


def create_order(c, buyer_id, listing, goods_amount):
    is_platform = 1 if listing["is_platform_owned"] else 0
    comm = commission_for(c, goods_amount, is_platform)
    fee, needs_quote, _ = delivery_fee(c, listing["size_class"],
                                        listing["weight_kg"], listing["region"])
    if needs_quote:
        return None, "needs_quote"
    total = goods_amount + fee
    key = secrets.token_hex(12)
    cur = c.execute(
        "INSERT INTO orders(buyer_id,seller_id,listing_id,goods_amount,commission,"
        "delivery_fee,total,status,payment_ref,idempotency_key,is_platform_sale,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (buyer_id, listing["seller_id"], listing["id"], goods_amount, comm, fee,
         total, "pending_payment", "", key, is_platform, now_tokyo(), now_tokyo()))
    oid = cur.lastrowid
    c.execute("INSERT INTO order_audit(order_id,event,amount_delta,note,created_at)"
              " VALUES(?,?,?,?,?)", (oid, "created", 0, "order created", now_tokyo()))
    c.execute("UPDATE listings SET status='reserved',updated_at=? WHERE id=?",
              (now_tokyo(), listing["id"]))
    c.commit()
    return oid, None


@app.post("/listings/{lid}/buy")
def buy(request: Request, lid: int):
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not r or r["status"] != "active":
            return redirect("/", "not_available")
        if r["seller_id"] and r["seller_id"] == user["id"]:
            return redirect(f"/listings/{lid}", "own_listing")
        hv = c.execute("SELECT appraisal_status FROM hv_reviews WHERE listing_id=?",
                       (lid,)).fetchone()
        if hv and hv["appraisal_status"] != "approved":
            return redirect(f"/listings/{lid}", "hv_review_pending")
        oid, err = create_order(c, user["id"], r, effective_price(r))
        if err:
            return redirect(f"/listings/{lid}", "needs_separate_quote")
        return redirect(f"/orders/{oid}", "order_created")
    finally:
        c.close()


@app.post("/listings/{lid}/offer")
def offer(request: Request, lid: int, amount: int = Form(...)):
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not r or r["status"] != "active" or r["seller_id"] == user["id"]:
            return redirect(f"/listings/{lid}", "cannot_offer")
        hv = c.execute("SELECT appraisal_status FROM hv_reviews WHERE listing_id=?",
                       (lid,)).fetchone()
        if hv and hv["appraisal_status"] != "approved":
            return redirect(f"/listings/{lid}", "hv_review_pending")
        c.execute("INSERT INTO offers(listing_id,buyer_id,amount,created_at)"
                  " VALUES(?,?,?,?)", (lid, user["id"], amount, now_tokyo()))
        c.commit()
        return redirect("/me", "offer_sent")
    finally:
        c.close()


@app.post("/offers/{oid}/accept")
def offer_accept(request: Request, oid: int):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        if not o:
            raise HTTPException(404, "not found")
        listing = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        if listing["seller_id"] != user["id"] or listing["status"] != "active":
            raise HTTPException(403, "forbidden")
        c.execute("UPDATE offers SET status='accepted' WHERE id=?", (oid,))
        new_oid, err = create_order(c, o["buyer_id"], listing, o["amount"])
        if err:
            return redirect(f"/listings/{listing['id']}", "needs_separate_quote")
        return redirect(f"/orders/{new_oid}", "offer_accepted")
    finally:
        c.close()


@app.post("/offers/{oid}/reject")
def offer_reject(request: Request, oid: int):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        listing = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        if not o or listing["seller_id"] != user["id"]:
            raise HTTPException(403, "forbidden")
        c.execute("UPDATE offers SET status='rejected' WHERE id=?", (oid,))
        c.commit()
        return redirect("/me", "offer_rejected")
    finally:
        c.close()


@app.post("/offers/{oid}/counter")
def offer_counter(request: Request, oid: int, counter_amount: int = Form(...)):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        listing = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        if not o or listing["seller_id"] != user["id"]:
            raise HTTPException(403, "forbidden")
        c.execute("UPDATE offers SET status='countered',counter_amount=? WHERE id=?",
                  (counter_amount, oid))
        c.commit()
        return redirect("/me", "offer_countered")
    finally:
        c.close()


@app.post("/offers/{oid}/accept-counter")
def offer_accept_counter(request: Request, oid: int):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM offers WHERE id=?", (oid,)).fetchone()
        listing = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        if not o or o["buyer_id"] != user["id"] or o["status"] != "countered":
            raise HTTPException(403, "forbidden")
        c.execute("UPDATE offers SET status='accepted' WHERE id=?", (oid,))
        new_oid, err = create_order(c, user["id"], listing, o["counter_amount"])
        if err:
            return redirect(f"/listings/{listing['id']}", "needs_separate_quote")
        return redirect(f"/orders/{new_oid}", "counter_accepted")
    finally:
        c.close()


# ---------------- messages ----------------
@app.get("/messages/{lid}/{buyer_id}")
def thread(request: Request, lid: int, buyer_id: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        listing = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not listing or (user["id"] != buyer_id and user["id"] != listing["seller_id"]):
            raise HTTPException(403, "forbidden")
        rows = c.execute("SELECT * FROM messages WHERE listing_id=? AND buyer_id=? "
                         "ORDER BY id", (lid, buyer_id)).fetchall()
        items = "".join(
            f'<div class="card"><b>{esc(d.user_by_id(c, m["sender_id"])["display_name"])}</b>'
            f': {esc(m["body"])} <small>{esc(m["created_at"])}</small></div>' for m in rows)
        receiver = listing["seller_id"] if user["id"] == buyer_id else buyer_id
        body = f"""<h2>{t(lang,"messages")} — {esc(listing_title(listing, lang))}</h2>
{items or f'<p>{t(lang,"no_data")}</p>'}
<form method="post"><textarea name="body" required></textarea>
<input type="hidden" name="receiver_id" value="{receiver}">
<button>{t(lang,"submit")}</button></form>"""
        return page(request, lang, user, t(lang, "messages"), body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/messages/{lid}/{buyer_id}")
def thread_post(request: Request, lid: int, buyer_id: int,
                body: str = Form(...), receiver_id: int = Form(...)):
    user = require_user(request)
    c = conn()
    try:
        listing = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not listing or (user["id"] != buyer_id and user["id"] != listing["seller_id"]):
            raise HTTPException(403, "forbidden")
        c.execute("INSERT INTO messages(listing_id,buyer_id,sender_id,receiver_id,"
                  "body,created_at) VALUES(?,?,?,?,?,?)",
                  (lid, buyer_id, user["id"], receiver_id, body, now_tokyo()))
        c.commit()
        return redirect(f"/messages/{lid}/{buyer_id}", "sent")
    finally:
        c.close()


@app.get("/me/messages")
def my_threads(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        rows = c.execute(
            "SELECT DISTINCT listing_id, buyer_id FROM messages "
            "WHERE sender_id=? OR receiver_id=? ORDER BY listing_id DESC",
            (user["id"], user["id"])).fetchall()
        items = "".join(
            f'<div class="card"><a href="/messages/{r["listing_id"]}/{r["buyer_id"]}">'
            f'商品 #{r["listing_id"]} · 买家 #{r["buyer_id"]}</a></div>' for r in rows)
        empty = f"<p>{t(lang, 'no_data')}</p>"
        body = f"<h2>{t(lang, 'messages')}</h2>{items or empty}"
        return page(request, lang, user, t(lang, "messages"), body)
    finally:
        c.close()


# ---------------- orders ----------------
@app.get("/orders/{oid}")
def order_detail(request: Request, oid: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or (user["id"] not in (o["buyer_id"], o["seller_id"])
                     and not can_operate(user)):
            raise HTTPException(403, "forbidden")
        listing = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        audits = c.execute("SELECT * FROM order_audit WHERE order_id=? ORDER BY id",
                           (oid,)).fetchall()
        audit_html = "".join(f"<li>{esc(a['event'])} {yen(a['amount_delta'])} "
                             f"{esc(a['note'])} {esc(a['created_at'])}</li>" for a in audits)
        acts = ""
        if o["status"] == "pending_payment":
            acts = f"""<form method="post" action="/orders/{oid}/pay">
<input type="hidden" name="idempotency_key" value="mock-{oid}-{user['id']}">
<button>{t(lang,"mock_badge")}模拟支付(不会真实扣款)</button></form>
<form method="post" action="/orders/{oid}/cancel"><button>取消订单</button></form>"""
        if o["status"] == "paid":
            acts = f"""<form method="post" action="/orders/{oid}/complete">
<button>确认收货并完成</button></form>"""
        if o["status"] in ("paid", "completed"):
            acts += f"""<h3>配送预约</h3>
<form method="post" action="/orders/{oid}/delivery-request">
<select name="kind"><option value="buyer_delivery">买家申请本地配送</option>
<option value="seller_pickup">卖家申请上门取件</option></select>
<input name="scheduled_at" placeholder="希望时间,如 2026-11-12 10:00">
<button>提交配送预约</button></form>
<h3>退款申请</h3>
<form method="post" action="/orders/{oid}/refund">
<input name="reason" required placeholder="退款原因">
<input name="evidence" placeholder="证据说明(照片说明等)">
<button>申请退款</button></form>
<h3>交易争议</h3>
<form method="post" action="/orders/{oid}/dispute">
<input name="reason" required placeholder="争议原因">
<button>发起争议</button></form>"""
        if o["status"] == "completed":
            acts += f"""<h3>交易评价(买卖双方互评)</h3>
<form method="post" action="/orders/{oid}/review">
<select name="rating"><option value="5">5 星</option><option value="4">4 星</option>
<option value="3">3 星</option><option value="2">2 星</option>
<option value="1">1 星</option></select>
<input name="comment" placeholder="评价内容">
<button>提交评价</button></form>"""
        body = f"""<h2>订单 #{oid}</h2><div class="card">
<p>商品:<a href="/listings/{o['listing_id']}">{esc(listing_title(listing, lang))}</a></p>
<p>商品金额:{yen(o['goods_amount'])} · {t(lang,"commission")}:{yen(o['commission'])}
· {t(lang,"delivery_fee")}:{yen(o['delivery_fee'])} · {t(lang,"total")}:{yen(o['total'])}</p>
<p>状态:{esc(o['status'])} · 支付凭证:{esc(o['payment_ref'] or '—')}</p>
<p class="warn">{t(lang,"mock_payment_note")}</p>{acts}
<h3>金额变动审计</h3><ul>{audit_html}</ul></div>"""
        return page(request, lang, user, "订单", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/orders/{oid}/pay")
def order_pay(request: Request, oid: int, idempotency_key: str = Form(...)):
    """模拟支付,幂等:同一幂等键重复提交只产生一次支付审计事件。
    界面与代码均明确标注模拟,不得宣称为真实完成。"""
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or (o["buyer_id"] != user["id"] and not can_operate(user)):
            raise HTTPException(403, "forbidden")
        if o["status"] in ("paid", "completed"):
            # 已支付:幂等返回,不重复记账
            return redirect(f"/orders/{oid}", "already_paid")
        if o["status"] != "pending_payment":
            return redirect(f"/orders/{oid}", "invalid_state")
        dup = c.execute("SELECT id FROM orders WHERE idempotency_key=? AND id!=?",
                        (idempotency_key, oid)).fetchone()
        if dup:
            return redirect(f"/orders/{oid}", "idempotency_conflict")
        # 支付服务商接口层:默认 Mock(模拟分账明细);持牌档未配置时拒绝,
        # 绝不把模拟当真实收款。
        try:
            intent = get_provider().create_intent(c, o, idempotency_key)
            pay_ref = intent["intent_ref"]
        except Exception:
            return redirect(f"/orders/{oid}", "payment_provider_error")
        c.execute("UPDATE orders SET status='paid',payment_ref=?,idempotency_key=?,"
                  "updated_at=? WHERE id=?",
                  (pay_ref, idempotency_key, now_tokyo(), oid))
        c.execute("INSERT INTO order_audit(order_id,event,amount_delta,note,created_at)"
                  " VALUES(?,?,?,?,?)",
                  (oid, "mock_payment", o["total"], "模拟支付,非真实扣款", now_tokyo()))
        c.execute("UPDATE listings SET status='sold' WHERE id=?", (o["listing_id"],))
        c.commit()
        return redirect(f"/orders/{oid}", "mock_paid")
    finally:
        c.close()


@app.post("/orders/{oid}/complete")
def order_complete(request: Request, oid: int):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or (o["buyer_id"] != user["id"] and not can_operate(user)):
            raise HTTPException(403, "forbidden")
        if not can_transition(ORDER_TRANSITIONS, o["status"], "completed"):
            return redirect(f"/orders/{oid}", "invalid_state")
        c.execute("UPDATE orders SET status='completed',updated_at=? WHERE id=?",
                  (now_tokyo(), oid))
        c.execute("INSERT INTO order_audit(order_id,event,amount_delta,note,created_at)"
                  " VALUES(?,?,?,?,?)", (oid, "completed", 0, "buyer confirmed", now_tokyo()))
        if o["is_platform_sale"]:
            c.execute("UPDATE inventory SET status='sold' WHERE listing_id=?",
                      (o["listing_id"],))
        c.commit()
        return redirect(f"/orders/{oid}", "completed")
    finally:
        c.close()


@app.post("/orders/{oid}/cancel")
def order_cancel(request: Request, oid: int):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or (o["buyer_id"] != user["id"] and not can_operate(user)):
            raise HTTPException(403, "forbidden")
        if not can_transition(ORDER_TRANSITIONS, o["status"], "cancelled"):
            return redirect(f"/orders/{oid}", "invalid_state")
        c.execute("UPDATE orders SET status='cancelled',updated_at=? WHERE id=?",
                  (now_tokyo(), oid))
        c.execute("INSERT INTO order_audit(order_id,event,amount_delta,note,created_at)"
                  " VALUES(?,?,?,?,?)", (oid, "cancelled", 0, "cancelled", now_tokyo()))
        c.execute("UPDATE listings SET status='active' WHERE id=?", (o["listing_id"],))
        c.commit()
        return redirect(f"/orders/{oid}", "cancelled")
    finally:
        c.close()


# ---------------- buyback ----------------
@app.post("/buyback/new")
def buyback_new(request: Request, listing_id: int = Form(...)):
    user = require_user(request)
    c = conn()
    try:
        listing = c.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not listing or listing["seller_id"] != user["id"] \
                or listing["is_platform_owned"] or listing["status"] != "active":
            raise HTTPException(403, "forbidden")
        r = local_ai_assist(c, listing["title_zh"] or listing["title_ja"],
                            listing["desc_zh"] or "", listing["condition_grade"], None)
        if r["price_low"] is not None:
            status, basis = "estimated", r["price_basis"]
        else:
            status, basis = "submitted", "no_sample"
        cur = c.execute(
            "INSERT INTO buybacks(listing_id,seller_id,status,ai_low,ai_high,"
            "ai_confidence,ai_basis,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (listing_id, user["id"], status, r["price_low"], r["price_high"],
             r["price_confidence"], basis, now_tokyo(), now_tokyo()))
        c.commit()
        return redirect(f"/buyback/{cur.lastrowid}", "buyback_submitted")
    finally:
        c.close()


@app.get("/buyback/{bid}")
def buyback_detail(request: Request, bid: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        b = c.execute("SELECT * FROM buybacks WHERE id=?", (bid,)).fetchone()
        if not b or (user["id"] != b["seller_id"] and not can_operate(user)
                     and not can_appraise(user)):
            raise HTTPException(403, "forbidden")
        listing = c.execute("SELECT * FROM listings WHERE id=?", (b["listing_id"],)).fetchone()
        params = json.loads(d.get_setting(c, "buyback_params") or "{}")
        cat = d.category_by_id(c, listing["category_id"])
        factor = (params.get("by_category") or {}).get(cat["slug"], 0.15) \
            if cat else 0.15
        inv_count = c.execute("SELECT COUNT(*) FROM inventory WHERE status='in_stock'"
                              ).fetchone()[0]
        penalty = min(params.get("max_inventory_penalty", 0.10),
                      inv_count * params.get("inventory_penalty_per_unit", 0.02))
        suggested = int(listing["price"] * max(0.02, factor - penalty))
        acts = ""
        st = b["status"]
        if can_operate(user) and st in ("submitted", "estimated"):
            acts += f'<form method="post" action="/buyback/{bid}/review"><button>进入审核</button></form>'
        if can_operate(user) and st == "reviewing":
            acts += f"""<form method="post" action="/buyback/{bid}/quote">
<input name="quote" type="number" min="1" required placeholder="平台报价 ¥">
<button>发出报价</button></form>"""
        if can_operate(user) and st in ("submitted", "estimated", "reviewing", "quoted"):
            acts += f'<form method="post" action="/buyback/{bid}/reject"><button>拒绝收购(平台有权不收)</button></form>'
        if user["id"] == b["seller_id"] and st == "quoted":
            acts += f'<form method="post" action="/buyback/{bid}/accept"><button>接受报价</button></form>'
        if st == "accepted":
            acts += f"""<form method="post" action="/buyback/{bid}/pickup">
<input name="pickup_at" placeholder="预约取货时间,如 2026-11-10 14:00" required>
<button>预约取货</button></form>"""
        if can_appraise(user) and st == "pickup_scheduled":
            acts += f"""<form method="post" action="/buyback/{bid}/inspect">
<input name="inspection_note" placeholder="验货记录" required><button>验货通过</button></form>"""
        if can_operate(user) and st == "inspected":
            acts += f"""<form method="post" action="/buyback/{bid}/pay">
<input name="resale_price" type="number" min="1" required placeholder="自营售价 ¥">
<button>收购付款并入库</button></form>"""
        ai_html = ""
        if b["ai_low"] is not None:
            ai_html = f"<p>AI 参考区间: {yen(b['ai_low'])} ~ {yen(b['ai_high'])} " \
                      f"(可信度 {esc(b['ai_confidence'])} · 依据 {esc(b['ai_basis'])})</p>"
        else:
            ai_html = ("<p class='warn'>暂无样本:平台暂无同类真实成交可供参考,"
                       "AI 未给出参考价。AI 估价不是最终收购承诺。</p>")
        body = f"""<h2>买断申请 #{bid}</h2><div class="card">
<p>商品:<a href="/listings/{b['listing_id']}">{esc(listing_title(listing, lang))}</a>
· 挂牌价 {yen(listing['price'])} · 状态:{esc(st)}</p>{ai_html}
<p>建议报价参考(人工可改,非固定比例):{yen(suggested)}
(品类因子 {factor} - 库存惩罚 {penalty:.0%})</p>
<p>平台报价:{yen(b['quote'])} · 预约取货:{esc(b['pickup_at'] or '—')}
· 验货:{esc(b['inspection_note'] or '—')} · 收购成本:{yen(b['acquisition_cost'])}</p>
<p class="warn">平台有权拒绝收购,不承诺回收所有商品;AI 估价不是最终收购承诺。</p>
{acts}</div>"""
        return page(request, lang, user, "买断申请", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


def _buyback_transition(request, bid, target, role_check, extra=None):
    user = require_user(request)
    c = conn()
    try:
        b = c.execute("SELECT * FROM buybacks WHERE id=?", (bid,)).fetchone()
        if not b or not role_check(user, b):
            raise HTTPException(403, "forbidden")
        if not can_transition(BUYBACK_TRANSITIONS, b["status"], target):
            return redirect(f"/buyback/{bid}", "invalid_state")
        sql = "UPDATE buybacks SET status=?,updated_at=? WHERE id=?"
        args = [target, now_tokyo(), bid]
        if extra:
            sql = ("UPDATE buybacks SET status=?,updated_at=?," +
                   ",".join(f"{k}=?" for k in extra) + " WHERE id=?")
            args = [target, now_tokyo()] + list(extra.values()) + [bid]
        c.execute(sql, args)
        c.commit()
        return redirect(f"/buyback/{bid}", target)
    finally:
        c.close()


@app.post("/buyback/{bid}/review")
def buyback_review(request: Request, bid: int):
    return _buyback_transition(request, bid, "reviewing",
                               lambda u, b: can_operate(u))


@app.post("/buyback/{bid}/reject")
def buyback_reject(request: Request, bid: int):
    return _buyback_transition(request, bid, "rejected",
                               lambda u, b: can_operate(u))


@app.post("/buyback/{bid}/quote")
def buyback_quote(request: Request, bid: int, quote: int = Form(...)):
    return _buyback_transition(request, bid, "quoted",
                               lambda u, b: can_operate(u), {"quote": quote})


@app.post("/buyback/{bid}/accept")
def buyback_accept(request: Request, bid: int):
    return _buyback_transition(request, bid, "accepted",
                               lambda u, b: u["id"] == b["seller_id"])


@app.post("/buyback/{bid}/pickup")
def buyback_pickup(request: Request, bid: int, pickup_at: str = Form(...)):
    return _buyback_transition(request, bid, "pickup_scheduled",
                               lambda u, b: u["id"] == b["seller_id"] or can_operate(u),
                               {"pickup_at": pickup_at})


@app.post("/buyback/{bid}/inspect")
def buyback_inspect(request: Request, bid: int, inspection_note: str = Form(...)):
    return _buyback_transition(request, bid, "inspected",
                               lambda u, b: can_appraise(u),
                               {"inspection_note": inspection_note})


@app.post("/buyback/{bid}/pay")
def buyback_pay(request: Request, bid: int, resale_price: int = Form(...)):
    """收购付款 -> 原商品售出 -> 生成平台自营商品 + 库存记录(成本=报价)。"""
    user = require_user(request)
    c = conn()
    try:
        b = c.execute("SELECT * FROM buybacks WHERE id=?", (bid,)).fetchone()
        if not b or not can_operate(user):
            raise HTTPException(403, "forbidden")
        if not can_transition(BUYBACK_TRANSITIONS, b["status"], "paid"):
            return redirect(f"/buyback/{bid}", "invalid_state")
        listing = c.execute("SELECT * FROM listings WHERE id=?", (b["listing_id"],)).fetchone()
        c.execute("UPDATE buybacks SET status='paid',acquisition_cost=?,updated_at=? "
                  "WHERE id=?", (b["quote"], now_tokyo(), bid))
        cur = c.execute(
            "INSERT INTO listings(seller_id,category_id,title_ja,title_zh,desc_ja,"
            "desc_zh,price,condition_grade,attrs_json,region,size_class,weight_kg,"
            "is_platform_owned,inspection_record,created_at,updated_at) "
            "VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (listing["category_id"], listing["title_ja"], listing["title_zh"],
             listing["desc_ja"], listing["desc_zh"], resale_price,
             listing["condition_grade"], listing["attrs_json"], listing["region"],
             listing["size_class"], listing["weight_kg"], 1,
             b["inspection_note"] or "", now_tokyo(), now_tokyo()))
        new_lid = cur.lastrowid
        c.execute("INSERT INTO inventory(listing_id,buyback_id,cost,status,created_at)"
                  " VALUES(?,?,?,'in_stock',?)", (new_lid, bid, b["quote"], now_tokyo()))
        c.execute("UPDATE listings SET status='sold' WHERE id=?", (listing["id"],))
        c.execute("UPDATE buybacks SET status='completed',updated_at=? WHERE id=?",
                  (now_tokyo(), bid))
        c.commit()
        return redirect(f"/listings/{new_lid}", "buyout_completed")
    finally:
        c.close()


# ---------------- my page ----------------
@app.get("/me")
def me(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        my_listings = c.execute("SELECT * FROM listings WHERE seller_id=? ORDER BY id DESC",
                                (user["id"],)).fetchall()
        my_orders = c.execute("SELECT * FROM orders WHERE buyer_id=? OR seller_id=? "
                              "ORDER BY id DESC", (user["id"], user["id"])).fetchall()
        offers_in = c.execute(
            "SELECT o.* FROM offers o JOIN listings l ON l.id=o.listing_id "
            "WHERE l.seller_id=? ORDER BY o.id DESC", (user["id"],)).fetchall()
        offers_out = c.execute("SELECT * FROM offers WHERE buyer_id=? ORDER BY id DESC",
                               (user["id"],)).fetchall()
        my_bb = c.execute("SELECT * FROM buybacks WHERE seller_id=? ORDER BY id DESC",
                          (user["id"],)).fetchall()

        def rows(title, items):
            inner = "".join(items) or f"<p>{t(lang,'no_data')}</p>"
            return f"<h3>{title}</h3>{inner}"
        li = [f'<div class="card"><a href="/listings/{r["id"]}">'
              f'{esc(listing_title(r, lang))}</a> {yen(r["price"])} · {esc(r["status"])}</div>'
              for r in my_listings]
        od = [f'<div class="card"><a href="/orders/{r["id"]}">订单 #{r["id"]}</a> '
              f'{yen(r["total"])} · {esc(r["status"])}</div>' for r in my_orders]
        oi = []
        for o in offers_in:
            btns = ""
            if o["status"] == "pending":
                btns = (f'<form method="post" action="/offers/{o["id"]}/accept" '
                        f'style="display:inline"><button>接受</button></form>'
                        f'<form method="post" action="/offers/{o["id"]}/reject" '
                        f'style="display:inline"><button>拒绝</button></form>'
                        f'<form method="post" action="/offers/{o["id"]}/counter" '
                        f'style="display:inline"><input name="counter_amount" '
                        f'type="number" min="1" required placeholder="还价"><button>还价</button></form>')
            oi.append(f'<div class="card">议价 #{o["id"]} 商品 #{o["listing_id"]} '
                      f'出价 {yen(o["amount"])} · {esc(o["status"])} {btns}</div>')
        oo = []
        for o in offers_out:
            btn = ""
            if o["status"] == "countered":
                btn = (f'<form method="post" action="/offers/{o["id"]}/accept-counter" '
                       f'style="display:inline"><button>接受还价 {yen(o["counter_amount"])}</button></form>')
            oo.append(f'<div class="card">我的出价 #{o["id"]} 商品 #{o["listing_id"]} '
                      f'{yen(o["amount"])} · {esc(o["status"])} {btn}</div>')
        bb = [f'<div class="card"><a href="/buyback/{r["id"]}">买断申请 #{r["id"]}</a> '
              f'商品 #{r["listing_id"]} · {esc(r["status"])} · 报价 {yen(r["quote"])}</div>'
              for r in my_bb]
        body = (f"<h2>{esc(user['display_name'])} ({esc(user['role'])})</h2>"
                f"<p>{esc(user['email'])} · 地区 {esc(user['region'])}</p>"
                + rows("我的商品", li) + rows("我的订单", od)
                + rows("收到的议价", oi) + rows("我发出的议价", oo)
                + rows("我的买断申请", bb))
        return page(request, lang, user, t(lang, "my_page"), body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


# ---------------- admin ----------------
def admin_page(request, lang, user, title, body, msg=""):
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    nav = """<p><a href="/admin">概览</a> <a href="/admin/users">用户</a>
<a href="/admin/listings">商品</a> <a href="/admin/buybacks">买断</a>
<a href="/admin/orders">订单</a> <a href="/admin/inventory">自营库存</a>
<a href="/admin/auctions">拍卖</a> <a href="/admin/deliveries">配送</a>
<a href="/admin/services">服务</a> <a href="/admin/refunds">退款</a>
<a href="/admin/disputes">争议</a> <a href="/admin/high-value">高价值审核</a>
<a href="/admin/alerts">预警</a> <a href="/admin/profit">利润分析</a>
<a href="/admin/agents">AI 运营</a>
<a href="/admin/settings">参数设置</a> <a href="/admin/expenses">费用</a></p>"""
    return page(request, lang, user, title, nav + body, msg)


@app.get("/admin")
def admin_home(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        s = stats(c)
        body = f"""<h2>经营概览(GMV 与收入严格区分)</h2><table>
<tr><th>指标</th><th>金额</th><th>说明</th></tr>
<tr><td>GMV(平台总交易额)</td><td>{yen(s['gmv'])}</td><td>已支付/已完成订单的商品金额合计,不是收入</td></tr>
<tr><td>其中 C2C 交易额</td><td>{yen(s['c2c_sales'])}</td><td>第三方卖家成交</td></tr>
<tr><td>其中自营销售额</td><td>{yen(s['platform_sales'])}</td><td>平台自营商品售出</td></tr>
<tr><td>佣金收入</td><td>{yen(s['commission_income'])}</td><td>仅 C2C 订单佣金,自营不收佣金</td></tr>
<tr><td>自营毛利</td><td>{yen(s['gross_profit'])}</td><td>自营销售额 - 已售库存成本({yen(s['sold_inventory_cost'])})</td></tr>
<tr><td>经营费用</td><td>{yen(s['expenses'])}</td><td>后台登记的费用合计</td></tr>
<tr><td>经营利润</td><td>{yen(s['operating_profit'])}</td><td>佣金收入 + 自营毛利 - 费用</td></tr>
<tr><td>净利润(税金未计)</td><td>{yen(s['net_profit'])}</td><td>本阶段未计税金,税金接入后另列</td></tr>
<tr><td>买断总成本</td><td>{yen(s['buyback_cost_total'])}</td><td>已完成买断的收购成本合计</td></tr>
</table>"""
        return admin_page(request, lang, user, "管理后台", body,
                          request.query_params.get("msg", ""))
    finally:
        c.close()


@app.get("/admin/users")
def admin_users(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT id,email,display_name,role,region,created_at "
                         "FROM users ORDER BY id").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['email'])}</td>"
            f"<td>{esc(r['display_name'])}</td><td>{esc(r['role'])}</td>"
            f"<td>{esc(r['region'])}</td>"
            f"<td><form method='post' action='/admin/users/{r['id']}/role'>"
            f"<select name='role'><option value='user'>user</option>"
            f"<option value='collector'>collector</option>"
            f"<option value='operator'>operator</option>"
            f"<option value='appraiser'>appraiser</option>"
            f"<option value='courier'>courier</option>"
            f"<option value='admin'>admin</option></select>"
            f"<button>改角色</button></form></td></tr>" for r in rows)
        return admin_page(request, lang, user, "用户管理",
                          f"<table><tr><th>ID</th><th>邮箱</th><th>昵称</th><th>角色</th>"
                          f"<th>地区</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.post("/admin/users/{uid}/role")
def admin_user_role(request: Request, uid: int, role: str = Form(...)):
    user = require_user(request)
    if not can_admin(user):
        raise HTTPException(403, "forbidden")
    if role not in ("user", "collector", "operator", "appraiser", "courier", "admin"):
        raise HTTPException(400, "bad role")
    c = conn()
    try:
        c.execute("UPDATE users SET role=? WHERE id=?", (role, uid)); c.commit()
        return redirect("/admin/users", "role_updated")
    finally:
        c.close()


@app.get("/admin/listings")
def admin_listings(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 200").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td><a href='/listings/{r['id']}'>"
            f"{esc(r['title_zh'] or r['title_ja'])}</a></td><td>{yen(r['price'])}</td>"
            f"<td>{esc(r['status'])}</td><td>{'自营' if r['is_platform_owned'] else '第三方'}</td>"
            f"<td><form method='post' action='/admin/listings/{r['id']}/toggle'>"
            f"<button>{'恢复' if r['status'] == 'removed' else '下架'}</button></form></td></tr>"
            for r in rows)
        return admin_page(request, lang, user, "商品管理",
                          f"<table><tr><th>ID</th><th>标题</th><th>价格</th><th>状态</th>"
                          f"<th>归属</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.post("/admin/listings/{lid}/toggle")
def admin_listing_toggle(request: Request, lid: int):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        r = c.execute("SELECT status FROM listings WHERE id=?", (lid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        new = "active" if r["status"] == "removed" else "removed"
        c.execute("UPDATE listings SET status=? WHERE id=?", (new, lid)); c.commit()
        return redirect("/admin/listings", new)
    finally:
        c.close()


@app.get("/admin/buybacks")
def admin_buybacks(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM buybacks ORDER BY id DESC").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td>{r['listing_id']}</td><td>{esc(r['status'])}</td>"
            f"<td>{yen(r['ai_low'])}~{yen(r['ai_high']) if r['ai_high'] else ''}</td>"
            f"<td>{yen(r['quote'])}</td><td><a href='/buyback/{r['id']}'>处理</a></td></tr>"
            for r in rows)
        return admin_page(request, lang, user, "买断审批",
                          f"<table><tr><th>ID</th><th>商品</th><th>状态</th><th>AI区间</th>"
                          f"<th>报价</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/orders")
def admin_orders(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td>{r['listing_id']}</td><td>{yen(r['goods_amount'])}</td>"
            f"<td>{yen(r['commission'])}</td><td>{yen(r['delivery_fee'])}</td>"
            f"<td>{yen(r['total'])}</td><td>{esc(r['status'])}</td>"
            f"<td><a href='/orders/{r['id']}'>查看</a></td></tr>" for r in rows)
        return admin_page(request, lang, user, "订单",
                          f"<table><tr><th>ID</th><th>商品</th><th>商品金额</th><th>佣金</th>"
                          f"<th>运费</th><th>合计</th><th>状态</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/inventory")
def admin_inventory(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT i.*, l.title_zh, l.title_ja, l.price FROM inventory i "
                         "JOIN listings l ON l.id=i.listing_id ORDER BY i.id DESC").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td><a href='/listings/{r['listing_id']}'>"
            f"{esc(r['title_zh'] or r['title_ja'])}</a></td><td>{yen(r['cost'])}</td>"
            f"<td>{yen(r['price'])}</td><td>{yen(r['price'] - r['cost'])}</td>"
            f"<td>{esc(r['status'])}</td></tr>" for r in rows)
        return admin_page(request, lang, user, "自营库存",
                          f"<table><tr><th>ID</th><th>商品</th><th>收购成本</th><th>售价</th>"
                          f"<th>毛利(未售为预期)</th><th>状态</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/settings")
def admin_settings(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_admin(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rate = d.get_setting(c, "commission_rate")
        regions = d.get_setting(c, "regions")
        params = d.get_setting(c, "buyback_params")
        body = f"""<h2>参数设置(仅管理员)</h2>
<form method="post">
<label>佣金率(0.07~0.10)<input name="commission_rate" value="{esc(rate)}"></label>
<label>地区配置(JSON)<textarea name="regions" rows="10">{esc(regions)}</textarea></label>
<label>买断报价参数(JSON,建议区间输入,最终报价人工确认)"""
        body += f"""<textarea name="buyback_params" rows="10">{esc(params)}</textarea></label>
<button>保存</button></form>"""
        return admin_page(request, lang, user, "参数设置", body,
                          request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/admin/settings")
def admin_settings_post(request: Request, commission_rate: str = Form(...),
                        regions: str = Form(...), buyback_params: str = Form(...)):
    user = require_user(request)
    if not can_admin(user):
        raise HTTPException(403, "forbidden")
    try:
        rate = float(commission_rate)
        if not (0.07 <= rate <= 0.10):
            return redirect("/admin/settings", "rate_out_of_range")
        json.loads(regions)
        json.loads(buyback_params)
    except (ValueError, json.JSONDecodeError):
        return redirect("/admin/settings", "bad_input")
    c = conn()
    try:
        d.set_setting(c, "commission_rate", str(rate))
        d.set_setting(c, "regions", regions)
        d.set_setting(c, "buyback_params", buyback_params)
        return redirect("/admin/settings", "saved")
    finally:
        c.close()


@app.get("/admin/expenses")
def admin_expenses(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    if not can_admin(user):
        raise HTTPException(403, "forbidden")
    body = """<h2>登记费用</h2><form method="post">
<input name="kind" required placeholder="费用类型,如:配送补贴/耗材">
<input name="amount" type="number" min="0" required placeholder="金额 ¥">
<input name="note" placeholder="备注"><button>登记</button></form>"""
    return admin_page(request, lang, user, "费用", body,
                      request.query_params.get("msg", ""))


@app.post("/admin/expenses")
def admin_expenses_post(request: Request, kind: str = Form(...),
                        amount: int = Form(...), note: str = Form("")):
    user = require_user(request)
    if not can_admin(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        c.execute("INSERT INTO expenses(kind,amount,note,created_at) VALUES(?,?,?,?)",
                  (kind, amount, note, now_tokyo()))
        c.commit()
        return redirect("/admin", "expense_added")
    finally:
        c.close()


# ================= 第二阶段:拍卖 =================
@app.get("/auctions")
def auction_list(request: Request):
    lang = lang_from(request)
    c = conn()
    try:
        rows = c.execute("SELECT a.*, l.title_ja, l.title_zh FROM auctions a "
                         "JOIN listings l ON l.id=a.listing_id "
                         "ORDER BY a.id DESC").fetchall()
        cards = ""
        for a in rows:
            bids = c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id",
                             (a["id"],)).fetchall()
            price, _ = compute_price(a, bids)
            cards += (f'<div class="card"><a href="/auctions/{a["id"]}">'
                      f'{esc(a["title_zh"] or a["title_ja"])}</a> · 当前价 '
                      f'{yen(price)} · 出价 {len(bids)} 笔 · 保留价 '
                      f'{yen(a["reserve_price"])} · 结束 {esc(a["ends_at"])} · '
                      f'{esc(a["status"])}</div>')
        body = f"<h2>拍卖专场(任何商品均可拍卖)</h2>{cards or '<p>暂无拍卖</p>'}"
        return page(request, lang, current_user(request), "拍卖", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.get("/auctions/{aid}")
def auction_detail(request: Request, aid: int):
    lang = lang_from(request)
    user = current_user(request)
    c = conn()
    try:
        a = c.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not a:
            raise HTTPException(404, "not found")
        listing = c.execute("SELECT * FROM listings WHERE id=?",
                            (a["listing_id"],)).fetchone()
        bids = c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id DESC",
                         (aid,)).fetchall()
        price, leader = compute_price(a, bids)
        nxt = min_next_bid(a, bids)
        bid_html = "".join(
            f"<li>出价人 #{b['bidder_id']} {yen(b['amount'])}"
            f"{' (代理上限 ' + yen(b['proxy_max']) + ')' if b['proxy_max'] else ''}"
            f" {esc(b['created_at'])}</li>" for b in bids)
        forms = ""
        if user and a["status"] == "active":
            if user["id"] != listing["seller_id"]:
                forms += f"""<h3>出价(最低 {yen(nxt)})</h3>
<form method="post" action="/auctions/{aid}/bid">
<input name="amount" type="number" min="1" required placeholder="出价 ¥">
<input name="proxy_max" type="number" min="0" placeholder="代理上限 ¥(可选)">
<button>出价</button></form>"""
                if a["deposit_required"]:
                    forms += f"""<form method="post" action="/auctions/{aid}/deposit">
<button>交保证金(模拟) {yen(a["deposit_amount"])}</button></form>
<p><small>保证金为模拟托管,非真实收款。</small></p>"""
                if a["buy_now_price"]:
                    forms += f"""<form method="post" action="/auctions/{aid}/buy-now">
<button>一口价 {yen(a["buy_now_price"])} 直接成交</button></form>"""
        if user and can_operate(user) and a["status"] == "active":
            forms += (f'<form method="post" action="/auctions/{aid}/settle">'
                      f'<button>结算拍卖(到结束时间后生效)</button></form>')
        body = f"""<h2>拍卖 #{aid} — {esc(listing_title(listing, lang))}</h2>
<div class="card"><p>当前价 {yen(price)} · 最低下一出价 {yen(nxt)} · 起拍
{yen(a["start_price"])} · 保留价 {yen(a["reserve_price"])} · 最小加价
{yen(a["min_increment"])} · 一口价 {yen(a["buy_now_price"])} · 开始
{esc(a["starts_at"])} · 结束 {esc(a["ends_at"])} · 状态 {esc(a["status"])}
· 保证金 {'需要 ' + yen(a["deposit_amount"]) + '(模拟)' if a["deposit_required"] else '不需要'}</p>
<p>防压线:结束前 5 分钟内出价自动延时 5 分钟。</p>{forms}
<h3>竞价记录</h3><ul>{bid_html or '<li>暂无出价</li>'}</ul></div>"""
        return page(request, lang, user, "拍卖", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/listings/{lid}/auction")
def auction_create(request: Request, lid: int, start_price: int = Form(...),
                   reserve_price: int = Form(0), min_increment: int = Form(100),
                   buy_now_price: int = Form(0), ends_at: str = Form(...),
                   deposit_required: str = Form(""), deposit_amount: int = Form(0)):
    user = require_user(request)
    c = conn()
    try:
        listing = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not listing or listing["seller_id"] != user["id"] \
                or listing["status"] != "active":
            raise HTTPException(403, "forbidden")
        hv = c.execute("SELECT appraisal_status FROM hv_reviews WHERE listing_id=?",
                       (lid,)).fetchone()
        if hv and hv["appraisal_status"] != "approved":
            return redirect(f"/listings/{lid}", "hv_review_pending")
        if c.execute("SELECT id FROM auctions WHERE listing_id=?",
                     (lid,)).fetchone():
            return redirect(f"/listings/{lid}", "auction_exists")
        cur = c.execute(
            "INSERT INTO auctions(listing_id,start_price,reserve_price,"
            "min_increment,buy_now_price,starts_at,ends_at,deposit_required,"
            "deposit_amount,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (lid, start_price, reserve_price, min_increment,
             buy_now_price or None, now_tokyo(), ends_at,
             1 if deposit_required else 0, deposit_amount, now_tokyo()))
        c.commit()
        return redirect(f"/auctions/{cur.lastrowid}", "auction_created")
    finally:
        c.close()


@app.post("/auctions/{aid}/bid")
def auction_bid(request: Request, aid: int, amount: int = Form(...),
                proxy_max: int = Form(0)):
    user = require_user(request)
    c = conn()
    try:
        a = c.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not a:
            raise HTTPException(404, "not found")
        listing = c.execute("SELECT * FROM listings WHERE id=?",
                            (a["listing_id"],)).fetchone()
        if listing["seller_id"] == user["id"]:
            return redirect(f"/auctions/{aid}", "own_listing")
        ok, msg, _ = place_bid(c, a, user["id"], amount,
                               proxy_max or None)
        if not ok:
            return redirect(f"/auctions/{aid}", msg)
        c.commit()
        return redirect(f"/auctions/{aid}", "bid_placed")
    finally:
        c.close()


@app.post("/auctions/{aid}/deposit")
def auction_deposit(request: Request, aid: int):
    user = require_user(request)
    c = conn()
    try:
        a = c.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not a:
            raise HTTPException(404, "not found")
        c.execute("INSERT INTO deposits(auction_id,bidder_id,amount,status,"
                  "created_at) VALUES(?,?,?,?,?)",
                  (aid, user["id"], a["deposit_amount"], "held", now_tokyo()))
        c.commit()
        return redirect(f"/auctions/{aid}", "deposit_held_simulated")
    finally:
        c.close()


@app.post("/auctions/{aid}/buy-now")
def auction_buy_now(request: Request, aid: int):
    user = require_user(request)
    c = conn()
    try:
        a = c.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not a or not a["buy_now_price"] or a["status"] != "active":
            return redirect(f"/auctions/{aid}", "no_buy_now")
        listing = c.execute("SELECT * FROM listings WHERE id=?",
                            (a["listing_id"],)).fetchone()
        if listing["seller_id"] == user["id"]:
            return redirect(f"/auctions/{aid}", "own_listing")
        oid, err = create_order(c, user["id"], listing, a["buy_now_price"])
        if err:
            return redirect(f"/auctions/{aid}", "needs_separate_quote")
        c.execute("UPDATE auctions SET status='ended_sold' WHERE id=?", (aid,))
        c.commit()
        return redirect(f"/orders/{oid}", "buy_now_order")
    finally:
        c.close()


@app.post("/auctions/{aid}/settle")
def auction_settle(request: Request, aid: int):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        a = c.execute("SELECT * FROM auctions WHERE id=?", (aid,)).fetchone()
        if not a:
            raise HTTPException(404, "not found")
        outcome, oid, price = settle_auction(c, a, create_order)
        c.commit()
        if outcome == "sold":
            return redirect(f"/orders/{oid}", "auction_sold")
        return redirect(f"/auctions/{aid}", outcome)
    finally:
        c.close()


# ================= 关注与评价 =================
@app.post("/listings/{lid}/follow")
def follow(request: Request, lid: int):
    user = require_user(request)
    c = conn()
    try:
        c.execute("INSERT OR IGNORE INTO listing_follows(user_id,listing_id,"
                  "created_at) VALUES(?,?,?)", (user["id"], lid, now_tokyo()))
        c.commit()
        return redirect(f"/listings/{lid}", "followed")
    finally:
        c.close()


@app.post("/listings/{lid}/unfollow")
def unfollow(request: Request, lid: int):
    user = require_user(request)
    c = conn()
    try:
        c.execute("DELETE FROM listing_follows WHERE user_id=? AND listing_id=?",
                  (user["id"], lid))
        c.commit()
        return redirect(f"/listings/{lid}", "unfollowed")
    finally:
        c.close()


@app.get("/users/{uid}")
def user_profile(request: Request, uid: int):
    lang = lang_from(request)
    c = conn()
    try:
        u = d.user_by_id(c, uid)
        if not u:
            raise HTTPException(404, "not found")
        rows = c.execute("SELECT rating FROM reviews WHERE reviewee_id=?",
                         (uid,)).fetchall()
        ratings = [r[0] for r in rows]
        avg = round(sum(ratings) / len(ratings), 1) if ratings else None
        items = c.execute("SELECT * FROM reviews WHERE reviewee_id=? ORDER BY id DESC",
                          (uid,)).fetchall()
        rev_html = "".join(
            f'<div class="card">评分 {r["rating"]}/5 · {esc(r["comment"])} '
            f'<small>订单 #{r["order_id"]}</small></div>' for r in items)
        body = (f"<h2>{esc(u['display_name'])} 的信誉</h2>"
                f"<p>平均评分: {avg if avg is not None else '暂无评价'} · "
                f"评价数: {len(ratings)}</p>{rev_html or '<p>暂无评价</p>'}")
        return page(request, lang, current_user(request), "用户信誉", body)
    finally:
        c.close()


@app.post("/orders/{oid}/review")
def order_review(request: Request, oid: int, rating: int = Form(...),
                 comment: str = Form("")):
    user = require_user(request)
    if rating < 1 or rating > 5:
        raise HTTPException(400, "bad rating")
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or o["status"] != "completed":
            return redirect(f"/orders/{oid}", "review_requires_completed")
        if user["id"] not in (o["buyer_id"], o["seller_id"]) or not o["seller_id"]:
            raise HTTPException(403, "forbidden")
        reviewee = o["seller_id"] if user["id"] == o["buyer_id"] else o["buyer_id"]
        dup = c.execute("SELECT id FROM reviews WHERE order_id=? AND reviewer_id=? "
                        "AND reviewee_id=?", (oid, user["id"], reviewee)).fetchone()
        if dup:
            return redirect(f"/orders/{oid}", "already_reviewed")
        c.execute("INSERT INTO reviews(order_id,reviewer_id,reviewee_id,rating,"
                  "comment,created_at) VALUES(?,?,?,?,?,?)",
                  (oid, user["id"], reviewee, rating, comment, now_tokyo()))
        c.commit()
        return redirect(f"/users/{reviewee}", "reviewed")
    finally:
        c.close()


# ================= 配送预约 =================
@app.get("/deliveries")
def delivery_list(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        if can_operate(user) or user["role"] == "courier":
            rows = c.execute("SELECT * FROM deliveries ORDER BY id DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT d.* FROM deliveries d JOIN orders o ON o.id=d.order_id "
                "WHERE o.buyer_id=? OR o.seller_id=? ORDER BY d.id DESC",
                (user["id"], user["id"])).fetchall()
        cards = ""
        for r in rows:
            cards += (f'<div class="card">配送 #{r["id"]} 订单 #{r["order_id"]} · '
                      f'{esc(r["kind"])} · 预约 {esc(r["scheduled_at"] or "—")} · '
                      f'{esc(r["status"])} <a href="/deliveries/{r["id"]}">处理</a></div>')
        body = f"<h2>配送任务</h2>{cards or '<p>暂无配送任务</p>'}"
        return page(request, lang, user, "配送", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.get("/deliveries/{did}")
def delivery_detail(request: Request, did: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        o = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone()
        if not (can_operate(user) or user["role"] == "courier"
                or user["id"] in (o["buyer_id"], o["seller_id"])):
            raise HTTPException(403, "forbidden")
        forms = ""
        if (can_operate(user) or user["role"] == "courier") and r["status"] == "requested":
            forms += (f'<form method="post" action="/deliveries/{did}/assign">'
                      f'<button>接单/派单</button></form>')
        if (can_operate(user) or user["role"] == "courier") \
                and r["status"] == "assigned":
            forms += (f'<form method="post" action="/deliveries/{did}/pickup" '
                      f'enctype="multipart/form-data">'
                      f'<input type="file" name="photo" accept="image/*">'
                      f'<button>取货完成(可附照片)</button></form>')
        if (can_operate(user) or user["role"] == "courier") \
                and r["status"] == "picked_up":
            forms += (f'<form method="post" action="/deliveries/{did}/deliver" '
                      f'enctype="multipart/form-data">'
                      f'<input type="file" name="photo" accept="image/*">'
                      f'<button>交付完成(可附照片)</button></form>')
        if user["id"] == o["buyer_id"] and r["status"] == "delivered":
            forms += (f'<form method="post" action="/deliveries/{did}/confirm">'
                      f'<button>确认收货</button></form>')
        ph = ""
        if r["pickup_photo"]:
            ph += f'<p>取货照片:<img src="/uploads/{r["pickup_photo"]}" style="max-width:100%"></p>'
        if r["delivery_photo"]:
            ph += f'<p>交付照片:<img src="/uploads/{r["delivery_photo"]}" style="max-width:100%"></p>'
        body = (f"<h2>配送 #{did}</h2><div class='card'><p>订单 #{r['order_id']} · "
                f"{esc(r['kind'])} · 预约 {esc(r['scheduled_at'] or '—')} · "
                f"{esc(r['status'])} · 配送员 #{r['courier_id'] or '—'}</p>{ph}{forms}"
                f"</div><p><small>运费沿用订单规则:轻小件 150 日元起按尺寸分档,"
                f"XL 单独报价,不承诺所有物品都能送达。</small></p>")
        return page(request, lang, user, "配送", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/orders/{oid}/delivery-request")
def delivery_request(request: Request, oid: int, kind: str = Form(...),
                     scheduled_at: str = Form("")):
    user = require_user(request)
    if kind not in ("buyer_delivery", "seller_pickup"):
        raise HTTPException(400, "bad kind")
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or user["id"] not in (o["buyer_id"], o["seller_id"]):
            raise HTTPException(403, "forbidden")
        if o["status"] not in ("paid", "completed"):
            return redirect(f"/orders/{oid}", "delivery_requires_paid")
        cur = c.execute("INSERT INTO deliveries(order_id,kind,scheduled_at,"
                        "created_at) VALUES(?,?,?,?)",
                        (oid, kind, scheduled_at, now_tokyo()))
        c.commit()
        return redirect(f"/deliveries/{cur.lastrowid}", "delivery_requested")
    finally:
        c.close()


def _delivery_transition(request, did, target, courier_field=None):
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()
        if not r or not (can_operate(user) or user["role"] == "courier"):
            raise HTTPException(403, "forbidden")
        allowed = {"requested": ("assigned",), "assigned": ("picked_up",),
                   "picked_up": ("delivered",), "delivered": ("confirmed",)}
        if target not in allowed.get(r["status"], ()):
            return redirect(f"/deliveries/{did}", "invalid_state")
        if target == "assigned":
            c.execute("UPDATE deliveries SET status='assigned',courier_id=? "
                      "WHERE id=?", (user["id"], did))
        else:
            c.execute("UPDATE deliveries SET status=? WHERE id=?", (target, did))
        c.commit()
        return redirect(f"/deliveries/{did}", target)
    finally:
        c.close()


@app.post("/deliveries/{did}/assign")
def delivery_assign(request: Request, did: int):
    return _delivery_transition(request, did, "assigned")


async def _delivery_photo(request, did, target, field):
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()
        if not r or not (can_operate(user) or user["role"] == "courier"):
            raise HTTPException(403, "forbidden")
        allowed = {"assigned": ("picked_up",), "picked_up": ("delivered",)}
        if target not in allowed.get(r["status"], ()):
            return redirect(f"/deliveries/{did}", "invalid_state")
        form = await request.form()
        photo = form.get("photo")
        fname = ""
        if photo is not None and getattr(photo, "filename", ""):
            data = await photo.read()
            ext = Path(photo.filename).suffix.lower()
            if ext in ALLOWED_IMG and len(data) <= 5 * 1024 * 1024:
                fname = f"{uuid.uuid4().hex}{ext}"
                (d.UPLOAD_DIR / fname).write_bytes(data)
        c.execute(f"UPDATE deliveries SET status=?,{field}=? WHERE id=?",
                  (target, fname, did))
        c.commit()
        return redirect(f"/deliveries/{did}", target)
    finally:
        c.close()


@app.post("/deliveries/{did}/pickup")
async def delivery_pickup(request: Request, did: int):
    return await _delivery_photo(request, did, "picked_up", "pickup_photo")


@app.post("/deliveries/{did}/deliver")
async def delivery_deliver(request: Request, did: int):
    return await _delivery_photo(request, did, "delivered", "delivery_photo")


@app.post("/deliveries/{did}/confirm")
def delivery_confirm(request: Request, did: int):
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()
        o = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone()
        if not r or user["id"] != o["buyer_id"] or r["status"] != "delivered":
            raise HTTPException(403, "forbidden")
        c.execute("UPDATE deliveries SET status='confirmed' WHERE id=?", (did,))
        c.commit()
        return redirect(f"/deliveries/{did}", "confirmed")
    finally:
        c.close()


# ================= 增值服务订单 =================
@app.get("/services")
def service_catalog(request: Request):
    lang = lang_from(request)
    user = current_user(request)
    c = conn()
    try:
        prices = json.loads(d.get_setting(c, "service_prices") or "{}")
        rows = ""
        for kind, v in prices.items():
            name = v.get(f"name_{lang}") or v.get("name_zh") or kind
            unit = "小时" if v.get("unit") == "hour" else "件"
            rows += (f'<div class="card"><b>{esc(name)}</b> · '
                     f'{yen(v["price"])}/{unit}'
                     f'{" (代售按成交另计)" if kind == "consignment" else ""}</div>')
        form = ""
        if user:
            opts = "".join(f'<option value="{k}">{esc(v.get("name_zh") or k)}'
                           f' {yen(v["price"])}</option>'
                           for k, v in prices.items())
            form = f"""<h3>下服务订单</h3><form method="post" action="/services/new">
<select name="kind">{opts}</select>
<input name="hours" type="number" step="0.5" value="1" placeholder="小时数(按小时计价时)">
<input name="qty" type="number" min="1" value="1" placeholder="件数(按件计价时)">
<input name="listing_id" placeholder="关联商品 ID(可选)">
<input name="buyback_id" placeholder="关联买断申请 ID(可选,用于同一笔结算抵扣)">
<input name="note" placeholder="备注"><button>下单</button></form>"""
        body = (f"<h2>增值服务</h2><p>家居清洁 2,000 日元/小时(可配置,见后台参数)。"
                f"服务订单独立结算;与买断同笔结算时,应收、应付与抵扣金额分项列示。</p>"
                f"{rows}{form}")
        return page(request, lang, user, "增值服务", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/services/new")
def service_create(request: Request, kind: str = Form(...),
                   hours: float = Form(1), qty: int = Form(1),
                   listing_id: str = Form(""), buyback_id: str = Form(""),
                   note: str = Form("")):
    user = require_user(request)
    c = conn()
    try:
        prices = json.loads(d.get_setting(c, "service_prices") or "{}")
        if kind not in prices:
            raise HTTPException(400, "bad service kind")
        unit_price = int(prices[kind]["price"])
        amount = int(unit_price * hours) if prices[kind].get("unit") == "hour" \
            else int(unit_price * qty)
        cur = c.execute(
            "INSERT INTO service_orders(user_id,listing_id,buyback_id,kind,hours,"
            "qty,unit_price,amount,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user["id"], int(listing_id) if listing_id.isdigit() else None,
             int(buyback_id) if buyback_id.isdigit() else None, kind, hours,
             qty, unit_price, amount, note, now_tokyo()))
        c.commit()
        return redirect(f"/services/{cur.lastrowid}", "service_created")
    finally:
        c.close()


@app.get("/services/{sid}")
def service_detail(request: Request, sid: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        s = c.execute("SELECT * FROM service_orders WHERE id=?", (sid,)).fetchone()
        if not s or (user["id"] != s["user_id"] and not can_operate(user)):
            raise HTTPException(403, "forbidden")
        payable, offset_note = 0, ""
        if s["buyback_id"]:
            bb = c.execute("SELECT quote FROM buybacks WHERE id=?",
                           (s["buyback_id"],)).fetchone()
            if bb and bb["quote"]:
                payable = bb["quote"]
                offset_note = (f"<p>同一笔结算:买断应付 {yen(payable)} - "
                               f"服务应收 {yen(s['amount'])} = 净付 "
                               f"{yen(payable - s['amount'])}</p>")
        acts = ""
        if can_operate(user) and s["status"] == "requested":
            acts += f'<form method="post" action="/services/{sid}/confirm"><button>确认接单</button></form>'
        if can_operate(user) and s["status"] == "confirmed":
            acts += f'<form method="post" action="/services/{sid}/start"><button>开始服务</button></form>'
        if can_operate(user) and s["status"] == "in_progress":
            acts += f'<form method="post" action="/services/{sid}/complete"><button>服务完成</button></form>'
        if s["status"] in ("requested", "confirmed"):
            acts += f'<form method="post" action="/services/{sid}/cancel"><button>取消</button></form>'
        body = (f"<h2>服务订单 #{sid}</h2><div class='card'><p>类型 {esc(s['kind'])} · "
                f"单价 {yen(s['unit_price'])} · 小时 {s['hours']} · 件数 {s['qty']} · "
                f"应收 {yen(s['amount'])} · 状态 {esc(s['status'])}</p>"
                f"{offset_note}{acts}</div>")
        return page(request, lang, user, "服务订单", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


def _service_transition(request, sid, target, allowed_from, operator_only=True):
    user = require_user(request)
    c = conn()
    try:
        s = c.execute("SELECT * FROM service_orders WHERE id=?", (sid,)).fetchone()
        if not s:
            raise HTTPException(404, "not found")
        if operator_only and not can_operate(user):
            raise HTTPException(403, "forbidden")
        if not operator_only and user["id"] != s["user_id"] \
                and not can_operate(user):
            raise HTTPException(403, "forbidden")
        if s["status"] not in allowed_from:
            return redirect(f"/services/{sid}", "invalid_state")
        c.execute("UPDATE service_orders SET status=? WHERE id=?", (target, sid))
        c.commit()
        return redirect(f"/services/{sid}", target)
    finally:
        c.close()


@app.post("/services/{sid}/confirm")
def service_confirm(request: Request, sid: int):
    return _service_transition(request, sid, "confirmed", ("requested",))


@app.post("/services/{sid}/start")
def service_start(request: Request, sid: int):
    return _service_transition(request, sid, "in_progress", ("confirmed",))


@app.post("/services/{sid}/complete")
def service_complete(request: Request, sid: int):
    return _service_transition(request, sid, "completed", ("in_progress",))


@app.post("/services/{sid}/cancel")
def service_cancel(request: Request, sid: int):
    return _service_transition(request, sid, "cancelled",
                               ("requested", "confirmed"), operator_only=False)


# ================= 退款与争议 =================
@app.post("/orders/{oid}/refund")
def refund_request(request: Request, oid: int, reason: str = Form(...),
                   evidence: str = Form("")):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or user["id"] != o["buyer_id"]:
            raise HTTPException(403, "forbidden")
        if o["status"] not in ("paid", "completed"):
            return redirect(f"/orders/{oid}", "refund_requires_paid")
        cur = c.execute("INSERT INTO refunds(order_id,applicant_id,reason,"
                        "evidence,created_at) VALUES(?,?,?,?,?)",
                        (oid, user["id"], reason, evidence, now_tokyo()))
        c.commit()
        return redirect(f"/refunds/{cur.lastrowid}", "refund_requested")
    finally:
        c.close()


@app.get("/refunds/{rid}")
def refund_detail(request: Request, rid: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM refunds WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        o = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone()
        if user["id"] not in (o["buyer_id"], o["seller_id"]) \
                and not can_operate(user):
            raise HTTPException(403, "forbidden")
        sug = dispute_agent(r)
        acts = ""
        if can_operate(user) and r["status"] == "requested":
            acts = f"""<form method="post" action="/refunds/{rid}/decide">
<select name="decision"><option value="approved">批准退款</option>
<option value="rejected">驳回</option></select>
<input name="decision_note" placeholder="裁决说明" required>
<button>裁决(须人工确认,写入审计)</button></form>"""
        body = (f"<h2>退款申请 #{rid}</h2><div class='card'><p>订单 #{r['order_id']} · "
                f"原因:{esc(r['reason'])} · 证据:{esc(r['evidence'] or '—')} · "
                f"状态:{esc(r['status'])} · 裁决:{esc(r['decision'] or '—')} · "
                f"说明:{esc(r['decision_note'] or '—')}</p>"
                f"<p>纠纷辅助建议(仅建议,不裁决):{esc(sug['suggestion'])}</p>{acts}</div>")
        return page(request, lang, user, "退款", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/refunds/{rid}/decide")
def refund_decide(request: Request, rid: int, decision: str = Form(...),
                  decision_note: str = Form(...)):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "bad decision")
    c = conn()
    try:
        r = c.execute("SELECT * FROM refunds WHERE id=?", (rid,)).fetchone()
        if not r or r["status"] != "requested":
            return redirect(f"/refunds/{rid}", "invalid_state")
        c.execute("UPDATE refunds SET status='decided',decision=?,decision_by=?,"
                  "decision_note=? WHERE id=?",
                  (decision, user["id"], decision_note, rid))
        if decision == "approved":
            o = c.execute("SELECT * FROM orders WHERE id=?",
                          (r["order_id"],)).fetchone()
            c.execute("UPDATE orders SET status='refunded',updated_at=? WHERE id=?",
                      (now_tokyo(), r["order_id"]))
            c.execute("INSERT INTO order_audit(order_id,event,amount_delta,note,"
                      "created_at) VALUES(?,?,?,?,?)",
                      (r["order_id"], "refund_approved", -o["total"],
                       f"refund decided by operator {user['id']}: {decision_note}",
                       now_tokyo()))
            try:
                get_provider().refund(c, o, o["total"])
            except Exception:
                pass
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "refund_decide", "refund", rid,
                   f"{decision}: {decision_note}", now_tokyo()))
        c.commit()
        return redirect(f"/refunds/{rid}", "decided")
    finally:
        c.close()


@app.post("/orders/{oid}/dispute")
def dispute_create(request: Request, oid: int, reason: str = Form(...)):
    user = require_user(request)
    c = conn()
    try:
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o or user["id"] not in (o["buyer_id"], o["seller_id"]):
            raise HTTPException(403, "forbidden")
        cur = c.execute("INSERT INTO disputes(order_id,reporter_id,reason,"
                        "created_at) VALUES(?,?,?,?)",
                        (oid, user["id"], reason, now_tokyo()))
        c.commit()
        return redirect(f"/disputes/{cur.lastrowid}", "dispute_created")
    finally:
        c.close()


@app.get("/disputes/{did}")
def dispute_detail(request: Request, did: int):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        r = c.execute("SELECT * FROM disputes WHERE id=?", (did,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        o = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone()
        if user["id"] not in (o["buyer_id"], o["seller_id"]) \
                and not can_operate(user):
            raise HTTPException(403, "forbidden")
        sug = dispute_agent(r)
        acts = ""
        if can_operate(user) and r["status"] == "open":
            acts = f"""<form method="post" action="/disputes/{did}/decide">
<input name="decision" placeholder="裁决结果" required>
<input name="note" placeholder="裁决说明" required>
<button>裁决(须人工确认,写入审计)</button></form>"""
        body = (f"<h2>争议 #{did}</h2><div class='card'><p>订单 #{r['order_id']} · "
                f"原因:{esc(r['reason'])} · 状态:{esc(r['status'])} · "
                f"裁决:{esc(r['decision'] or '—')} · 说明:{esc(r['note'] or '—')}</p>"
                f"<p>纠纷辅助建议(仅建议,不裁决):{esc(sug['suggestion'])}</p>{acts}</div>")
        return page(request, lang, user, "争议", body,
                    request.query_params.get("msg", ""))
    finally:
        c.close()


@app.post("/disputes/{did}/decide")
def dispute_decide(request: Request, did: int, decision: str = Form(...),
                   note: str = Form(...)):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        r = c.execute("SELECT * FROM disputes WHERE id=?", (did,)).fetchone()
        if not r or r["status"] != "open":
            return redirect(f"/disputes/{did}", "invalid_state")
        c.execute("UPDATE disputes SET status='decided',decision=?,decided_by=?,"
                  "note=? WHERE id=?", (decision, user["id"], note, did))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "dispute_decide", "dispute", did,
                   f"{decision}: {note}", now_tokyo()))
        c.commit()
        return redirect(f"/disputes/{did}", "decided")
    finally:
        c.close()


# ================= 第三阶段:行情 =================
@app.get("/market")
def market_page(request: Request):
    lang = lang_from(request)
    c = conn()
    try:
        cats = category_stats(c)
        rows = ""
        for s in cats:
            rows += (f"<tr><td>{esc(s['name_zh'])}</td><td>{s['listed']}</td>"
                     f"<td>{s['active']}</td><td>{s['completed']}</td>"
                     f"<td>{yen(s['volume'])}</td>"
                     f"<td>{yen(s['avg'])} / {yen(s['median'])}</td>"
                     f"<td>{yen(s['low'])} ~ {yen(s['high'])}</td>"
                     f"<td>{s['follows']}</td>"
                     f"<td>{s['avg_cycle_days'] if s['avg_cycle_days'] is not None else '—'}</td>"
                     f"<td>{esc(s['sample_note'])}</td></tr>")
        top = top_listings(c, 10)
        top_html = "".join(
            f"<li>#{t['id']} {esc(t['title_zh'] or t['title_ja'])} · "
            f"成交 {t['sold_n']} 笔 · 关注 {t['follow_n']} 人 · 挂牌 {yen(t['price'])}</li>"
            for t in top)
        curve = weekly_curve(c)
        curve_html = "".join(
            f"<li>{w['week']}: 成交 {w['count']} 笔"
            f"{' · 均价 ' + yen(w['avg']) if w['avg'] else ' · 暂无成交'}</li>"
            for w in curve)
        coll = collectible_trend(c)
        coll_html = "".join(
            f"<li>{x['slug']}: 真实成交 {x['completed_n']} 笔"
            f"{' · 均价 ' + yen(x['completed_avg']) if x['completed_avg'] else ' · 暂无成交'}"
            f" · 在售 {x['active_n']} 件"
            f"{' · 挂牌均价 ' + yen(x['active_avg']) if x['active_avg'] else ''}</li>"
            for x in coll)
        body = f"""<h2>交易行情(全部基于平台真实订单,演示订单已排除)</h2>
<p class="warn">挂牌价与真实成交价严格区分:下表成交列只统计已支付/已完成订单;
样本不足时已标注,请勿把挂牌价当作成交价。</p>
<h3>各类别交易量与成交价格区间</h3><table><tr><th>类别</th><th>挂牌数</th>
<th>在售数</th><th>成交数</th><th>成交总额</th><th>均价/中位数</th>
<th>成交区间</th><th>关注数</th><th>平均成交周期(天)</th><th>样本说明</th></tr>
{rows}</table>
<h3>热门交易榜 TOP 10</h3><ol>{top_html or '<li>暂无数据</li>'}</ol>
<h3>最近 12 周价格走势(全平台成交均价)</h3><ul>{curve_html}</ul>
<h3>收藏品价格变化(手表/钱币/古董:成交均价 vs 在售挂牌均价)</h3>
<ul>{coll_html}</ul>"""
        return page(request, lang, current_user(request), "行情", body)
    finally:
        c.close()


# ================= 客服 Agent =================
@app.get("/support")
def support_form(request: Request):
    lang = lang_from(request)
    body = """<h2>客服(本地规则问答)</h2><form method="post">
<input name="question" required placeholder="例如:运费怎么算?佣金多少?">
<button>提问</button></form>
<p><small>规则问答由本地规则库回答,不调用外部模型;复杂问题请转人工客服。</small></p>"""
    return page(request, lang, current_user(request), "客服", body,
                request.query_params.get("msg", ""))


@app.post("/support")
def support_ask(request: Request, question: str = Form(...)):
    lang = lang_from(request)
    ans = support_agent(question)
    body = (f"<h2>客服回答</h2><div class='card'><p>问题:{esc(question)}</p>"
            f"<p>{esc(ans['answer'])}</p><p><small>{esc(ans['note'])}</small></p></div>"
            f"<p><a href='/support'>再问一个</a></p>")
    return page(request, lang, current_user(request), "客服", body)


# ================= 后台:二三阶段 =================
@app.get("/admin/auctions")
def admin_auctions(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM auctions ORDER BY id DESC").fetchall()
        tr = "".join(f"<tr><td>{r['id']}</td><td>{r['listing_id']}</td>"
                     f"<td>{yen(r['start_price'])}</td><td>{yen(r['reserve_price'])}</td>"
                     f"<td>{esc(r['ends_at'])}</td><td>{esc(r['status'])}</td>"
                     f"<td><a href='/auctions/{r['id']}'>处理</a></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "拍卖管理",
                          f"<table><tr><th>ID</th><th>商品</th><th>起拍</th><th>保留价</th>"
                          f"<th>结束</th><th>状态</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/deliveries")
def admin_deliveries(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM deliveries ORDER BY id DESC").fetchall()
        tr = "".join(f"<tr><td>{r['id']}</td><td>{r['order_id']}</td>"
                     f"<td>{esc(r['kind'])}</td><td>{esc(r['status'])}</td>"
                     f"<td><a href='/deliveries/{r['id']}'>处理</a></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "配送任务",
                          f"<table><tr><th>ID</th><th>订单</th><th>类型</th><th>状态</th>"
                          f"<th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/services")
def admin_services(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM service_orders ORDER BY id DESC").fetchall()
        tr = "".join(f"<tr><td>{r['id']}</td><td>{esc(r['kind'])}</td>"
                     f"<td>{yen(r['amount'])}</td><td>{esc(r['status'])}</td>"
                     f"<td><a href='/services/{r['id']}'>处理</a></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "服务订单",
                          f"<table><tr><th>ID</th><th>类型</th><th>应收</th><th>状态</th>"
                          f"<th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/refunds")
def admin_refunds(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM refunds ORDER BY id DESC").fetchall()
        tr = "".join(f"<tr><td>{r['id']}</td><td>{r['order_id']}</td>"
                     f"<td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td>"
                     f"<td><a href='/refunds/{r['id']}'>裁决</a></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "退款",
                          f"<table><tr><th>ID</th><th>订单</th><th>原因</th><th>状态</th>"
                          f"<th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/disputes")
def admin_disputes(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM disputes ORDER BY id DESC").fetchall()
        tr = "".join(f"<tr><td>{r['id']}</td><td>{r['order_id']}</td>"
                     f"<td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td>"
                     f"<td><a href='/disputes/{r['id']}'>裁决</a></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "争议",
                          f"<table><tr><th>ID</th><th>订单</th><th>原因</th><th>状态</th>"
                          f"<th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.get("/admin/high-value")
def admin_high_value(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT h.*, l.title_zh, l.title_ja, l.price FROM hv_reviews h "
                         "JOIN listings l ON l.id=h.listing_id ORDER BY h.id DESC").fetchall()
        tr = ""
        for r in rows:
            tr += (f"<tr><td>{r['id']}</td><td><a href='/listings/{r['listing_id']}'>"
                   f"{esc(r['title_zh'] or r['title_ja'])}</a></td><td>{yen(r['price'])}</td>"
                   f"<td>{'已验证' if r['identity_verified'] else '未验证'}</td>"
                   f"<td>{esc(r['appraisal_status'])}</td>"
                   f"<td><form method='post' action='/admin/high-value/{r['id']}/review'>"
                   f"<select name='appraisal_status'><option value='pending'>pending</option>"
                   f"<option value='approved'>approved</option>"
                   f"<option value='rejected'>rejected</option></select>"
                   f"<label><input type='checkbox' name='identity_verified' value='1'>身份已验证</label>"
                   f"<input name='appraisal_note' placeholder='鉴定说明'>"
                   f"<button>保存审核</button></form></td></tr>")
        return admin_page(request, lang_from(request), user, "高价值收藏品审核",
                          f"<table><tr><th>ID</th><th>商品</th><th>价格</th><th>身份</th>"
                          f"<th>鉴定</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.post("/admin/high-value/{hid}/review")
def admin_high_value_review(request: Request, hid: int,
                            appraisal_status: str = Form(...),
                            identity_verified: str = Form(""),
                            appraisal_note: str = Form("")):
    user = require_user(request)
    if not can_appraise(user):
        raise HTTPException(403, "forbidden")
    if appraisal_status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "bad status")
    c = conn()
    try:
        row = c.execute("SELECT listing_id FROM hv_reviews WHERE id=?",
                        (hid,)).fetchone()
        if not row:
            raise HTTPException(404, "not found")
        c.execute("UPDATE hv_reviews SET appraisal_status=?,identity_verified=?,"
                  "appraisal_note=?,reviewer_id=? WHERE id=?",
                  (appraisal_status, 1 if identity_verified else 0,
                   appraisal_note, user["id"], hid))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "hv_review", "hv_review", hid,
                   f"{appraisal_status}: {appraisal_note}", now_tokyo()))
        c.commit()
        return redirect("/admin/high-value", "hv_reviewed")
    finally:
        c.close()


@app.get("/admin/alerts")
def admin_alerts(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rows = c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 200").fetchall()
        tr = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['kind'])}</td>"
            f"<td>{esc(r['target_type'])} #{r['target_id']}</td>"
            f"<td>{esc(r['detail'])}</td><td>{esc(r['severity'])}</td>"
            f"<td>{esc(r['status'])}</td>"
            f"<td><form method='post' action='/admin/alerts/{r['id']}/ack'>"
            f"<button>确认处理</button></form></td></tr>" for r in rows)
        return admin_page(request, lang_from(request), user, "异常预警",
                          f"<table><tr><th>ID</th><th>类型</th><th>对象</th><th>详情</th>"
                          f"<th>级别</th><th>状态</th><th>操作</th></tr>{tr}</table>")
    finally:
        c.close()


@app.post("/admin/alerts/{aid}/ack")
def admin_alert_ack(request: Request, aid: int):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        c.execute("UPDATE alerts SET status='acknowledged' WHERE id=?", (aid,))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "alert_ack", "alert", aid, "acknowledged", now_tokyo()))
        c.commit()
        return redirect("/admin/alerts", "acknowledged")
    finally:
        c.close()


@app.get("/admin/profit")
def admin_profit(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        p = profit_report(c)
        body = f"""<h2>经营利润分析(GMV 不是收入)</h2><table>
<tr><th>指标</th><th>金额</th><th>说明</th></tr>
<tr><td>营业额(turnover)</td><td>{yen(p['turnover'])}</td><td>GMV + 服务收入</td></tr>
<tr><td>GMV</td><td>{yen(p['gmv'])}</td><td>已支付/已完成订单商品金额合计,不是收入</td></tr>
<tr><td>商品销售额(自营)</td><td>{yen(p['platform_sales'])}</td><td>平台自营商品售出</td></tr>
<tr><td>C2C 交易额</td><td>{yen(p['c2c_sales'])}</td><td>第三方卖家成交,平台只收佣金</td></tr>
<tr><td>佣金收入</td><td>{yen(p['commission_income'])}</td><td>仅 C2C 佣金</td></tr>
<tr><td>服务收入</td><td>{yen(p['service_income'])}</td><td>已完成服务订单</td></tr>
<tr><td>商品毛利</td><td>{yen(p['gross_profit'])}</td><td>自营销售额 - 已售库存成本</td></tr>
<tr><td>退款合计</td><td>{yen(p['refunded_total'])}</td><td>已批准退款订单合计</td></tr>
<tr><td>实际费用</td><td>{yen(p['expenses'])}</td><td>后台登记费用</td></tr>
<tr><td>经营利润</td><td>{yen(p['operating_profit_full'])}</td><td>佣金 + 毛利 + 服务收入 - 退款 - 费用</td></tr>
<tr><td>净利润(税金未计)</td><td>{yen(p['net_profit_full'])}</td><td>税金接入后另列</td></tr>
</table>"""
        return admin_page(request, lang_from(request), user, "利润分析", body)
    finally:
        c.close()


@app.get("/admin/agents")
def admin_agents(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        rep = ops_agent(c)
        sugg = c.execute("SELECT * FROM price_suggestions ORDER BY id DESC "
                         "LIMIT 50").fetchall()
        sugg_html = ""
        for s in sugg:
            acts = ""
            if s["status"] == "pending":
                acts = (f'<form method="post" action="/admin/suggestions/{s["id"]}/approve" '
                        f'style="display:inline"><button>批准调价</button></form>'
                        f'<form method="post" action="/admin/suggestions/{s["id"]}/reject" '
                        f'style="display:inline"><button>驳回</button></form>')
            sugg_html += (f'<div class="card">商品 #{s["listing_id"]} 建议价 '
                          f'{yen(s["suggested_price"])} · {esc(s["reason"])} · '
                          f'{esc(s["status"])} {acts}</div>')
        body = f"""<h2>AI 运营 Agent(全部本地启发式,零 API 成本)</h2>
<p>经营摘要:GMV {yen(rep['gmv'])} · 佣金收入 {yen(rep['commission_income'])} ·
自营毛利 {yen(rep['gross_profit'])} · 服务收入 {yen(rep['service_income'])} ·
经营利润 {yen(rep['operating_profit'])} · 净利润(税前) {yen(rep['net_profit'])}</p>
<p><small>高风险操作(收购付款、封禁、争议裁决)只接受人工审批,Agent 只给建议,
建议与裁决均写入审计记录。</small></p>
<form method="post" action="/admin/agents/run-anomalies">
<button>运行异常监控扫描</button></form>
<form method="post" action="/admin/agents/run-pricing">
<button>生成自营库存调价建议</button></form>
<h3>调价建议(运营确认后才生效)</h3>{sugg_html or '<p>暂无建议</p>'}
<p><a href="/admin/alerts">查看异常预警</a> · <a href="/admin/profit">利润分析</a></p>"""
        return admin_page(request, lang_from(request), user, "AI 运营", body)
    finally:
        c.close()


@app.post("/admin/agents/run-anomalies")
def admin_run_anomalies(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        found = anomaly_agent(c)
        for kind, ttype, tid, detail, sev in found:
            c.execute("INSERT INTO alerts(kind,target_type,target_id,detail,"
                      "severity,created_at) VALUES(?,?,?,?,?,?)",
                      (kind, ttype, tid, detail, sev, now_tokyo()))
        c.commit()
        return redirect("/admin/alerts", f"scanned_{len(found)}")
    finally:
        c.close()


@app.post("/admin/agents/run-pricing")
def admin_run_pricing(request: Request):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        for s in inventory_agent(c):
            dup = c.execute("SELECT id FROM price_suggestions WHERE listing_id=? "
                            "AND status='pending'", (s["listing_id"],)).fetchone()
            if not dup:
                c.execute("INSERT INTO price_suggestions(listing_id,"
                          "suggested_price,reason,created_at) VALUES(?,?,?,?)",
                          (s["listing_id"], s["suggested_price"], s["reason"],
                           now_tokyo()))
        c.commit()
        return redirect("/admin/agents", "suggestions_generated")
    finally:
        c.close()


@app.post("/admin/suggestions/{sid}/approve")
def admin_suggestion_approve(request: Request, sid: int):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        s = c.execute("SELECT * FROM price_suggestions WHERE id=?", (sid,)).fetchone()
        if not s or s["status"] != "pending":
            return redirect("/admin/agents", "invalid_state")
        c.execute("UPDATE listings SET price=? WHERE id=?",
                  (s["suggested_price"], s["listing_id"]))
        c.execute("UPDATE price_suggestions SET status='approved',decided_by=? "
                  "WHERE id=?", (user["id"], sid))
        c.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                  "note,created_at) VALUES(?,?,?,?,?,?)",
                  (user["id"], "price_change", "listing", s["listing_id"],
                   f"approved suggestion to {s['suggested_price']}", now_tokyo()))
        c.commit()
        return redirect("/admin/agents", "price_updated")
    finally:
        c.close()


@app.post("/admin/suggestions/{sid}/reject")
def admin_suggestion_reject(request: Request, sid: int):
    user = require_user(request)
    if not can_operate(user):
        raise HTTPException(403, "forbidden")
    c = conn()
    try:
        c.execute("UPDATE price_suggestions SET status='rejected',decided_by=? "
                  "WHERE id=?", (user["id"], sid))
        c.commit()
        return redirect("/admin/agents", "suggestion_rejected")
    finally:
        c.close()


# ================= 我的页面补充:拍卖/配送/服务 =================
@app.get("/me/extra")
def me_extra(request: Request):
    lang = lang_from(request)
    user = require_user(request)
    c = conn()
    try:
        aucs = c.execute(
            "SELECT a.* FROM auctions a JOIN listings l ON l.id=a.listing_id "
            "WHERE l.seller_id=? ORDER BY a.id DESC", (user["id"],)).fetchall()
        aucs_html = "".join(
            f'<div class="card"><a href="/auctions/{a["id"]}">拍卖 #{a["id"]}</a> '
            f'商品 #{a["listing_id"]} · {esc(a["status"])}</div>' for a in aucs)
        dels = c.execute(
            "SELECT d.* FROM deliveries d JOIN orders o ON o.id=d.order_id "
            "WHERE o.buyer_id=? OR o.seller_id=? ORDER BY d.id DESC",
            (user["id"], user["id"])).fetchall()
        dels_html = "".join(
            f'<div class="card"><a href="/deliveries/{d["id"]}">配送 #{d["id"]}</a> '
            f'订单 #{d["order_id"]} · {esc(d["status"])}</div>' for d in dels)
        servs = c.execute("SELECT * FROM service_orders WHERE user_id=? "
                          "ORDER BY id DESC", (user["id"],)).fetchall()
        serv_html = "".join(
            f'<div class="card"><a href="/services/{s["id"]}">服务 #{s["id"]}</a> '
            f'{esc(s["kind"])} · {yen(s["amount"])} · {esc(s["status"])}</div>'
            for s in servs)
        body = (f"<h2>我的拍卖 / 配送 / 服务</h2><h3>我的拍卖</h3>"
                f"{aucs_html or '<p>暂无</p>'}<h3>我的配送</h3>"
                f"{dels_html or '<p>暂无</p>'}<h3>我的服务订单</h3>"
                f"{serv_html or '<p>暂无</p>'}")
        return page(request, lang, user, "我的拍卖/配送/服务", body)
    finally:
        c.close()

