"""Native app JSON boundary. Commands call the existing business entry points."""
from contextlib import closing
import inspect
import json
import threading
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.params import File, Form
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from . import db as d
from .security import audit_log, can_admin, can_appraise, can_operate, check_rate_limit, now_tokyo

router = APIRouter(prefix="/api/v1")
# Serialize commands in this single-process SQLite application, including retries.
_command_lock = threading.Lock()
PUBLIC_ACTIONS = {"register", "login"}
ACTIONS = """
register login logout listing_create listing_photo_add listing_photo_cover
listing_photo_delete listing_photo_replace oneclick_upload oneclick_photo_add
oneclick_photo_delete oneclick_model_confirm oneclick_recognize oneclick_publish
draft_photo_cover draft_photo_replace
ai_job_create buy offer offer_accept offer_reject offer_counter offer_accept_counter
thread_post order_pay order_complete order_cancel buyback_new buyback_review
buyback_reject buyback_quote buyback_accept buyback_pickup buyback_inspect buyback_pay
auction_create auction_bid auction_deposit auction_buy_now auction_settle follow unfollow
order_review delivery_request delivery_assign delivery_pickup delivery_deliver
delivery_confirm service_create service_confirm service_start service_complete
service_cancel refund_request refund_decide dispute_create dispute_decide
admin_user_role admin_listing_toggle admin_settings_post admin_expenses_post
admin_high_value_review admin_alert_ack admin_run_anomalies admin_run_pricing
admin_suggestion_approve admin_suggestion_reject
""".split()
ERROR_MESSAGES = {
    "invalid_login", "email_exists", "not_available", "own_listing", "cannot_offer",
    "hv_review_pending", "needs_separate_quote", "auction_exists", "recognize_first",
    "no_buy_now", "invalid_state", "idempotency_conflict", "payment_provider_error",
    "delivery_requires_paid", "refund_requires_paid", "review_requires_completed",
    "rate_out_of_range", "bad_input",
    "auction_not_active", "auction_not_started", "auction_ended", "deposit_required",
    "proxy_below_bid", "not_ended", "needs_quote",
}
TABLES = {
    "listings": ("listings", None),
    "orders": ("orders", "buyer_id=? OR seller_id=?"),
    "offers": ("offers", "buyer_id=? OR listing_id IN (SELECT id FROM listings WHERE seller_id=?)"),
    "buybacks": ("buybacks", "seller_id=?"),
    "drafts": ("oneclick_drafts", "user_id=?"),
    "deliveries": ("deliveries", "order_id IN (SELECT id FROM orders WHERE buyer_id=? OR seller_id=?)"),
    "services": ("service_orders", "user_id=?"),
    "refunds": ("refunds", "applicant_id=? OR order_id IN (SELECT id FROM orders WHERE seller_id=?)"),
    "disputes": ("disputes", "reporter_id=? OR order_id IN (SELECT id FROM orders WHERE seller_id=?)"),
    "jobs": ("ai_jobs", "user_id=?"),
    "auctions": ("auctions", None),
}
ADMIN_TABLES = {
    "users": "users", "inventory": "inventory", "alerts": "alerts",
    "high-value": "hv_reviews", "suggestions": "price_suggestions",
    "expenses": "expenses", "audit": "audit_log",
}


def legacy():
    from . import main
    return main


def principal(request, optional=False):
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        if optional:
            return None, None
        raise HTTPException(401, "login_required")
    token = header[7:]
    with closing(d.connect()) as c:
        row = c.execute(
            "SELECT u.id,u.email,u.display_name,u.role,u.phone,u.region "
            "FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token=? AND s.expires_at>?", (token, now_tokyo())).fetchone()
    if not row:
        raise HTTPException(401, "session_expired")
    if not check_rate_limit(f"api:{row['id']}", 300, 60):
        raise HTTPException(429, "too_many_requests")
    return dict(row), token


def native_request(request, token, form):
    scope = dict(request.scope)
    headers = [(k, v) for k, v in request.scope["headers"] if k.lower() != b"cookie"]
    if token:
        headers.append((b"cookie", f"yuno_session={token}".encode()))
    scope["headers"] = headers
    cloned = Request(scope, receive=request.receive)
    cloned._form = form
    return cloned


def clean(row):
    item = dict(row)
    for name in ("pw_hash", "salt", "token", "idempotency_key"):
        item.pop(name, None)
    for key in list(item):
        if key.endswith("_json"):
            try:
                item[key[:-5]] = json.loads(item.pop(key) or "{}")
            except (ValueError, TypeError):
                item[key[:-5]] = {}
    return item


def listing(c, row):
    item = clean(row)
    item["price"] = legacy().effective_price(row)
    item["photos"] = [dict(r) | {"url": "/uploads/" + r["filename"]}
                      for r in c.execute("SELECT * FROM images WHERE listing_id=? ORDER BY sort,id",
                                         (row["id"],))]
    cat = d.category_by_id(c, row["category_id"])
    item["category_slug"] = cat["slug"]
    item["category_ja"] = cat["name_ja"]
    item["category_zh"] = cat["name_zh"]
    item["review"] = next((clean(r) for r in c.execute(
        "SELECT * FROM hv_reviews WHERE listing_id=?", (row["id"],))), None)
    # Cost/profit fields belong to the operations API.
    return item


def action_schema(name):
    fn = command_function(name)
    fields = []
    for key, param in inspect.signature(fn).parameters.items():
        if key == "request":
            continue
        default = param.default
        required = default is inspect.Parameter.empty
        file = isinstance(default, File)
        if isinstance(default, Form):
            default = default.default
            required = param.default.is_required()
        fields.append({
            "name": key, "required": required,
            "default": None if required else default,
            "type": "photos" if file else ("integer" if param.annotation is int else
                     "number" if param.annotation is float else "text"),
            "multiple": file and "list" in str(param.annotation),
        })
    if name in ("delivery_pickup", "delivery_deliver"):
        fields.append({"name": "photo", "type": "photos", "multiple": False,
                       "required": False, "default": None})
    return {"name": name, "fields": fields}


@router.get("/config")
def config():
    with closing(d.connect()) as c:
        return {
            "categories": [clean(r) for r in c.execute("SELECT * FROM categories")],
            "regions": legacy().active_regions(c),
            "services": d.FINAL_SERVICE_PRICES,
            "commission_rate": legacy().commission_rate(c),
            "simulation": {"payment": True, "delivery": True},
            "max_photos": 10, "currency": "JPY",
            "actions": [action_schema(a) for a in ACTIONS],
        }


@router.get("/me")
def me(request: Request):
    user, _ = principal(request)
    return {"user": user, "simulation": True}


@router.post("/actions/{action}")
async def command(action: str, request: Request):
    if action not in ACTIONS:
        raise HTTPException(404, "unknown_action")
    user, token = (None, None) if action in PUBLIC_ACTIONS else principal(request)
    appraiser_action = action == "admin_high_value_review" and can_appraise(user)
    if action.startswith("admin_") and not can_operate(user) and not appraiser_action:
        raise HTTPException(403, "forbidden")
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "bad_json")
        if not isinstance(body, dict):
            raise HTTPException(400, "bad_input")
        form = FormData([(k, str(v) if not isinstance(v, str) else v)
                         for k, v in body.items() if v is not None])
    else:
        form = await request.form(max_files=10, max_fields=100)
    fn = command_function(action)
    kwargs = {}
    for key, param in inspect.signature(fn).parameters.items():
        if key == "request":
            continue
        default = param.default
        if isinstance(default, File):
            value = form.getlist(key) if "list" in str(param.annotation) else form.get(key)
            if default.is_required() and not value:
                raise HTTPException(400, f"missing_{key}")
        else:
            value = form.get(key)
            if value is None:
                if isinstance(default, Form) and not default.is_required():
                    value = default.default
                elif default is not inspect.Parameter.empty and not isinstance(default, Form):
                    value = default
                else:
                    raise HTTPException(400, f"missing_{key}")
            try:
                value = TypeAdapter(param.annotation).validate_python(value)
            except (ValidationError, ValueError, TypeError):
                raise HTTPException(400, f"invalid_{key}")
        kwargs[key] = value
    cloned = native_request(request, token, form)
    # Lock in worker thread, including async legacy handlers. No await while holding
    # a thread lock on the event loop.
    def invoke():
        with _command_lock:
            if inspect.iscoroutinefunction(fn):
                import anyio
                return anyio.from_thread.run(fn, cloned) if not kwargs else _async_in_thread(fn, cloned, kwargs)
            return fn(cloned, **kwargs)
    result = await run_in_threadpool(invoke)
    if isinstance(result, JSONResponse):
        return result
    location = result.headers.get("location", "/")
    parsed = urlparse(location)
    message = parse_qs(parsed.query).get("msg", [""])[0]
    if message in ERROR_MESSAGES or message.startswith("bid_too_low:"):
        raise HTTPException(401 if message == "invalid_login" else 409, message)
    output = {"location": parsed.path, "message": message, "simulation": True}
    parts = parsed.path.strip("/").split("/")
    if len(parts) == 2 and parts[1].isdigit():
        output["resource"] = {"oneclick": "drafts", "buyback": "buybacks",
                              "users": "users"}.get(parts[0], parts[0])
        output["id"] = int(parts[1])
    if action in PUBLIC_ACTIONS:
        cookies = SimpleCookie()
        cookies.load(result.headers.get("set-cookie", ""))
        if "yuno_session" not in cookies:
            raise HTTPException(400, message or "authentication_failed")
        output["token"] = cookies["yuno_session"].value
        with closing(d.connect()) as c:
            row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
                            "WHERE s.token=?", (output["token"],)).fetchone()
            output["user"] = clean(row)
    return output


def _async_in_thread(fn, request, kwargs):
    from functools import partial
    import anyio
    return anyio.from_thread.run(partial(fn, request, **kwargs))


def command_function(name):
    if name == "draft_photo_cover":
        return draft_photo_cover
    if name == "draft_photo_replace":
        return draft_photo_replace
    return getattr(legacy(), name)


def draft_photo_cover(request: Request, did: int, idx: int):
    user = legacy().require_user(request)
    with closing(d.connect()) as c:
        draft = legacy()._draft_or_403(c, did, user)
        if draft["status"] == "published":
            raise HTTPException(409, "invalid_state")
        photos, _ = legacy()._draft_photos(draft)
        if idx < 0 or idx >= len(photos):
            raise HTTPException(400, "bad_photo_index")
        photos.insert(0, photos.pop(idx))
        legacy()._set_draft_photos(c, did, photos, draft)
        audit_log(c, user["id"], "draft_photo_cover", "oneclick_draft", did,
                  f"photo_index={idx}")
        c.commit()
    return legacy().redirect(f"/oneclick/{did}", "cover_changed")


async def draft_photo_replace(request: Request, did: int, idx: int,
                              photo: UploadFile = File(...)):
    user = legacy().require_user(request)
    blobs = await legacy()._read_uploads([photo])
    if len(blobs) != 1:
        raise HTTPException(400, "bad_image")
    with closing(d.connect()) as c:
        draft = legacy()._draft_or_403(c, did, user)
        if draft["status"] == "published":
            raise HTTPException(409, "invalid_state")
        photos, _ = legacy()._draft_photos(draft)
        if idx < 0 or idx >= len(photos):
            raise HTTPException(400, "bad_photo_index")
        legacy()._save_upload_blobs(blobs, c)
        photos[idx] = blobs[0][0]
        legacy()._set_draft_photos(c, did, photos, draft)
        c.execute("UPDATE oneclick_drafts SET status='uploaded' WHERE id=?", (did,))
        audit_log(c, user["id"], "draft_photo_replace", "oneclick_draft", did,
                  f"photo_index={idx}")
        c.commit()
    return legacy().redirect(f"/oneclick/{did}", "photo_replaced")


@router.get("/market")
def market():
    with closing(d.connect()) as c:
        return {"moves": legacy().listing_price_moves(c),
                "categories": legacy().category_stats(c),
                "top": legacy().top_listings(c, 10),
                "curve": legacy().weekly_curve(c),
                "collectibles": legacy().collectible_trend(c)}


@router.get("/rules/{key}")
def rules(key: str, request: Request):
    functions = {"terms": "terms_page", "privacy": "privacy_page",
                 "returns": "returns_page", "prohibited": "prohibited_page"}
    if key not in functions:
        raise HTTPException(404, "not_found")
    # These public rules are authored in one place. Extract text blocks for a
    # native renderer, never return HTML to the app.
    from html.parser import HTMLParser
    class RulesParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.text = []
        def handle_starttag(self, tag, attrs):
            if tag == "h2":
                self.depth = 1
            if tag == "hr":
                self.depth = 0
            if self.depth and tag in ("p", "h2", "h3", "li", "br"):
                self.text.append("\n")
        def handle_endtag(self, tag):
            pass
        def handle_data(self, data):
            if self.depth:
                self.text.append(data)
    response = getattr(legacy(), functions[key])(native_request(request, None, FormData()))
    parser = RulesParser()
    parser.feed(response.body.decode())
    return {"text": "".join(parser.text).strip()}


@router.get("/threads/{lid}/{buyer_id}")
def messages(lid: int, buyer_id: int, request: Request):
    user, _ = principal(request)
    with closing(d.connect()) as c:
        item = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not item or user["id"] not in (buyer_id, item["seller_id"]):
            raise HTTPException(403, "forbidden")
        return {"items": [clean(r) for r in c.execute(
            "SELECT * FROM messages WHERE listing_id=? AND buyer_id=? ORDER BY id",
            (lid, buyer_id))], "seller_id": item["seller_id"]}


@router.get("/threads")
def threads(request: Request):
    user, _ = principal(request)
    with closing(d.connect()) as c:
        rows = c.execute(
            "SELECT m.* FROM messages m WHERE m.id IN "
            "(SELECT MAX(id) FROM messages WHERE sender_id=? OR receiver_id=? "
            "GROUP BY listing_id,buyer_id) ORDER BY m.id DESC", (user["id"], user["id"]))
        return {"items": [clean(r) for r in rows]}


@router.get("/admin/{resource}")
def admin_data(resource: str, request: Request):
    user, _ = principal(request)
    if not can_operate(user) and not (resource == "high-value" and can_appraise(user)):
        raise HTTPException(403, "forbidden")
    with closing(d.connect()) as c:
        if resource == "profit":
            return {"item": legacy().profit_report(c)}
        if resource == "settings":
            if not can_admin(user):
                raise HTTPException(403, "forbidden")
            return {"item": {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}}
        table = ADMIN_TABLES.get(resource)
        if not table:
            raise HTTPException(404, "not_found")
        if resource == "users" and not can_admin(user):
            raise HTTPException(403, "forbidden")
        return {"items": [clean(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 200")]}


@router.get("/profiles/{user_id}")
def profile(user_id: int):
    with closing(d.connect()) as c:
        user = c.execute("SELECT id,display_name,role,region FROM users WHERE id=?",
                         (user_id,)).fetchone()
        if not user:
            raise HTTPException(404, "not_found")
        rating = c.execute("SELECT COUNT(*) count,AVG(rating) average "
                           "FROM reviews WHERE reviewee_id=?", (user_id,)).fetchone()
        return {"item": dict(user) | dict(rating), "reviews": [clean(r) for r in c.execute(
            "SELECT rating,comment,created_at FROM reviews WHERE reviewee_id=? ORDER BY id DESC LIMIT 50",
            (user_id,))]}


def scope_filter(resource, user, admin=False):
    table, clause = TABLES[resource]
    if clause and not user:
        raise HTTPException(401, "login_required")
    if admin and can_operate(user):
        return table, "1=1", []
    if resource == "deliveries" and user and user["role"] == "courier":
        return table, "courier_id=? OR status='requested'", [user["id"]]
    return table, clause or "1=1", [user["id"]] * clause.count("?") if clause else []


@router.get("/{resource}")
def collection(resource: str, request: Request, q: str = "", category: str = "",
               region: str = "", price_min: int = 0, price_max: int = 2_000_000_000,
               owned: bool = False, mine: bool = False, admin: bool = False,
               offset: int = 0, limit: int = 50):
    if resource not in TABLES:
        raise HTTPException(404, "not_found")
    user, _ = principal(request, optional=True)
    table, clause, args = scope_filter(resource, user, admin)
    if resource == "listings":
        if mine:
            if not user:
                raise HTTPException(401, "login_required")
            clause, args = "seller_id=?", [user["id"]]
        else:
            clause = "status='active'"
        clause += " AND price BETWEEN ? AND ? AND (title_ja LIKE ? OR title_zh LIKE ?)"
        args += [price_min, price_max, f"%{q[:200]}%", f"%{q[:200]}%"]
        if category:
            clause += " AND category_id IN (SELECT id FROM categories WHERE slug=?)"
            args.append(category)
        if region:
            clause += " AND region=?"
            args.append(region)
        if owned:
            clause += " AND is_platform_owned=1"
    with closing(d.connect()) as c:
        total = c.execute(f"SELECT COUNT(*) FROM {table} WHERE ({clause})", args).fetchone()[0]
        rows = c.execute(f"SELECT * FROM {table} WHERE ({clause}) ORDER BY id DESC LIMIT ? OFFSET ?",
                         [*args, max(1, min(limit, 100)), max(0, offset)]).fetchall()
        return {"items": [listing(c, r) if resource == "listings" else clean(r) for r in rows],
                "total": total, "offset": max(0, offset)}


@router.get("/{resource}/{item_id}")
def detail(resource: str, item_id: int, request: Request):
    if resource not in TABLES:
        raise HTTPException(404, "not_found")
    user, _ = principal(request, optional=True)
    table, clause, args = scope_filter(resource, user)
    with closing(d.connect()) as c:
        row = c.execute(f"SELECT * FROM {table} WHERE id=? AND ({clause})", [item_id, *args]).fetchone()
        if not row and can_operate(user):
            row = c.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "not_found")
        if resource == "listings" and row["status"] not in ("active", "sold") and (
                not user or (row["seller_id"] != user["id"] and not can_operate(user))):
            raise HTTPException(403, "forbidden")
        item = listing(c, row) if resource == "listings" else clean(row)
        related = {}
        if resource == "drafts":
            photos, draft = legacy()._draft_photos(row)
            item["photos"] = [{"url": "/uploads/" + p} for p in photos]
            item["detail_checklist"] = legacy().detail_checklist_for(draft.get("category_slug", ""))
        if resource in ("orders", "auctions", "buybacks", "offers"):
            lr = c.execute("SELECT * FROM listings WHERE id=?", (row["listing_id"],)).fetchone()
            related["listing"] = listing(c, lr) if lr else None
        if resource == "auctions":
            bids = c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY id", (item_id,)).fetchall()
            item["current_price"], item["leader_id"] = legacy().compute_price(row, bids)
            # Proxy ceilings are private and must never be sent to competitors.
            related["bids"] = [dict(r) for r in c.execute(
                "SELECT id,bidder_id,amount,created_at FROM bids WHERE auction_id=? ORDER BY id DESC",
                (item_id,))]
        if resource == "orders":
            related["audits"] = [clean(r) for r in c.execute(
                "SELECT * FROM order_audit WHERE order_id=? ORDER BY id", (item_id,))]
        if resource == "jobs":
            return {"item": legacy().get_job(c, item_id)}
        return {"item": item, "related": related, "simulation": True}
