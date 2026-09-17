from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from risk_timeline import build_change_matrix, build_company_timeline, diff_two_assessments


def _assess(name, score, at, hid):
    return {
        "id": hid,
        "company_name": name,
        "assessed_at": at,
        "assessment": {
            "company_name": name,
            "assessed_at": at,
            "overall_score": score,
            "overall_level": "中等风险",
            "dimensions": [
                {"name": "财务风险", "score": score, "level": "中等风险"},
                {"name": "运营风险", "score": score - 0.5, "level": "低风险"},
            ],
        },
    }


def test_timeline_and_matrix():
    hist = [
        _assess("Acme", 2.0, "2026-01-01T10:00:00", "a"),
        _assess("Acme", 2.4, "2026-06-01T10:00:00", "b"),
    ]
    tl = build_company_timeline(hist, "Acme")
    assert tl["period_count"] == 2
    assert tl["matrix"]["overall_row"]["cells"][1]["delta_from_prev"] == 0.4


def test_diff():
    cur = _assess("Acme", 2.4, "2026-06-01", "b")["assessment"]
    pri = _assess("Acme", 2.0, "2026-01-01", "a")["assessment"]
    d = diff_two_assessments(cur, pri)
    assert d["has_prior"] and d["overall_delta"] == 0.4
