# -*- coding: utf-8 -*-
"""董事会一页纸执行摘要 — 决策层输出"""

from __future__ import annotations

from typing import List

from risk_engine import AssessmentResult


def build_executive_brief(result: AssessmentResult, analytics: dict = None) -> dict:
    analytics = analytics or {}
    top = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)[:3]
    cross = analytics.get("cross_risk_alerts") or []
    appetite = analytics.get("risk_appetite") or {}
    bayes = analytics.get("bayesian_update") or {}
    p0 = 0
    try:
        from action_planner import build_action_plans
        p0 = build_action_plans(result).get("p0_count", 0)
    except Exception:
        pass

    headline = (
        f"{result.company_name} 综合风险 {result.overall_score:.2f}/4.00（{result.overall_level.value}）"
        f"{'，超出风险偏好' if not appetite.get('within_appetite', True) else ''}"
    )

    key_messages: List[str] = []
    for line in (analytics.get("executive_summary") or [])[:3]:
        key_messages.append(line)
    if bayes.get("has_prior"):
        key_messages.append(
            f"贝叶斯复评：后验 {bayes.get('posterior_overall')}，趋势「{bayes.get('overall_trend')}」"
        )

    board_asks = []
    if result.overall_score >= 2.5:
        board_asks.append("审议风险偏好偏离项与资本/流动性缓冲是否充足")
    if cross:
        board_asks.append(f"关注交叉风险：{cross[0].get('message', '')}")
    deep = analytics.get("deep_analysis") or {}
    mc = deep.get("monte_carlo") or {}
    if mc.get("probability_breach_appetite_pct", 0) >= 25:
        board_asks.append(f"蒙特卡洛显示超承受度概率 {mc['probability_breach_appetite_pct']}%，建议设定专项督导")
    if not board_asks:
        board_asks.append("确认季度风险复评机制与 KRI 阈值")

    next_90 = []
    if p0:
        next_90.append(f"立即启动 P0 行动 {p0} 项，30 天内提交进展报告")
    next_90.append("完成高风险维度 ISO 31000 应对策略审批")
    if top:
        next_90.append(f"优先维度：{'、'.join(d.name for d in top)}")

    return {
        "headline": headline,
        "risk_level": result.overall_level.value,
        "overall_score": result.overall_score,
        "confidence": (analytics.get("confidence") or {}).get("score"),
        "erm_maturity": (analytics.get("erm_maturity") or {}).get("level"),
        "key_messages": key_messages[:5],
        "board_asks": board_asks[:4],
        "next_90_days": next_90[:4],
        "top_risks": [{"dimension": d.name, "score": d.score, "level": d.level.value} for d in top],
    }
