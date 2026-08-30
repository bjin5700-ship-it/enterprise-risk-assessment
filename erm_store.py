# -*- coding: utf-8 -*-
"""E2 评估档案存储：PostgreSQL 为主，JSON 仅作未配置数据库时的降级。"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uscc TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS enterprise_name_idx ON enterprise (lower(name));
CREATE INDEX IF NOT EXISTS enterprise_uscc_idx ON enterprise (uscc) WHERE uscc IS NOT NULL AND uscc <> '';

CREATE TABLE IF NOT EXISTS assessment_version (
    id TEXT PRIMARY KEY,
    enterprise_id TEXT REFERENCES enterprise(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    overall_score DOUBLE PRECISION,
    overall_level TEXT,
    report_date TEXT,
    assessed_at TIMESTAMPTZ,
    note TEXT DEFAULT '',
    form_stats JSONB,
    assessment JSONB NOT NULL,
    created_by TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS assessment_company_idx ON assessment_version (company_name);
CREATE INDEX IF NOT EXISTS assessment_assessed_idx ON assessment_version (assessed_at DESC);

CREATE TABLE IF NOT EXISTS evidence_object (
    id TEXT PRIMARY KEY,
    assessment_id TEXT REFERENCES assessment_version(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    filename TEXT,
    content_type TEXT,
    storage TEXT NOT NULL DEFAULT 'local',
    object_key TEXT NOT NULL,
    size_bytes BIGINT,
    created_by TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_item (
    id TEXT PRIMARY KEY,
    assessment_id TEXT REFERENCES assessment_version(id) ON DELETE CASCADE,
    enterprise_id TEXT REFERENCES enterprise(id) ON DELETE SET NULL,
    title TEXT,
    owner TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'open',
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS action_item_status_idx ON action_item (status);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS audit_log_created_idx ON audit_log (created_at DESC);

CREATE TABLE IF NOT EXISTS risk_register_item (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    assessment_id TEXT,
    enterprise_id TEXT,
    dimension TEXT,
    title TEXT,
    priority TEXT,
    risk_rating TEXT,
    status TEXT NOT NULL DEFAULT 'identified',
    owner TEXT,
    due_date TEXT,
    acceptance_reason TEXT,
    review_date TEXT,
    approver TEXT,
    approved_at TIMESTAMPTZ,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS register_company_idx ON risk_register_item (company_name);

ALTER TABLE action_item ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS priority TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS dimension TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS acceptance_reason TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS review_date TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS approver TEXT;
ALTER TABLE action_item ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS kri_snapshot (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    overall_score DOUBLE PRECISION,
    overall_level TEXT,
    kri_health DOUBLE PRECISION,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS kri_snapshot_company_idx ON kri_snapshot (company_name, assessed_at ASC);

CREATE TABLE IF NOT EXISTS reassessment_task (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    title TEXT,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    interval_days INT,
    last_assessed_at TEXT,
    urgency TEXT,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS reassessment_task_status_idx ON reassessment_task (status, due_date);
"""

JSON_LIMIT = 100


def data_dir() -> str:
    env = (os.environ.get("ERM_DATA_DIR") or "").strip()
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data")
    os.makedirs(path, exist_ok=True)
    return path


def history_json_path() -> str:
    return os.path.join(data_dir(), "history.json")


def database_url() -> str:
    return (
        (os.environ.get("ERM_DATABASE_URL") or "").strip()
        or (os.environ.get("DATABASE_URL") or "").strip()
    )


def using_postgres() -> bool:
    url = database_url()
    return bool(url) and url.startswith(("postgres://", "postgresql://"))


def backend_name() -> str:
    return "postgres" if using_postgres() else "json"


def _actor() -> str:
    try:
        from flask import has_request_context
        if not has_request_context():
            return os.environ.get("ERM_STORE_ACTOR") or ""
        from erm_auth import current_user
        user = current_user()
        return user.username if user else ""
    except Exception:
        return ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _iso(value: Any) -> str:
    dt = _parse_dt(value)
    if not dt:
        return str(value or "")
    return dt.isoformat()


def _connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(database_url(), row_factory=dict_row, autocommit=True)


def _jsonb(value: Any):
    from psycopg.types.json import Jsonb
    return Jsonb(value if value is not None else {})


def init_schema() -> None:
    if not using_postgres():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


def storage_status() -> dict:
    pg = using_postgres()
    pg_ok = False
    pg_count = 0
    err = ""
    if pg:
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS n FROM assessment_version")
                    pg_count = int((cur.fetchone() or {}).get("n") or 0)
                    pg_ok = True
        except Exception as exc:
            err = str(exc)
    json_path = history_json_path()
    json_exists = os.path.isfile(json_path)
    try:
        from erm_objects import object_store_status
        blobs = object_store_status()
    except Exception as exc:
        blobs = {"backend": "local", "connected": False, "note": str(exc)}
    return {
        "history_backend": backend_name() if pg_ok or not pg else "postgres_error",
        "postgres": pg_ok,
        "postgres_configured": pg,
        "assessment_count": pg_count if pg_ok else None,
        "json_primary": not pg_ok,
        "json_file_exists": json_exists,
        "error": err,
        "objects": blobs,
    }


def _row_to_record(row: dict, include_assessment: bool = True) -> dict:
    rec = {
        "id": row.get("id"),
        "company_name": row.get("company_name"),
        "overall_score": row.get("overall_score"),
        "overall_level": row.get("overall_level"),
        "report_date": row.get("report_date") or "",
        "assessed_at": _iso(row.get("assessed_at")),
        "note": row.get("note") or "",
        "form_stats": row.get("form_stats"),
        "created_by": row.get("created_by") or "",
    }
    if include_assessment:
        rec["assessment"] = row.get("assessment") or {}
    return rec


def _json_load() -> List[dict]:
    path = history_json_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _json_save(records: List[dict]) -> None:
    path = history_json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records[:JSON_LIMIT], f, ensure_ascii=False, indent=2)


def load_history() -> List[dict]:
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, company_name, overall_score, overall_level, report_date,
                           assessed_at, note, form_stats, assessment, created_by
                    FROM assessment_version
                    ORDER BY assessed_at DESC NULLS LAST, created_at DESC
                    """
                )
                return [_row_to_record(r) for r in cur.fetchall()]
    return _json_load()


def get_assessment(record_id: str) -> Optional[dict]:
    if not record_id:
        return None
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, company_name, overall_score, overall_level, report_date,
                           assessed_at, note, form_stats, assessment, created_by
                    FROM assessment_version WHERE id = %s
                    """,
                    (record_id,),
                )
                row = cur.fetchone()
                return _row_to_record(row) if row else None
    for rec in _json_load():
        if rec.get("id") == record_id:
            return rec
    return None


def list_actions(company_name: str) -> List[dict]:
    if not using_postgres():
        return []
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, company_name, title, owner, due_date, status, priority, dimension,
                       acceptance_reason, review_date, approver, approved_at, payload, updated_at
                FROM action_item WHERE company_name = %s ORDER BY priority, title
                """,
                (company_name,),
            )
            return [dict(r) for r in cur.fetchall()]


def list_register(company_name: str) -> List[dict]:
    if not using_postgres():
        return []
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, company_name, dimension, title, priority, risk_rating, status, owner,
                       due_date, acceptance_reason, review_date, approver, approved_at, payload, updated_at
                FROM risk_register_item WHERE company_name = %s ORDER BY priority, dimension
                """,
                (company_name,),
            )
            return [dict(r) for r in cur.fetchall()]


def patch_action(item_id: str, fields: dict) -> Optional[dict]:
    if not using_postgres():
        return None
    allowed = {
        "status", "owner", "due_date", "acceptance_reason", "review_date",
        "approver", "title", "priority", "dimension", "company_name",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        vals.append(v)
    if fields.get("approver") and "approved_at" not in fields:
        sets.append("approved_at = NOW()")
    if not sets:
        return None
    vals.append(item_id)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE action_item SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s RETURNING *",
                vals,
            )
            row = cur.fetchone()
            return dict(row) if row else None


def patch_register(item_id: str, fields: dict) -> Optional[dict]:
    if not using_postgres():
        return None
    allowed = {
        "status", "owner", "due_date", "acceptance_reason", "review_date",
        "approver", "title", "priority", "risk_rating", "dimension", "company_name",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        vals.append(v)
    if fields.get("approver"):
        sets.append("approved_at = NOW()")
    if not sets:
        return None
    vals.append(item_id)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE risk_register_item SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s RETURNING *",
                vals,
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_kri_snapshot(row: dict) -> dict:
    rec = dict(row or {})
    rec["id"] = str(rec.get("id") or uuid.uuid4())[:16]
    rec["company_name"] = rec.get("company_name") or "未命名企业"
    rec["assessed_at"] = rec.get("assessed_at") or _now().isoformat()
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kri_snapshot (
                        id, company_name, assessed_at, overall_score, overall_level, kri_health, payload
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        company_name=EXCLUDED.company_name,
                        assessed_at=EXCLUDED.assessed_at,
                        overall_score=EXCLUDED.overall_score,
                        overall_level=EXCLUDED.overall_level,
                        kri_health=EXCLUDED.kri_health,
                        payload=EXCLUDED.payload
                    """,
                    (
                        rec["id"], rec["company_name"], rec["assessed_at"],
                        rec.get("overall_score"), rec.get("overall_level"), rec.get("kri_health"),
                        _jsonb(rec),
                    ),
                )
        return rec
    path = os.path.join(data_dir(), "kpi_timeseries.json")
    db = {}
    if os.path.isfile(path):
        try:
            db = json.loads(open(path, encoding="utf-8").read()) or {}
        except (json.JSONDecodeError, OSError):
            db = {}
    key = rec["company_name"]
    entry = db.setdefault(key, {"company_name": key, "snapshots": []})
    snaps = [s for s in (entry.get("snapshots") or []) if s.get("id") != rec["id"]]
    snaps.insert(0, rec)
    entry["snapshots"] = snaps[:48]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return rec


def list_kri_snapshots(company_name: str) -> List[dict]:
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, company_name, assessed_at, overall_score, overall_level, kri_health, payload
                    FROM kri_snapshot WHERE company_name = %s ORDER BY assessed_at ASC
                    """,
                    (company_name,),
                )
                out = []
                for r in cur.fetchall():
                    payload = r.get("payload") or {}
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            payload = {}
                    snap = dict(payload) if isinstance(payload, dict) else {}
                    snap.update({
                        "id": r["id"],
                        "company_name": r["company_name"],
                        "assessed_at": str(r["assessed_at"]) if r.get("assessed_at") else snap.get("assessed_at"),
                        "overall_score": r.get("overall_score") if r.get("overall_score") is not None else snap.get("overall_score"),
                        "overall_level": r.get("overall_level") or snap.get("overall_level"),
                        "kri_health": r.get("kri_health") if r.get("kri_health") is not None else snap.get("kri_health"),
                    })
                    out.append(snap)
                return out
    path = os.path.join(data_dir(), "kpi_timeseries.json")
    if not os.path.isfile(path):
        return []
    try:
        db = json.loads(open(path, encoding="utf-8").read()) or {}
    except (json.JSONDecodeError, OSError):
        return []
    snaps = list(reversed((db.get(company_name) or {}).get("snapshots") or []))
    return snaps


def delete_company_kri(company_name: str) -> int:
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kri_snapshot WHERE company_name = %s", (company_name,))
                return cur.rowcount or 0
    path = os.path.join(data_dir(), "kpi_timeseries.json")
    if not os.path.isfile(path):
        return 0
    try:
        db = json.loads(open(path, encoding="utf-8").read()) or {}
    except (json.JSONDecodeError, OSError):
        return 0
    n = len((db.get(company_name) or {}).get("snapshots") or [])
    db.pop(company_name, None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return n


def upsert_reassessment_task(row: dict) -> dict:
    rec = dict(row or {})
    rec["id"] = str(rec.get("id") or uuid.uuid4())[:12]
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM reassessment_task
                WHERE company_name=%s AND due_date=%s AND status='open' LIMIT 1
                """,
                (rec.get("company_name"), rec.get("due_date")),
            )
            existing = cur.fetchone()
            if existing:
                rec["id"] = existing["id"]
            cur.execute(
                """
                INSERT INTO reassessment_task (
                    id, company_name, title, due_date, status, interval_days,
                    last_assessed_at, urgency, payload
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, due_date=EXCLUDED.due_date, status=EXCLUDED.status,
                    interval_days=EXCLUDED.interval_days, last_assessed_at=EXCLUDED.last_assessed_at,
                    urgency=EXCLUDED.urgency, payload=EXCLUDED.payload, updated_at=NOW()
                RETURNING *
                """,
                (
                    rec["id"], rec.get("company_name"), rec.get("title"), rec.get("due_date"),
                    rec.get("status") or "open", rec.get("interval_days"),
                    rec.get("last_assessed_at"), rec.get("urgency"), _jsonb(rec.get("payload") or rec),
                ),
            )
            out = cur.fetchone()
            return dict(out) if out else rec


def list_reassessment_tasks(status: str = "", company: str = "") -> List[dict]:
    sql = "SELECT * FROM reassessment_task WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=%s"
        args.append(status)
    if company:
        sql += " AND company_name=%s"
        args.append(company)
    sql += " ORDER BY due_date ASC, updated_at DESC"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = []
            for r in cur.fetchall():
                item = dict(r)
                if item.get("created_at"):
                    item["created_at"] = str(item["created_at"])
                if item.get("updated_at"):
                    item["updated_at"] = str(item["updated_at"])
                rows.append(item)
            return rows


def patch_reassessment_task(task_id: str, fields: dict) -> Optional[dict]:
    sets, vals = [], []
    for k in ("status", "title", "due_date", "urgency"):
        if k in fields:
            sets.append(f"{k}=%s")
            vals.append(fields[k])
    if not sets:
        return None
    vals.append(task_id)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE reassessment_task SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s RETURNING *",
                vals,
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_enterprise(name: str, uscc: str = "") -> str:
    name = (name or "未命名企业").strip() or "未命名企业"
    uscc = (uscc or "").strip()
    if not using_postgres():
        return ""
    with _connect() as conn:
        with conn.cursor() as cur:
            if uscc:
                cur.execute("SELECT id FROM enterprise WHERE uscc = %s LIMIT 1", (uscc,))
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE enterprise SET name=%s, updated_at=NOW() WHERE id=%s",
                        (name, row["id"]),
                    )
                    return row["id"]
            cur.execute("SELECT id FROM enterprise WHERE lower(name)=lower(%s) LIMIT 1", (name,))
            row = cur.fetchone()
            if row:
                if uscc:
                    cur.execute(
                        "UPDATE enterprise SET uscc=%s, updated_at=NOW() WHERE id=%s",
                        (uscc, row["id"]),
                    )
                return row["id"]
            eid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO enterprise (id, name, uscc) VALUES (%s, %s, %s)",
                (eid, name, uscc or None),
            )
            return eid


def _uscc_from_assessment(assessment: dict) -> str:
    basic = (assessment or {}).get("all_raw_data") or {}
    info = basic.get("企业基本信息") or {}
    return str(info.get("统一社会信用代码") or info.get("社会信用代码") or "").strip()


def _sync_action_items(cur, record: dict, enterprise_id: str) -> None:
    assessment = record.get("assessment") or {}
    plans = assessment.get("action_plans")
    if isinstance(plans, dict):
        items = plans.get("action_items") or []
    elif isinstance(plans, list):
        items = plans
    else:
        items = []
    deep = assessment.get("deep_analysis") or (assessment.get("analytics") or {}).get("deep_analysis") or {}
    register = (deep.get("risk_register") or []) if isinstance(deep, dict) else []
    company = record.get("company_name") or assessment.get("company_name") or ""
    for plan in items[:80]:
        if not isinstance(plan, dict):
            continue
        aid = str(plan.get("id") or uuid.uuid4())
        due = str(plan.get("due_date") or plan.get("deadline") or "")
        if not due and plan.get("timeline_days"):
            due = str(plan.get("timeline_days")) + "天"
        cur.execute(
            """
            INSERT INTO action_item (
                id, assessment_id, enterprise_id, company_name, title, owner, due_date,
                status, priority, dimension, payload
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,'open',%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                assessment_id=EXCLUDED.assessment_id,
                enterprise_id=EXCLUDED.enterprise_id,
                company_name=EXCLUDED.company_name,
                title=EXCLUDED.title,
                owner=COALESCE(NULLIF(action_item.owner,''), EXCLUDED.owner),
                due_date=COALESCE(NULLIF(action_item.due_date,''), EXCLUDED.due_date),
                priority=EXCLUDED.priority,
                dimension=EXCLUDED.dimension,
                payload=EXCLUDED.payload,
                updated_at=NOW()
            """,
            (
                aid, record["id"], enterprise_id or None, company,
                str(plan.get("title") or plan.get("action") or plan.get("name") or "")[:240],
                str(plan.get("owner") or plan.get("responsible") or "")[:120],
                due[:40],
                str(plan.get("priority") or "")[:20],
                str(plan.get("dimension") or "")[:80],
                _jsonb(plan),
            ),
        )
    for row in register[:40]:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or uuid.uuid4())
        rating = str(row.get("risk_rating") or row.get("level") or "")
        prio = "P0" if rating in ("极高", "高") else "P1"
        cur.execute(
            """
            INSERT INTO risk_register_item (
                id, company_name, assessment_id, enterprise_id, dimension, title,
                priority, risk_rating, status, owner, payload
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'identified',%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                assessment_id=EXCLUDED.assessment_id,
                enterprise_id=EXCLUDED.enterprise_id,
                company_name=EXCLUDED.company_name,
                dimension=EXCLUDED.dimension,
                title=EXCLUDED.title,
                priority=EXCLUDED.priority,
                risk_rating=EXCLUDED.risk_rating,
                owner=COALESCE(NULLIF(risk_register_item.owner,''), EXCLUDED.owner),
                payload=EXCLUDED.payload,
                updated_at=NOW()
            """,
            (
                rid, company, record["id"], enterprise_id or None,
                str(row.get("dimension") or "")[:80],
                str(row.get("risk_description") or row.get("dimension") or "")[:240],
                prio, rating[:20],
                str(row.get("owner") or "")[:120],
                _jsonb(row),
            ),
        )


def audit(action: str, entity_type: str = "", entity_id: str = "", detail: Optional[dict] = None) -> None:
    if not using_postgres():
        return
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log (actor, action, entity_type, entity_id, detail)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (_actor(), action, entity_type, entity_id, _jsonb(detail or {})),
                )
    except Exception:
        pass


def upsert_assessment(record: dict) -> dict:
    rec = dict(record or {})
    rec["id"] = str(rec.get("id") or str(uuid.uuid4())[:8])
    rec["company_name"] = rec.get("company_name") or (rec.get("assessment") or {}).get("company_name") or "未命名企业"
    rec["assessed_at"] = rec.get("assessed_at") or _now().isoformat()
    rec["note"] = rec.get("note") or ""
    rec["created_by"] = rec.get("created_by") or _actor()
    assessment = rec.get("assessment") or {}
    if using_postgres():
        eid = upsert_enterprise(rec["company_name"], _uscc_from_assessment(assessment))
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessment_version (
                        id, enterprise_id, company_name, overall_score, overall_level,
                        report_date, assessed_at, note, form_stats, assessment, created_by
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        enterprise_id=EXCLUDED.enterprise_id,
                        company_name=EXCLUDED.company_name,
                        overall_score=EXCLUDED.overall_score,
                        overall_level=EXCLUDED.overall_level,
                        report_date=EXCLUDED.report_date,
                        assessed_at=EXCLUDED.assessed_at,
                        note=EXCLUDED.note,
                        form_stats=EXCLUDED.form_stats,
                        assessment=EXCLUDED.assessment
                    """,
                    (
                        rec["id"],
                        eid or None,
                        rec["company_name"],
                        rec.get("overall_score"),
                        rec.get("overall_level"),
                        rec.get("report_date") or "",
                        _parse_dt(rec.get("assessed_at")),
                        rec.get("note") or "",
                        _jsonb(rec.get("form_stats")),
                        _jsonb(assessment),
                        rec.get("created_by") or "",
                    ),
                )
                _sync_action_items(cur, rec, eid)
        audit("assessment.upsert", "assessment_version", rec["id"], {"company": rec["company_name"]})
        _sync_reassessment_task(rec)
        return rec
    records = [r for r in _json_load() if r.get("id") != rec["id"]]
    records.insert(0, rec)
    _json_save(records)
    try:
        from risk_workflow import ensure_generated_items
        ensure_generated_items(rec)
    except Exception:
        pass
    _sync_reassessment_task(rec)
    return rec


def _sync_reassessment_task(rec: dict) -> None:
    try:
        from risk_tasks import sync_from_assessment
        assessment = rec.get("assessment") or {}
        basic = (assessment.get("all_raw_data") or {}).get("企业基本信息") or {}
        sync_from_assessment(rec.get("company_name") or "", rec.get("assessed_at"), basic)
    except Exception:
        pass


def add_history_record(assessment: dict, note: str = "") -> dict:
    record = {
        "id": str(uuid.uuid4())[:8],
        "company_name": (assessment or {}).get("company_name", "未命名企业"),
        "overall_score": (assessment or {}).get("overall_score"),
        "overall_level": (assessment or {}).get("overall_level"),
        "report_date": (assessment or {}).get("report_date"),
        "assessed_at": (assessment or {}).get("assessed_at") or _now().isoformat(),
        "note": note,
        "form_stats": (assessment or {}).get("form_stats"),
        "assessment": assessment,
    }
    return upsert_assessment(record)


def delete_assessment(record_id: str) -> bool:
    if not record_id:
        return False
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM assessment_version WHERE id = %s", (record_id,))
                gone = cur.rowcount > 0
        if gone:
            audit("assessment.delete", "assessment_version", record_id, {})
        return gone
    records = [r for r in _json_load() if r.get("id") != record_id]
    _json_save(records)
    return True


def save_history(records: List[dict]) -> None:
    """兼容旧接口：JSON 整文件覆盖；PG 逐条 upsert，并删除不在列表中的记录。"""
    records = list(records or [])
    if using_postgres():
        keep = set()
        for rec in records:
            upsert_assessment(rec)
            keep.add(str(rec.get("id")))
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM assessment_version")
                for row in cur.fetchall():
                    if row["id"] not in keep:
                        cur.execute("DELETE FROM assessment_version WHERE id = %s", (row["id"],))
        return
    _json_save(records)


def delete_demo_assessments() -> int:
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM assessment_version
                    WHERE id LIKE 'demo-%' OR company_name LIKE 'DEMO-%' OR COALESCE(note,'') LIKE '演示%'
                    """
                )
                return cur.rowcount
    kept = [
        r for r in _json_load()
        if not (
            str(r.get("id") or "").startswith("demo-")
            or str(r.get("company_name") or "").startswith("DEMO-")
            or str(r.get("note") or "").startswith("演示")
        )
    ]
    removed = len(_json_load()) - len(kept)
    _json_save(kept)
    return removed


def insert_evidence(
    *,
    assessment_id: str = "",
    kind: str,
    filename: str,
    content_type: str,
    storage: str,
    object_key: str,
    size_bytes: int = 0,
) -> dict:
    rec = {
        "id": str(uuid.uuid4()),
        "assessment_id": assessment_id or None,
        "kind": kind,
        "filename": filename,
        "content_type": content_type,
        "storage": storage,
        "object_key": object_key,
        "size_bytes": size_bytes,
        "created_by": _actor(),
        "created_at": _now().isoformat(),
    }
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                aid = rec["assessment_id"]
                if aid:
                    cur.execute("SELECT 1 FROM assessment_version WHERE id=%s", (aid,))
                    if not cur.fetchone():
                        aid = None
                cur.execute(
                    """
                    INSERT INTO evidence_object
                        (id, assessment_id, kind, filename, content_type, storage, object_key, size_bytes, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        rec["id"], aid, rec["kind"], rec["filename"], rec["content_type"],
                        rec["storage"], rec["object_key"], rec["size_bytes"], rec["created_by"],
                    ),
                )
        audit("evidence.insert", "evidence_object", rec["id"], {"kind": kind, "filename": filename})
        return rec
    path = os.path.join(data_dir(), "evidence_index.json")
    rows = []
    if os.path.isfile(path):
        try:
            rows = json.loads(open(path, encoding="utf-8").read())
            if not isinstance(rows, list):
                rows = []
        except (json.JSONDecodeError, OSError):
            rows = []
    rows.insert(0, rec)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows[:500], f, ensure_ascii=False, indent=2)
    return rec


def get_evidence(oid: str) -> Optional[dict]:
    if using_postgres():
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM evidence_object WHERE id=%s", (oid,))
                row = cur.fetchone()
                return dict(row) if row else None
    path = os.path.join(data_dir(), "evidence_index.json")
    if not os.path.isfile(path):
        return None
    try:
        rows = json.loads(open(path, encoding="utf-8").read())
    except (json.JSONDecodeError, OSError):
        return None
    for rec in rows if isinstance(rows, list) else []:
        if rec.get("id") == oid:
            return rec
    return None


def migrate_json_if_needed() -> dict:
    """PG 为空且存在 history.json 时导入，并改名为备份。"""
    if not using_postgres():
        return {"migrated": False, "reason": "json_backend"}
    init_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM assessment_version")
            n = int((cur.fetchone() or {}).get("n") or 0)
    if n > 0:
        return {"migrated": False, "reason": "postgres_already_has_rows", "count": n}
    records = _json_load()
    if not records:
        return {"migrated": False, "reason": "no_json_history", "count": 0}
    for rec in reversed(records):
        upsert_assessment(rec)
    src = history_json_path()
    bak = src + ".migrated-" + _now().strftime("%Y%m%d%H%M%S")
    try:
        shutil.move(src, bak)
        backup = bak
    except OSError:
        backup = ""
    audit("history.migrate_json", "assessment_version", "", {"count": len(records), "backup": backup})
    return {"migrated": True, "count": len(records), "backup": backup}


def init_store() -> dict:
    status = {"backend": backend_name()}
    if using_postgres():
        init_schema()
        status.update(migrate_json_if_needed())
        try:
            from erm_objects import ensure_bucket, object_store_status
            ensure_bucket()
            status["objects"] = object_store_status()
        except Exception as exc:
            status["objects_error"] = str(exc)
    else:
        status["json_file"] = history_json_path()
    return status
