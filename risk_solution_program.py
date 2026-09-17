# -*- coding: utf-8 -*-
"""
International-grade solution program (ISO 31000 treatment + COSO response).

Produces a board-ready portfolio: 4T strategy, 90-day roadmap, owners, KPIs, evidence links.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult, RiskLevel

TREATMENT_4T = ("降低 Reduce", "转移 Transfer", "接受 Accept", "规避 Avoid")


def _severity_rank(dim) -> float:
    return float(dim.score or 0)


def _pick_4t(dim) -> str:
    if dim.level in (RiskLevel.CRITICAL,) or dim.score >= 3.2:
        return "规避 Avoid"
    if dim.level in (RiskLevel.HIGH,) or dim.score >= 2.8:
        return "降低 Reduce"
    if dim.name in ("信用风险", "财务风险", "法律与合规风险"):
        return "转移 Transfer"
    if dim.score < 1.8:
        return "接受 Accept"
    return "降低 Reduce"


def _owner(dim_name: str) -> str:
    mapping = {
        "财务风险": "CFO / 财务总监",
        "法律与合规风险": "法务合规负责人",
        "技术与信息安全风险": "CISO / IT",
        "安全生产风险": "EHS 总监",
        "环境风险": "EHS / 可持续发展",
        "供应链风险": "采购与供应链负责人",
        "人力资源风险": "CHRO",
        "经营风险": "COO / 业务负责人",
        "战略与声誉风险": "CEO 办公室",
        "业务连续性风险": "BCM 负责人",
        "数据隐私合规风险": "DPO / 法务",
        "公司治理风险": "董事会秘书",
        "反贿赂道德合规风险": "合规官",
    }
    return mapping.get(dim_name, "风险委员会秘书处")


def build_solution_program(
    result: AssessmentResult,
    *,
    action_plans: Optional[dict] = None,
    deep_solutions: Optional[List[dict]] = None,
    external_evidence: Optional[dict] = None,
) -> Dict[str, Any]:
    """Enterprise solution program aligned to ISO 31000 §6.5 + COSO 2017."""
    action_plans = action_plans or {}
    deep_solutions = deep_solutions or []
    ext = external_evidence or {}
    deep_by_dim = {str(d.get("dimension")): d for d in deep_solutions if d.get("dimension")}

    dimensions = sorted(result.dimensions.values(), key=_severity_rank, reverse=True)
    portfolio: List[dict] = []
    roadmap: List[dict] = []
    day = 0

    for dim in dimensions:
        if dim.score < 1.5 and dim.level not in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            continue
        strategy = _pick_4t(dim)
        deep = deep_by_dim.get(dim.name) or {}
        immediate = deep.get("immediate_actions") or []
        short = deep.get("short_term_actions") or []
        measures = []
        if not immediate and not short and dim.key_risks:
            immediate = [
                {
                    "measure": f"针对「{dim.key_risks[0]}」启动专项整改",
                    "owner": _owner(dim.name),
                    "priority": "P0",
                    "verification": "30 天交付物验收",
                }
            ]
        for bucket, phase, offset in ((immediate, "0-30天", 0), (short, "31-90天", 30)):
            for m in bucket[:3]:
                measures.append(
                    {
                        "phase": phase,
                        "measure": m.get("measure") if isinstance(m, dict) else str(m),
                        "owner": (m.get("owner") if isinstance(m, dict) else None) or _owner(dim.name),
                        "priority": (m.get("priority") if isinstance(m, dict) else "P1"),
                        "verification": (m.get("verification") if isinstance(m, dict) else "交付物+复盘"),
                    }
                )
                day += 7
                roadmap.append(
                    {
                        "day_window": f"D{offset + 1}-D{min(offset + 30, 90)}",
                        "dimension": dim.name,
                        "action": measures[-1]["measure"],
                        "owner": measures[-1]["owner"],
                        "strategy": strategy,
                    }
                )

        portfolio.append(
            {
                "dimension": dim.name,
                "score": round(float(dim.score), 2),
                "level": dim.level.value,
                "treatment_strategy": strategy,
                "framework": "ISO 31000:2018 §6.5 · COSO ERM 2017 风险应对",
                "root_causes": (deep.get("root_cause_analysis") or dim.key_risks[:3])[:5],
                "measures": measures[:6],
                "kpis": (deep.get("kpis") or [])[:4],
                "success_metrics": deep.get("success_metrics") or [],
                "resources": deep.get("resources") or {},
                "insurance_transfer_note": (
                    "可考虑通过董责险/财产险/信用险转移部分财务与责任暴露（需精算复核）。"
                    if strategy == "转移 Transfer"
                    else None
                ),
            }
        )

    ext_records = list(ext.get("records") or [])[:5]
    evidence_actions = []
    for rec in ext_records:
        evidence_actions.append(
            {
                "source": rec.get("source") or ext.get("provider") or "external",
                "title": rec.get("title") or rec.get("type") or "外部证据",
                "suggested_action": rec.get("suggested_action") or "纳入风险登记册并指定跟进人",
            }
        )

    headline_dims = [p["dimension"] for p in portfolio[:3]]
    overall = result.overall_level.value if result.overall_level else "—"

    return {
        "version": "2026-p0",
        "standards": ["ISO 31000:2018", "ISO 31010", "COSO ERM 2017", "TCFD", "ISO 22301", "ISO 37001"],
        "executive_summary": (
            f"{result.company_name} 综合等级 {overall}（{result.overall_score:.2f}/4.00）。"
            f"优先处理维度：{'、'.join(headline_dims) if headline_dims else '维持季度复评'}。"
            "本方案按国际通行的 4T 应对（降低/转移/接受/规避）编排，并附 90 天行动路线图。"
        ),
        "treatment_portfolio": portfolio[:10],
        "roadmap_90d": roadmap[:24],
        "action_plan_sync": {
            "total_actions": len(action_plans.get("items") or action_plans.get("actions") or []),
            "note": "与 action_plans / deep_solutions 同步；审批门仍须人工签核。",
        },
        "external_evidence_actions": evidence_actions,
        "board_asks": _board_asks(portfolio, result),
        "maturity_target": {
            "current": "L3 系统化评估",
            "target_12m": "L4 量化与持续监控（KRI + 情景分析 + 外源证据 SLA）",
        },
    }


def _board_asks(portfolio: List[dict], result: AssessmentResult) -> List[str]:
    asks: List[str] = []
    if any(p["level"] in ("极高风险", "高风险") for p in portfolio):
        asks.append("批准高风险维度的专项预算与牵头高管（30 天内复盘）。")
    if result.overall_score >= 2.5:
        asks.append("将本评估纳入季度董事会风险议程，并指定风险委员会跟进 KPI。")
    asks.append("确认风险 appetite 阈值与容忍度（与蒙特卡洛/情景分析一致）。")
    if not asks:
        asks.append("维持现有风险管理节奏；下季度更新登记册与 KRI。")
    return asks[:5]
