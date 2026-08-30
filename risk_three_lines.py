# -*- coding: utf-8 -*-
"""
COSO 三道防线量化评估 — 治理与文化 · 风险合规 · 内部审计
"""

from __future__ import annotations

from typing import Any, Dict, List

from risk_engine import AssessmentResult, _ss


def _score_choice(val: str, mapping: dict, default: float = 2.0) -> float:
    text = _ss(val)
    if not text:
        return default
    for key, sc in mapping.items():
        if key in text:
            return sc
    return default


def assess_three_lines(result: AssessmentResult, form_data: dict = None) -> dict:
    form_data = form_data or result.all_raw_data or {}
    gov = form_data.get("公司治理风险", {})
    legal = form_data.get("法律合规风险", {}) or form_data.get("法律与合规风险", {})
    safety = form_data.get("安全生产风险", {})
    tech = form_data.get("技术风险", {}) or form_data.get("技术与信息安全风险", {})

    # ── 第一道防线：业务运营层 ──
    line1_factors = []
    op_dims = ["经营风险", "生产运营风险", "供应链风险", "财务风险"]
    op_scores = [result.dimensions[d].score for d in op_dims if d in result.dimensions]
    op_avg = sum(op_scores) / len(op_scores) if op_scores else 2.0
    line1_factors.append({"factor": "运营维度风险水平", "score": round(5 - min(4, op_avg), 1), "note": f"均值 {op_avg:.2f}"})

    safety_iso = _score_choice(safety.get("ISO45001认证"), {"有": 4.5, "无": 2.0}, 2.5)
    line1_factors.append({"factor": "一线安全体系", "score": safety_iso, "note": _ss(safety.get("ISO45001认证")) or "未填"})

    biz_ownership = 3.5 if op_avg < 2.0 else 2.5 if op_avg < 2.5 else 1.5
    line1_factors.append({"factor": "业务单元风险自检", "score": biz_ownership, "note": "基于运营评分推断"})

    line1 = round(sum(f["score"] for f in line1_factors) / len(line1_factors), 1)

    # ── 第二道防线：风险/合规/法务 ──
    line2_factors = []
    line2_factors.append({
        "factor": "董事会风险委员会",
        "score": _score_choice(gov.get("董事会风险委员会"), {"有": 4.5, "无": 1.5}, 2.0),
        "note": _ss(gov.get("董事会风险委员会")) or "未填",
    })
    line2_factors.append({
        "factor": "CRO/首席风险官",
        "score": _score_choice(gov.get("首席风险官CRO建制"), {"有": 4.5, "无": 1.5}, 2.0),
        "note": _ss(gov.get("首席风险官CRO建制")) or "未填",
    })
    line2_factors.append({
        "factor": "风险管理政策",
        "score": _score_choice(gov.get("风险管理政策"), {"董事会": 4.5, "有且": 4.0, "有": 3.0, "无": 1.0}, 2.0),
        "note": _ss(gov.get("风险管理政策")) or "未填",
    })
    comp_score = result.dimensions.get("法律与合规风险")
    comp_s = 5 - (comp_score.score if comp_score else 2.5)
    line2_factors.append({"factor": "合规风险状况", "score": round(comp_s, 1), "note": "合规维度反推"})

    line2 = round(sum(f["score"] for f in line2_factors) / len(line2_factors), 1)

    # ── 第三道防线：内部审计 ──
    line3_factors = []
    line3_factors.append({
        "factor": "内审独立性",
        "score": _score_choice(gov.get("内部审计独立性"), {"强": 4.5, "一般": 3.0, "弱": 1.5, "无": 1.0}, 2.5),
        "note": _ss(gov.get("内部审计独立性")) or "未填",
    })
    line3_factors.append({
        "factor": "三道防线成熟度",
        "score": _score_choice(gov.get("三道防线成熟度"), {
            "优化": 5.0, "量化": 4.5, "已定义": 3.5, "部分": 2.5, "初始": 1.5, "无": 1.0,
        }, 2.0),
        "note": _ss(gov.get("三道防线成熟度")) or "未填",
    })
    audit_trail = _score_choice(tech.get("日志审计机制"), {"完善": 4.0, "有": 3.5, "无": 1.5}, 2.5)
    line3_factors.append({"factor": "审计轨迹/日志", "score": audit_trail, "note": _ss(tech.get("日志审计机制")) or "未填"})

    line3 = round(sum(f["score"] for f in line3_factors) / len(line3_factors), 1)

    overall = round((line1 + line2 + line3) / 3, 1)
    maturity = _maturity_label(overall)
    gaps = _identify_gaps(line1, line2, line3, line1_factors, line2_factors, line3_factors)

    return {
        "line1_operational": {"score": line1, "max": 5, "label": "第一道防线（业务运营）", "factors": line1_factors},
        "line2_oversight": {"score": line2, "max": 5, "label": "第二道防线（风险合规）", "factors": line2_factors},
        "line3_assurance": {"score": line3, "max": 5, "label": "第三道防线（内部审计）", "factors": line3_factors},
        "overall_score": overall,
        "overall_maturity": maturity,
        "weakest_line": min(
            [("第一道防线", line1), ("第二道防线", line2), ("第三道防线", line3)],
            key=lambda x: x[1],
        )[0],
        "gaps": gaps,
        "recommendations": _recommendations(line1, line2, line3),
        "framework": "COSO ERM 2017 · 三道防线模型 · IIA 国际内审实务",
    }


def _maturity_label(score: float) -> str:
    if score >= 4.5:
        return "优化级"
    if score >= 3.5:
        return "量化管理级"
    if score >= 2.5:
        return "已定义级"
    if score >= 1.5:
        return "可重复级"
    return "初始级"


def _identify_gaps(l1, l2, l3, f1, f2, f3) -> List[str]:
    gaps = []
    if l1 < 2.5:
        gaps.append("第一道防线：业务单元风险识别与自控不足")
    if l2 < 2.5:
        gaps.append("第二道防线：风险/合规职能薄弱，缺乏独立监督")
    if l3 < 2.5:
        gaps.append("第三道防线：内部审计独立性或覆盖面不足")
    for f in f2 + f3:
        if f["score"] < 2.0:
            gaps.append(f"关键缺口：{f['factor']}（{f['note']}）")
    return gaps[:6]


def _recommendations(l1, l2, l3) -> List[str]:
    recs = []
    if l2 < l1 and l2 < l3:
        recs.append("优先强化第二道防线：设立/激活董事会风险委员会，明确 CRO 职责与汇报线")
    if l3 < 2.5:
        recs.append("提升第三道防线：保障内审独立性，年度审计计划覆盖高风险领域")
    if l1 < 2.5:
        recs.append("夯实第一道防线：业务单元 KPI 纳入风险指标，一线管理者风险责任制")
    if l1 >= 3.5 and l2 >= 3.5 and l3 >= 3.5:
        recs.append("三道防线整体成熟，建议年度联合演练与 board risk report 标准化")
    if not recs:
        recs.append("按最弱防线制定 12 个月提升路线图，季度跟踪 maturity score")
    return recs
