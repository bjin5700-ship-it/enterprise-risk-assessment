"""空表诚实性：数据门禁 block 时禁止写成低风险 / 优于同业。"""
from __future__ import annotations

from typing import Any, Dict, Optional


INSUFFICIENT = "数据不足"


def apply_honesty_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """就地改写评估 JSON，使 headline 与门禁一致。"""
    gate = _gate(payload)
    if not gate:
        return payload
    status = str(gate.get("gate") or "")
    if status != "block":
        return payload

    payload["overall_level"] = INSUFFICIENT
    payload["scoring_suppressed"] = True
    payload["honesty"] = {
        "applied": True,
        "reason": gate.get("gate_label") or "数据不足 · 不建议直接决策",
        "original_score": payload.get("overall_score"),
        "original_level_would_be": "低风险" if float(payload.get("overall_score") or 0) < 1.5 else payload.get("overall_level"),
    }

    warnings = list(payload.get("warnings") or [])
    banner = "【诚实性】数据门禁未通过：综合等级改为「数据不足」，不对标同业、不计算 KRI 健康度、不把空观测当改善。"
    if banner not in warnings:
        warnings.insert(0, banner)
    payload["warnings"] = warnings

    _rewrite_analytics(payload.get("analytics") or {}, gate, payload.get("overall_score"))
    _rewrite_brief(payload.get("executive_brief"), payload)
    _rewrite_phase1(payload.get("phase1_enhancement"), gate)
    if payload.get("deep_analysis"):
        _rewrite_deep(payload["deep_analysis"], gate)
    if payload.get("closed_loop"):
        _rewrite_closed_loop(payload["closed_loop"])
    if payload.get("bayesian_update"):
        payload["bayesian_update"] = _neutral_bayes(payload["bayesian_update"])
    ext = payload.get("external_evidence")
    if isinstance(ext, dict):
        ext = dict(ext)
        ext["records"] = []
        ext["suggested_fields"] = []
        ext["note"] = "数据不足，不采信外部命中，亦不据此判定无风险。"
        payload["external_evidence"] = ext
    return payload


def _gate(payload: Dict[str, Any]) -> Optional[dict]:
    g = payload.get("data_quality_gate")
    if isinstance(g, dict) and g.get("gate"):
        return g
    analytics = payload.get("analytics") or {}
    g = analytics.get("data_quality_gate") if isinstance(analytics, dict) else None
    return g if isinstance(g, dict) else None


def _rewrite_analytics(analytics: dict, gate: dict, score: Any) -> None:
    if not analytics:
        return
    analytics["data_quality_gate"] = gate
    conf = analytics.get("confidence") or {}
    conf["gate"] = "block"
    conf["level"] = "低"
    conf["note"] = gate.get("gate_label") or "数据不足 · 不建议直接决策"
    analytics["confidence"] = conf

    appetite = analytics.get("risk_appetite") or {}
    appetite["within_appetite"] = None
    appetite["recommendation"] = "数据不足，无法判断是否在风险偏好内"
    analytics["risk_appetite"] = appetite

    kri = analytics.get("kri_dashboard")
    if isinstance(kri, dict):
        summary = kri.get("summary") or {}
        filled = int(summary.get("green") or 0) + int(summary.get("amber") or 0) + int(summary.get("red") or 0)
        if filled == 0:
            kri["health_score"] = None
            kri["health_label"] = "未填报，不计算健康度"
            analytics["kri_dashboard"] = kri

    if analytics.get("bayesian_update"):
        analytics["bayesian_update"] = _neutral_bayes(analytics["bayesian_update"])
    if analytics.get("executive_brief"):
        analytics["executive_brief"]["headline"] = f"{analytics['executive_brief'].get('headline', '')}".split("综合")[0].rstrip() + " 数据不足，暂不给出风险等级"
        analytics["executive_brief"]["risk_level"] = INSUFFICIENT
        analytics["executive_brief"]["key_messages"] = [
            "当前完成度过低，综合评分仅作内部占位，不得作为低风险结论。",
            gate.get("gate_label") or "",
        ]
        analytics["executive_brief"]["board_asks"] = ["先补齐企业基本信息、财务、经营、合规、安全等关键表后再上会。"]
    if analytics.get("executive_summary"):
        analytics["executive_summary"] = [
            f"数据门禁未通过（置信度 {gate.get('confidence_score')}%），等级为「数据不足」而非低风险。",
            "请补齐关键字段后再评估；空表不会优于同业。",
        ]
    analytics["heatmap_matrix"] = []
    analytics["heatmap_meta"] = {
        "independent_count": 0,
        "suggested_count": 0,
        "note": "数据不足，不展示 5×5 矩阵。",
    }
    ext = analytics.get("external_evidence")
    if isinstance(ext, dict):
        ext["records"] = []
        ext["suggested_fields"] = []
        ext["note"] = "数据不足，不采信外部命中，亦不据此判定无风险。"
        analytics["external_evidence"] = ext
    if analytics.get("deep_analysis"):
        _rewrite_deep(analytics["deep_analysis"], gate)
    if analytics.get("phase1_enhancement"):
        _rewrite_phase1(analytics["phase1_enhancement"], gate)
    if analytics.get("closed_loop"):
        _rewrite_closed_loop(analytics["closed_loop"])
    if analytics.get("scenario_analysis"):
        sa = analytics["scenario_analysis"]
        if isinstance(sa, dict) and isinstance(sa.get("scenarios"), list):
            for sc in sa["scenarios"]:
                if sc.get("id") == "base":
                    sc["overall_level"] = INSUFFICIENT
                    sc["description"] = "数据不足，基准情景不成立"
        if isinstance(sa, dict) and isinstance(sa.get("transition_risk"), dict):
            sa["transition_risk"]["level"] = INSUFFICIENT


def _rewrite_brief(brief: Optional[dict], payload: dict) -> None:
    if not isinstance(brief, dict):
        return
    name = payload.get("company_name") or "未命名企业"
    brief["headline"] = f"{name} 数据不足，暂不给出风险等级"
    brief["risk_level"] = INSUFFICIENT
    brief["key_messages"] = [
        "完成度过低，禁止将默认分 1.0 解释为低风险。",
        "补齐关键表后再生成董事会摘要。",
    ]
    brief["board_asks"] = ["先完成数据录入门禁（关键字段 ≥50%）"]
    brief["top_risks"] = []


def _rewrite_phase1(p1: Optional[dict], gate: dict) -> None:
    if not isinstance(p1, dict):
        return
    bench = p1.get("industry_benchmark") or {}
    pct = dict(bench.get("percentile") or {})
    pct["better_than_peers_pct"] = None
    pct["band"] = "数据不足，不对标"
    pct["method_note"] = "门禁 block 时不对标同业分位，避免空表显示优于 96% 同业。"
    bench["percentile"] = pct
    bench["overall_vs_industry"] = "数据不足，不对标"
    p1["industry_benchmark"] = bench
    p1["summary_lines"] = [
        f"数据门禁：{gate.get('gate_label')}（置信度 {gate.get('confidence_score')}%）。",
        "行业对标：数据不足，不对标。",
        "空表不得解释为低风险或优于同业。",
    ]


def _rewrite_deep(deep: dict, gate: dict) -> None:
    recs = deep.get("board_recommendations") or []
    deep["board_recommendations"] = [
        {
            "title": "先补数据再决策",
            "priority": "P0",
            "framework": "ISO 31000 最佳信息原则",
            "detail": gate.get("gate_label") or "数据不足",
        }
    ] + [r for r in recs if "整体可控" not in str(r.get("detail") or "")][:2]
    bench = deep.get("industry_benchmark") or {}
    if bench:
        pct = dict(bench.get("percentile") or {})
        pct["better_than_peers_pct"] = None
        pct["band"] = "数据不足，不对标"
        bench["percentile"] = pct
        bench["overall_vs_industry"] = "数据不足，不对标"
        deep["industry_benchmark"] = bench
    tld = deep.get("three_lines_of_defense")
    if isinstance(tld, dict):
        tld["overall_maturity"] = "无法评估（数据不足）"
        tld["note"] = "未填字段不得用默认分推断三道防线成熟度"
    mc = deep.get("monte_carlo")
    if isinstance(mc, dict):
        mc["money_track"] = None
        mc["sensitivity"] = []
        mc["interpretation"] = "数据不足，不展示评分不确定性结论，亦不映射经营冲击情景。"
        mc["disclaimer"] = "门禁未通过时蒙特卡洛不得解读为低风险或无损失。"


def _rewrite_closed_loop(cl: dict) -> None:
    rv = cl.get("remediation_verification")
    if isinstance(rv, dict):
        rv["overall_trend"] = "数据不足，不判定改善或恶化"
        rv["verification_label"] = "不可验证"
        rv["recommendation"] = "空观测不能当作整改有效。"
        cal = rv.get("model_calibration") or {}
        cal["note"] = "数据不足时不进行模型校准"
        rv["model_calibration"] = cal
        cl["remediation_verification"] = rv
    cl["summary"] = "数据门禁未通过，闭环验证跳过。"


def _neutral_bayes(bayes: dict) -> dict:
    out = dict(bayes)
    out["has_prior"] = False
    out["interpretation"] = "数据不足，不将空表观测纳入贝叶斯更新，亦不判定改善。"
    out["overall_trend"] = "不适用"
    out["skipped"] = True
    return out
