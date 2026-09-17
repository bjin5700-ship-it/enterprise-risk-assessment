# -*- coding: utf-8 -*-
"""Multi-period risk timeline, diff, and change matrix (ISO 31000 dynamic ERM)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:19])
    except (ValueError, TypeError):
        return None


def _assessment_from_record(rec: dict) -> dict:
    if not rec:
        return {}
    return rec.get("assessment") if isinstance(rec.get("assessment"), dict) else rec


def _snapshot_from_assessment(assessment: dict, meta: Optional[dict] = None) -> dict:
    meta = meta or {}
    dims = {}
    for d in assessment.get("dimensions") or []:
        name = d.get("name")
        if name:
            dims[name] = {
                "score": d.get("score"),
                "level": d.get("level"),
            }
    return {
        "history_id": meta.get("id") or assessment.get("history_id"),
        "company_name": assessment.get("company_name") or meta.get("company_name"),
        "assessed_at": assessment.get("assessed_at") or meta.get("assessed_at"),
        "report_date": assessment.get("report_date"),
        "note": meta.get("note") or "",
        "overall_score": assessment.get("overall_score"),
        "overall_level": assessment.get("overall_level"),
        "completion_pct": (assessment.get("form_stats") or {}).get("completion_pct"),
        "dimensions": dims,
        "event_tags": _event_tags(assessment, meta.get("note") or ""),
    }


def _event_tags(assessment: dict, note: str) -> List[str]:
    tags: List[str] = []
    n = (note or "").strip()
    if n:
        tags.append(n[:80])
    for w in (assessment.get("warnings") or [])[:3]:
        tags.append(str(w)[:80])
    cl = (assessment.get("closed_loop") or {}) if isinstance(assessment.get("closed_loop"), dict) else {}
    trig = cl.get("reassessment_trigger")
    if trig:
        tags.append(f"复评触发: {str(trig)[:60]}")
    for a in (assessment.get("alerts") or {}).get("alerts", [])[:2]:
        if isinstance(a, dict) and a.get("title"):
            tags.append(str(a["title"])[:60])
    return tags[:5]


def build_company_timeline(history: List[dict], company_name: str, *, limit: int = 12) -> dict:
    name = (company_name or "").strip()
    if not name:
        return {"company_name": "", "snapshots": [], "matrix": None, "message": "缺少企业名称"}

    rows: List[dict] = []
    for rec in history or []:
        a = _assessment_from_record(rec)
        if (a.get("company_name") or rec.get("company_name") or "").strip() != name:
            continue
        snap = _snapshot_from_assessment(a, rec)
        if snap.get("overall_score") is None:
            continue
        rows.append(snap)

    rows.sort(key=lambda r: _parse_dt(r.get("assessed_at")) or datetime.min, reverse=True)
    rows = rows[:limit]
    rows.reverse()  # chronological for matrix columns

    return {
        "company_name": name,
        "snapshots": rows,
        "matrix": build_change_matrix(rows) if len(rows) >= 1 else None,
        "period_count": len(rows),
        "message": "需至少两次评估以观察趋势" if len(rows) < 2 else None,
    }


def build_change_matrix(snapshots: List[dict]) -> dict:
    if not snapshots:
        return {"columns": [], "rows": []}

    columns = []
    for s in snapshots:
        columns.append(
            {
                "history_id": s.get("history_id"),
                "assessed_at": (s.get("assessed_at") or "")[:10],
                "overall_score": s.get("overall_score"),
                "overall_level": s.get("overall_level"),
                "events": s.get("event_tags") or [],
            }
        )

    dim_names = set()
    for s in snapshots:
        dim_names.update((s.get("dimensions") or {}).keys())
    dim_names = sorted(dim_names, key=lambda n: n)

    matrix_rows = []
    for dim in dim_names:
        cells = []
        prev_score = None
        for s in snapshots:
            cell = (s.get("dimensions") or {}).get(dim) or {}
            score = cell.get("score")
            delta = None
            if score is not None and prev_score is not None:
                delta = round(float(score) - float(prev_score), 2)
            cells.append(
                {
                    "score": score,
                    "level": cell.get("level"),
                    "delta_from_prev": delta,
                }
            )
            if score is not None:
                prev_score = score
        matrix_rows.append({"dimension": dim, "cells": cells})

    overall_cells = []
    prev_o = None
    for s in snapshots:
        o = s.get("overall_score")
        delta = None
        if o is not None and prev_o is not None:
            delta = round(float(o) - float(prev_o), 2)
        overall_cells.append({"score": o, "level": s.get("overall_level"), "delta_from_prev": delta})
        if o is not None:
            prev_o = o

    return {
        "columns": columns,
        "rows": matrix_rows,
        "overall_row": {"dimension": "综合评分", "cells": overall_cells},
    }


def diff_two_assessments(current: dict, prior: dict) -> dict:
    """Compare two full assessment payloads (newer vs older)."""
    if not prior:
        return {"has_prior": False, "message": "无历史可比评估"}
    cur_dims = {d["name"]: d for d in (current.get("dimensions") or []) if d.get("name")}
    pri_dims = {d["name"]: d for d in (prior.get("dimensions") or []) if d.get("name")}
    changes = []
    for name in sorted(set(cur_dims) | set(pri_dims)):
        c = cur_dims.get(name, {})
        p = pri_dims.get(name, {})
        cs, ps = c.get("score"), p.get("score")
        if cs is None and ps is None:
            continue
        delta = round(float(cs or 0) - float(ps or 0), 2) if cs is not None and ps is not None else None
        changes.append(
            {
                "dimension": name,
                "prior_score": ps,
                "current_score": cs,
                "prior_level": p.get("level"),
                "current_level": c.get("level"),
                "delta": delta,
                "direction": "up" if delta and delta > 0.05 else "down" if delta and delta < -0.05 else "flat",
            }
        )
    changes.sort(key=lambda x: abs(x.get("delta") or 0), reverse=True)

    o_delta = None
    if current.get("overall_score") is not None and prior.get("overall_score") is not None:
        o_delta = round(float(current["overall_score"]) - float(prior["overall_score"]), 2)

    return {
        "has_prior": True,
        "prior_assessed_at": prior.get("assessed_at"),
        "current_assessed_at": current.get("assessed_at"),
        "prior_overall": prior.get("overall_score"),
        "current_overall": current.get("overall_score"),
        "overall_delta": o_delta,
        "prior_level": prior.get("overall_level"),
        "current_level": current.get("overall_level"),
        "dimension_changes": changes[:24],
        "notable_events": list(
            dict.fromkeys(
                (_event_tags(current, "") + _event_tags(prior, ""))[:8]
            )
        ),
    }
