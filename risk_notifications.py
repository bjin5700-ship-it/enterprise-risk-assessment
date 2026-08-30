# -*- coding: utf-8 -*-
"""风险告警推送 — 应用内队列、浏览器通知、Webhook、邮件"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from urllib import error, request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data")
NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "notifications.json")
NOTIFICATION_CONFIG_FILE = os.path.join(DATA_DIR, "notification_config.json")
MAX_NOTIFICATIONS = 200


def _default_config() -> dict:
    return {
        "browser_push_enabled": True,
        "webhook_enabled": False,
        "webhook_url": "",
        "webhook_type": "generic",
        "email_enabled": False,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "smtp_use_tls": True,
        "email_from": "",
        "email_to": [],
        "mobile_push_enabled": True,
    }


def load_notification_config(path: str = None) -> dict:
    path = path or NOTIFICATION_CONFIG_FILE
    if not os.path.exists(path):
        cfg = _default_config()
        save_notification_config(cfg, path)
        return _apply_smtp_env(cfg)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = _default_config()
        if isinstance(data, dict):
            merged.update(data)
        return _apply_smtp_env(merged)
    except (json.JSONDecodeError, OSError):
        return _apply_smtp_env(_default_config())


def _apply_smtp_env(cfg: dict) -> dict:
    out = dict(cfg)
    host = (os.environ.get("ERM_SMTP_HOST") or "").strip()
    if host:
        out["smtp_host"] = host
    port = (os.environ.get("ERM_SMTP_PORT") or "").strip()
    if port:
        try:
            out["smtp_port"] = int(port)
        except ValueError:
            pass
    user = (os.environ.get("ERM_SMTP_USER") or "").strip()
    if user:
        out["smtp_user"] = user
    pwd = os.environ.get("ERM_SMTP_PASSWORD")
    if pwd is not None and str(pwd) != "":
        out["smtp_password"] = pwd
    frm = (os.environ.get("ERM_SMTP_FROM") or "").strip()
    if frm:
        out["email_from"] = frm
    tls = (os.environ.get("ERM_SMTP_TLS") or "").strip().lower()
    if tls in ("0", "false", "no"):
        out["smtp_use_tls"] = False
    elif tls in ("1", "true", "yes"):
        out["smtp_use_tls"] = True
    out["smtp_configured"] = bool(out.get("smtp_host") and out.get("smtp_password"))
    return out


def save_notification_config(cfg: dict, path: str = None) -> None:
    path = path or NOTIFICATION_CONFIG_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_notifications(path: str = None) -> List[dict]:
    path = path or NOTIFICATIONS_FILE
    if not os.path.exists(path):
        return []
    try:
        raw = open(path, "rb").read()
    except OSError:
        return []
    data = None
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            data = json.loads(raw.decode(enc))
            if enc != "utf-8":
                try:
                    save_notifications(data if isinstance(data, list) else [], path)
                except Exception:
                    pass
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    if not isinstance(data, list):
        try:
            corrupt = path + ".corrupt"
            if not os.path.exists(corrupt):
                open(corrupt, "wb").write(raw)
        except OSError:
            pass
        return []
    return data


def save_notifications(items: List[dict], path: str = None) -> None:
    path = path or NOTIFICATIONS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items[:MAX_NOTIFICATIONS], f, ensure_ascii=False, indent=2)


def list_notifications(unread_only: bool = False, company: str = None, limit: int = 50) -> dict:
    items = load_notifications()
    if company:
        items = [n for n in items if n.get("company_name") == company]
    if unread_only:
        items = [n for n in items if not n.get("read")]
    unread = sum(1 for n in load_notifications() if not n.get("read"))
    return {
        "notifications": items[:limit],
        "unread_count": unread,
        "total": len(items),
    }


def mark_notifications_read(ids: List[str] = None, mark_all: bool = False) -> dict:
    items = load_notifications()
    updated = 0
    id_set = set(ids or [])
    for n in items:
        if mark_all or n.get("id") in id_set:
            if not n.get("read"):
                n["read"] = True
                n["read_at"] = datetime.now().isoformat()
                updated += 1
    save_notifications(items)
    return {"updated": updated, "unread_count": sum(1 for n in items if not n.get("read"))}


def _severity_rank(sev: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(sev or "", 0)


def emit_assessment_alerts(
    company_name: str,
    alerts: dict = None,
    closed_loop: dict = None,
    source: str = "assess",
) -> List[dict]:
    """评估或定时同步后写入通知队列并触发外部推送。"""
    alerts = alerts or {}
    closed_loop = closed_loop or {}
    alert_list = alerts.get("alerts") or []
    if not alert_list and not closed_loop.get("reassessment_trigger"):
        return []

    created: List[dict] = []
    items = load_notifications()
    now = datetime.now().isoformat()

    for a in alert_list[:10]:
        items.insert(0, {
            "id": str(uuid.uuid4())[:8],
            "company_name": company_name,
            "severity": a.get("severity", "medium"),
            "title": a.get("title", "风险告警"),
            "message": a.get("message", ""),
            "suggested_action": a.get("suggested_action", ""),
            "type": a.get("type", "alert"),
            "source": source,
            "read": False,
            "created_at": now,
        })
        created.append(items[0])

    if closed_loop.get("reassessment_trigger") and not any(
        n.get("type") == "reassessment_trigger" and n.get("company_name") == company_name
        for n in items[:5]
    ):
        items.insert(0, {
            "id": str(uuid.uuid4())[:8],
            "company_name": company_name,
            "severity": "critical",
            "title": "建议立即复评",
            "message": closed_loop.get("summary") or alerts.get("summary", "存在严重告警，请尽快复评"),
            "suggested_action": "完成全量复评并更新风险登记册",
            "type": "reassessment_trigger",
            "source": source,
            "read": False,
            "created_at": now,
        })
        created.append(items[0])

    save_notifications(items[:MAX_NOTIFICATIONS])

    cfg = load_notification_config()
    if cfg.get("webhook_enabled") and cfg.get("webhook_url"):
        _dispatch_webhook(cfg, company_name, alerts, closed_loop, source)
    if cfg.get("email_enabled") and cfg.get("email_to"):
        _dispatch_email(cfg, company_name, alerts, closed_loop, source)

    if cfg.get("mobile_push_enabled", True):
        try:
            from risk_mobile_push import push_assessment_alerts
            alert_list = alerts.get("alerts") or []
            if alert_list or closed_loop.get("reassessment_trigger"):
                top = alert_list[0] if alert_list else {}
                push_assessment_alerts(company_name, alerts, closed_loop)
        except Exception:
            pass

    return created


def _build_push_text(company_name: str, alerts: dict, closed_loop: dict, source: str) -> str:
    lines = [f"【{company_name}】风险告警 ({source})"]
    lines.append(alerts.get("summary", ""))
    for a in (alerts.get("alerts") or [])[:5]:
        lines.append(f"- [{a.get('severity', '').upper()}] {a.get('title')}: {a.get('message')}")
    v = (closed_loop or {}).get("remediation_verification") or {}
    if v.get("verification_label"):
        lines.append(f"整改验证：{v.get('verification_label')} (Δ{v.get('overall_delta', 0):+.2f})")
    return "\n".join(p for p in lines if p)


def _dispatch_webhook(cfg: dict, company_name: str, alerts: dict, closed_loop: dict, source: str) -> bool:
    url = (cfg.get("webhook_url") or "").strip()
    if not url:
        return False
    text = _build_push_text(company_name, alerts, closed_loop, source)
    wtype = cfg.get("webhook_type", "generic")

    if wtype == "dingtalk":
        body = {"msgtype": "markdown", "markdown": {"title": f"{company_name} 风险告警", "text": text}}
    elif wtype == "wecom":
        body = {"msgtype": "markdown", "markdown": {"content": text}}
    else:
        body = {
            "company_name": company_name,
            "source": source,
            "summary": alerts.get("summary"),
            "alerts": alerts.get("alerts", [])[:10],
            "closed_loop_summary": closed_loop.get("summary"),
            "text": text,
            "sent_at": datetime.now().isoformat(),
        }

    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=12) as resp:
            return 200 <= resp.status < 300
    except (error.URLError, OSError, ValueError):
        return False


def _dispatch_email(cfg: dict, company_name: str, alerts: dict, closed_loop: dict, source: str) -> bool:
    host = (cfg.get("smtp_host") or "").strip()
    recipients = [e for e in (cfg.get("email_to") or []) if e]
    if not host or not recipients:
        return False
    text = _build_push_text(company_name, alerts, closed_loop, source)
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = f"[ERM] {company_name} 风险告警"
    msg["From"] = cfg.get("email_from") or cfg.get("smtp_user") or "erm@localhost"
    msg["To"] = ", ".join(recipients)
    try:
        port = int(cfg.get("smtp_port") or 587)
        with smtplib.SMTP(host, port, timeout=15) as server:
            if cfg.get("smtp_use_tls", True):
                server.starttls(context=ssl.create_default_context())
            user = cfg.get("smtp_user")
            pwd = cfg.get("smtp_password")
            if user and pwd:
                server.login(user, pwd)
            server.sendmail(msg["From"], recipients, msg.as_string())
        return True
    except (smtplib.SMTPException, OSError, ValueError):
        return False
