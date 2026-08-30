# -*- coding: utf-8 -*-
"""E3 审批与残余风险接受：P0 无审批不能关闭；完成率来自持久化状态。"""
from __future__ import annotations

import os
import shutil
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

def _data_dir() -> str:
    overflow = r"F:\SystemOverflow\Temp\erm-e3-test"
    try:
        os.makedirs(overflow, exist_ok=True)
        return overflow
    except OSError:
        path = os.path.join(ROOT, "web_app", "data", "_e3_test")
        os.makedirs(path, exist_ok=True)
        return path


def main():
    data = _data_dir()
    os.environ["ERM_DATA_DIR"] = data
    os.environ["ERM_DATABASE_URL"] = ""
    os.environ["DATABASE_URL"] = ""
    os.environ["ERM_AUTH_MODE"] = "off"

    from risk_workflow import apply_status, completion_stats, overlay_workflow, ensure_generated_items

    assessor = SimpleNamespace(username="assess", role="assessor")
    approver = SimpleNamespace(username="approve", role="approver")
    company = "E3-审批测试企业"

    rec = {
        "id": "e3test",
        "company_name": company,
        "assessment": {
            "company_name": company,
            "action_plans": {
                "action_items": [
                    {"id": "ACT-p0", "title": "P0 行动", "priority": "P0", "dimension": "财务风险", "owner": "CFO"},
                    {"id": "ACT-p2", "title": "P2 行动", "priority": "P2", "dimension": "经营风险", "owner": "COO"},
                ]
            },
            "deep_analysis": {
                "risk_register": [
                    {"id": "R-high", "dimension": "财务风险", "risk_description": "杠杆过高", "risk_rating": "高", "owner": "CFO"},
                    {"id": "R-low", "dimension": "环境风险", "risk_description": "一般", "risk_rating": "低", "owner": "EHS"},
                ]
            },
            "closed_loop": {"remediation_verification": {"actions_tracked": {"total": 2, "completed": 0, "completion_pct": 0}}},
        },
    }
    ensure_generated_items(rec)

    try:
        apply_status(kind="action", item_id="ACT-p0", company_name=company, status="closed", user=assessor, priority="P0")
        raise SystemExit("P0 评估人关闭应当失败")
    except PermissionError as e:
        assert "审批" in str(e)

    try:
        apply_status(
            kind="action", item_id="ACT-p0", company_name=company, status="closed",
            user=approver, priority="P0",
        )
        raise SystemExit("P0 无理由应当失败")
    except PermissionError as e:
        assert "理由" in str(e) or "复评" in str(e)

    apply_status(
        kind="action", item_id="ACT-p0", company_name=company, status="closed",
        user=approver, priority="P0", reason="残余风险可接受，已投保", review_date="2026-11-21",
    )
    apply_status(kind="action", item_id="ACT-p2", company_name=company, status="closed", user=assessor, priority="P2")

    try:
        apply_status(kind="register", item_id="R-high", company_name=company, status="closed", user=assessor, priority="P0")
        raise SystemExit("高风险登记项评估人关闭应当失败")
    except PermissionError:
        pass

    apply_status(
        kind="register", item_id="R-high", company_name=company, status="closed",
        user=approver, priority="P0", reason="董事会接受残余风险", review_date="2026-12-01",
    )
    apply_status(kind="register", item_id="R-low", company_name=company, status="treating", user=assessor)

    stats = completion_stats(company, rec["assessment"]["action_plans"]["action_items"])
    assert stats["completed"] == 2, stats
    assert stats["completion_pct"] == 100, stats
    assert stats["p0_closed"] == 1, stats
    assert stats["register_closed"] >= 1, stats

    overlay_workflow(rec["assessment"])
    tracked = rec["assessment"]["closed_loop"]["remediation_verification"]["actions_tracked"]
    assert tracked["source"] == "persisted"
    assert tracked["completion_pct"] == 100
    print("E3 workflow ok", stats)

    shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
