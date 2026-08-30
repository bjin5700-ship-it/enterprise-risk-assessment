# -*- coding: utf-8 -*-
"""Phase C — 情景分析与压力测试（TCFD / 流动性 / 运营）"""

from __future__ import annotations

from typing import Any, Dict, List

from risk_engine import AssessmentResult, RiskLevel, _sf, _ss


def _level_from_score(s: float) -> str:
    return RiskLevel.from_score(s).value


def run_scenario_analysis(result: AssessmentResult, form_data: dict = None) -> dict:
    """基准 / 不利 / 严重 三情景 + 专项压力测试"""
    form_data = form_data or result.all_raw_data or {}
    basic = form_data.get("企业基本信息", {})
    financial = form_data.get("财务风险", {})
    industry = _ss(basic.get("所属行业"))

    base = result.overall_score
    dim_scores = {d.name: d.score for d in result.dimensions.values()}

    # 不利情景：财务+供应链+行业 加权上浮
    adverse_boost = 0.0
    for name, w in [("财务风险", 0.35), ("供应链风险", 0.2), ("行业与市场风险", 0.2), ("经营风险", 0.15)]:
        adverse_boost += dim_scores.get(name, 1.5) * w * 0.25
    adverse_score = round(min(4.0, base + adverse_boost + 0.3), 2)

    # 严重情景：流动性危机 + 合规诉讼叠加
    severe_boost = 0.0
    if dim_scores.get("财务风险", 0) >= 2.5:
        severe_boost += 0.6
    if dim_scores.get("法律与合规风险", 0) >= 2.5:
        severe_boost += 0.4
    if dim_scores.get("信用风险", 0) >= 2.5:
        severe_boost += 0.3
    severe_score = round(min(4.0, adverse_score + severe_boost + 0.4), 2)

    scenarios = [
        {
            "id": "base",
            "name": "基准情景",
            "description": "基于当前填报数据的静态评估结果",
            "overall_score": base,
            "overall_level": result.overall_level.value,
            "probability": "当前状态",
        },
        {
            "id": "adverse",
            "name": "不利情景",
            "description": "宏观下行、供应链中断、需求萎缩（TCFD 转型/市场风险参考）",
            "overall_score": adverse_score,
            "overall_level": _level_from_score(adverse_score),
            "probability": "12个月内中等可能",
            "triggers": ["营收下滑>15%", "核心供应商断供", "行业政策收紧"],
        },
        {
            "id": "severe",
            "name": "严重情景",
            "description": "流动性危机 + 重大合规事件 + 信用违约连锁",
            "overall_score": severe_score,
            "overall_level": _level_from_score(severe_score),
            "probability": "低概率高影响",
            "triggers": ["流动比率<0.8", "重大诉讼/处罚", "债务违约"],
        },
    ]

    liquidity = _liquidity_stress(financial, dim_scores.get("财务风险", 1.0))
    transition = _transition_risk(form_data, industry)
    operational = _operational_stress(dim_scores)

    return {
        "scenarios": scenarios,
        "liquidity_stress": liquidity,
        "transition_risk": transition,
        "operational_stress": operational,
        "methodology": "参考 TCFD 情景分析框架 · 巴塞尔流动性压力测试思路 · ISO 31000 不确定性分析",
        "recommendation": _scenario_recommendation(base, adverse_score, severe_score),
    }


def _liquidity_stress(financial: dict, fin_score: float) -> dict:
    current = _sf(financial.get("流动比率"))
    ocf = _sf(financial.get("经营性现金流净额(万元)"))
    short_debt = _sf(financial.get("短期借款占比(%)"))

    shock_pct = 30  # 收入下降30%
    survival_days = None
    if ocf is not None and ocf > 0:
        survival_days = round(ocf / 12 * 0.7, 0)  # 粗算月现金流缓冲
    elif ocf is not None and ocf <= 0:
        survival_days = 0

    status = "可控"
    if current is not None and current < 1.0:
        status = "预警"
    if fin_score >= 3.0 or (current is not None and current < 0.8):
        status = "危急"

    return {
        "shock_assumption": f"营收骤降 {shock_pct}%",
        "current_ratio": current,
        "operating_cashflow": ocf,
        "short_term_debt_ratio": short_debt,
        "estimated_runway_months": survival_days,
        "status": status,
        "mitigation": [
            "激活13周 rolling cash forecast",
            "加速应收催收与库存变现",
            "谈判授信展期/备用流动性工具",
        ],
    }


def _transition_risk(form_data: dict, industry: str) -> dict:
    env = form_data.get("环境风险", {})
    tech = form_data.get("技术风险", {}) or form_data.get("技术与信息安全风险", {})
    carbon = _ss(env.get("碳排放管理") or env.get("碳排放达标情况"))
    green_invest = _sf(env.get("环保投入占营收比(%)"))

    score = 1.0
    findings = []
    if "无" in carbon or "未" in carbon:
        score += 0.8; findings.append("碳排放管理不完善")
    if green_invest is not None and green_invest < 0.5:
        score += 0.3
    digital = _ss(tech.get("数字化转型阶段") if tech else "")
    if "初期" in digital or "未" in digital:
        score += 0.4; findings.append("数字化转型滞后")

    if any(k in industry for k in ("化工", "能源", "制造", "建筑")):
        score += 0.3
        findings.append("行业转型压力较高（物理/转型风险）")

    score = round(min(4.0, score), 2)
    return {
        "tcfd_category": "转型风险 + 物理风险",
        "score": score,
        "level": _level_from_score(score),
        "findings": findings,
        "2c_scenario_note": "在2°C温控情景下，高碳资产与供应链可能面临额外合规与资本成本",
    }


def _operational_stress(dim_scores: dict) -> dict:
    ops_dims = ["生产运营风险", "供应链风险", "安全生产风险", "业务连续性风险"]
    hits = [n for n in ops_dims if dim_scores.get(n, 0) >= 2.5]
    avg = sum(dim_scores.get(n, 1.0) for n in ops_dims) / len(ops_dims)
    return {
        "avg_score": round(avg, 2),
        "high_risk_areas": hits,
        "interruption_probability": "高" if len(hits) >= 2 else "中" if hits else "低",
        "note": "运营/供应链/安全/BCM 联动中断评估",
    }


def _scenario_recommendation(base: float, adverse: float, severe: float) -> str:
    if severe >= 3.5:
        return "严重情景下风险极高，建议董事会审议应急资本与业务连续性预案，季度压力测试。"
    if adverse >= 2.8:
        return "不利情景下风险显著上升，建议开展专项情景演练并配置缓冲资本。"
    return "情景差距可控，建议年度更新情景假设并纳入战略审查。"
