# -*- coding: utf-8 -*-
import os
import sys

ROOT = r"D:\_Work\01_Projects\enterprise-risk-assessment"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from risk_engine import AssessmentResult, RiskDimension, RiskLevel
from risk_matrix import build_heatmap_matrix, parse_scale


def test_parse() -> None:
    assert parse_scale("4 很可能", "prob") == 4
    assert parse_scale("不太可能", "prob") == 2
    assert parse_scale("较高(60-80%)", "prob") == 4
    assert parse_scale("极严重", "impact") == 5


def test_independent_not_tied_to_score() -> None:
    dims = {
        "财务风险": RiskDimension("财务风险", 20, 2.8, RiskLevel.from_score(2.8), ["a"], ["k1", "k2"], {
            "可能性(1-5)": "3 可能", "影响(1-5)": "5 极严重",
        }),
        "人力资源风险": RiskDimension("人力资源风险", 8, 2.8, RiskLevel.from_score(2.8), ["b"], ["k1"], {
            "可能性(1-5)": "5 几乎确定", "影响(1-5)": "2 轻微",
        }),
    }
    form = {
        "财务风险": dims["财务风险"].raw_data,
        "人力资源风险": dims["人力资源风险"].raw_data,
    }
    res = AssessmentResult("T", 2.8, RiskLevel.from_score(2.8), dims, form, "2026")
    cells = {c["dimension"]: c for c in build_heatmap_matrix(res, form)}
    assert cells["财务风险"]["probability"] == 3 and cells["财务风险"]["impact"] == 5
    assert cells["人力资源风险"]["probability"] == 5 and cells["人力资源风险"]["impact"] == 2
    assert cells["财务风险"]["source"] == "independent"
    assert cells["财务风险"]["score"] == cells["人力资源风险"]["score"]
    src = open(os.path.join(ROOT, "risk_analytics.py"), encoding="utf-8").read()
    assert "int(d.score * 0.85" not in src
    print("OK", {k: (v["probability"], v["impact"], v["source"]) for k, v in cells.items()})


if __name__ == "__main__":
    test_parse()
    test_independent_not_tied_to_score()
