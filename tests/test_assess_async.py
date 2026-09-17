from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_assess_job_lifecycle():
    from erm_assess_jobs import create_job, get_job, run_job_async

    job_id = create_job()
    run_job_async(job_id, lambda: {"ok": True, "score": 1.0}, webhook_url="")
    deadline = time.time() + 5
    status = "queued"
    while time.time() < deadline:
        row = get_job(job_id)
        assert row is not None
        status = row["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert status == "completed"
    assert get_job(job_id)["result"]["ok"] is True
