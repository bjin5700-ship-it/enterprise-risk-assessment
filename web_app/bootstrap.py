# -*- coding: utf-8 -*-
"""应用启动引导 — 调度器、生产环境初始化（WSGI / Waitress 入口调用一次）"""

from __future__ import annotations

import os

_bootstrapped = False


def init_server() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True

    _env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(_env):
        try:
            from dotenv import load_dotenv
            load_dotenv(_env)
        except ImportError:
            pass

    try:
        from erm_store import init_store
        info = init_store()
        print(f"[bootstrap] store {info}")
    except Exception as exc:
        print(f"[bootstrap] store init failed: {exc}")

    if os.environ.get("ERM_DISABLE_SCHEDULER") == "1":
        return
    try:
        from sync_scheduler import start_background_scheduler
        interval = int(os.environ.get("ERM_SCHEDULER_INTERVAL", "60"))
        start_background_scheduler(interval_seconds=interval)
    except Exception as exc:
        print(f"[bootstrap] scheduler not started: {exc}")
