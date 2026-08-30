# -*- coding: utf-8 -*-
"""Phase C — 关键风险指标 KRI 与复评提醒"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from risk_config import KRI_CRITICAL_THRESHOLD, KRI_WARNING_THRESHOLD, get_reassessment_interval_days
from risk_engine import AssessmentResult, _sf, _ss


# 表单字段 → KRI 定义
KRI_FIELD_MAP = [
    ("财务风险", "资产负债率(%)", "资产负债率", "%", "≤65", "lower"),
    ("财务风险", "流动比率", "流动比率", "", "≥1.5", "higher"),
    ("财务风险", "净利率(%)", "净利率", "%", "≥5", "higher"),
    ("经营风险", "前五大客户收入占比(%)", "客户集中度", "%", "≤50", "lower"),
    ("经营风险", "应收账款周转天数", "应收周转天数", "天", "≤90", "lower"),
    ("供应链风险", "最大单一供应商占比(%)", "供应商集中度", "%", "≤30", "lower"),
    ("安全生产风险", "近三年工伤事故次数", "工伤事故", "次", "0", "lower"),
    ("环境风险", "排放达标率(%)", "排放达标率", "%", "100", "higher"),
    ("法律合规风险", "在审案件数量", "在审诉讼", "件", "0", "lower"),
    ("法律合规风险", "近3年重大行政处罚次数", "重大处罚", "次", "0", "lower"),
    ("技术与信息安全风险", "近12个月信息安全事件数", "安全事件", "次", "0", "lower"),
    ("人力资源风险", "核心人才流失率(%)", "核心流失率", "%", "≤10", "lower"),
    ("信用风险", "坏账率(%)", "坏账率", "%", "≤2", "lower"),
    ("数据隐私合规风险", "近3年数据泄露事件数", "数据泄露", "次", "0", "lower"),
    ("业务连续性风险", "BC演练频次(次/年)", "BC演练", "次/年", "≥2", "higher"),
]


def _kri_status(value: Optional[float], direction: str, warn_score_dim: float = None) -> str:
    if warn_score_dim is not None:
        if warn_score_dim >= KRI_CRITICAL_THRESHOLD:
            return "red"
        if warn_score_dim >= KRI_WARNING_THRESHOLD:
            return "amber"
        return "green"
    if value is None:
        return "grey"
    return "green"


def build_kri_dashboard(result: AssessmentResult, form_data: dict = None) -> dict:
    form_data = form_data or result.all_raw_data or {}
    dim_map = {d.name: d.score for d in result.dimensions.values()}
    kris: List[dict] = []

    for sheet, field, name, unit, target, direction in KRI_FIELD_MAP:
        raw = (form_data.get(sheet) or {}).get(field)
        val = _sf(raw)
        dim_name = _sheet_to_dim(sheet)
        dim_score = dim_map.get(dim_name, 1.0)

        status = "grey"
        if val is not None:
            status = _evaluate_kri_value(val, direction, field)
        elif dim_score >= KRI_WARNING_THRESHOLD:
            status = "amber" if dim_score < KRI_CRITICAL_THRESHOLD else "red"

        kris.append({
            "name": name,
            "field": field,
            "sheet": sheet,
            "dimension": dim_name,
            "value": val if val is not None else raw,
            "unit": unit,
            "target": target,
            "status": status,
            "status_label": {"green": "正常", "amber": "预警", "red": "告警", "grey": "未填报"}[status],
            "linked_dim_score": round(dim_score, 2),
        })

    # 维度级 KRI（无具体字段时）
    for dim in result.dimensions.values():
        if dim.score >= KRI_WARNING_THRESHOLD:
            kris.append({
                "name": f"{dim.name}综合指数",
                "field": None,
                "sheet": None,
                "dimension": dim.name,
                "value": dim.score,
                "unit": "分",
                "target": "<2.5",
                "status": "red" if dim.score >= KRI_CRITICAL_THRESHOLD else "amber",
                "status_label": "告警" if dim.score >= KRI_CRITICAL_THRESHOLD else "预警",
                "linked_dim_score": dim.score,
            })

    counts = {"green": 0, "amber": 0, "red": 0, "grey": 0}
    for k in kris:
        counts[k["status"]] = counts.get(k["status"], 0) + 1

    filled = counts["green"] + counts["amber"] + counts["red"]
    if filled == 0:
        health = None
        health_label = "未填报，不计算健康度"
    else:
        health = round(max(0, 100 - counts["red"] * 15 - counts["amber"] * 5 - counts["grey"] * 2), 1)
        health_label = "已填报"

    return {
        "kris": kris[:30],
        "summary": counts,
        "health_score": health,
        "health_label": health_label,
        "updated_at": datetime.now().isoformat(),
    }


def _evaluate_kri_value(val: float, direction: str, field: str) -> str:
    rules = {
        "资产负债率(%)": [(80, "red"), (65, "amber")],
        "流动比率": [(0.8, "red"), (1.2, "amber")],
        "净利率(%)": [(-999, "red"), (3, "amber")],
        "前五大客户收入占比(%)": [(60, "red"), (50, "amber")],
        "应收账款周转天数": [(120, "red"), (90, "amber")],
        "最大单一供应商占比(%)": [(40, "red"), (30, "amber")],
        "近三年工伤事故次数": [(3, "red"), (1, "amber")],
        "排放达标率(%)": [(95, "red"), (100, "amber")],
        "在审案件数量": [(3, "red"), (1, "amber")],
        "近3年重大行政处罚次数": [(1, "red"), (0, "amber")],
        "近12个月信息安全事件数": [(2, "red"), (1, "amber")],
        "核心人才流失率(%)": [(20, "red"), (10, "amber")],
        "坏账率(%)": [(5, "red"), (2, "amber")],
        "近3年数据泄露事件数": [(1, "red"), (0, "amber")],
        "BC演练频次(次/年)": [(0, "red"), (1, "amber")],
    }
    if field not in rules:
        return "green"
    for threshold, status in rules[field]:
        if direction == "lower" and val >= threshold:
            return status
        if direction == "higher":
            if field == "排放达标率(%)":
                if val < threshold:
                    return status
            elif field == "流动比率":
                if val <= threshold:
                    return status
            elif field == "净利率(%)":
                if val < 3:
                    return "amber" if val >= 0 else "red"
            elif field == "BC演练频次(次/年)":
                if val <= threshold:
                    return status
    return "green"


def _sheet_to_dim(sheet: str) -> str:
    mapping = {
        "法律合规风险": "法律与合规风险",
        "技术风险": "技术与信息安全风险",
        "行业政策风险": "行业与市场风险",
    }
    return mapping.get(sheet, sheet.replace("风险", "风险") if "风险" in sheet else sheet)


def build_reassessment_reminder(assessed_at: str = None, basic: dict = None) -> dict:
    basic = basic or {}
    interval = get_reassessment_interval_days(basic)
    now = datetime.now()

    if assessed_at:
        try:
            last = datetime.fromisoformat(assessed_at.replace("Z", "+00:00")[:19])
        except ValueError:
            last = now
    else:
        last = now

    next_due = last + timedelta(days=interval)
    days_left = (next_due - now).days
    overdue = days_left < 0

    if overdue:
        urgency, message = "critical", f"评估已逾期 {abs(days_left)} 天，请立即复评"
    elif days_left <= 14:
        urgency, message = "high", f"距下次复评仅剩 {days_left} 天"
    elif days_left <= 30:
        urgency, message = "medium", f"建议在 {days_left} 天内完成季度复评"
    else:
        urgency, message = "low", f"下次复评日期：{next_due.strftime('%Y-%m-%d')}"

    return {
        "last_assessed_at": last.isoformat(),
        "next_due_date": next_due.strftime("%Y-%m-%d"),
        "interval_days": interval,
        "days_until_due": days_left,
        "overdue": overdue,
        "urgency": urgency,
        "message": message,
        "auto_reminder": True,
    }
