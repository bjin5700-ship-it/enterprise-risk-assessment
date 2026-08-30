# -*- coding: utf-8 -*-
"""定时 ERP / 财务数据同步调度器 — APScheduler，失败则回退线程轮询。"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()
_last_tick = ""
_aps_scheduler = None
_backend = "none"


def _tick() -> None:
    global _last_tick
    try:
        from data_integration import execute_due_jobs_parallel, load_sync_schedule
        load_sync_schedule()
        _last_tick = datetime.now().isoformat()
        out = execute_due_jobs_parallel(force=False)
        errs = [r for r in (out.get("results") or []) if r.get("status") == "error"]
        if errs:
            try:
                from erm_store import audit
                audit(
                    "scheduler.job_failed",
                    "sync_job",
                    str(errs[0].get("job_id") or ""),
                    {"count": len(errs), "message": str(errs[0].get("message") or "")[:400]},
                )
            except Exception:
                pass
        try:
            from risk_tasks import scan_due_tasks
            scan_due_tasks()
        except Exception as scan_exc:
            try:
                from erm_store import audit
                audit("scheduler.tick_failed", "reassessment_task", "", {"error": str(scan_exc)[:400]})
            except Exception:
                pass
    except Exception as exc:
        print(f"[scheduler] tick error: {exc}")
        try:
            from erm_store import audit
            audit("scheduler.tick_failed", "scheduler", "", {"error": str(exc)[:400]})
        except Exception:
            pass


def start_background_scheduler(interval_seconds: int = 60) -> None:
    global _scheduler_thread, _aps_scheduler, _backend
    if _aps_scheduler is not None or (_scheduler_thread and _scheduler_thread.is_alive()):
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        sched = BackgroundScheduler(timezone="Asia/Shanghai")
        sched.add_job(
            _tick,
            IntervalTrigger(seconds=max(30, int(interval_seconds))),
            id="erm-sync",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        sched.start()
        _aps_scheduler = sched
        _backend = "apscheduler"
        print("[scheduler] APScheduler started")
        threading.Thread(target=_tick, name="erm-sync-first-tick", daemon=True).start()
        return
    except Exception as exc:
        print(f"[scheduler] APScheduler unavailable ({exc}), fallback thread")

    def _loop():
        while not _scheduler_stop.is_set():
            _tick()
            _scheduler_stop.wait(interval_seconds)

    _scheduler_thread = threading.Thread(target=_loop, name="erm-sync-scheduler", daemon=True)
    _scheduler_thread.start()
    _backend = "thread"


def stop_background_scheduler() -> None:
    global _aps_scheduler
    _scheduler_stop.set()
    if _aps_scheduler is not None:
        try:
            _aps_scheduler.shutdown(wait=False)
        except Exception:
            pass
        _aps_scheduler = None


def scheduler_status() -> dict:
    aps_on = False
    if _aps_scheduler is not None:
        try:
            aps_on = bool(_aps_scheduler.running)
        except Exception:
            aps_on = False
    alive = aps_on or bool(_scheduler_thread and _scheduler_thread.is_alive())
    return {"running": alive, "last_tick": _last_tick, "backend": _backend}
