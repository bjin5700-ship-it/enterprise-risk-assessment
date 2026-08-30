# -*- coding: utf-8 -*-
import os
import sys
import tempfile
from pathlib import Path

ROOT = r"D:\_Work\01_Projects\enterprise-risk-assessment"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["ERM_AUTH_MODE"] = "off"
os.environ.pop("ERM_DATABASE_URL", None)
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ERM_MINIO_ENDPOINT", None)
os.environ.pop("MINIO_ENDPOINT", None)


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="erm-e2-")
    os.environ["ERM_DATA_DIR"] = tmp
    from erm_store import (
        add_history_record,
        backend_name,
        delete_assessment,
        get_assessment,
        init_store,
        load_history,
        upsert_assessment,
    )
    from erm_objects import put_file, using_minio

    assert backend_name() == "json"
    init_store()
    rec = add_history_record(
        {"company_name": "测-仓储企业", "overall_score": 2.1, "overall_level": "中等风险", "all_raw_data": {}},
        note="e2-test",
    )
    assert rec["id"]
    rows = load_history()
    assert any(r["id"] == rec["id"] for r in rows), rows
    got = get_assessment(rec["id"])
    assert got and got["company_name"] == "测-仓储企业"
    upsert_assessment({**rec, "note": "updated"})
    assert get_assessment(rec["id"])["note"] == "updated"
    demo = upsert_assessment({
        "id": "demo-x",
        "company_name": "DEMO-测试",
        "overall_score": 1.5,
        "overall_level": "低风险",
        "note": "演示",
        "assessment": {"company_name": "DEMO-测试"},
    })
    assert demo["id"] == "demo-x"
    assert using_minio() is False
    sample = Path(tmp) / "sample.txt"
    sample.write_text("hello-e2", encoding="utf-8")
    ev = put_file(str(sample), kind="export", content_type="text/plain", company_name="测-仓储企业")
    assert ev["storage"] == "local"
    assert ev["id"]
    assert delete_assessment(rec["id"]) is True
    assert get_assessment(rec["id"]) is None
    print("OK e2-store", tmp)


if __name__ == "__main__":
    main()
