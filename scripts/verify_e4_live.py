# -*- coding: utf-8 -*-
"""生产验收：红旗登录；DEMO 三次快照后 KPI 趋势非空。不打印口令。"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
USERS = os.path.join(ROOT, "web_app", "data", "users.json")


def http(method, path, body=None, cookie=None):
    url = "http://127.0.0.1:8091" + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return resp.status, payload, resp.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw[:200]}
        return exc.code, payload, exc.headers


def main():
    rows = json.loads(open(USERS, encoding="utf-8").read())
    users = rows.get("users") if isinstance(rows, dict) else rows
    admin = next((u for u in users if str(u.get("role")) == "admin"), users[0])
    code, body, hdrs = http("POST", "/api/auth/login", {
        "username": admin["username"], "password": admin["password"],
    })
    assert code == 200 and body.get("ok"), body.get("error", "login failed")
    cookie = ""
    setc = hdrs.get("Set-Cookie") or ""
    if "erm_session=" in setc:
        cookie = "erm_session=" + setc.split("erm_session=")[1].split(";")[0]
    company = "DEMO-江东精密制造"
    code, ts, _ = http("GET", "/api/kpi/timeseries?company=" + urllib.parse.quote(company), cookie=cookie)
    assert code == 200, ts
    analysis = ts.get("analysis") or {}
    assert analysis.get("has_trend"), analysis
    assert analysis.get("kpi_trends"), analysis
    print("E4 live ok", company, "snaps", analysis.get("snapshot_count"), "kpis", len(analysis.get("kpi_trends") or []))


if __name__ == "__main__":
    main()
