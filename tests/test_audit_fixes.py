from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web_app"))


def test_credit_code_checksum():
    from credit_code import make_credit_code, validate_credit_code

    code = make_credit_code("91110000MA0123456")
    ok, msg = validate_credit_code(code)
    assert ok, msg
    bad = code[:-1] + ("0" if code[-1] != "0" else "1")
    ok, _ = validate_credit_code(bad)
    assert not ok


def test_honesty_block_not_low_risk():
    from risk_honesty import INSUFFICIENT, apply_honesty_gate

    payload = {
        "company_name": "审计空表",
        "overall_score": 1.0,
        "overall_level": "低风险",
        "warnings": [],
        "data_quality_gate": {
            "gate": "block",
            "gate_label": "数据不足 · 不建议直接决策",
            "confidence_score": 5,
        },
        "analytics": {
            "data_quality_gate": {"gate": "block", "gate_label": "数据不足 · 不建议直接决策", "confidence_score": 5},
            "kri_dashboard": {"summary": {"grey": 15, "green": 0, "amber": 0, "red": 0}, "health_score": 70},
            "bayesian_update": {"has_prior": True, "overall_trend": "改善", "interpretation": "改善"},
            "phase1_enhancement": {
                "industry_benchmark": {"percentile": {"better_than_peers_pct": 96.5, "band": "优于多数同业（低风险区）"}},
                "summary_lines": [],
            },
            "deep_analysis": {
                "board_recommendations": [{"detail": "当前风险整体可控", "title": "维持"}],
                "industry_benchmark": {"percentile": {"better_than_peers_pct": 96.5, "band": "x"}},
            },
        },
        "executive_brief": {"headline": "审计空表 综合风险 1.00/4.00（低风险）", "risk_level": "低风险"},
        "phase1_enhancement": {
            "industry_benchmark": {"percentile": {"better_than_peers_pct": 96.5, "band": "优于多数同业（低风险区）"}},
        },
        "bayesian_update": {"has_prior": True, "overall_trend": "改善"},
    }
    apply_honesty_gate(payload)
    assert payload["overall_level"] == INSUFFICIENT
    assert payload["scoring_suppressed"] is True
    assert payload["analytics"]["kri_dashboard"]["health_score"] is None
    assert payload["phase1_enhancement"]["industry_benchmark"]["percentile"]["better_than_peers_pct"] is None
    assert payload["bayesian_update"].get("skipped") is True
    assert "低风险" not in payload["executive_brief"]["headline"]


def test_sanitize_windows_csv_path(tmp_path, monkeypatch):
    from data_integration import sanitize_schedule_inplace, _sample_csv_path

    sample = _sample_csv_path()
    assert os.path.isfile(sample)
    cfg = {
        "jobs": [
            {
                "id": "default",
                "source_type": "csv_file",
                "source_path": r"D:\_Work\foo\erp_sample.csv",
                "enabled": True,
            }
        ]
    }
    assert sanitize_schedule_inplace(cfg) is True
    assert cfg["jobs"][0]["source_path"] == sample


def test_erp_schema_rejects_negative_current_ratio():
    from schema_validate import validate_erp_payload

    errs, _ = validate_erp_payload({"current_ratio": -1})
    assert errs


def test_suggest_fields_from_text():
    from evidence_extract import suggest_fields_from_text
    from credit_code import make_credit_code

    code = make_credit_code("91110000MA0123456")
    text = f"企业名称：示例科技有限公司\n统一社会信用代码：{code}\n资产负债率 66.5%\n流动比率 1.2"
    items = suggest_fields_from_text(text, source="demo.pdf")
    fields = {(i["sheet"], i["field"]): i["value"] for i in items}
    assert ("企业基本信息", "统一社会信用代码") in fields
    assert ("财务风险", "资产负债率(%)") in fields
