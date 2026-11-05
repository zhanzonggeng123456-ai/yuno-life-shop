"""安全基础:全部标准库,零外部依赖、零 API 成本。
- 密码:PBKDF2-HMAC-SHA256,200k 次迭代,随机盐。
- 会话:随机 token,存 SQLite,30 天过期,Cookie 传递。
- 敏感字段:密码只存哈希;邮箱/电话不对外展示给无关用户。
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

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
