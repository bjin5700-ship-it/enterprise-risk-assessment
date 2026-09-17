# -*- coding: utf-8 -*-
"""Board-ready English executive summary (ISO 31000 / COSO ERM aligned)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult, RiskLevel


_LEVEL_EN = {
    "低风险": "Low",
    "中等风险": "Moderate",
    "高风险": "High",
    "极高风险": "Critical",
    "数据不足": "Insufficient data",
}


def build_executive_summary_en(
    result: AssessmentResult,
    payload: Optional[dict] = None,
) -> Dict[str, Any]:
    payload = payload or {}
    prog = payload.get("solution_program") or {}
    gate = payload.get("data_quality_gate") or (payload.get("analytics") or {}).get("data_quality_gate") or {}
    ext = payload.get("external_evidence") or {}

    top_dims = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)[:5]
    drivers: List[str] = []
    for d in top_dims:
        if d.score >= 2.0:
            kr = (d.key_risks or [""])[0]
            drivers.append(f"{d.name} ({_LEVEL_EN.get(d.level.value, d.level.value)}, score {d.score:.2f}): {kr}")

    treatments = []
    for item in (prog.get("treatment_portfolio") or [])[:4]:
        treatments.append(
            f"{item.get('dimension')}: {item.get('treatment_strategy', 'Treat')} — "
            f"{(item.get('measures') or [{}])[0].get('measure', 'See roadmap')}"
        )

    paragraphs = [
        (
            f"{result.company_name} — enterprise risk assessment as of {result.report_date}. "
            f"Composite score {result.overall_score:.2f}/4.00 ({_LEVEL_EN.get(result.overall_level.value, result.overall_level.value)}). "
            f"Method: rule-based multi-dimensional engine with ISO 31000-aligned treatment design (4T) and independent heat-map inputs where provided."
        ),
    ]
    if gate.get("gate") == "block" or payload.get("scoring_suppressed"):
        paragraphs.append(
            "Data quality gate: scoring suppressed — conclusions are indicative only until mandatory fields are completed."
        )
    elif gate.get("confidence_score") is not None:
        paragraphs.append(f"Data confidence: {gate.get('confidence_score')}% ({gate.get('gate_label', 'review recommended')}).")

    if drivers:
        paragraphs.append("Primary risk drivers: " + "; ".join(drivers[:4]) + ".")
    else:
        paragraphs.append("No material elevated dimensions under current inputs.")

    if ext.get("connected"):
        paragraphs.append(
            f"External evidence ({ext.get('provider', 'provider')}): {len(ext.get('records') or [])} items attached; "
            "does not override rule scores without human confirmation."
        )

    if treatments:
        paragraphs.append("Priority treatments: " + " | ".join(treatments))

    board = prog.get("board_asks") or []
    return {
        "language": "en",
        "frameworks": ["ISO 31000:2018", "COSO ERM 2017", "ISO 31010 (uncertainty)"],
        "headline": (
            f"{result.company_name}: {_LEVEL_EN.get(result.overall_level.value, 'Review')} enterprise risk profile "
            f"(score {result.overall_score:.2f})"
        ),
        "paragraphs": paragraphs,
        "board_asks_en": board[:6],
        "maturity_note": (
            "International tier: strong on structured assessment, treatment roadmaps, and export; "
            "reach top-quartile board packs when external data APIs, audited model governance, and "
            "third-party scenario libraries are fully wired."
        ),
    }
