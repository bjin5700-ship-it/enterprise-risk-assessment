# -*- coding: utf-8 -*-
"""E5：高风险建议含可点击法规引用；到期复评生成任务。"""
from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _data_dir() -> str:
    overflow = r"F:\SystemOverflow\Temp\erm-e5-test"
    try:
        os.makedirs(overflow, exist_ok=True)
        return overflow
    except OSError:
        path = os.path.join(ROOT, "web_app", "data", "_e5_test")
        os.makedirs(path, exist_ok=True)
        return path


def main():
    data = _data_dir()
    os.environ["ERM_DATA_DIR"] = data
    os.environ["ERM_DATABASE_URL"] = ""
    os.environ["DATABASE_URL"] = ""

    from risk_knowledge import lookup_citations
    cites = lookup_citations("安全生产风险", "化工", limit=2)
    assert cites and cites[0].get("url", "").startswith("http"), cites
    assert any("安全" in c["title"] or "ISO" in c["title"] for c in cites)

    from risk_tasks import list_tasks, sync_from_assessment
    rec = sync_from_assessment("E5-复评测试", assessed_at="2025-01-01T00:00:00", basic={"评估复评周期(天)": "30"}, force_due=True)
    assert rec.get("status") == "open"
    rows = list_tasks(status="open", company="E5-复评测试")
    assert rows, rows
    print("E5 knowledge+tasks ok", cites[0]["title"], "tasks", len(rows))
    shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
