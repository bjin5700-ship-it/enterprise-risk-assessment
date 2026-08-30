# -*- coding: utf-8 -*-
"""数据闭环 — KRI 告警、整改验证、复评触发"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult

DEFAULT_TRACKING_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "action_tracking.json"
)
DEFAULT_HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "history.json"
)


def load_action_tracking(path: str = None) -> dict:
    path = path or DEFAULT_TRACKING_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_action_tracking(db: dict, path: str = None) -> None:
    path = path or DEFAULT_TRACKING_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _company_key(name: str) -> str:
    return (name or "未命名企业").strip()


def get_action_status(company_name: str, path: str = None) -> dict:
    try:
        from risk_workflow import action_tracking_map
        mapped = action_tracking_map(company_name)
        if mapped.get("actions"):
            return mapped
    except Exception:
        pass
    db = load_action_tracking(path)
    return db.get(_company_key(company_name), {})


def update_action_status(
    company_name: str,
    action_id: str,
    status: str,
    note: str = "",
    path: str = None,
) -> dict:
    db = load_action_tracking(path)
    key = _company_key(company_name)
    co = db.setdefault(key, {"company_name": company_name, "actions": {}})
    co["actions"][action_id] = {
        "status": status,
        "note": note,
        "updated_at": datetime.now().isoformat(),
    }
    save_action_tracking(db, path)
    return co["actions"][action_id]


def build_kri_alerts(
    kri_dashboard: dict = None,
    reassessment: dict = None,
    timeseries_analysis: dict = None,
) -> dict:
    alerts: List[dict] = []
    kri_dashboard = kri_dashboard or {}
    reassessment = reassessment or {}
    timeseries_analysis = timeseries_analysis or {}

    for k in kri_dashboard.get("kris") or []:
        if k.get("status") == "red":
            alerts.append({
                "id": f"KRI-{k.get('name', '')[:8]}",
                "type": "kri_critical",
                "severity": "critical",
                "title": f"KRI 告警：{k.get('name')}",
                "message": f"当前值 {k.get('value')}{k.get('unit', '')}，目标 {k.get('target')}，关联 {k.get('dimension')}",
                "suggested_action": "立即启动专项整改并在 7 天内复评 KRI",
            })
        elif k.get("status") == "amber":
            alerts.append({
                "id": f"KRI-{k.get('name', '')[:8]}-A",
                "type": "kri_warning",
                "severity": "high",
                "title": f"KRI 预警：{k.get('name')}",
                "message": f"接近阈值，当前 {k.get('value')}{k.get('unit', '')}，目标 {k.get('target')}",
                "suggested_action": "纳入月度 KRI 监控并制定预防行动",
            })

    if reassessment.get("overdue"):
        alerts.insert(0, {
            "id": "REASSESS-OVERDUE",
            "type": "reassessment_overdue",
            "severity": "critical",
            "title": "评估已逾期",
            "message": reassessment.get("message", "请立即复评"),
            "suggested_action": "完成全量复评并更新风险登记册",
        })
    elif reassessment.get("urgency") in ("high", "critical"):
        alerts.append({
            "id": "REASSESS-DUE",
            "type": "reassessment_due",
            "severity": "high",
            "title": "复评即将到期",
            "message": reassessment.get("message", ""),
            "suggested_action": f"建议在 {reassessment.get('next_due_date')} 前完成复评",
        })

    for kpi_name in (timeseries_analysis.get("worsening_kpis") or [])[:3]:
        alerts.append({
            "id": f"TREND-{kpi_name[:6]}",
            "type": "kpi_trend_worsening",
            "severity": "medium",
            "title": f"KPI 趋势恶化：{kpi_name}",
            "message": f"历史快照显示 {kpi_name} 呈不利变化",
            "suggested_action": "复核相关维度控制措施有效性",
        })

    if (kri_dashboard.get("health_score") or 100) < 60:
        alerts.append({
            "id": "KRI-HEALTH-LOW",
            "type": "kpi_health",
            "severity": "high",
            "title": "KRI 健康度偏低",
            "message": f"综合 KRI 健康度 {kri_dashboard.get('health_score')}%，多项指标需关注",
            "suggested_action": "召开风险委员会专项审查 KRI 阈值",
        })

    critical = sum(1 for a in alerts if a["severity"] == "critical")
    high = sum(1 for a in alerts if a["severity"] == "high")

    return {
        "alerts": alerts[:20],
        "critical_count": critical,
        "high_count": high,
        "total_count": len(alerts),
        "requires_reassessment": critical > 0 or reassessment.get("overdue") or high >= 3,
        "summary": f"共 {len(alerts)} 条告警（严重 {critical} · 高 {high}）",
        "generated_at": datetime.now().isoformat(),
    }


def verify_remediation(
    result: AssessmentResult,
    prior_assessment: dict = None,
    action_plans: dict = None,
    action_tracking: dict = None,
    bayesian_update: dict = None,
) -> dict:
    action_plans = action_plans or {}
    action_tracking = (action_tracking or {}).get("actions") or {}
    items = action_plans.get("action_items") or []

    tracked_total = len(items)
    completed = [
        a for a in items
        if action_tracking.get(a.get("id"), {}).get("status") in ("completed", "done", "已完成")
    ]
    completion_pct = round(len(completed) / tracked_total * 100, 1) if tracked_total else 0

    if not prior_assessment:
        return {
            "has_prior": False,
            "verification": "待验证",
            "verification_label": "首次评估基线",
            "message": "完成首次评估。实施整改行动后标记完成状态，下次复评将自动验证效果。",
            "actions_tracked": {
                "total": tracked_total,
                "completed": len(completed),
                "completion_pct": completion_pct,
            },
            "dimension_changes": [],
            "overall_delta": 0,
            "recommendation": "保存评估至档案，90 天内复评以建立闭环",
        }

    prior_score = float(prior_assessment.get("overall_score", result.overall_score))
    overall_delta = round(result.overall_score - prior_score, 3)
    prior_dims = {d["name"]: d["score"] for d in prior_assessment.get("dimensions", [])}

    dim_changes = []
    improved = worsened = 0
    for dim in sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True):
        ps = prior_dims.get(dim.name)
        if ps is None:
            continue
        delta = round(dim.score - ps, 3)
        if delta < -0.08:
            improved += 1
            trend = "改善"
        elif delta > 0.08:
            worsened += 1
            trend = "恶化"
        else:
            trend = "稳定"
        dim_changes.append({
            "dimension": dim.name,
            "prior": ps,
            "current": dim.score,
            "delta": delta,
            "trend": trend,
            "target_score": max(1.0, round(ps - 0.5, 2)),
            "met_target": dim.score <= max(1.0, ps - 0.3),
        })

    # 整改验证逻辑
    if overall_delta <= -0.15 and improved >= 1:
        verification = "有效"
        verification_label = "整改有效"
    elif overall_delta <= -0.05 or improved >= 2:
        verification = "部分有效"
        verification_label = "部分改善"
    elif overall_delta > 0.1 or worsened >= 2:
        verification = "无效"
        verification_label = "风险上升"
    elif completion_pct >= 50 and len(completed) > 0:
        verification = "待复评"
        verification_label = "行动进行中"
    else:
        verification = "待验证"
        verification_label = "待验证"

    bayes = bayesian_update or {}
    calibration = None
    if bayes.get("has_prior"):
        predicted = bayes.get("posterior_overall")
        actual = result.overall_score
        if predicted is not None:
            calibration = {
                "predicted_posterior": predicted,
                "actual_observation": actual,
                "prediction_error": round(abs(actual - predicted), 3),
                "note": "误差较小表示模型校准良好" if abs(actual - predicted) < 0.2 else "建议补充数据后重新校准",
            }

    rec_parts = []
    if verification == "有效":
        rec_parts.append("整改成效显著，建议将有效措施标准化并降低复评频次。")
    elif verification == "无效":
        rec_parts.append("风险未降反升，建议董事会审议并升级 P0 行动。")
    elif completion_pct < 30:
        rec_parts.append(f"行动完成率仅 {completion_pct}%，请在解决方案页标记已完成项。")
    else:
        rec_parts.append("继续推进未完成行动，并在下一复评周期验证。")
    if worsened:
        rec_parts.append(f"有 {worsened} 个维度恶化，需专项分析根因。")

    return {
        "has_prior": True,
        "prior_date": prior_assessment.get("assessed_at") or prior_assessment.get("report_date"),
        "overall_delta": overall_delta,
        "overall_trend": "改善" if overall_delta < -0.05 else "恶化" if overall_delta > 0.05 else "稳定",
        "improved_count": improved,
        "worsened_count": worsened,
        "dimension_changes": dim_changes[:12],
        "actions_tracked": {
            "total": tracked_total,
            "completed": len(completed),
            "completion_pct": completion_pct,
            "completed_ids": [a.get("id") for a in completed[:10]],
        },
        "verification": verification,
        "verification_label": verification_label,
        "model_calibration": calibration,
        "recommendation": "".join(rec_parts),
        "closed_loop_status": "closed" if verification == "有效" else "open",
    }


def load_history_records(path: str = None) -> list:
    try:
        from erm_store import load_history
        return load_history()
    except Exception:
        pass
    path = path or DEFAULT_HISTORY_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def build_export_closed_loop(result: AssessmentResult) -> dict:
    """供 Word/PDF 导出使用的闭环数据（不写入 KPI 快照）。"""
    from action_planner import build_action_plans
    from risk_analytics import enrich_assessment_full
    from risk_bayesian import find_prior_assessment

    basic = (result.all_raw_data or {}).get("企业基本信息", {})
    prior = find_prior_assessment(load_history_records(), result.company_name)
    plans = build_action_plans(result)
    full = enrich_assessment_full(
        result, None, basic,
        prior_assessment=prior, action_plans=plans, record_snapshot=False,
    )
    return {"closed_loop": full.get("closed_loop"), "alerts": full.get("alerts")}


def build_closed_loop_package(
    result: AssessmentResult,
    analytics: dict,
    prior_assessment: dict = None,
    action_plans: dict = None,
    timeseries_path: str = None,
    tracking_path: str = None,
    record_snapshot: bool = True,
) -> dict:
    from risk_timeseries import analyze_timeseries, record_assessment_snapshot

    form_data = result.all_raw_data or {}
    snapshot = (
        record_assessment_snapshot(result, form_data, path=timeseries_path)
        if record_snapshot else {"id": None, "assessed_at": datetime.now().isoformat()}
    )
    ts_analysis = analyze_timeseries(result.company_name, timeseries_path)
    tracking = get_action_status(result.company_name, tracking_path)

    alerts = build_kri_alerts(
        analytics.get("kri_dashboard"),
        analytics.get("reassessment"),
        ts_analysis,
    )
    verification = verify_remediation(
        result,
        prior_assessment,
        action_plans,
        tracking,
        analytics.get("bayesian_update"),
    )

    stat_corr = ts_analysis.get("statistical_correlation")
    heuristic_corr = (analytics.get("deep_analysis") or {}).get("correlation_matrix")
    correlation_source = "historical_pearson" if stat_corr else "heuristic"

    return {
        "alerts": alerts,
        "remediation_verification": verification,
        "timeseries": ts_analysis,
        "latest_snapshot_id": snapshot.get("id"),
        "action_tracking_summary": {
            "company": result.company_name,
            "tracked_actions": len(tracking.get("actions") or {}),
        },
        "correlation_source": correlation_source,
        "enhanced_correlation": stat_corr or heuristic_corr,
        "reassessment_trigger": alerts.get("requires_reassessment", False),
        "summary": _closed_loop_summary(alerts, verification, ts_analysis),
    }


def _closed_loop_summary(alerts: dict, verification: dict, ts: dict) -> str:
    parts = [alerts.get("summary", "")]
    if verification.get("has_prior"):
        parts.append(
            f"整改验证：{verification.get('verification_label')}（Δ评分 {verification.get('overall_delta'):+.2f}）。"
        )
    if ts.get("has_trend"):
        parts.append(ts.get("message", ""))
    return "".join(p for p in parts if p)


def format_closed_loop_for_report(cl: dict = None, alerts: dict = None) -> dict:
    """导出报告（HTML/MD/Word/PDF）共用的闭环章节结构。"""
    cl = cl or {}
    alerts = alerts or {}
    v = cl.get("remediation_verification") or {}
    ts = cl.get("timeseries") or {}
    alert_items = [
        {
            "severity": a.get("severity", ""),
            "title": a.get("title", ""),
            "message": a.get("message", ""),
            "action": a.get("suggested_action", ""),
        }
        for a in (alerts.get("alerts") or [])[:8]
    ]
    return {
        "show": bool(alert_items or v or ts.get("has_trend") or cl.get("summary")),
        "alert_summary": alerts.get("summary", ""),
        "alert_items": alert_items,
        "verification_label": v.get("verification_label") or v.get("verification") or "",
        "overall_delta": v.get("overall_delta"),
        "overall_trend": v.get("overall_trend", ""),
        "completion_pct": (v.get("actions_tracked") or {}).get("completion_pct", 0),
        "actions_completed": (v.get("actions_tracked") or {}).get("completed", 0),
        "actions_total": (v.get("actions_tracked") or {}).get("total", 0),
        "recommendation": v.get("recommendation", ""),
        "timeseries_message": ts.get("message", "") if ts.get("has_trend") else "",
        "timeseries_period": ts.get("period", ""),
        "snapshot_count": ts.get("snapshot_count", 0),
        "summary": cl.get("summary", ""),
        "dim_changes": (v.get("dimension_changes") or [])[:8],
    }

