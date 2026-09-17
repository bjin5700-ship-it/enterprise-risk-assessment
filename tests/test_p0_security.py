from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_solution_program_structure():
    from risk_engine import AssessmentResult, RiskDimension, RiskLevel
    from risk_solution_program import build_solution_program

    dim = RiskDimension(
        name="财务风险", weight=0.12, score=3.1, level=RiskLevel.HIGH, key_risks=["流动性偏紧"], findings=[],
    )
    result = AssessmentResult(
        company_name="测试企业",
        overall_score=2.8,
        overall_level=RiskLevel.HIGH,
        report_date="2026-09-17",
        dimensions={"财务风险": dim},
        all_raw_data={},
    )
    prog = build_solution_program(result, action_plans={"items": []}, deep_solutions=[], external_evidence={})
    assert prog["treatment_portfolio"]
    assert prog["roadmap_90d"]
    assert "ISO 31000" in prog["executive_summary"] or "4T" in prog["executive_summary"]


def test_rate_limit_blocks_after_max():
    from erm_rate_limit import check_allowed, client_key, record_failure, record_success

    os.environ["ERM_LOGIN_MAX_ATTEMPTS"] = "3"
    os.environ["ERM_LOGIN_WINDOW_SECONDS"] = "900"
    key = client_key("127.0.0.1", "audit-user")
    record_success(key)
    for _ in range(3):
        record_failure(key)
    allowed, retry = check_allowed(key)
    assert not allowed
    assert retry > 0


def test_users_file_has_no_plain_password():
    import json

    users_path = ROOT / "web_app" / "data" / "users.json"
    data = json.loads(users_path.read_text(encoding="utf-8"))
    for row in data.get("users") or []:
        assert not row.get("password"), "plaintext password must not be committed"
        assert row.get("password_hash") or os.environ.get("ERM_SKIP_USER_HASH_TEST")
