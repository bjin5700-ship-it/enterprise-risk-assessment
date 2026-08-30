# -*- coding: utf-8 -*-
"""高级风险分析 — 置信度、ERM 成熟度、交叉风险、董事会摘要"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult
from risk_framework import (
    COSO_COMPONENTS,
    DIMENSION_FRAMEWORK_MAP,
    ISO31000_PRINCIPLES,
    MATURITY_LEVELS,
    RECOMMENDED_EXTENSION_DOMAINS,
)
from risk_config import get_industry_profile
from risk_matrix import build_heatmap_matrix, heatmap_meta

RISK_CLUSTERS = [
    {"name": "财务流动性集群", "dimensions": {"财务风险", "信用风险"}, "threshold": 2.5, "min_count": 2,
     "message": "财务与信用共振，存在流动性连锁风险"},
    {"name": "合规诉讼集群", "dimensions": {"法律与合规风险", "税务风险"}, "threshold": 2.5, "min_count": 2,
     "message": "法律与税务双重合规压力"},
    {"name": "运营中断集群", "dimensions": {"生产运营风险", "供应链风险", "安全生产风险"}, "threshold": 2.5, "min_count": 2,
     "message": "运营/供应链/安全联动中断风险"},
    {"name": "声誉与数据集群", "dimensions": {"战略与声誉风险", "数据隐私合规风险"}, "threshold": 2.5, "min_count": 2,
     "message": "声誉与数据隐私双重暴露，监管与舆情风险叠加"},
    {"name": "治理合规集群", "dimensions": {"公司治理风险", "反贿赂道德合规风险", "法律与合规风险"}, "threshold": 2.5, "min_count": 2,
     "message": "治理薄弱与合规风险共振"},
    {"name": "战略转型集群", "dimensions": {"行业与市场风险", "技术与信息安全风险", "经营风险"}, "threshold": 2.5, "min_count": 2,
     "message": "外部环境与数字化、经营压力叠加"},
]


def compute_confidence(form_stats: Optional[dict]) -> dict:
    if not form_stats:
        return {"score": 50, "level": "中", "note": "缺少填写统计"}
    key_pct = form_stats.get("key_completion_pct", 0)
    total_pct = form_stats.get("completion_pct", 0)
    st = form_stats.get("scoring_sheets_total", 1) or 1
    scoring_ratio = form_stats.get("scoring_sheets_filled", 0) / st * 100
    score = round(min(100, max(10, key_pct * 0.45 + total_pct * 0.35 + scoring_ratio * 0.20)), 1)
    level = "高" if score >= 75 else "中" if score >= 50 else "低"
    notes = {"高": "数据充分，结论可信", "中": "可用于管理参考", "低": "建议补充关键字段后再决策"}
    return {"score": score, "level": level, "note": notes[level]}


def compute_erm_maturity(result: AssessmentResult, form_stats: Optional[dict]) -> dict:
    dims = result.dimensions
    scores = []

    def avg_score(names):
        ds = [dims[n] for n in names if n in dims]
        return 5 - min(4, sum(d.score for d in ds) / len(ds)) if ds else 2.5

    scores.append(avg_score(["关联方与集团风险", "法律与合规风险"]))
    scores.append(avg_score(["行业与市场风险", "经营风险"]))
    scores.append(avg_score(["财务风险", "信用风险"]))
    info = dims.get("技术与信息安全风险")
    info_s = 5 - (info.score if info else 2)
    if form_stats and form_stats.get("completion_pct", 0) >= 60:
        info_s = min(5, info_s + 0.5)
    scores.append(info_s)
    scores.append(5 - min(4, result.overall_score))

    level = max(1, min(5, round(sum(scores) / len(scores))))
    meta = MATURITY_LEVELS[level]
    return {
        "level": level, "name": meta["name"], "description": meta["desc"],
        "coso_breakdown": {COSO_COMPONENTS[i]: round(scores[i], 1) for i in range(min(5, len(scores)))},
    }


def detect_cross_risks(result: AssessmentResult) -> List[dict]:
    sm = {d.name: d.score for d in result.dimensions.values()}
    alerts = []
    for c in RISK_CLUSTERS:
        hit = [d for d in c["dimensions"] if sm.get(d, 0) >= c["threshold"]]
        if len(hit) >= c["min_count"]:
            alerts.append({"cluster": c["name"], "dimensions": hit, "message": c["message"],
                           "severity": "高" if len(hit) >= 3 else "中"})
    return alerts


def compute_risk_appetite(result: AssessmentResult, basic: dict) -> dict:
    appetite = str((basic or {}).get("风险承受度") or (basic or {}).get("风险偏好") or "未声明").strip()
    tol = {"保守": 1.8, "稳健": 2.2, "平衡": 2.6, "积极": 3.0, "激进": 3.4}
    threshold = 2.5
    for k, v in tol.items():
        if k in appetite:
            threshold = v
    breach = result.overall_score > threshold
    return {
        "stated_appetite": appetite or "未声明",
        "implied_threshold": threshold,
        "within_appetite": not breach,
        "breach_dimensions": [d.name for d in result.dimensions.values() if d.score >= threshold],
        "recommendation": "综合风险超出承受度，建议董事会审议" if breach else "整体在可接受范围，持续监控",
    }


def build_executive_summary(result, confidence, maturity, cross) -> List[str]:
    top = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)[:3]
    lines = [
        f"{result.company_name} 综合评分 {result.overall_score:.2f}/4.00，等级「{result.overall_level.value}」。",
        f"ERM 成熟度 {maturity['level']}/5（{maturity['name']}），数据置信度 {confidence['score']}%（{confidence['level']}）。",
    ]
    if top:
        lines.append("优先关注：" + "、".join(f"{d.name}({d.score:.2f})" for d in top))
    if cross:
        lines.append(f"交叉风险：{cross[0]['message']}")
    kr = sum(len(d.key_risks) for d in result.dimensions.values())
    lines.append(f"风险登记 {kr} 项关键风险，建议按 ISO 31000 完成应对策略审批，90 天内闭环 P0 项。")
    return lines


def enrich_assessment(result: AssessmentResult, form_stats=None, basic_info=None) -> dict:
    confidence = compute_confidence(form_stats)
    maturity = compute_erm_maturity(result, form_stats)
    cross = detect_cross_risks(result)
    cells = build_heatmap_matrix(result, result.all_raw_data or {})
    return {
        "confidence": confidence,
        "erm_maturity": maturity,
        "cross_risk_alerts": cross,
        "risk_appetite": compute_risk_appetite(result, basic_info or {}),
        "heatmap_matrix": cells,
        "heatmap_meta": heatmap_meta(cells),
        "framework_alignment": [{
            "dimension": d.name,
            "score": d.score,
            "level": d.level.value,
            "iso31000": DIMENSION_FRAMEWORK_MAP.get(d.name, {}).get("iso31000", "—"),
            "coso": DIMENSION_FRAMEWORK_MAP.get(d.name, {}).get("coso_component", "—"),
            "tcfd": DIMENSION_FRAMEWORK_MAP.get(d.name, {}).get("tcfd", "—"),
        } for d in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True)],
        "gap_analysis": {
            "template_coverage_pct": round((form_stats or {}).get("scoring_sheets_filled", 0) /
                                           max(1, (form_stats or {}).get("scoring_sheets_total", 14)) * 100, 1),
            "extension_domains": RECOMMENDED_EXTENSION_DOMAINS,
            "summary": "模板已覆盖核心 ERM 及声誉/BCM/隐私/治理/反贿赂扩展域；建议按行业校准阈值并季度复评",
        },
        "industry_profile": get_industry_profile((basic_info or {}).get("所属行业")),
        "executive_summary": build_executive_summary(result, confidence, maturity, cross),
        "iso31000_principles": ISO31000_PRINCIPLES,
        "standards_footer": "方法论对齐 ISO 31000:2018 · COSO ERM 2017 · TCFD · ISO 22301 · ISO 37001",
    }


def enrich_assessment_full(result, form_stats=None, basic_info=None, assessed_at=None, prior_assessment=None, action_plans=None, record_snapshot=True) -> dict:
    """完整分析包 — Phase A–D + 贝叶斯 + 数据闭环"""
    base = enrich_assessment(result, form_stats, basic_info)
    form_data = result.all_raw_data or {}

    try:
        from risk_scenario import run_scenario_analysis
        base["scenario_analysis"] = run_scenario_analysis(result, form_data)
    except Exception:
        base["scenario_analysis"] = None

    try:
        from risk_kri import build_kri_dashboard, build_reassessment_reminder
        base["kri_dashboard"] = build_kri_dashboard(result, form_data)
        base["reassessment"] = build_reassessment_reminder(assessed_at, basic_info or {})
    except Exception:
        base["kri_dashboard"] = None
        base["reassessment"] = None

    try:
        from risk_executive import build_executive_brief
        base["executive_brief"] = build_executive_brief(result, base)
    except Exception:
        base["executive_brief"] = None

    try:
        from risk_bayesian import run_bayesian_update
        base["bayesian_update"] = run_bayesian_update(result, prior_assessment, form_stats)
    except Exception:
        base["bayesian_update"] = None

    try:
        from risk_deep_analysis import run_deep_analysis
        conf = base.get("confidence", {}).get("score", 50)
        cross = base.get("cross_risk_alerts")
        base["deep_analysis"] = run_deep_analysis(
            result, basic_info or {}, confidence_pct=conf, cross_alerts=cross,
        )
    except Exception:
        base["deep_analysis"] = None

    try:
        from risk_closed_loop import build_closed_loop_package
        if action_plans is None:
            from action_planner import build_action_plans
            action_plans = build_action_plans(result)
        cl = build_closed_loop_package(result, base, prior_assessment, action_plans, record_snapshot=record_snapshot)
        base["closed_loop"] = cl
        base["alerts"] = cl.get("alerts")
        # 历史 Pearson 相关优先覆盖启发式矩阵
        if cl.get("enhanced_correlation") and base.get("deep_analysis"):
            base["deep_analysis"]["correlation_matrix"] = cl["enhanced_correlation"]
            if cl.get("correlation_source") == "historical_pearson":
                base["deep_analysis"]["correlation_matrix"]["source"] = "historical_pearson"
    except Exception:
        base["closed_loop"] = None
        base["alerts"] = None

    # Phase-1 additive enhancement (data gate / peer percentile / verifiable actions)
    try:
        from risk_phase1 import build_phase1_package
        supplements = None
        if isinstance(form_stats, dict):
            supplements = form_stats.get("_supplements")
        p1 = build_phase1_package(
            result,
            form_stats=form_stats,
            basic_info=basic_info,
            action_plans=action_plans,
            deep_analysis=base.get("deep_analysis"),
            template=None,
            supplements=supplements,
        )
        base["phase1_enhancement"] = p1
        base["data_quality_gate"] = p1.get("data_quality_gate")
        base["verifiable_actions"] = p1.get("verifiable_actions")
        # keep confidence aligned with gate score when available
        gate = p1.get("data_quality_gate") or {}
        if gate.get("confidence_score") is not None:
            conf = base.get("confidence") or {}
            conf["score"] = gate["confidence_score"]
            conf["level"] = "高" if gate["confidence_score"] >= 75 else "中" if gate["confidence_score"] >= 50 else "低"
            conf["note"] = gate.get("gate_label") or conf.get("note")
            conf["gate"] = gate.get("gate")
            base["confidence"] = conf
    except Exception as _p1_exc:
        base["phase1_enhancement"] = {"error": str(_p1_exc)}

    try:
        from data_external_risk import attach_external_evidence
        base["external_evidence"] = attach_external_evidence(result, basic_info)
    except Exception as _ext_exc:
        base["external_evidence"] = {
            "connected": False,
            "provider": "none",
            "note": "外部证据模块未加载",
            "records": [],
            "does_not_score": True,
            "errors": [str(_ext_exc)[:200]],
        }

    return base
