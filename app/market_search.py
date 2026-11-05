"""第 3 阶段:同型号市场比价搜索(公开市场,绝不走平台自身数据)。

口径(用户已定,见任务书):
- 按用户确认的精确型号(品牌 + 型号)并行查多源,每源独立超时,
  全局硬上限 60 秒:60 秒到时立即返回已获样本的尽力结果
  (注明"60 秒内获 N 个样本")或如实无结果;超时源标注"超时",
  不可达源标注"不可达",无结果源标注"无结果",绝不编造样本。
- 8~10 个样本提前结束: foreground 收集到 10 个样本即返回,
  未跑完的源标注"后台继续",由 daemon 线程继续跑并写缓存。
- 每源只取前 N 个样本(默认 5 个);轻量摘要优先:只抓搜索页,
  从页面文本里提取价格片段,不深爬详情页。
- 同型号 24 小时缓存:comp_cache 表,model_key 为归一化后的
  品牌 + 型号(见 normalize_model_key);缓存命中直接返回并注明
  来自缓存;后台续跑结果写入缓存供下次查询使用。
- 诚实说明:这些站点大多有反爬,纯 httpx 抓取经常被挡或返回
  无价格页面——这是预期内的"不可达/无结果",按标注返回即可。
- 测试注入:search_market_comps 支持 providers(按源注入样本函数)
  与 httpx transport(注入 MockTransport),测试一律不做真实联网。
  providers 注入的样本只原样返回,函数本身不生成任何价格。
"""
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

try:
    from zoneinfo import ZoneInfo
    TOKYO = ZoneInfo("Asia/Tokyo")
except Exception:  # pragma: no cover
    TOKYO = timezone(timedelta(hours=9))

import httpx

CACHE_TTL_SECONDS = 86400  # 24 小时
HARD_CAP_SECONDS = 60.0
EARLY_EXIT_COUNT = 10  # 8~10 个样本提前结束:取区间上限 10
PER_SOURCE_LIMIT = 5
DEFAULT_PER_SOURCE_TIMEOUT = 10.0

# 源定义:slug -> (中文名, 搜索页 URL 模板, {q} 为 url 编码后的查询词)。
# URL 只是搜索页入口;站点结构变化或反爬时按"不可达/无结果"标注,
# 绝不因此编造样本。
SOURCES = {
    "mercari": ("Mercari", "https://jp.mercari.com/search?keyword={q}"),
    "yahoo": ("Yahoo 拍卖", "https://auctions.yahoo.co.jp/search/search?p={q}"),
    "rakuma": ("Rakuma", "https://fril.jp/search/{q}"),
    "paypay": ("PayPay 跳蚤市场",
               "https://paypayfleamarket.yahoo.co.jp/search/{q}"),
    "ebay": ("eBay", "https://www.ebay.com/sch/i.html?_nkw={q}"),
    "amazon_used": ("Amazon 二手", "https://www.amazon.co.jp/s?k={q}"),
    "bookoff": ("BOOKOFF", "https://shopping.bookoff.co.jp/search/stock?query={q}"),
    "chrono24": ("Chrono24",
                 "https://www.chrono24.jp/search/index.htm?query={q}"),
}

GENERIC_SOURCES = ("mercari", "yahoo", "rakuma", "paypay", "ebay")
BOOK_SOURCES = ("amazon_used", "bookoff")
WATCH_SOURCES = ("chrono24",) + GENERIC_SOURCES

USER_AGENT = ("Mozilla/5.0 (compatible; YunoLifeMarketSearch/1.0; "
              "snippet-only)")

_PRICE_RE = re.compile(r"¥\s*([\d,]{3,})|([\d,]{3,})\s*円")


def normalize_model_key(brand, model):
    """缓存键:品牌 + 型号归一化——小写、只保留字母数字。

    例:品牌 "Grand Seiko" + 型号 "SBGX-263" -> "grandseikosbgx263"。
    同一型号的不同写法(空格/连字符/大小写)命中同一缓存键。
    """
    blob = f"{brand or ''}{model or ''}".lower()
    return "".join(ch for ch in blob if ch.isalnum())


def sources_for_category(category_slug):
    """按品类选源:图书类走 Amazon 二手/BOOKOFF;手表类 Chrono24 优先
    (排首位)再查通用源;其余品类查全部通用源。"""
    if category_slug == "book":
        return list(BOOK_SOURCES)
    if category_slug == "watch":
        return list(WATCH_SOURCES)
    return list(GENERIC_SOURCES)


def _now_iso():
    return datetime.now(TOKYO).isoformat(timespec="seconds")


def _parse_time(value):
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TOKYO)
    return dt


def read_cache(conn, model_key):
    """返回 {source_slug: comps}，仅含 24 小时内新鲜的缓存条目。"""
    if conn is None or not model_key:
        return {}
    try:
        rows = conn.execute(
            "SELECT source, comps_json, fetched_at FROM comp_cache "
            "WHERE model_key=?", (model_key,)).fetchall()
    except Exception:
        return {}
    now = datetime.now(TOKYO)
    out = {}
    for r in rows:
        fetched = _parse_time(r["fetched_at"] or "")
        if fetched is None or (now - fetched).total_seconds() > CACHE_TTL_SECONDS:
            continue
        try:
            import json as _json
            comps = _json.loads(r["comps_json"] or "[]")
        except ValueError:
            continue
        if isinstance(comps, list):
            out[r["source"]] = [c for c in comps
                                if isinstance(c, dict) and c.get("price")]
    return out


def write_cache(conn, model_key, source, comps):
    """用调用方连接写缓存(调用方负责 commit)。"""
    import json as _json
    conn.execute("DELETE FROM comp_cache WHERE model_key=? AND source=?",
                 (model_key, source))
    conn.execute("INSERT INTO comp_cache(model_key,source,comps_json,fetched_at)"
                 " VALUES(?,?,?,?)",
                 (model_key, source, _json.dumps(comps, ensure_ascii=False),
                  _now_iso()))
    conn.commit()


def _write_cache_fresh(model_key, source, comps):
    """后台线程写缓存:自开连接(绝不跨线程共用调用方连接)。失败静默,
    因为缓存只是加速手段,写失败不影响前台已返回的结果。"""
    try:
        from . import db as _d
        c = _d.connect()
        try:
            write_cache(c, model_key, source, comps)
        finally:
            c.close()
    except Exception:
        pass


def _clean_comps(raw, source_name, limit):
    """只做清洗与截断:价格须为正整数,去重保序,每源只取前 limit 个。
    绝不生成、补全或改写价格;日期/链接缺失即缺失,不编造。"""
    out, seen = [], set()
    for item in raw or []:
        if isinstance(item, dict):
            price = item.get("price")
        else:
            price = item
        try:
            price = int(price)
        except (TypeError, ValueError):
            continue
        if price <= 0 or price in seen:
            continue
        seen.add(price)
        comp = {"price": price, "source": source_name}
        if isinstance(item, dict):
            if item.get("date"):
                comp["date"] = str(item["date"])
            if item.get("url"):
                comp["url"] = str(item["url"])
        out.append(comp)
        if len(out) >= limit:
            break
    return out


def _extract_prices_from_html(text, source_name, limit):
    """从搜索页文本提取价格片段(轻量摘要,不深爬详情页)。"""
    prices = []
    for m in _PRICE_RE.finditer(text or ""):
        raw = m.group(1) or m.group(2)
        try:
            price = int(raw.replace(",", ""))
        except ValueError:
            continue
        if 100 <= price <= 100_000_000:
            prices.append(price)
    return _clean_comps([{"price": p} for p in prices], source_name, limit)


def _fetch_via_httpx(slug, query, per_source_timeout, transport, limit=PER_SOURCE_LIMIT):
    name, tmpl = SOURCES[slug]
    url = tmpl.format(q=quote(query))
    try:
        with httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT},
                          follow_redirects=True,
                          timeout=per_source_timeout) as client:
            resp = client.get(url)
    except httpx.TimeoutException:
        raise TimeoutError(f"{slug} timeout")
    except httpx.HTTPError as exc:
        raise ConnectionError(f"{slug} unreachable: {exc}")
    if resp.status_code != 200:
        raise ConnectionError(f"{slug} http {resp.status_code}")
    return _extract_prices_from_html(resp.text, name, limit)


def _fetch_via_provider(slug, query, provider, limit=PER_SOURCE_LIMIT):
    name, _tmpl = SOURCES[slug]
    raw = provider(query)
    return _clean_comps(raw, name, limit)


def cached_market_comps(conn, brand, model, category_slug=""):
    """仅读缓存(不联网):返回 (comps, statuses)。

    comps 按源顺序合并、上限 10 个;statuses 中缓存命中的源标注
    "来自缓存"。无缓存时返回 ([], {})，调用方据此走诚实无报价分支。
    """
    key = normalize_model_key(brand, model)
    if not key:
        return [], {}
    cached = read_cache(conn, key)
    slugs = sources_for_category(category_slug)
    comps, statuses = [], {}
    for slug in slugs:
        if slug in cached and cached[slug]:
            statuses[slug] = "来自缓存"
            comps.extend(cached[slug])
    return comps[:EARLY_EXIT_COUNT], statuses


def search_market_comps(brand, model, category_slug="", conn=None,
                        transport=None, providers=None, source_slugs=None,
                        timeout_total=HARD_CAP_SECONDS,
                        per_source_timeout=DEFAULT_PER_SOURCE_TIMEOUT,
                        early_exit=EARLY_EXIT_COUNT,
                        per_source_limit=PER_SOURCE_LIMIT):
    """并行查多源,硬上限内返回尽力结果。

    参数:
      brand/model: 用户确认的精确型号(未确认时调用方不应调用本函数)。
      conn: 可选,用于读写 comp_cache(缓存命中直接返回)。
      transport: 可选,httpx transport(测试注入 MockTransport)。
      providers: 可选,{slug: callable(query)->样本列表},测试注入;
        注入源的样本只原样返回,函数不生成价格。provider 抛
        TimeoutError 计"超时",其他异常计"不可达",空列表计"无结果"。
      source_slugs: 可选,覆盖按品类选源的结果(测试用)。
      timeout_total: 全局硬上限秒数,默认 60.0(截止线,不是平均值)。
      per_source_timeout: 每源独立超时秒数,默认 10.0。
      early_exit: 收集到该样本数即提前结束,默认 10。
      per_source_limit: 每源最多样本数,默认 5。
    返回 dict:
      {brand, model, model_key, category_slug, comps, sample_count,
       statuses: {slug: "ok"|"无结果"|"不可达"|"超时"|"后台继续"|"来自缓存"},
       from_cache, timed_out, search_note}
    comps 每项 {price, source, date?(缺失不编), url?(有则给)}。
    """
    return _search_impl(brand, model, category_slug, conn, transport,
                        providers, source_slugs, timeout_total,
                        per_source_timeout, early_exit, per_source_limit)


def _search_impl(brand, model, category_slug, conn, transport, providers,
                 source_slugs, timeout_total, per_source_timeout, early_exit,
                 per_source_limit):
    key = normalize_model_key(brand, model)
    slugs = list(source_slugs) if source_slugs else sources_for_category(category_slug)
    query = f"{brand or ''} {model or ''}".strip()
    cached = read_cache(conn, key) if conn is not None else {}
    # 全源缓存命中:直接返回,不联网。
    if slugs and all(slug in cached and cached[slug] for slug in slugs):
        comps = []
        for slug in slugs:
            comps.extend(cached[slug])
        comps = comps[:early_exit]
        return {
            "brand": brand, "model": model, "model_key": key,
            "category_slug": category_slug, "comps": comps,
            "sample_count": len(comps),
            "statuses": {slug: "来自缓存" for slug in slugs},
            "from_cache": True, "timed_out": False,
            "search_note": "来自 24 小时缓存,未重新联网搜索。",
        }

    results = {}   # slug -> (comps_or_None, status)
    lock = threading.Lock()
    deadline = time.monotonic() + timeout_total

    def _run(slug):
        started = time.monotonic()
        try:
            if providers is not None and slug in providers:
                comps = _fetch_via_provider(slug, query, providers[slug], per_source_limit)
            else:
                comps = _fetch_via_httpx(slug, query, per_source_timeout,
                                         transport, per_source_limit)
        except TimeoutError:
            with lock:
                results[slug] = (None, "超时")
            return
        except Exception:
            with lock:
                results[slug] = (None, "不可达")
            return
        elapsed = time.monotonic() - started
        if elapsed > per_source_timeout:
            # 每源独立超时:即使最终跑完,超时的源也不计入前台结果,
            # 但结果仍写缓存供下次使用(后台续跑同理)。
            _write_cache_fresh(key, slug, comps)
            with lock:
                results[slug] = (None, "超时")
            return
        _write_cache_fresh(key, slug, comps)
        with lock:
            results[slug] = (comps, "ok" if comps else "无结果")

    threads = {}
    for slug in slugs:
        if slug in cached and cached[slug]:
            # 部分缓存命中:该源不重查,直接采用缓存样本。
            with lock:
                results[slug] = (list(cached[slug]), "来自缓存")
            continue
        th = threading.Thread(target=_run, args=(slug,), daemon=True)
        th.start()
        threads[slug] = th

    timed_out = False
    early_exited = False
    while True:
        with lock:
            done = len(results) == len(slugs)
            total = sum(len(v[0]) for v in results.values() if v[0])
        if done:
            break
        if total >= early_exit:
            early_exited = True
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.05)

    with lock:
        snapshot = dict(results)
    statuses, comps = {}, []
    for slug in slugs:
        if slug in snapshot:
            cs, st = snapshot[slug]
            statuses[slug] = st
            if cs:
                comps.extend(cs)
        elif timed_out:
            statuses[slug] = "超时"
        elif early_exited:
            statuses[slug] = "后台继续"
        else:
            statuses[slug] = "超时"
    comps = comps[:early_exit]
    # 前台已收集的源立即写缓存(调用方连接);后台线程结束时自写缓存。
    if conn is not None:
        for slug in slugs:
            if slug in snapshot and snapshot[slug][0]:
                try:
                    write_cache(conn, key, slug, snapshot[slug][0])
                except Exception:
                    pass
    if timed_out:
        note = f"60 秒内获 {len(comps)} 个样本(部分源超时,已标注)。"
    elif early_exited:
        note = (f"60 秒内获 {len(comps)} 个样本,已提前结束;"
                f"未跑完的源在后台继续并写入缓存。")
    elif comps:
        note = f"60 秒内获 {len(comps)} 个样本。"
    else:
        note = "60 秒内未获同型号市场样本,各源状态已如实标注。"
    return {
        "brand": brand, "model": model, "model_key": key,
        "category_slug": category_slug, "comps": comps,
        "sample_count": len(comps), "statuses": statuses,
        "from_cache": False, "timed_out": timed_out,
        "search_note": note,
    }
