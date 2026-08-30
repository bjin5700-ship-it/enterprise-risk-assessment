# -*- coding: utf-8 -*-
"""移动端推送 — FCM、设备注册、Service Worker 触发"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from urllib import error, request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data")
MOBILE_DEVICES_FILE = os.path.join(DATA_DIR, "mobile_devices.json")
MOBILE_PUSH_CONFIG_FILE = os.path.join(DATA_DIR, "mobile_push_config.json")
MAX_DEVICES = 100


def _default_mobile_config() -> dict:
    return {
        "fcm_enabled": False,
        "fcm_server_key": "",
        "custom_push_url": "",
        "web_push_poll_seconds": 90,
    }


def load_mobile_push_config(path: str = None) -> dict:
    path = path or MOBILE_PUSH_CONFIG_FILE
    if not os.path.exists(path):
        cfg = _default_mobile_config()
        save_mobile_push_config(cfg, path)
        return _apply_fcm_env(cfg)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = _default_mobile_config()
        if isinstance(data, dict):
            merged.update(data)
        return _apply_fcm_env(merged)
    except (json.JSONDecodeError, OSError):
        return _apply_fcm_env(_default_mobile_config())


def _apply_fcm_env(cfg: dict) -> dict:
    out = dict(cfg)
    key = (os.environ.get("ERM_FCM_SERVER_KEY") or "").strip()
    if key:
        out["fcm_server_key"] = key
        out["fcm_configured"] = True
    else:
        out["fcm_configured"] = bool(out.get("fcm_server_key"))
    return out


def save_mobile_push_config(cfg: dict, path: str = None) -> None:
    path = path or MOBILE_PUSH_CONFIG_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_mobile_devices(path: str = None) -> List[dict]:
    path = path or MOBILE_DEVICES_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_mobile_devices(devices: List[dict], path: str = None) -> None:
    path = path or MOBILE_DEVICES_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(devices[:MAX_DEVICES], f, ensure_ascii=False, indent=2)


def register_device(
    token: str,
    platform: str = "web",
    device_name: str = "",
    company_filter: str = "",
) -> dict:
    token = (token or "").strip()
    if not token:
        raise ValueError("缺少 device token")
    devices = load_mobile_devices()
    now = datetime.now().isoformat()
    for d in devices:
        if d.get("token") == token:
            d.update({
                "platform": platform,
                "device_name": device_name or d.get("device_name"),
                "company_filter": company_filter or d.get("company_filter", ""),
                "last_seen_at": now,
                "active": True,
            })
            save_mobile_devices(devices)
            return d
    device = {
        "id": str(uuid.uuid4())[:8],
        "token": token,
        "platform": platform,
        "device_name": device_name or f"{platform} 设备",
        "company_filter": company_filter,
        "created_at": now,
        "last_seen_at": now,
        "active": True,
    }
    devices.insert(0, device)
    save_mobile_devices(devices)
    return device


def unregister_device(token: str = None, device_id: str = None) -> bool:
    devices = load_mobile_devices()
    before = len(devices)
    if token:
        devices = [d for d in devices if d.get("token") != token]
    elif device_id:
        devices = [d for d in devices if d.get("id") != device_id]
    else:
        return False
    save_mobile_devices(devices)
    return len(devices) < before


def list_devices(active_only: bool = True) -> dict:
    devices = load_mobile_devices()
    if active_only:
        devices = [d for d in devices if d.get("active", True)]
    return {"devices": devices, "total": len(devices)}


def _build_mobile_payload(company_name: str, title: str, body: str, data: dict = None) -> dict:
    return {
        "company_name": company_name,
        "title": title,
        "body": body,
        "data": data or {},
        "sent_at": datetime.now().isoformat(),
    }


def push_to_mobile_devices(
    company_name: str,
    title: str,
    body: str,
    data: dict = None,
) -> dict:
    """向已注册移动设备推送（FCM + 自定义 Push URL）。"""
    cfg = load_mobile_push_config()
    devices = [d for d in load_mobile_devices() if d.get("active", True)]
    sent = failed = 0
    errors: List[str] = []

    filtered = []
    for d in devices:
        cf = (d.get("company_filter") or "").strip()
        if cf and cf != company_name:
            continue
        filtered.append(d)

    if cfg.get("fcm_enabled") and cfg.get("fcm_server_key") and filtered:
        fcm_tokens = [d["token"] for d in filtered if d.get("platform") in ("android", "ios", "fcm", "mobile")]
        web_tokens = [d["token"] for d in filtered if d.get("platform") in ("android", "ios", "fcm", "mobile", "web")]
        tokens = fcm_tokens or web_tokens
        if tokens:
            ok, err = _send_fcm(cfg["fcm_server_key"], tokens, title, body, data)
            if ok:
                sent += len(tokens)
            else:
                failed += len(tokens)
                if err:
                    errors.append(err)

    if cfg.get("custom_push_url"):
        ok, err = _send_custom_push(cfg["custom_push_url"], company_name, title, body, data)
        if ok:
            sent += 1
        else:
            failed += 1
            if err:
                errors.append(err)

    return {"sent": sent, "failed": failed, "devices": len(filtered), "errors": errors[:5]}


def push_assessment_alerts(company_name: str, alerts: dict, closed_loop: dict = None) -> dict:
    alerts = alerts or {}
    alert_list = alerts.get("alerts") or []
    if not alert_list and not (closed_loop or {}).get("reassessment_trigger"):
        return {"skipped": True}
    top = alert_list[0] if alert_list else {}
    title = top.get("title") or "风险告警"
    body = top.get("message") or alerts.get("summary") or "请打开 ERM 查看详情"
    data = {
        "type": "risk_alert",
        "company": company_name,
        "severity": top.get("severity", "medium"),
        "alert_count": len(alert_list),
        "requires_reassessment": bool((closed_loop or {}).get("reassessment_trigger")),
    }
    return push_to_mobile_devices(company_name, title, body, data)


def _send_fcm(server_key: str, tokens: List[str], title: str, body: str, data: dict = None) -> tuple:
    payload = {
        "registration_ids": tokens[:500],
        "notification": {"title": title, "body": body, "sound": "default"},
        "data": {str(k): str(v) for k, v in (data or {}).items()},
        "priority": "high",
    }
    try:
        req = request.Request(
            "https://fcm.googleapis.com/fcm/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"key={server_key}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("failure", 0) > 0 and result.get("success", 0) == 0:
                return False, str(result.get("results", result))
            return True, ""
    except (error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _send_custom_push(url: str, company_name: str, title: str, body: str, data: dict = None) -> tuple:
    body_json = _build_mobile_payload(company_name, title, body, data)
    try:
        req = request.Request(
            url.strip(),
            data=json.dumps(body_json, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=12) as resp:
            return 200 <= resp.status < 300, ""
    except (error.URLError, OSError, ValueError) as exc:
        return False, str(exc)
