# -*- coding: utf-8 -*-
"""独立 5×5 可能性 × 影响（ISO 31010）。
规则引擎综合分不推导矩阵格；未填时仅给出建议值并标明来源。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from risk_engine import AssessmentResult, RiskDimension

PROB_FIELD = "可能性(1-5)"
IMPACT_FIELD = "影响(1-5)"

PROB_CHOICES = ["1 罕见", "2 不太可能", "3 可能", "4 很可能", "5 几乎确定"]
IMPACT_CHOICES = ["1 可忽略", "2 轻微", "3 中等", "4 严重", "5 极严重"]

MATRIX_FIELDS = [
    {"is_group": True, "name": "5×5 矩阵（独立估计，不参与规则打分）"},
    {
        "name": PROB_FIELD,
        "type": "下拉",
        "choices": PROB_CHOICES,
        "note": "发生可能性 1–5，与综合评分独立",
    },
    {
        "name": IMPACT_FIELD,
        "type": "下拉",
        "choices": IMPACT_CHOICES,
        "note": "影响程度 1–5，与综合评分独立",
    },
]

SKIP_MATRIX_SHEETS = {"企业基本信息", "综合评估", "其他补充信息"}

SHEET_ALIASES = {
    "法律合规风险": "法律与合规风险",
    "法律与合规风险": "法律与合规风险",
    "技术风险": "技术与信息安全风险",
    "技术与信息安全风险": "技术与信息安全风险",
    "行业政策风险": "行业与市场风险",
    "行业与市场风险": "行业与市场风险",
}

_PROB_WORDS = (
    (5, ("几乎确定", "很高(>80", "很高", ">80%")),
    (4, ("很可能", "较高(60", "较高", "60-80")),
    (2, ("不太可能", "较低(20", "较低", "20-40")),
    (1, ("罕见", "很低(<20", "很低", "<20%")),
    (3, ("可能", "中等(40", "中等", "40-60")),
)
_IMPACT_WORDS = (
    (5, ("极严重", "灾难", "5")),
    (4, ("严重", "4")),
    (3, ("中等", "3")),
    (2, ("轻微", "2")),
    (1, ("可忽略", "1")),
)


def is_matrix_sheet(title: str) -> bool:
    return bool(title) and title not in SKIP_MATRIX_SHEETS


def canonical_dim_name(name: str) -> str:
    return SHEET_ALIASES.get(str(name or "").strip(), str(name or "").strip())


def parse_scale(raw: Any, kind: str = "prob") -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text[0].isdigit():
        n = int(text[0])
        return n if 1 <= n <= 5 else None
    try:
        n = int(float(text))
        return n if 1 <= n <= 5 else None
    except ValueError:
        pass
    table = _PROB_WORDS if kind == "prob" else _IMPACT_WORDS
    for value, keys in table:
        if any(k in text for k in keys):
            return value
    return None


def suggest_pi(dim: RiskDimension) -> Tuple[int, int]:
    """建议值：影响看评分，可能性看证据密度。二者公式不同，避免 P=I=f(score)。"""
    score = float(dim.score or 1.0)
    if score >= 3.5:
        impact = 5
    elif score >= 2.5:
        impact = 4
    elif score >= 1.8:
        impact = 3
    elif score >= 1.3:
        impact = 2
    else:
        impact = 1
    evidence = len(dim.key_risks or []) + min(2, len(dim.findings or []))
    if evidence >= 5:
        prob = 4
    elif evidence >= 3:
        prob = 3
    elif evidence >= 1:
        prob = 2
    else:
        prob = 1
    if score >= 3.0:
        prob = min(5, prob + 1)
    return prob, impact


def _sheet_lookup(form_data: dict, dim_name: str) -> dict:
    if not form_data:
        return {}
    canon = canonical_dim_name(dim_name)
    for key in (dim_name, canon, *(k for k, v in SHEET_ALIASES.items() if v == canon)):
        block = form_data.get(key)
        if isinstance(block, dict) and block:
            return block
    return {}


def _from_overall_sheet(form_data: dict, dim_name: str) -> Tuple[Optional[int], Optional[int]]:
    overall = form_data.get("综合评估") or {}
    if not isinstance(overall, dict):
        return None, None
    aliases = {dim_name, canonical_dim_name(dim_name)}
    aliases.update(k for k, v in SHEET_ALIASES.items() if v in aliases or k in aliases)
    prob = impact = None
    for alias in aliases:
        if prob is None:
            for key in (f"{alias}_发生概率", f"{alias}发生概率", PROB_FIELD):
                if overall.get(key) not in (None, ""):
                    prob = parse_scale(overall.get(key), "prob")
                    break
        if impact is None:
            for key in (f"{alias}_影响程度", f"{alias}影响程度", IMPACT_FIELD):
                if overall.get(key) not in (None, ""):
                    impact = parse_scale(overall.get(key), "impact")
                    break
    return prob, impact


def resolve_prob_impact(dim: RiskDimension, form_data: Optional[dict] = None) -> dict:
    form_data = form_data or {}
    sheet = _sheet_lookup(form_data, dim.name)
    prob = parse_scale(sheet.get(PROB_FIELD) or sheet.get("发生概率") or sheet.get("发生可能性"), "prob")
    impact = parse_scale(sheet.get(IMPACT_FIELD) or sheet.get("影响程度") or sheet.get("影响"), "impact")
    if prob is None or impact is None:
        o_prob, o_impact = _from_overall_sheet(form_data, dim.name)
        prob = prob if prob is not None else o_prob
        impact = impact if impact is not None else o_impact
    if prob is not None and impact is not None:
        source = "independent"
    else:
        s_prob, s_impact = suggest_pi(dim)
        prob = prob if prob is not None else s_prob
        impact = impact if impact is not None else s_impact
        source = "suggested"
    rating_n = int(prob) * int(impact)
    if rating_n >= 20:
        rating = "极高"
    elif rating_n >= 12:
        rating = "高"
    elif rating_n >= 6:
        rating = "中"
    else:
        rating = "低"
    return {
        "dimension": dim.name,
        "probability": int(prob),
        "impact": int(impact),
        "score": dim.score,
        "level": dim.level.value if hasattr(dim.level, "value") else str(dim.level),
        "source": source,
        "matrix_rating": rating,
        "product": rating_n,
    }


def build_heatmap_matrix(result: AssessmentResult, form_data: Optional[dict] = None) -> List[dict]:
    form_data = form_data or result.all_raw_data or {}
    return [resolve_prob_impact(d, form_data) for d in result.dimensions.values()]


def heatmap_meta(cells: List[dict]) -> dict:
    independent = sum(1 for c in cells if c.get("source") == "independent")
    suggested = sum(1 for c in cells if c.get("source") == "suggested")
    return {
        "independent_count": independent,
        "suggested_count": suggested,
        "note": (
            "矩阵来自各维度独立填写的可能性×影响（1–5）；综合评分来自规则引擎，二者不互相推导。"
            + (
                " 未填单元格已用建议值占位，不得视为已完成 ISO 31010 独立估计。"
                if suggested
                else " 全部单元格均为独立估计。"
            )
        ),
    }


def inject_matrix_fields(template: Dict[str, Dict]) -> Dict[str, Dict]:
    """Web 录入模板补上 P/I 字段（已有则跳过）。"""
    for sheet, info in (template or {}).items():
        if not is_matrix_sheet(sheet):
            continue
        fields = list(info.get("fields") or [])
        names = {str(f.get("name")) for f in fields}
        if PROB_FIELD in names and IMPACT_FIELD in names:
            continue
        seq = max((int(f.get("seq") or 0) for f in fields), default=0)
        extra = []
        for spec in MATRIX_FIELDS:
            if spec.get("is_group"):
                continue
            seq += 1
            extra.append({
                "seq": seq,
                "name": spec["name"],
                "type": "下拉",
                "is_key": False,
                "options": list(spec.get("choices") or []),
                "hint": spec.get("note") or "",
            })
        info["fields"] = fields + extra
        template[sheet] = info
    return template
