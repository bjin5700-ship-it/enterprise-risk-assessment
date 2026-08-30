# -*- coding: utf-8 -*-
"""E3 风险登记状态机：识别 / 应对中 / 接受 / 关闭。P0/高风险关闭须审批。"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

STATUS_LABEL = {
    "identified": "识别",
    "treating": "应对中",
    "accepted": "接受",
    "closed": "关闭",
    "open": "识别",
    "completed": "关闭",
}
STATUS_CODE = {v: k for k, v in STATUS_LABEL.items()}
STATUS_CODE.update({"已关闭": "closed", "已完成": "closed", "完成": "closed"})

DONE = frozenset({"closed", "completed", "done", "关闭", "已关闭", "已完成"})
HIGH_RATING = frozenset({"极高", "高"})
APPROVE_ROLES = frozenset({"approver", "admin"})
WRITE_ROLES = frozenset({"assessor", "approver", "admin"})


def stable_item_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"


def _state_path() -> str:
    from erm_store import data_dir
    return os.path.join(data_dir(), "workflow_state.json")


def _load_json_state() -> dict:
    path = _state_path()
    if not os.path.isfile(path):
        return {"register": {}, "actions": {}}
    try:
        data = json.loads(open(path, encoding="utf-8").read())
        if not isinstance(data, dict):
            return {"register": {}, "actions": {}}
        data.setdefault("register", {})
        data.setdefault("actions", {})
        return data
    except (json.JSONDecodeError, OSError):
        return {"register": {}, "actions": {}}


def _save_json_state(data: dict) -> None:
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_status(raw: str, *, kind: str = "register") -> str:
    s = (raw or "").strip()
    if s in STATUS_CODE:
        s = STATUS_CODE[s]
    if kind == "action" and s in ("closed", "completed", "done"):
        return "completed" if s != "closed" else "closed"
    if s in STATUS_LABEL:
        return s
    return "identified" if kind == "register" else "open"


def status_label(code: str) -> str:
    return STATUS_LABEL.get(code, code or "识别")


def is_p0(item: dict) -> bool:
    if str(item.get("priority") or "") == "P0":
        return True
    rating = str(item.get("risk_rating") or item.get("level") or "")
    return rating in HIGH_RATING


def requires_approval(item: dict, new_status: str) -> bool:
    target = normalize_status(new_status, kind=item.get("kind") or "register")
    if target not in DONE and target != "accepted":
        return False
    return is_p0(item)


def _actor_role(user) -> Tuple[str, str]:
    if not user:
        return "", ""
    return getattr(user, "username", "") or "", getattr(user, "role", "") or ""


def validate_transition(item: dict, new_status: str, user, reason: str = "", review_date: str = "") -> Optional[str]:
    role = getattr(user, "role", "") if user else ""
    if role not in WRITE_ROLES:
        return "需要评估人或审批人登录"
    target = normalize_status(new_status, kind=item.get("kind") or "register")
    if not requires_approval(item, target):
        return None
    if role not in APPROVE_ROLES:
        return "P0/高风险项关闭或接受必须由审批人操作"
    if not (reason or "").strip():
        return "须填写接受/关闭理由"
    if not (review_date or "").strip():
        return "须填写复评日期"
    return None


def _rows_for_company(company: str) -> Tuple[List[dict], List[dict]]:
    from erm_store import list_actions, list_register, using_postgres
    if using_postgres():
        return list_register(company), list_actions(company)
    st = _load_json_state()
    reg = [v for v in (st.get("register") or {}).values() if v.get("company_name") == company]
    acts = [v for v in (st.get("actions") or {}).values() if v.get("company_name") == company]
    return reg, acts


def action_tracking_map(company: str) -> dict:
    _, acts = _rows_for_company(company)
    actions = {}
    for a in acts:
        actions[a["id"]] = {
            "status": a.get("status") or "open",
            "note": a.get("acceptance_reason") or "",
            "updated_at": str(a.get("updated_at") or ""),
            "owner": a.get("owner") or "",
            "due_date": a.get("due_date") or "",
            "approver": a.get("approver") or "",
        }
    return {"company_name": company, "actions": actions}


def completion_stats(company: str, generated_actions: Optional[List[dict]] = None) -> dict:
    _, persisted = _rows_for_company(company)
    by_id = {a["id"]: a for a in persisted}
    items = generated_actions or persisted
    total = len(items)
    completed = 0
    p0_total = p0_closed = 0
    for a in items:
        row = by_id.get(a.get("id"), a)
        merged = {**a, **{k: row.get(k) for k in ("status", "priority") if row.get(k)}}
        if is_p0(merged):
            p0_total += 1
        if normalize_status(merged.get("status") or "", kind="action") in DONE:
            completed += 1
            if is_p0(merged):
                p0_closed += 1
    reg, _ = _rows_for_company(company)
    reg_closed = sum(1 for r in reg if normalize_status(r.get("status") or "") in DONE | {"accepted"})
    return {
        "total": total,
        "completed": completed,
        "completion_pct": round(completed / total * 100, 1) if total else 0,
        "p0_total": p0_total,
        "p0_closed": p0_closed,
        "register_total": len(reg),
        "register_closed": reg_closed,
        "source": "persisted",
    }


def snapshot(company: str) -> dict:
    reg, acts = _rows_for_company(company)
    return {
        "company_name": company,
        "register": [_public_row(r, "register") for r in reg],
        "actions": [_public_row(a, "action") for a in acts],
        "completion": completion_stats(company, acts),
        "status_labels": STATUS_LABEL,
    }


def _public_row(row: dict, kind: str) -> dict:
    code = normalize_status(row.get("status") or "", kind=kind)
    out = dict(row)
    if out.get("approved_at"):
        out["approved_at"] = str(out["approved_at"])
    if out.get("updated_at"):
        out["updated_at"] = str(out["updated_at"])
    out["kind"] = kind
    out["status"] = code
    out["status_label"] = status_label(code)
    out["requires_approval"] = is_p0(out)
    return out


def ensure_generated_items(record: dict) -> None:
    """JSON 后端：把生成的登记项/行动项写入本地状态，不覆盖已有状态。"""
    from erm_store import using_postgres
    if using_postgres():
        return
    assessment = record.get("assessment") or record
    company = record.get("company_name") or assessment.get("company_name") or ""
    plans = assessment.get("action_plans") or {}
    items = plans.get("action_items") if isinstance(plans, dict) else plans
    deep = assessment.get("deep_analysis") or (assessment.get("analytics") or {}).get("deep_analysis") or {}
    register = (deep.get("risk_register") or []) if isinstance(deep, dict) else []
    st = _load_json_state()
    for plan in items or []:
        if not isinstance(plan, dict) or not plan.get("id"):
            continue
        prev = (st["actions"] or {}).get(plan["id"]) or {}
        st["actions"][plan["id"]] = {
            **prev,
            "id": plan["id"],
            "company_name": company,
            "title": plan.get("title"),
            "owner": prev.get("owner") or plan.get("owner"),
            "due_date": prev.get("due_date") or (str(plan.get("timeline_days")) + "天" if plan.get("timeline_days") else ""),
            "priority": plan.get("priority"),
            "dimension": plan.get("dimension"),
            "status": prev.get("status") or "open",
            "kind": "action",
        }
    for row in register:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        prev = (st["register"] or {}).get(row["id"]) or {}
        rating = row.get("risk_rating") or row.get("level") or ""
        st["register"][row["id"]] = {
            **prev,
            "id": row["id"],
            "company_name": company,
            "dimension": row.get("dimension"),
            "title": row.get("risk_description") or row.get("dimension"),
            "priority": "P0" if rating in HIGH_RATING else "P1",
            "risk_rating": rating,
            "owner": prev.get("owner") or row.get("owner"),
            "status": prev.get("status") or "identified",
            "kind": "register",
        }
    _save_json_state(st)


def apply_status(
    *,
    kind: str,
    item_id: str,
    company_name: str,
    status: str,
    user,
    reason: str = "",
    review_date: str = "",
    owner: str = "",
    due_date: str = "",
    priority: str = "",
    risk_rating: str = "",
) -> dict:
    from erm_store import audit, patch_action, patch_register, using_postgres

    kind = "action" if kind == "action" else "register"
    target = normalize_status(status, kind=kind)
    item = _find_item(kind, item_id, company_name)
    if not item:
        item = {
            "id": item_id, "company_name": company_name, "kind": kind,
            "priority": priority, "risk_rating": risk_rating, "status": "open",
        }
    else:
        item["priority"] = item.get("priority") or priority
        item["risk_rating"] = item.get("risk_rating") or risk_rating
    item["kind"] = kind
    err = validate_transition(item, target, user, reason, review_date)
    if err:
        raise PermissionError(err)

    username, role = _actor_role(user)
    fields: Dict[str, Any] = {"status": target, "company_name": company_name}
    if priority:
        fields["priority"] = priority
    if risk_rating:
        fields["risk_rating"] = risk_rating
    if owner:
        fields["owner"] = owner
    if due_date:
        fields["due_date"] = due_date
    if requires_approval(item, target):
        fields["acceptance_reason"] = reason.strip()
        fields["review_date"] = review_date.strip()
        fields["approver"] = username
    elif reason:
        fields["acceptance_reason"] = reason.strip()

    if using_postgres():
        row = patch_action(item_id, fields) if kind == "action" else patch_register(item_id, fields)
        if not row:
            # 尚未随评估落库时先插一条最小记录
            _insert_stub(kind, item_id, company_name, fields)
            row = patch_action(item_id, fields) if kind == "action" else patch_register(item_id, fields)
        audit(
            "workflow.status",
            "action_item" if kind == "action" else "risk_register_item",
            item_id,
            {"status": target, "approver": fields.get("approver"), "role": role},
        )
        return _public_row(row or fields, kind)

    st = _load_json_state()
    bucket = st["actions" if kind == "action" else "register"]
    prev = bucket.get(item_id) or {"id": item_id, "company_name": company_name, "kind": kind}
    prev.update(fields)
    prev["updated_at"] = datetime.now(timezone.utc).isoformat()
    if fields.get("approver"):
        prev["approved_at"] = prev["updated_at"]
    bucket[item_id] = prev
    _save_json_state(st)
    return _public_row(prev, kind)


def _insert_stub(kind: str, item_id: str, company: str, fields: dict) -> None:
    from erm_store import using_postgres, _connect
    if not using_postgres():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            if kind == "action":
                cur.execute(
                    """
                    INSERT INTO action_item (id, company_name, title, status, priority)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (item_id, company, fields.get("title") or item_id, "open", fields.get("priority") or ""),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO risk_register_item (id, company_name, title, status, priority)
                    VALUES (%s,%s,%s,'identified',%s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (item_id, company, fields.get("title") or item_id, fields.get("priority") or "P1"),
                )


def _find_item(kind: str, item_id: str, company: str) -> Optional[dict]:
    reg, acts = _rows_for_company(company)
    pool = acts if kind == "action" else reg
    for row in pool:
        if row.get("id") == item_id:
            row = dict(row)
            row["kind"] = kind
            return row
    return None


def overlay_workflow(payload: dict) -> dict:
    if not payload:
        return payload
    company = payload.get("company_name") or ""
    if not company:
        return payload
    snap = snapshot(company)
    act_map = {a["id"]: a for a in snap["actions"]}
    reg_map = {r["id"]: r for r in snap["register"]}
    plans = payload.get("action_plans") or {}
    for a in (plans.get("action_items") or []) if isinstance(plans, dict) else []:
        st = act_map.get(a.get("id"))
        if st:
            a["status"] = st.get("status")
            a["status_label"] = st.get("status_label")
            a["owner"] = st.get("owner") or a.get("owner")
            a["due_date"] = st.get("due_date") or a.get("due_date")
            a["approver"] = st.get("approver")
            a["acceptance_reason"] = st.get("acceptance_reason")
            a["review_date"] = st.get("review_date")
            a["requires_approval"] = st.get("requires_approval")
    deep = payload.get("deep_analysis") or (payload.get("analytics") or {}).get("deep_analysis") or {}
    if isinstance(deep, dict):
        for r in deep.get("risk_register") or []:
            st = reg_map.get(r.get("id"))
            if st:
                r["workflow_status"] = st.get("status")
                r["workflow_status_label"] = st.get("status_label")
                r["owner"] = st.get("owner") or r.get("owner")
                r["approver"] = st.get("approver")
                r["acceptance_reason"] = st.get("acceptance_reason")
                r["review_date"] = st.get("review_date")
                r["requires_approval"] = st.get("requires_approval")
            else:
                r["workflow_status"] = "identified"
                r["workflow_status_label"] = "识别"
                r["requires_approval"] = is_p0({"priority": "P0" if str(r.get("risk_rating") or "") in HIGH_RATING else "P1", "risk_rating": r.get("risk_rating")})
    stats = completion_stats(company, (payload.get("action_plans") or {}).get("action_items") if isinstance(payload.get("action_plans"), dict) else None)
    cl = payload.get("closed_loop") or (payload.get("analytics") or {}).get("closed_loop") or {}
    v = cl.get("remediation_verification") or {}
    tracked = v.get("actions_tracked") or {}
    tracked.update({
        "total": stats["total"] or tracked.get("total") or 0,
        "completed": stats["completed"],
        "completion_pct": stats["completion_pct"],
        "source": "persisted",
        "p0_closed": stats["p0_closed"],
        "p0_total": stats["p0_total"],
        "register_closed": stats["register_closed"],
        "register_total": stats["register_total"],
    })
    v["actions_tracked"] = tracked
    cl["remediation_verification"] = v
    cl["workflow"] = stats
    payload["closed_loop"] = cl
    if payload.get("analytics"):
        payload["analytics"]["closed_loop"] = cl
    payload["workflow"] = stats
    try:
        from risk_timeseries import analyze_timeseries
        ts = analyze_timeseries(company)
        cl["timeseries"] = ts
        payload["closed_loop"] = cl
        if payload.get("analytics"):
            payload["analytics"]["closed_loop"] = cl
    except Exception:
        pass
    return payload
