# -*- coding: utf-8 -*-
"""复评任务：到期生成可列表查看的任务，不只是文案提醒。"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional


def _json_path() -> str:
    from erm_store import data_dir
    return os.path.join(data_dir(), "reassessment_tasks.json")


def _load_json() -> List[dict]:
    path = _json_path()
    if not os.path.isfile(path):
        return []
    try:
        data = json.loads(open(path, encoding="utf-8").read())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_json(rows: List[dict]) -> None:
    path = _json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def upsert_task(row: dict) -> dict:
    rec = dict(row or {})
    rec["id"] = str(rec.get("id") or uuid.uuid4())[:12]
    rec["company_name"] = rec.get("company_name") or "未命名企业"
    rec["status"] = rec.get("status") or "open"
    rec["title"] = rec.get("title") or f"{rec['company_name']} 定期复评"
    rec["due_date"] = rec.get("due_date") or datetime.now().strftime("%Y-%m-%d")
    rec["updated_at"] = datetime.now().isoformat()
    from erm_store import using_postgres
    if using_postgres():
        from erm_store import upsert_reassessment_task
        return upsert_reassessment_task(rec)
    rows = _load_json()
    for r in rows:
        same = r.get("company_name") == rec["company_name"] and r.get("due_date") == rec["due_date"] and r.get("status") == "open"
        if r.get("id") == rec["id"] or same:
            r.update(rec)
            _save_json(rows)
            return r
    rec.setdefault("created_at", rec["updated_at"])
    rows.insert(0, rec)
    _save_json(rows)
    return rec


def list_tasks(status: str = "", company: str = "") -> List[dict]:
    from erm_store import using_postgres
    if using_postgres():
        from erm_store import list_reassessment_tasks
        return list_reassessment_tasks(status=status, company=company)
    rows = _load_json()
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if company:
        rows = [r for r in rows if r.get("company_name") == company]
    return rows


def complete_task(task_id: str) -> Optional[dict]:
    rec = {"id": task_id, "status": "done", "updated_at": datetime.now().isoformat()}
    from erm_store import using_postgres
    if using_postgres():
        from erm_store import patch_reassessment_task
        return patch_reassessment_task(task_id, {"status": "done"})
    rows = _load_json()
    found = None
    for r in rows:
        if r.get("id") == task_id:
            r["status"] = "done"
            r["updated_at"] = rec["updated_at"]
            found = r
    _save_json(rows)
    return found


def sync_from_assessment(company: str, assessed_at: str = None, basic: dict = None, force_due: bool = False) -> dict:
    from risk_kri import build_reassessment_reminder
    reminder = build_reassessment_reminder(assessed_at, basic or {})
    due = reminder["next_due_date"]
    if force_due:
        due = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        reminder["overdue"] = True
        reminder["urgency"] = "critical"
    status = "open"
    title = f"{company} 定期复评（{reminder['interval_days']} 天周期）"
    if reminder.get("overdue"):
        title = f"{company} 复评已逾期"
    rec = upsert_task({
        "company_name": company,
        "due_date": due,
        "status": status,
        "title": title,
        "interval_days": reminder.get("interval_days"),
        "last_assessed_at": reminder.get("last_assessed_at"),
        "urgency": reminder.get("urgency"),
        "payload": reminder,
    })
    return rec


def scan_due_tasks() -> dict:
    """调度器调用：对每家企业最新评估生成/刷新到期任务。"""
    from erm_store import load_history, audit
    seen = set()
    opened = 0
    for rec in load_history():
        company = rec.get("company_name") or ""
        if not company or company in seen:
            continue
        seen.add(company)
        basic = ((rec.get("assessment") or {}).get("all_raw_data") or {}).get("企业基本信息") or {}
        task = sync_from_assessment(company, rec.get("assessed_at"), basic)
        if task.get("status") == "open":
            opened += 1
    try:
        audit("reassessment.scan", "reassessment_task", "", {"companies": len(seen), "open": opened})
    except Exception:
        pass
    return {"companies": len(seen), "open": opened}
