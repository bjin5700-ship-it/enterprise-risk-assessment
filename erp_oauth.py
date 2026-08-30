# -*- coding: utf-8 -*-
"""OAuth2 ERP 直连 — 用友/金蝶/通用 OAuth2 财务数据拉取"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib import error, parse, request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data")
OAUTH_PROVIDERS_FILE = os.path.join(DATA_DIR, "oauth_providers.json")
OAUTH_TOKENS_FILE = os.path.join(DATA_DIR, "oauth_tokens.json")
OAUTH_STATE_FILE = os.path.join(DATA_DIR, "oauth_states.json")

# 预设模板（用户填入 client_id/secret 即可）
PROVIDER_PRESETS = {
    "generic": {
        "name": "通用 OAuth2 ERP",
        "authorize_url": "https://your-erp.com/oauth/authorize",
        "token_url": "https://your-erp.com/oauth/token",
        "scope": "read financial",
        "api_data_url": "https://your-erp.com/api/v1/financial/kpi",
    },
    "yonyou": {
        "name": "用友 YonBIP",
        "authorize_url": "https://open.yonyoucloud.com/oauth/authorize",
        "token_url": "https://open.yonyoucloud.com/oauth/token",
        "scope": "financial_read",
        "api_data_url": "https://open.yonyoucloud.com/api/financial/metrics",
    },
    "kingdee": {
        "name": "金蝶云星空",
        "authorize_url": "https://api.kingdee.com/oauth2/authorize",
        "token_url": "https://api.kingdee.com/oauth2/token",
        "scope": "read",
        "api_data_url": "https://api.kingdee.com/v1/financial/indicators",
    },
}


def _default_providers_doc() -> dict:
    providers = []
    for pid, preset in PROVIDER_PRESETS.items():
        providers.append({
            "id": pid,
            "name": preset["name"],
            "enabled": pid == "generic",
            "client_id": "",
            "client_secret": "",
            "authorize_url": preset["authorize_url"],
            "token_url": preset["token_url"],
            "scope": preset["scope"],
            "api_data_url": preset["api_data_url"],
            "redirect_uri": "",
        })
    return {"providers": providers}


def load_oauth_providers(path: str = None) -> dict:
    path = path or OAUTH_PROVIDERS_FILE
    if not os.path.exists(path):
        doc = _default_providers_doc()
        save_oauth_providers(doc, path)
        return doc
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("providers"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    doc = _default_providers_doc()
    save_oauth_providers(doc, path)
    return doc


def save_oauth_providers(doc: dict, path: str = None) -> None:
    path = path or OAUTH_PROVIDERS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def get_provider(provider_id: str) -> Optional[dict]:
    for p in load_oauth_providers().get("providers", []):
        if p.get("id") == provider_id:
            return apply_oauth_env(p)
    return None


def apply_oauth_env(provider: dict) -> dict:
    out = dict(provider)
    pid = str(out.get("id") or "generic").upper().replace("-", "_")
    sec = (os.environ.get(f"ERM_OAUTH_{pid}_SECRET") or os.environ.get("ERM_OAUTH_CLIENT_SECRET") or "").strip()
    if sec:
        out["client_secret"] = sec
    cid = (os.environ.get(f"ERM_OAUTH_{pid}_CLIENT_ID") or "").strip()
    if cid:
        out["client_id"] = cid
    url = (os.environ.get(f"ERM_OAUTH_{pid}_API_URL") or "").strip()
    if url:
        out["api_data_url"] = url
    return out


def update_provider(provider_id: str, updates: dict) -> dict:
    doc = load_oauth_providers()
    for i, p in enumerate(doc.get("providers", [])):
        if p.get("id") == provider_id:
            safe = {k: v for k, v in updates.items() if k not in ("id", "client_secret")}
            doc["providers"][i].update(safe)
            save_oauth_providers(doc)
            return doc["providers"][i]
    raise ValueError(f"未知 provider: {provider_id}")


def load_oauth_tokens(path: str = None) -> dict:
    path = path or OAUTH_TOKENS_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_oauth_tokens(tokens: dict, path: str = None) -> None:
    path = path or OAUTH_TOKENS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def _load_states() -> dict:
    if not os.path.exists(OAUTH_STATE_FILE):
        return {}
    try:
        with open(OAUTH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_states(states: dict) -> None:
    os.makedirs(os.path.dirname(OAUTH_STATE_FILE), exist_ok=True)
    with open(OAUTH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)


def build_authorization_url(provider_id: str, redirect_uri: str, company_name: str = "") -> dict:
    provider = get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        raise ValueError("OAuth 提供商未启用或不存在")
    if not provider.get("client_id"):
        raise ValueError("请先配置 client_id")

    state = secrets.token_urlsafe(16)
    states = _load_states()
    states[state] = {
        "provider_id": provider_id,
        "company_name": company_name,
        "redirect_uri": redirect_uri,
        "created_at": datetime.now().isoformat(),
    }
    _save_states(states)

    params = {
        "response_type": "code",
        "client_id": provider["client_id"],
        "redirect_uri": redirect_uri,
        "scope": provider.get("scope", "read"),
        "state": state,
    }
    url = provider["authorize_url"] + "?" + parse.urlencode(params)
    return {"authorization_url": url, "state": state, "provider_id": provider_id}


def handle_oauth_callback(code: str, state: str) -> dict:
    states = _load_states()
    ctx = states.pop(state, None)
    _save_states(states)
    if not ctx:
        raise ValueError("无效或已过期的 OAuth state")

    provider = get_provider(ctx["provider_id"])
    if not provider:
        raise ValueError("OAuth 提供商不存在")

    redirect_uri = ctx.get("redirect_uri") or provider.get("redirect_uri", "")
    token_data = _exchange_code(provider, code, redirect_uri)
    expires_in = int(token_data.get("expires_in") or 3600)
    record = {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
        "company_name": ctx.get("company_name", ""),
        "connected_at": datetime.now().isoformat(),
        "provider_name": provider.get("name"),
    }
    tokens = load_oauth_tokens()
    tokens[ctx["provider_id"]] = record
    save_oauth_tokens(tokens)
    return {"ok": True, "provider_id": ctx["provider_id"], "company_name": record["company_name"]}


def _exchange_code(provider: dict, code: str, redirect_uri: str) -> dict:
    body = parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": provider.get("client_id", ""),
        "client_secret": provider.get("client_secret", ""),
    }).encode("utf-8")
    req = request.Request(
        provider["token_url"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _refresh_access_token(provider_id: str) -> Optional[str]:
    provider = get_provider(provider_id)
    tokens = load_oauth_tokens()
    rec = tokens.get(provider_id) or {}
    refresh = rec.get("refresh_token")
    if not provider or not refresh:
        return rec.get("access_token")

    body = parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": provider.get("client_id", ""),
        "client_secret": provider.get("client_secret", ""),
    }).encode("utf-8")
    try:
        req = request.Request(
            provider["token_url"],
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rec["access_token"] = data.get("access_token")
        if data.get("refresh_token"):
            rec["refresh_token"] = data["refresh_token"]
        rec["expires_at"] = (datetime.now() + timedelta(seconds=int(data.get("expires_in") or 3600))).isoformat()
        tokens[provider_id] = rec
        save_oauth_tokens(tokens)
        return rec["access_token"]
    except (error.URLError, OSError, json.JSONDecodeError):
        return rec.get("access_token")


def get_valid_access_token(provider_id: str) -> Optional[str]:
    tokens = load_oauth_tokens()
    rec = tokens.get(provider_id)
    if not rec:
        return None
    expires_at = rec.get("expires_at")
    if expires_at:
        try:
            if datetime.now() >= datetime.fromisoformat(expires_at) - timedelta(minutes=2):
                return _refresh_access_token(provider_id)
        except ValueError:
            pass
    return rec.get("access_token")


def fetch_oauth_erp_payload(provider_id: str) -> dict:
    """从 OAuth 保护的 ERP API 拉取财务 KPI JSON。"""
    from data_integration import apply_erp_payload, apply_financial_api_payload

    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"未知 provider: {provider_id}")
    token = get_valid_access_token(provider_id)
    if not token:
        raise ValueError(f"Provider {provider_id} 未授权，请先完成 OAuth 登录")

    api_url = (provider.get("api_data_url") or "").strip()
    if not api_url:
        raise ValueError("未配置 api_data_url")

    req = request.Request(
        api_url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    with request.urlopen(req, timeout=25) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    erp = apply_erp_payload(body if isinstance(body, dict) else {})
    fin = apply_financial_api_payload(body if isinstance(body, dict) else {})
    external = {**erp, **fin}
    if not external and isinstance(body, dict):
        external = body
    return {"type": "oauth_erp", "external": external, "raw": body, "provider_id": provider_id}


def oauth_connection_status() -> List[dict]:
    tokens = load_oauth_tokens()
    providers = load_oauth_providers().get("providers", [])
    out = []
    for p in providers:
        rec = tokens.get(p["id"], {})
        out.append({
            "provider_id": p["id"],
            "name": p.get("name"),
            "enabled": p.get("enabled"),
            "connected": bool(rec.get("access_token")),
            "company_name": rec.get("company_name", ""),
            "connected_at": rec.get("connected_at"),
            "expires_at": rec.get("expires_at"),
        })
    return out
