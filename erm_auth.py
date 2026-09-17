# -*- coding: utf-8 -*-
"""E1 身份：本地会话 + 可选 EnterpriseRiskAI JWT；角色 RBAC。
生产默认开启。匿名可看演示报告；录入与写接口必须登录。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import List, Optional

from flask import jsonify, redirect, request, session
from werkzeug.security import check_password_hash

def _is_production() -> bool:
    return os.environ.get("ERM_ENV", "").lower() in ("production", "prod")

ROLES = ("director", "assessor", "approver", "admin")
ROLE_LABEL = {
    "director": "只读董事",
    "assessor": "评估人",
    "approver": "审批人",
    "admin": "管理员",
}

# 评估人及以上可写评估；管理员可改集成配置
WRITE_ROLES = frozenset({"assessor", "approver", "admin"})
ADMIN_ROLES = frozenset({"admin"})
APPROVE_ROLES = frozenset({"approver", "admin"})
ENTRY_ROLES = WRITE_ROLES  # 数据录入页

SENSITIVE_RULES = (
    ("PUT", "/api/integrations/oauth/providers"),
    ("POST", "/api/integrations/oauth/sync"),
    ("PUT", "/api/integrations/schedule"),
    ("POST", "/api/integrations/schedule/jobs"),
    ("DELETE", "/api/integrations/schedule/jobs"),
    ("POST", "/api/integrations/schedule/run"),
    ("PUT", "/api/notifications/config"),
    ("PUT", "/api/notifications/mobile-config"),
)

PUBLIC_GET_EXACT = frozenset({
    "/", "/report", "/login",
    "/ping", "/health", "/api/health",
    "/api/engines", "/api/auth/me", "/api/validate/uscc",
    "/api/notifications",
    "/api/integrations/oauth/callback",
    "/api/template/download",
    "/api/workflow",
    "/api/knowledge/citations",
})
PUBLIC_GET_PREFIXES = (
    "/static/",
    "/api/history",
    "/api/external-risk",
)
PUBLIC_POST_PREFIXES = ("/api/auth/login", "/api/auth/logout", "/api/auth/session")
ADMIN_PREFIXES = (
    "/api/integrations/oauth",
    "/api/integrations/schedule",
    "/api/notifications/config",
    "/api/notifications/mobile-config",
)
ENTRY_PATHS = frozenset({"/data-entry"})
LOGIN_PAGES = frozenset({"/data-entry", "/solution"})

USERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "users.json",
)


@dataclass
class ErmUser:
    username: str
    role: str = "director"
    source: str = "session"

    @property
    def label(self) -> str:
        return ROLE_LABEL.get(self.role, self.role)

    def can_write(self) -> bool:
        return self.role in WRITE_ROLES

    def can_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    def can_enter(self) -> bool:
        return self.role in ENTRY_ROLES

    def can_approve(self) -> bool:
        return self.role in APPROVE_ROLES

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "role": self.role,
            "role_label": self.label,
            "can_write": self.can_write(),
            "can_admin": self.can_admin(),
            "can_enter": self.can_enter(),
            "can_approve": self.can_approve(),
        }


def app_path(path: str = "/") -> str:
    root = (request.script_root or "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{root}{path}"


def default_admin_username() -> str:
    return (os.environ.get("ERM_ADMIN_USER") or "红旗").strip() or "红旗"


def admin_token() -> str:
    return (os.environ.get("ERM_ADMIN_TOKEN") or "").strip()


def auth_enabled() -> bool:
    mode = (os.environ.get("ERM_AUTH_MODE") or "").strip().lower()
    if mode in ("off", "disable", "disabled", "0"):
        return False
    if mode in ("on", "local", "jwt", "required", "1"):
        return True
    if _is_production():
        return True
    return bool(
        admin_token()
        or (os.environ.get("ERM_ADMIN_PASSWORD") or "").strip()
        or os.path.isfile(USERS_FILE)
        or (os.environ.get("ERM_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or "").strip()
    )


def jwt_secret() -> str:
    return (
        (os.environ.get("ERM_JWT_SECRET") or "").strip()
        or (os.environ.get("JWT_SECRET_KEY") or "").strip()
    )


def _query_token_allowed() -> bool:
    return (os.environ.get("ERM_ALLOW_QUERY_TOKEN") or "").strip().lower() in ("1", "true", "yes")


def _provided_token() -> str:
    hdr = (request.headers.get("X-ERM-Token") or "").strip()
    if hdr:
        return hdr
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if _query_token_allowed():
        q = (request.args.get("token") or "").strip()
        if q:
            return q
    if request.is_json:
        body = request.get_json(silent=True) or {}
        t = str(body.get("admin_token") or "").strip()
        if t:
            return t
    return str(session.get("erm_admin_token") or "").strip()


def is_sensitive(method: str, path: str) -> bool:
    method = (method or "").upper()
    path = path or ""
    for m, prefix in SENSITIVE_RULES:
        if method == m and path.startswith(prefix):
            return True
    return False


def check_admin() -> Optional[tuple]:
    """旧口令门：仅保护 OAuth/SMTP/FCM/调度。新 RBAC 在 enforce_request 中处理。"""
    token = admin_token()
    if not token:
        user = current_user()
        if user and user.can_admin():
            return None
        if not auth_enabled():
            return None
        if user and user.can_admin():
            return None
        return jsonify({
            "error": "需要管理员登录",
            "code": "ERR-ERM-AUTH",
        }), 401
    user = current_user()
    if user and user.can_admin():
        return None
    got = _provided_token()
    if got and hmac.compare_digest(got, token):
        return None
    return jsonify({
        "error": "需要管理员权限",
        "code": "ERR-ERM-AUTH",
        "hint": "请使用管理员账号登录；密钥已改为环境变量，页面不再填写 SMTP/OAuth 口令。",
    }), 401


def _load_file_users() -> List[dict]:
    if not os.path.isfile(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("users") if isinstance(data, dict) else data
        return [u for u in (rows or []) if isinstance(u, dict) and u.get("username")]
    except (OSError, json.JSONDecodeError):
        return []


def _env_users() -> List[dict]:
    raw = (os.environ.get("ERM_USERS") or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = data.get("users") if isinstance(data, dict) else data
    return [u for u in (rows or []) if isinstance(u, dict)]


def list_login_users() -> List[dict]:
    users = _env_users() + _load_file_users()
    admin_user = default_admin_username()
    admin_pwd = (os.environ.get("ERM_ADMIN_PASSWORD") or "").strip() or admin_token()
    if admin_pwd and not any(str(u.get("username")) == admin_user for u in users):
        users.append({"username": admin_user, "password": admin_pwd, "role": "admin"})
    director_user = (os.environ.get("ERM_DIRECTOR_USER") or "").strip()
    director_pwd = (os.environ.get("ERM_DIRECTOR_PASSWORD") or "").strip()
    if director_user and director_pwd and not any(str(u.get("username")) == director_user for u in users):
        users.append({"username": director_user, "password": director_pwd, "role": "director"})
    return users


def _password_ok(user: dict, password: str) -> bool:
    hashed = str(user.get("password_hash") or "").strip()
    if hashed:
        try:
            return check_password_hash(hashed, password)
        except (ValueError, TypeError):
            return False
    plain = str(user.get("password") or "")
    if not plain or not password:
        return False
    return hmac.compare_digest(plain, password)


def authenticate(username: str, password: str) -> Optional[ErmUser]:
    name = (username or "").strip()
    pwd = password or ""
    if not name or not pwd:
        return None
    for row in list_login_users():
        if str(row.get("username") or "").strip() != name:
            continue
        if not _password_ok(row, pwd):
            continue
        role = str(row.get("role") or "director").strip().lower()
        if role not in ROLES:
            role = "director"
        return ErmUser(username=name, role=role, source="password")
    return None


def _b64url_decode(part: str) -> bytes:
    pad = "=" * (-len(part) % 4)
    return base64.urlsafe_b64decode(part + pad)


def decode_hs256_jwt(token: str, secret: str) -> Optional[dict]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing, hashlib.sha256).digest()
        given = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, given):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


def user_from_jwt(token: str) -> Optional[ErmUser]:
    secret = jwt_secret()
    if not secret or not token:
        return None
    payload = decode_hs256_jwt(token, secret)
    if not payload:
        return None
    if payload.get("type") not in (None, "access"):
        return None
    name = str(payload.get("email") or payload.get("preferred_username") or payload.get("sub") or "").strip()
    if not name:
        return None
    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    roles_l = {str(r).lower() for r in roles}
    if payload.get("is_superuser") or "admin" in roles_l or "superuser" in roles_l:
        role = "admin"
    elif "approver" in roles_l or "审批" in roles_l:
        role = "approver"
    elif "assessor" in roles_l or "评估" in roles_l or "analyst" in roles_l:
        role = "assessor"
    else:
        role = "director"
    return ErmUser(username=name[:80], role=role, source="jwt")


def current_user() -> Optional[ErmUser]:
    data = session.get("erm_user")
    if isinstance(data, dict) and data.get("username"):
        role = str(data.get("role") or "director")
        if role not in ROLES:
            role = "director"
        return ErmUser(username=str(data["username"]), role=role, source="session")
    bearer = (request.headers.get("Authorization") or "").strip()
    if bearer.lower().startswith("bearer "):
        return user_from_jwt(bearer[7:].strip())
    tok = _provided_token()
    expected = admin_token()
    if expected and tok and hmac.compare_digest(tok, expected):
        return ErmUser(username=default_admin_username(), role="admin", source="token")
    return None


def login_user(user: ErmUser) -> None:
    session["erm_user"] = {"username": user.username, "role": user.role}
    session.permanent = True


def logout_user() -> None:
    session.pop("erm_user", None)
    session.pop("erm_admin_token", None)


def is_demo_record(rec: dict) -> bool:
    name = str((rec or {}).get("company_name") or "")
    note = str((rec or {}).get("note") or "")
    rid = str((rec or {}).get("id") or "")
    return name.startswith("DEMO-") or note.startswith("演示") or rid.startswith("demo-")


def filter_history(records: List[dict], user: Optional[ErmUser]) -> List[dict]:
    if user:
        return list(records)
    return [r for r in records if is_demo_record(r)]


def can_read_record(rec: dict, user: Optional[ErmUser]) -> bool:
    if user:
        return True
    return is_demo_record(rec)


def _is_public(method: str, path: str) -> bool:
    if path.startswith("/api/auth/"):
        return True
    if method in ("GET", "HEAD"):
        if path in PUBLIC_GET_EXACT:
            return True
        if path.startswith("/static/"):
            return True
        for prefix in PUBLIC_GET_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return True
    if method == "POST":
        for prefix in PUBLIC_POST_PREFIXES:
            if path.startswith(prefix):
                return True
    return False


def enforce_request():
    """before_request：返回 Flask 响应或 None。"""
    if request.method == "OPTIONS":
        return None
    path = request.path or "/"
    if path.startswith("/static/"):
        return None
    if not auth_enabled():
        if is_sensitive(request.method, path):
            blocked = check_admin()
            if blocked:
                return blocked[0], blocked[1]
        return None

    user = current_user()
    method = request.method.upper()

    if _is_public(method, path):
        if method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api/history"):
            pass  # POST/DELETE history 不是 public
        elif method == "GET" or path.startswith("/api/auth/") or path in ("/", "/report", "/login"):
            return None

    # 写 history / 评估等
    if path in ENTRY_PATHS:
        if not user:
            return _deny(user, "需要评估人登录才能录入", html_redirect=True)
        if not user.can_enter():
            return redirect(app_path("/report"))
        return None

    if path in LOGIN_PAGES and path not in ENTRY_PATHS:
        if not user:
            return _deny(user, "请先登录", html_redirect=True)
        return None

    for prefix in ADMIN_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            if not user or not user.can_admin():
                blocked = check_admin()
                if blocked:
                    return blocked[0], blocked[1]
                if not user or not user.can_admin():
                    return _deny(user, "需要管理员权限", html_redirect=False)
            return None

    if is_sensitive(method, path):
        if not user or not user.can_admin():
            blocked = check_admin()
            if blocked:
                return blocked[0], blocked[1]
        return None

    if method in ("POST", "PUT", "PATCH", "DELETE"):
        if not user:
            return _deny(user, "未登录", html_redirect=False)
        if not user.can_write():
            return _deny(user, "当前角色为只读，不能提交评估或修改数据", html_redirect=False)
        return None

    # 其余 GET（模板、解决方案页已处理）
    if not user and path.startswith("/api/"):
        # 非公开 API GET
        if not _is_public("GET", path):
            return _deny(user, "未登录", html_redirect=False)
    return None


def _deny(user: Optional[ErmUser], message: str, html_redirect: bool):
    if html_redirect and not (request.path or "").startswith("/api/"):
        nxt = request.path or "/data-entry"
        from urllib.parse import quote
        return redirect(f"{app_path('/login')}?next={quote(nxt)}")
    status = 401 if not user else 403
    return jsonify({
        "error": message,
        "code": "ERR-ERM-AUTH",
        "login": "/login",
    }), status
