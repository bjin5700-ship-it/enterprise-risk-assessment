# -*- coding: utf-8 -*-
"""
贝叶斯风险更新 — ISO 31010 不确定性量化
将历史评估作为先验，新填报数据作为观测，更新各维度后验评分
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:19])
    except (ValueError, TypeError):
        return None


def find_prior_assessment(history: List[dict], company_name: str) -> Optional[dict]:
    """从历史档案中取同企业最近一次评估（作为先验）"""
    name = (company_name or "").strip()
    if not name or not history:
        return None
    for rec in history:
        if (rec.get("company_name") or "").strip() == name:
            return rec.get("assessment") or rec
    return None


def _data_weight(form_stats: Optional[dict]) -> float:
    """观测数据权重：完成度越高，新数据越可信"""
    pct = (form_stats or {}).get("completion_pct", 50)
    key_pct = (form_stats or {}).get("key_completion_pct", pct)
    blended = pct * 0.55 + key_pct * 0.45
    return min(0.88, max(0.25, 0.25 + blended / 100 * 0.63))


def _prior_weight(data_w: float, days_since_prior: Optional[int]) -> float:
    """先验权重：距上次评估越近，先验保留越多"""
    if days_since_prior is None:
        return 1.0 - data_w
    decay = min(0.35, days_since_prior / 365 * 0.35)
    return max(0.12, (1.0 - data_w) - decay)


def run_bayesian_update(
    result: AssessmentResult,
    prior_assessment: Optional[dict] = None,
    form_stats: Optional[dict] = None,
) -> dict:
    """
    对综合评分与各维度评分做共轭高斯近似贝叶斯更新。
    posterior = w_prior * prior + w_obs * observation
    """
    current = result.overall_score
    data_w = _data_weight(form_stats)

    if not prior_assessment:
        dims = [
            {
                "dimension": d.name,
                "prior": d.score,
                "observation": d.score,
                "posterior": d.score,
                "delta": 0.0,
                "trend": "初评",
                "confidence": "—",
            }
            for d in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True)
        ]
        return {
            "has_prior": False,
            "prior_date": None,
            "days_since_prior": None,
            "prior_overall": current,
            "observation_overall": current,
            "posterior_overall": current,
            "overall_delta": 0.0,
            "overall_trend": "初评",
            "data_weight_pct": round(data_w * 100, 1),
            "dimension_updates": dims,
            "significant_changes": [],
            "interpretation": "暂无历史评估作为先验。完成首次评估后，下次复评将自动进行贝叶斯更新。",
            "methodology": "ISO 31010 贝叶斯更新 · 高斯共轭近似",
        }

    prior_date = prior_assessment.get("assessed_at") or prior_assessment.get("report_date")
    prior_dt = _parse_dt(prior_assessment.get("assessed_at"))
    days = None
    if prior_dt:
        days = max(0, (datetime.now() - prior_dt.replace(tzinfo=None)).days)

    prior_w = _prior_weight(data_w, days)
    obs_w = 1.0 - prior_w

    prior_overall = float(prior_assessment.get("overall_score", current))
    posterior_overall = round(prior_overall * prior_w + current * obs_w, 3)
    overall_delta = round(posterior_overall - prior_overall, 3)

    if overall_delta > 0.08:
        overall_trend = "风险上升"
    elif overall_delta < -0.08:
        overall_trend = "风险下降"
    else:
        overall_trend = "基本稳定"

    prior_dims = {d["name"]: d["score"] for d in prior_assessment.get("dimensions", [])}
    dimension_updates = []
    significant = []

    for dim in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True):
        prior_s = prior_dims.get(dim.name)
        if prior_s is None:
            posterior = dim.score
            delta = 0.0
            trend = "新增维度"
        else:
            posterior = round(float(prior_s) * prior_w + dim.score * obs_w, 3)
            delta = round(posterior - float(prior_s), 3)
            if delta > 0.1:
                trend = "上升"
            elif delta < -0.1:
                trend = "下降"
            else:
                trend = "稳定"

        conf = "高" if abs(delta) >= 0.15 else "中" if abs(delta) >= 0.05 else "低"
        row = {
            "dimension": dim.name,
            "prior": round(float(prior_s), 2) if prior_s is not None else dim.score,
            "observation": dim.score,
            "posterior": posterior,
            "delta": delta,
            "trend": trend,
            "confidence": conf,
        }
        dimension_updates.append(row)
        if abs(delta) >= 0.12:
            significant.append(row)

    interpretation = _interpret(
        prior_overall, posterior_overall, overall_delta, overall_trend,
        len(significant), days, round(data_w * 100, 1),
    )

    return {
        "has_prior": True,
        "prior_date": prior_date,
        "days_since_prior": days,
        "prior_overall": round(prior_overall, 2),
        "observation_overall": current,
        "posterior_overall": posterior_overall,
        "overall_delta": overall_delta,
        "overall_trend": overall_trend,
        "prior_weight_pct": round(prior_w * 100, 1),
        "data_weight_pct": round(obs_w * 100, 1),
        "dimension_updates": dimension_updates,
        "significant_changes": significant[:8],
        "interpretation": interpretation,
        "methodology": "ISO 31010 贝叶斯更新 · 历史先验 + 新观测加权融合",
    }


def _interpret(
    prior: float, posterior: float, delta: float, trend: str,
    sig_count: int, days: Optional[int], data_pct: float,
) -> str:
    parts = [
        f"先验综合评分 {prior:.2f}，当前观测 {posterior:.2f}（融合权重：新数据 {data_pct}%）。",
        f"后验综合评分 {posterior:.2f}，较先验{'+' if delta >= 0 else ''}{delta:.2f}（{trend}）。",
    ]
    if days is not None:
        parts.append(f"距上次评估 {days} 天。")
    if sig_count:
        parts.append(f"有 {sig_count} 个维度后验变化显著（|Δ|≥0.12），建议重点复核。")
    else:
        parts.append("各维度后验变化在正常波动范围内。")
    return "".join(parts)
