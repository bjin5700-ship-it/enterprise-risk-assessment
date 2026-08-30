# -*- coding: utf-8 -*-
import os
import sys

ROOT = r"D:\_Work\01_Projects\enterprise-risk-assessment"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from credit_code import validate_credit_code
from data_external_risk import DEMO_MFG_USCC, lookup_external_risk, records_to_suggestions
from risk_engine import AssessmentResult, RiskDimension, RiskLevel, score_legal_compliance


def main() -> None:
    ok, _ = validate_credit_code(DEMO_MFG_USCC)
    assert ok, DEMO_MFG_USCC
    none = lookup_external_risk("", "某普通企业")
    assert none["provider"] in ("none", "demo_fixture")
    assert none["records"] == []
    assert "未接外部源" in (none["note"] or "") or none["connected"] is False

    demo = lookup_external_risk(DEMO_MFG_USCC, "DEMO-江东精密制造")
    assert demo["records"], demo
    assert demo["does_not_score"] is True
    assert any(r["category"] == "lawsuit" for r in demo["records"])
    sug = records_to_suggestions(demo["records"])
    assert any(s["field"] == "在审案件数量" for s in sug)

    form = {"在审案件数量": "2", "行政处罚次数(近三年)": "1"}
    baseline = score_legal_compliance(form).score
    with_extra = dict(form)
    with_extra["_external_records"] = demo["records"]
    after = score_legal_compliance(with_extra).score
    assert after == baseline, (after, baseline)
    print("OK", DEMO_MFG_USCC, "records", len(demo["records"]), "legal", baseline)


if __name__ == "__main__":
    main()
