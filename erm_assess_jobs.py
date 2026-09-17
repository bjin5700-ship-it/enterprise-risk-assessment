"""Background ERM assessments — avoids HTTP timeouts on large Excel runs."""

from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any, Callable
from urllib import request as urlrequest

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def _now() -> float:
    return time.time()


def create_job() -> str:
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "result": None,
            "error": None,
        }
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _JOBS.get(job_id)
        return dict(row) if row else None


def _set_job(job_id: str, **updates: Any) -> None:
    with _LOCK:
        row = _JOBS.get(job_id)
        if not row:
            return
        row.update(updates)
        row["updated_at"] = _now()


def _post_webhook(url: str, payload: dict[str, Any]) -> None:
    url = (url or "").strip()
    if not url:
        return
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urlrequest.urlopen(req, timeout=15)


def run_job_async(
    job_id: str,
    runner: Callable[[], dict[str, Any]],
    *,
    webhook_url: str = "",
) -> None:
    def _work() -> None:
        _set_job(job_id, status="running")
        try:
            result = runner()
            _set_job(job_id, status="completed", result=result, error=None)
            hook_payload = {"job_id": job_id, "status": "completed", "result": result}
        except Exception as exc:  # noqa: BLE001
            _set_job(job_id, status="failed", error=str(exc)[:500])
            hook_payload = {"job_id": job_id, "status": "failed", "error": str(exc)[:500]}
        try:
            _post_webhook(webhook_url, hook_payload)
        except Exception:
            pass

    threading.Thread(target=_work, daemon=True).start()
