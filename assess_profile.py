# -*- coding: utf-8 -*-
"""Build AssessmentResult from ERA enterprise profile (no Excel required).

Maps CRM enterprise fields into the sheet dicts expected by risk_engine scorers,
then produces the same AssessmentResult used by Word/HTML generators.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from risk_engine import (
    SHEET_SCORERS,
    AssessmentResult,
    RiskDimension,
    RiskLevel,
    _ss,
)


def _profile_sheets(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    name = _ss(payload.get("name") or payload.get("enterprise_name") or "未命名企业")
    industry = _ss(payload.get("industry") or "")
    city = _ss(payload.get("city") or "")
    country = _ss(payload.get("country") or "")
    employees = payload.get("employee_count")
    revenue = payload.get("annual_revenue")
    credit = payload.get("credit_score")
    description = _ss(payload.get("description") or "")

    basic = {
        "企业名称": name,
        "所属行业": industry,
        "所在城市": city,
        "所在国家": country,
        "企业简介": description,
    }
    if employees is not None:
        basic["员工人数"] = employees

    financial: dict[str, Any] = {}
    if revenue is not None:
        try:
            # 万元
            financial["营业收入(万元)"] = float(revenue) / 10000.0
        except (TypeError, ValueError):
            pass

    credit_sheet: dict[str, Any] = {}
    if credit is not None:
        try:
            c = int(credit)
            credit_sheet["外部信用评分"] = c
            if c < 580:
                credit_sheet["是否存在债务违约记录"] = "是"
            elif c < 650:
                credit_sheet["近三年是否连续亏损"] = "否"
        except (TypeError, ValueError):
            pass

    hr: dict[str, Any] = {}
    if employees is not None:
        hr["在职员工总数"] = employees

    industry_sheet: dict[str, Any] = {"所属行业": industry} if industry else {}
    operation: dict[str, Any] = {}
    if city:
        operation["主要经营区域"] = city

    return {
        "企业基本信息": basic,
        "财务风险": financial,
        "负债与偿债风险": financial,
        "信用风险": credit_sheet,
        "人力资源风险": hr,
        "行业与市场风险": industry_sheet,
        "经营风险": operation,
    }


def assess_from_profile(payload: dict[str, Any]) -> AssessmentResult:
    """Score an enterprise using profile fields → Chinese AssessmentResult."""
    all_data = _profile_sheets(payload)
    company_name = _ss(all_data.get("企业基本信息", {}).get("企业名称")) or "未命名企业"

    # Allow caller to inject extra sheet field overrides
    extra = payload.get("sheet_overrides")
    if isinstance(extra, dict):
        for sheet, fields in extra.items():
            if isinstance(fields, dict):
                all_data.setdefault(str(sheet), {}).update(fields)

    dimensions: dict[str, RiskDimension] = {}
    total_weighted = 0.0
    total_weight = 0.0

    for sheet_name, scorer in SHEET_SCORERS.items():
        data = all_data.get(sheet_name, {})
        dim = scorer(data)
        dimensions[dim.name] = dim
        total_weighted += dim.score * dim.weight
        total_weight += dim.weight

    overall_score = total_weighted / total_weight if total_weight > 0 else 1.0
    overall_level = RiskLevel.from_score(overall_score)
    report_date = date.today().strftime("%Y年%m月%d日")

    return AssessmentResult(
        company_name=company_name,
        overall_score=round(overall_score, 2),
        overall_level=overall_level,
        dimensions=dimensions,
        all_raw_data=all_data,
        report_date=report_date,
    )


def result_to_chinese_dict(result: AssessmentResult) -> dict[str, Any]:
    dims = []
    for dim in sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True):
        dims.append(
            {
                "name": dim.name,
                "score": dim.score,
                "level": dim.level.value,
                "weight": dim.weight,
                "findings": list(dim.findings),
                "key_risks": list(dim.key_risks),
                "suggested_action": (
                    "立即整改，最高优先级"
                    if dim.score >= 3.5
                    else "制定专项整改计划"
                    if dim.score >= 2.5
                    else "持续监控，完善制度"
                    if dim.score >= 1.5
                    else "维持现状，定期复查"
                ),
            }
        )

    key_risks = []
    for dim in dims:
        for kr in dim["key_risks"]:
            key_risks.append({"dimension": dim["name"], "risk": kr})

    return {
        "company_name": result.company_name,
        "overall_score": result.overall_score,
        "overall_level": result.overall_level.value,
        "score_scale": "1.00–4.00（越高风险越大）",
        "report_date": result.report_date,
        "dimensions": dims,
        "key_risks": key_risks,
        "summary": (
            f"{result.company_name}综合风险评分 {result.overall_score:.2f}/4.00，"
            f"等级为「{result.overall_level.value}」。"
            f"共识别 {len(key_risks)} 项关键风险点，覆盖 {len(dims)} 个风险维度。"
        ),
    }
