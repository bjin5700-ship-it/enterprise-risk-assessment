# -*- coding: utf-8 -*-
"""生产验收 E3：匿名不能改状态；P0 无理由不能关；审批后完成率回写。不打印密钥。"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ENV = os.path.join(ROOT, "web_app", ".env")


def _load_env():
    if not os.path.isfile(ENV):
        return
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def http(method, path, body=None, headers=None, cookie=None):
    url = "http://127.0.0.1:8091" + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"_raw": raw[:200]}
            return resp.status, payload, resp.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw[:200]}
        return exc.code, payload, exc.headers


def main():
    _load_env()
    token = os.environ.get("ERM_ADMIN_TOKEN") or ""
    if not token:
        raise SystemExit("missing admin token")

    code, body, _ = http("POST", "/api/actions/track", {
        "company_name": "DEMO-江东精密制造",
        "action_id": "ACT-dummy",
        "status": "closed",
        "priority": "P0",
    })
    assert code in (401, 403), code

    code, body, hdrs = http("POST", "/api/auth/login", {"username": "admin", "password": token})
    assert code == 200 and body.get("ok"), body.get("error", "login failed")
    cookie = ""
    setc = hdrs.get("Set-Cookie") or ""
    if "erm_session=" in setc:
        cookie = "erm_session=" + setc.split("erm_session=")[1].split(";")[0]

    code, hist, _ = http("GET", "/api/history", cookie=cookie)
    assert code == 200
    rows = (hist.get("records") if isinstance(hist, dict) else hist) or []
    demo = next((r for r in rows if str(r.get("company_name") or "").startswith("DEMO-")), None)
    assert demo, "no demo record"
    company = demo["company_name"]
    code, full, _ = http("GET", "/api/history/" + demo["id"], cookie=cookie)
    assert code == 200
    assessment = full.get("assessment") or full
    items = (assessment.get("action_plans") or {}).get("action_items") or []
    p0 = next((a for a in items if a.get("priority") == "P0"), items[0] if items else None)
    assert p0, "no action item"

    code, denied, _ = http("POST", "/api/actions/track", {
        "company_name": company, "action_id": p0["id"], "status": "closed", "priority": "P0",
    }, cookie=cookie)
    assert code == 403, (code, denied)

    code, ok, _ = http("POST", "/api/actions/track", {
        "company_name": company, "action_id": p0["id"], "status": "closed", "priority": "P0",
        "reason": "E3 验收：残余风险已投保并经审批人确认", "review_date": "2026-11-21",
    }, cookie=cookie)
    assert code == 200 and ok.get("ok"), ok

    code, wf, _ = http("GET", "/api/workflow?company=" + urllib.parse.quote(company), cookie=cookie)
    assert code == 200
    comp = (wf.get("completion") or {})
    assert comp.get("completed", 0) >= 1, comp
    print("E3 live ok", company, "completion", comp.get("completion_pct"), comp.get("completed"), "/", comp.get("total"))


if __name__ == "__main__":
    main()
