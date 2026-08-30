# -*- coding: utf-8 -*-
"""维度统计相关矩阵 — ISO 31010 关联分析"""

from __future__ import annotations

from typing import List

from risk_engine import AssessmentResult

# 业务关联先验（无历史时用于增强相关估计）
PRIOR_LINKS = [
    ("财务风险", "信用风险", 0.75),
    ("财务风险", "经营风险", 0.65),
    ("供应链风险", "生产运营风险", 0.70),
    ("法律与合规风险", "战略与声誉风险", 0.60),
    ("技术与信息安全风险", "数据隐私合规风险", 0.80),
    ("公司治理风险", "关联方与集团风险", 0.65),
    ("行业与市场风险", "经营风险", 0.70),
    ("税务风险", "法律与合规风险", 0.55),
    ("人力资源风险", "经营风险", 0.50),
    ("环境风险", "战略与声誉风险", 0.55),
]


def _text_tokens(dim) -> set:
    text = " ".join((dim.key_risks or []) + (dim.findings or []) + [dim.name])
    return set(text.replace("，", " ").replace("、", " ").split())


def _pair_correlation(a, b) -> float:
    if a.name == b.name:
        return 1.0
    score_sim = max(0.0, 1.0 - abs(a.score - b.score) / 3.0)
    ta, tb = _text_tokens(a), _text_tokens(b)
    overlap = len(ta & tb) / max(1, len(ta | tb))
    prior = 0.0
    for x, y, w in PRIOR_LINKS:
        if (a.name, b.name) in ((x, y), (y, x)):
            prior = w
            break
    raw = score_sim * 0.45 + overlap * 0.25 + prior * 0.30
    if a.score >= 2.3 and b.score >= 2.3:
        raw = min(0.98, raw + 0.08)
    return round(min(0.98, max(0.05, raw)), 2)


def build_correlation_matrix(result: AssessmentResult) -> dict:
    dims = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)
    labels = [d.name for d in dims]
    matrix: List[List[float]] = []
    high_pairs = []

    for i, da in enumerate(dims):
        row = []
        for j, db in enumerate(dims):
            c = _pair_correlation(da, db)
            row.append(c)
            if i < j and c >= 0.55 and da.score >= 2.0 and db.score >= 2.0:
                high_pairs.append({
                    "dim_a": da.name,
                    "dim_b": db.name,
                    "correlation": c,
                    "scores": f"{da.score:.2f} / {db.score:.2f}",
                    "strength": "强" if c >= 0.72 else "中",
                })
    high_pairs.sort(key=lambda x: x["correlation"], reverse=True)

    return {
        "labels": labels,
        "matrix": matrix,
        "high_pairs": high_pairs[:10],
        "methodology": "评分邻近 + 文本共现 + 行业先验路径 · 供热力图与传导验证",
    }
