"""ERP/财务入站校验：jsonschema 契约 + 可选 pandera 数值约束。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

ERP_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "debt_ratio": {"type": ["number", "string"]},
        "current_ratio": {"type": ["number", "string"]},
        "quick_ratio": {"type": ["number", "string"]},
        "net_margin": {"type": ["number", "string"]},
        "gross_margin": {"type": ["number", "string"]},
        "roe": {"type": ["number", "string"]},
        "revenue": {"type": ["number", "string"]},
        "total_assets": {"type": ["number", "string"]},
        "ocf": {"type": ["number", "string"]},
        "fcf": {"type": ["number", "string"]},
        "employee_count": {"type": ["number", "string", "integer"]},
        "interest_coverage": {"type": ["number", "string"]},
        "short_debt_ratio": {"type": ["number", "string"]},
        "ar_days": {"type": ["number", "string"]},
        "customer_conc": {"type": ["number", "string"]},
        "supplier_conc": {"type": ["number", "string"]},
        "asset_liability_ratio": {"type": ["number", "string"]},
        "operating_cash_flow": {"type": ["number", "string"]},
        "company_name": {"type": "string"},
        "credit_code": {"type": "string"},
        "industry": {"type": "string"},
    },
}


def validate_erp_payload(payload: dict) -> Tuple[List[str], List[str]]:
    """返回 (errors, warnings)。jsonschema 不可用时做轻量类型检查。"""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return ["ERP 载荷必须是 JSON 对象"], warnings
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(instance=payload, schema=ERP_JSON_SCHEMA)
    except ImportError:
        pass
    except Exception as exc:
        errors.append(f"JSON 契约校验失败: {exc}")
    numeric_keys = [
        "debt_ratio", "current_ratio", "quick_ratio", "net_margin", "gross_margin",
        "roe", "revenue", "total_assets", "ocf", "fcf", "employee_count",
        "interest_coverage", "short_debt_ratio", "ar_days", "customer_conc",
        "supplier_conc", "asset_liability_ratio", "operating_cash_flow",
    ]
    cleaned = {}
    for k in numeric_keys:
        if k not in payload:
            continue
        try:
            cleaned[k] = float(str(payload[k]).replace("%", "").replace(",", "").strip())
        except (TypeError, ValueError):
            errors.append(f"字段 {k} 不是数值: {payload[k]!r}")
    if "debt_ratio" in cleaned and not (0 <= cleaned["debt_ratio"] <= 300):
        warnings.append(f"资产负债率 {cleaned['debt_ratio']} 超出常规区间 0–300")
    if "current_ratio" in cleaned and cleaned["current_ratio"] < 0:
        errors.append("流动比率不能为负")
    if "employee_count" in cleaned and cleaned["employee_count"] < 0:
        errors.append("员工总数不能为负")
    pandera_warnings = _pandera_check(cleaned)
    warnings.extend(pandera_warnings)
    return errors, warnings


def _pandera_check(cleaned: dict) -> List[str]:
    if not cleaned:
        return []
    try:
        import pandas as pd  # type: ignore
        import pandera as pa  # type: ignore
        from pandera import Column, DataFrameSchema
    except Exception:
        return []
    schema = DataFrameSchema(
        {
            "debt_ratio": Column(float, nullable=True, checks=pa.Check.in_range(0, 300), required=False),
            "current_ratio": Column(float, nullable=True, checks=pa.Check.ge(0), required=False),
            "net_margin": Column(float, nullable=True, checks=pa.Check.in_range(-100, 100), required=False),
            "employee_count": Column(float, nullable=True, checks=pa.Check.ge(0), required=False),
        },
        coerce=True,
        strict=False,
    )
    try:
        df = pd.DataFrame([cleaned])
        schema.validate(df, lazy=True)
    except Exception as exc:
        return [f"pandera: {exc}"]
    return []
