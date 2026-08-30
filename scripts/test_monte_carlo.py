# -*- coding: utf-8 -*-
import os
import sys

ROOT = r"D:\_Work\01_Projects\enterprise-risk-assessment"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from risk_engine import AssessmentResult, RiskDimension, RiskLevel
from risk_quant import run_monte_carlo


def main() -> None:
    dims = {
        "财务风险": RiskDimension(
            "财务风险", 20, 2.4, RiskLevel.from_score(2.4), ["负债偏高"], ["流动性"], {}
        ),
        "经营风险": RiskDimension(
            "经营风险", 15, 2.8, RiskLevel.from_score(2.8), ["客户集中"], ["集中度"], {}
        ),
        "安全生产风险": RiskDimension(
            "安全生产风险", 10, 1.6, RiskLevel.from_score(1.6), [], [], {}
        ),
    }
    basic = {
        "企业名称": "DEMO-测试",
        "年营业额(万元)": "86000",
        "资产总额(万元)": "124000",
    }
    res = AssessmentResult(
        "DEMO-测试", 2.3, RiskLevel.from_score(2.3), dims,
        {"企业基本信息": basic}, "2026年08月21日",
    )
    mc = run_monte_carlo(
        res, iterations=1500, confidence_pct=55, seed=7, basic=basic,
    )
    blob = mc["interpretation"] + mc["methodology"] + (mc.get("disclaimer") or "")
    assert "尾部期望损失" not in blob, blob
    assert mc.get("money_track") and mc["money_track"].get("revenue_pressure")
    assert mc.get("sensitivity")
    empty = run_monte_carlo(res, basic={}, seed=1)
    assert empty.get("money_track") is None
    print("mean", mc["mean_score"], "p95", mc["score_p95"], "ci", mc["confidence_interval_80"])
    print("sens", [s["dimension"] for s in mc["sensitivity"]])
    print("rev_p50", mc["money_track"]["revenue_pressure"]["p50"])
    print("OK")


if __name__ == "__main__":
    main()
