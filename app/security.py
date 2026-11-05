"""安全基础:全部标准库,零外部依赖、零 API 成本。
- 密码:PBKDF2-HMAC-SHA256,200k 次迭代,随机盐。
- 会话:随机 token,存 SQLite,30 天过期,Cookie 传递。
- 敏感字段:密码只存哈希;邮箱/电话不对外展示给无关用户。
"""
import hashlib
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
    TOKYO = ZoneInfo("Asia/Tokyo")
except Exception:  # pragma: no cover
    TOKYO = timezone(timedelta(hours=9))


def now_tokyo():
    return datetime.now(TOKYO).isoformat(timespec="seconds")


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return salt, h


def verify_password(password, salt, pw_hash):
    _, h = hash_password(password, salt)
    return secrets.compare_digest(h, pw_hash)


def new_session_token():
    return secrets.token_hex(32)


def session_expiry():
    return (datetime.now(TOKYO) + timedelta(days=30)).isoformat(timespec="seconds")


# 角色与权限(服务端强制校验,前端隐藏不算权限)
ROLES = ("user", "collector", "operator", "appraiser", "courier", "admin")
ADMIN_ROLES = ("admin",)
OPERATOR_ROLES = ("admin", "operator")
APPRAISER_ROLES = ("admin", "operator", "appraiser")


def can_admin(user):
    return user is not None and user["role"] in ADMIN_ROLES


def can_operate(user):
    return user is not None and user["role"] in OPERATOR_ROLES


def can_appraise(user):
    return user is not None and user["role"] in APPRAISER_ROLES


# ---------------- 商业级优化:审计 / 限流 / Origin 纵深防御 ----------------
# 全部标准库,无新增依赖。限流为内存表,按 IP + 账号键,阈值宽松,
# 只拦高频刷接口;正常操作(单次/少量重复)不受影响。

def audit_log(conn, actor_id, action, target_type, target_id, note=""):
    """写 audit_log。note 只写业务标识与状态,绝不写口令/token/密钥。"""
    conn.execute(
        "INSERT INTO audit_log(actor_id,action,target_type,target_id,note,"
        "created_at) VALUES(?,?,?,?,?,?)",
        (actor_id, action, target_type, target_id, note or "", now_tokyo()))


_RATE = {}
_RATE_LOCK = threading.Lock()
LOGIN_LIMIT, LOGIN_WINDOW = 10, 600
REGISTER_LIMIT, REGISTER_WINDOW = 10, 600
ROLE_LIMIT, ROLE_WINDOW = 20, 600


def reset_rate_limits():
    with _RATE_LOCK:
        _RATE.clear()


def check_rate_limit(key, limit, window_seconds):
    """返回 True 表示放行并记一次;False 表示已超限。"""
    now = time.monotonic()
    with _RATE_LOCK:
        stamps = [t for t in _RATE.get(key, []) if now - t < window_seconds]
        if len(stamps) >= limit:
            _RATE[key] = stamps
            return False
        stamps.append(now)
        _RATE[key] = stamps
        return True


def origin_allowed(request):
    """Origin 纵深防御:无 Origin 头放行(非浏览器调用/旧测试不受影响);
    有 Origin 头时其 host 必须与本站 Host 一致,否则拒绝。"""
    origin = request.headers.get("origin")
    if not origin:
        return True
    try:
        ohost = urlparse(origin).hostname
    except Exception:
        return False
    if not ohost:
        return False
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return ohost.lower() == host


def client_ip(request):
    try:
        return request.client.host if request.client else "unknown"
    except Exception:
        return "unknown"


def valid_email(email):
    return bool(email) and len(email) <= 254 and "@" in email \
        and "." in email.split("@", 1)[1] and " " not in email


def text_ok(value, max_len, required=False):
    if value is None:
        return not required
    if required and not str(value).strip():
        return False
    return len(str(value)) <= max_len
