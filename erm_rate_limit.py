# -*- coding: utf-8 -*-
"""Simple in-process login rate limiting (P0)."""
from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock
from typing import DefaultDict, Tuple

_LOCK = Lock()
_BUCKETS: DefaultDict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))


def _max_attempts() -> int:
    try:
        return max(3, int(os.environ.get("ERM_LOGIN_MAX_ATTEMPTS", "12")))
    except ValueError:
        return 12


def _window_seconds() -> float:
    try:
        return max(60.0, float(os.environ.get("ERM_LOGIN_WINDOW_SECONDS", "900")))
    except ValueError:
        return 900.0


def _lockout_seconds() -> float:
    try:
        return max(60.0, float(os.environ.get("ERM_LOGIN_LOCKOUT_SECONDS", "600")))
    except ValueError:
        return 600.0


def client_key(ip: str, username: str = "") -> str:
    ip = (ip or "unknown").strip()
    user = (username or "").strip().lower()
    return f"{ip}|{user}" if user else ip


def check_allowed(key: str) -> Tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    now = time.monotonic()
    max_fail = _max_attempts()
    window = _window_seconds()
    lockout = _lockout_seconds()
    with _LOCK:
        fails, until = _BUCKETS[key]
        if until > now:
            return False, int(until - now) + 1
        if fails >= max_fail and (now - until) < window:
            _BUCKETS[key] = (fails, now + lockout)
            return False, int(lockout)
        if fails > 0 and (now - until) > window:
            _BUCKETS[key] = (0, now)
        return True, 0


def record_failure(key: str) -> None:
    now = time.monotonic()
    with _LOCK:
        fails, _ = _BUCKETS[key]
        _BUCKETS[key] = (fails + 1, now)


def record_success(key: str) -> None:
    with _LOCK:
        _BUCKETS.pop(key, None)
