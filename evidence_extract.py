"""从证据文本中抽取可写入表单的候选字段（需人审确认）。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from credit_code import normalize_credit_code, validate_credit_code

# (regex, sheet, field, postprocess)
_RULES: List[Tuple[str, str, str, str]] = [
    (r"统一社会信用代码[：:\s]*([0-9A-HJ-NPQRTUWXY]{18})", "企业基本信息", "统一社会信用代码", "uscc"),
    (r"信用代码[：:\s]*([0-9A-HJ-NPQRTUWXY]{18})", "企业基本信息", "统一社会信用代码", "uscc"),
    (r"(?:企业名称|公司名称|名称)[：:\s]*([^\n，,。]{4,40})", "企业基本信息", "企业名称", "name"),
    (r"所属行业[：:\s]*([^\n，,。]{2,20})", "企业基本信息", "所属行业", "text"),
    (r"员工总数[^\d]{0,8}(\d{1,7})", "企业基本信息", "员工总数(人)", "num"),
    (r"资产负债率[^\d]{0,12}(\d+(?:\.\d+)?)\s*%?", "财务风险", "资产负债率(%)", "num"),
    (r"流动比率[^\d]{0,12}(\d+(?:\.\d+)?)", "财务风险", "流动比率", "num"),
    (r"速动比率[^\d]{0,12}(\d+(?:\.\d+)?)", "财务风险", "速动比率", "num"),
    (r"净利率[^\d]{0,12}(-?\d+(?:\.\d+)?)\s*%?", "财务风险", "净利率(%)", "num"),
    (r"毛利率[^\d]{0,12}(-?\d+(?:\.\d+)?)\s*%?", "财务风险", "毛利率(%)", "num"),
    (r"(?:ROE|净资产收益率)[^\d]{0,12}(-?\d+(?:\.\d+)?)\s*%?", "财务风险", "净资产收益率ROE(%)", "num"),
    (r"年营业额[^\d]{0,12}(\d+(?:\.\d+)?)", "企业基本信息", "年营业额(万元)", "num"),
    (r"资产总额[^\d]{0,12}(\d+(?:\.\d+)?)", "企业基本信息", "资产总额(万元)", "num"),
]


def suggest_fields_from_text(text: str, source: str = "") -> List[Dict[str, Any]]:
    """返回 [{sheet, field, value, source, confidence, note}]，不去重覆盖。"""
    blob = text or ""
    if not blob.strip():
        return []
    found: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for pattern, sheet, field, kind in _RULES:
        m = re.search(pattern, blob, re.I)
        if not m:
            continue
        raw = str(m.group(1)).strip()
        value, note, conf = _normalize(raw, kind)
        if value is None:
            continue
        key = (sheet, field)
        if key in found and found[key]["confidence"] >= conf:
            continue
        found[key] = {
            "sheet": sheet,
            "field": field,
            "value": value,
            "source": source or "evidence",
            "confidence": conf,
            "note": note,
            "needs_confirm": True,
        }
    return list(found.values())


def _normalize(raw: str, kind: str) -> Tuple[Any, str, int]:
    if kind == "uscc":
        ok, msg = validate_credit_code(raw)
        code = normalize_credit_code(raw)
        if not ok:
            return None, msg, 0
        return code, "校验位通过", 95
    if kind == "name":
        name = re.sub(r"\s+", "", raw)
        if len(name) < 4 or "公司" not in name and "企业" not in name and "集团" not in name:
            if len(name) < 4:
                return None, "名称过短", 0
        return name, "", 70
    if kind == "num":
        try:
            return float(raw.replace(",", "")), "", 75
        except ValueError:
            return None, "非数值", 0
    return raw.strip(), "", 60
