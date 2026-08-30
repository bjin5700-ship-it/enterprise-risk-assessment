# -*- coding: utf-8 -*-
"""E4：少于 3 次显示样本不足；3 次后 KPI 趋势非空。"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "web_app"))


def _data_dir() -> str:
    overflow = r"F:\SystemOverflow\Temp\erm-e4-test"
    try:
        os.makedirs(overflow, exist_ok=True)
        return overflow
    except OSError:
        path = os.path.join(ROOT, "web_app", "data", "_e4_test")
        os.makedirs(path, exist_ok=True)
        return path


def main():
    data = _data_dir()
    os.environ["ERM_DATA_DIR"] = data
    os.environ["ERM_DATABASE_URL"] = ""
    os.environ["DATABASE_URL"] = ""
    path = os.path.join(data, "kpi_timeseries.json")

    from risk_engine import AssessmentResult, RiskLevel, RiskDimension
    from risk_timeseries import analyze_timeseries, record_assessment_snapshot

    dim = RiskDimension(name="财务风险", score=2.2, level=RiskLevel.MEDIUM, weight=0.1, findings=[], key_risks=[], raw_data={})
    form = {"企业基本信息": {"企业名称": "E4-时序测试"}, "财务风险": {"资产负债率(%)": "70"}}
    result = AssessmentResult(
        company_name="E4-时序测试",
        overall_score=2.1,
        overall_level=RiskLevel.MEDIUM,
        report_date="2026-08-21",
        dimensions={"财务风险": dim},
        all_raw_data=form,
    )

    a1 = analyze_timeseries("E4-时序测试", path)
    assert a1["has_trend"] is False and "样本不足" in a1["message"]

    base = datetime(2026, 1, 1)
    for i in range(3):
        form["财务风险"]["资产负债率(%)"] = str(70 - i * 2)
        record_assessment_snapshot(
            result, form, assessment_id=f"e4-{i}", path=path,
            assessed_at=(base + timedelta(days=i * 30)).isoformat(),
        )
    a3 = analyze_timeseries("E4-时序测试", path)
    assert a3["has_trend"] is True, a3
    assert a3["kpi_trends"], a3
    assert a3["score_trend"], a3
    print("E4 timeseries ok", a3["snapshot_count"], "kpi", a3["kpi_trends"][0]["kpi"], a3["kpi_trends"][0]["delta"])
    shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
