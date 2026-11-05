"""第 3 阶段:AI 任务(ai_jobs 表)派发、轮询与后台执行。

状态机: queued -> running -> done / failed, result_json 存结果。
派发后立即返回任务 id,执行在 daemon 线程后台完成,调用方轮询
GET /ai-jobs/{id} 可见状态变化。任务仅所有者或运营可见,他人 403
(由路由层校验,此处 get_job 只取行)。

任务 kind:
  oneclick_recognize: payload {draft_id}。复用 oneclick 的识别/
    鉴定两轴/估价逻辑(与同步 /oneclick/{did}/recognize 相同函数),
    型号已确认时只读缓存中的同型号市场样本(不联网),未确认时
    走型号未确认分支,平台数据绝不进入估价。
  oneclick_valuation: payload {draft_id}。型号未确认 -> 诚实无报价;
    已确认 -> 跑市场搜索(先查缓存,60 秒硬上限),样本喂给
    valuation_interval,市场区间中位数自动填入可编辑草稿
    (draft_json.suggested_price / price_source),样本与各源状态
    一并写入 valuation_json 供页面展示。
  market_search: payload {brand, model, category_slug}。直接跑
    市场搜索并返回结果(样本只来自公开市场抓取或缓存)。
  其他 kind -> failed,error 说明 unknown kind(供失败态测试与排错)。
本模块不 import app.main(避免循环依赖),只用 oneclick/business/
valuation/market_search 等底层函数。
"""
import json
import threading

from . import db as d
from .market_search import cached_market_comps, search_market_comps
from .oneclick import (appraise_two_axis, build_draft, recognize)
from .security import now_tokyo
from .valuation import valuation_interval

JOB_KINDS = ("oneclick_recognize", "oneclick_valuation", "market_search")


def create_job(conn, user_id, kind, payload):
    cur = conn.execute(
        "INSERT INTO ai_jobs(user_id,kind,status,payload_json,result_json,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, kind, "queued", json.dumps(payload or {}, ensure_ascii=False),
         "{}", now_tokyo(), now_tokyo()))
    conn.commit()
    return cur.lastrowid


def get_job(conn, job_id):
    row = conn.execute("SELECT * FROM ai_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "user_id": row["user_id"], "kind": row["kind"],
            "status": row["status"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "result": json.loads(row["result_json"] or "{}")}


def _set_job(conn, job_id, status, result):
    conn.execute("UPDATE ai_jobs SET status=?, result_json=?, updated_at=? "
                 "WHERE id=?",
                 (status, json.dumps(result or {}, ensure_ascii=False),
                  now_tokyo(), job_id))
    conn.commit()


def _draft_photos(draft_json):
    try:
        dr = json.loads(draft_json or "{}")
    except ValueError:
        dr = {}
    photos = [p for p in (dr.get("photos") or []) if p]
    return photos, dr


def _run_recognize(conn, user_id, payload):
    did = payload.get("draft_id")
    draft = conn.execute("SELECT * FROM oneclick_drafts WHERE id=?",
                         (did,)).fetchone()
    if not draft:
        return {"error": "draft not found"}
    if draft["user_id"] != user_id:
        return {"error": "not your draft"}
    if draft["status"] == "published":
        return {"error": "already published"}
    rec = recognize(conn, draft["name"], draft["text"],
                    draft["condition_grade"], draft["price_hint"])
    photos, old_dr = _draft_photos(draft["draft_json"])
    model_confirmed = bool(old_dr.get("model_confirmed"))
    rec["photo_count"] = len(photos)
    rec["photos"] = photos
    ap = appraise_two_axis(rec.get("category_slug"), draft["price_hint"],
                           rec.get("condition_guess"), rec,
                           photo_count=len(photos))
    if model_confirmed:
        comps, _statuses = cached_market_comps(
            conn, old_dr.get("brand", ""), old_dr.get("model", ""),
            rec.get("category_slug") or "")
        val = valuation_interval(comps, rec.get("condition_guess"),
                                 model_confirmed=True)
    else:
        val = valuation_interval([], rec.get("condition_guess"),
                                 model_confirmed=False)
    dr = build_draft(conn, draft["name"], draft["text"],
                     draft["condition_grade"], draft["price_hint"], rec)
    dr["photos"] = photos
    dr["photo_count"] = len(photos)
    dr["brand"] = rec.get("brand", "")
    dr["model"] = rec.get("model", "")
    dr["model_confirmed"] = model_confirmed
    dr["suggested_price"] = val.get("suggested_price")
    dr["price_source"] = val.get("kind")
    conn.execute("UPDATE oneclick_drafts SET recognition_json=?,draft_json=?,"
                 "appraisal_json=?,valuation_json=?,status='recognized',"
                 "updated_at=? WHERE id=?",
                 (json.dumps(rec, ensure_ascii=False),
                  json.dumps(dr, ensure_ascii=False),
                  json.dumps(ap, ensure_ascii=False),
                  json.dumps(val, ensure_ascii=False),
                  now_tokyo(), did))
    conn.execute("INSERT INTO audit_log(actor_id,action,target_type,target_id,"
                 "note,created_at) VALUES(?,?,?,?,?,?)",
                 (user_id, "oneclick_recognize_job", "oneclick_draft", did,
                  f"category={rec.get('category_slug')};photos={len(photos)}",
                  now_tokyo()))
    conn.commit()
    return {"draft_id": did, "category_slug": rec.get("category_slug"),
            "valuation_kind": val.get("kind"),
            "suggested_price": val.get("suggested_price")}


def _run_valuation(conn, user_id, payload):
    did = payload.get("draft_id")
    draft = conn.execute("SELECT * FROM oneclick_drafts WHERE id=?",
                         (did,)).fetchone()
    if not draft:
        return {"error": "draft not found"}
    if draft["user_id"] != user_id:
        return {"error": "not your draft"}
    photos, dr = _draft_photos(draft["draft_json"])
    brand = (dr.get("brand") or "").strip()
    model = (dr.get("model") or "").strip()
    condition = dr.get("condition_grade") or draft["condition_grade"] or "good"
    category = dr.get("category_slug") or ""
    if not dr.get("model_confirmed") or not model:
        val = valuation_interval([], condition, model_confirmed=False)
        conn.execute("UPDATE oneclick_drafts SET valuation_json=?,"
                     "updated_at=? WHERE id=?",
                     (json.dumps(val, ensure_ascii=False), now_tokyo(), did))
        conn.commit()
        return {"draft_id": did, "valuation_kind": "model_unconfirmed",
                "low": None, "high": None, "sample_count": 0}
    search = search_market_comps(brand, model, category, conn=conn)
    val = valuation_interval(search["comps"], condition, model_confirmed=True)
    val["market_comps"] = search["comps"]
    val["source_statuses"] = search["statuses"]
    val["from_cache"] = search["from_cache"]
    val["search_note"] = search["search_note"]
    dr["suggested_price"] = val.get("suggested_price")
    dr["price_source"] = val.get("kind")
    conn.execute("UPDATE oneclick_drafts SET draft_json=?,valuation_json=?,"
                 "updated_at=? WHERE id=?",
                 (json.dumps(dr, ensure_ascii=False),
                  json.dumps(val, ensure_ascii=False), now_tokyo(), did))
    conn.commit()
    return {"draft_id": did, "valuation_kind": val.get("kind"),
            "low": val.get("low"), "high": val.get("high"),
            "suggested_price": val.get("suggested_price"),
            "sample_count": val.get("sample_count"),
            "source_statuses": search["statuses"],
            "from_cache": search["from_cache"]}


def run_job(job_id):
    """后台线程入口:自开数据库连接,按状态机流转,异常 -> failed。"""
    conn = d.connect()
    try:
        job = get_job(conn, job_id)
        if not job:
            return
        _set_job(conn, job_id, "running", {})
        try:
            kind, payload = job["kind"], job["payload"]
            if kind == "oneclick_recognize":
                result = _run_recognize(conn, job["user_id"], payload)
            elif kind == "oneclick_valuation":
                result = _run_valuation(conn, job["user_id"], payload)
            elif kind == "market_search":
                result = search_market_comps(
                    payload.get("brand", ""), payload.get("model", ""),
                    payload.get("category_slug", ""), conn=conn)
            else:
                result = {"error": f"unknown kind: {kind}"}
            if isinstance(result, dict) and result.get("error"):
                _set_job(conn, job_id, "failed", result)
            else:
                _set_job(conn, job_id, "done", result)
        except Exception as exc:  # 后台异常不得丢任务,必须落 failed
            _set_job(conn, job_id, "failed", {"error": str(exc)})
    finally:
        conn.close()


def start_job(job_id):
    """派发后立即返回:执行在 daemon 线程后台完成。"""
    th = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    th.start()
    return th
