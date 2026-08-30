# -*- coding: utf-8 -*-
"""系统深度巡检 — 模块导入、API、导出、闭环全链路"""
from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from typing import Any, Callable, List, Tuple
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web_app")
sys.path.insert(0, ROOT)
sys.path.insert(0, WEB)

BASE = os.environ.get("ERM_AUDIT_URL", "http://127.0.0.1:8088")
FAILURES: List[str] = []
PASSES: List[str] = []


def ok(name: str, detail: str = ""):
    PASSES.append(name)
    print(f"  [OK] {name}" + (f" — {detail}" if detail else ""))


def fail(name: str, err: str):
    FAILURES.append(f"{name}: {err}")
    print(f"  [FAIL] {name}: {err}")


def http(method: str, path: str, body: Any = None, content_type: str = "application/json") -> Tuple[int, Any]:
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        if content_type == "application/json":
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            data = body.encode("utf-8") if isinstance(body, str) else body
            headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def run_check(name: str, fn: Callable):
    try:
        fn()
        ok(name)
    except Exception as exc:
        fail(name, str(exc))
        traceback.print_exc()


def minimal_form(company: str = "AuditTestCo") -> dict:
    form = {"企业基本信息": {"企业名称": company, "所属行业": "制造业"}}
    for s in (
        "经营风险", "财务风险", "生产运营风险", "安全生产风险", "环境风险",
        "法律合规风险", "供应链风险", "技术风险", "人力资源风险", "信用风险",
        "综合评估", "关联方与集团风险", "项目投资风险", "行业政策风险", "税务风险",
    ):
        form[s] = {}
    return form


# ── 1. 模块导入 ──
def check_imports():
    mods = [
        "risk_engine", "risk_analytics", "risk_deep_analysis", "risk_quant",
        "risk_bayesian", "risk_kri", "risk_scenario", "risk_closed_loop",
        "risk_timeseries", "risk_notifications", "risk_mobile_push",
        "data_integration", "erp_oauth", "sync_scheduler", "action_planner",
        "industry_playbooks", "report_word", "report_pdf", "report_html",
        "report_markdown", "solution_generator",
    ]
    for m in mods:
        __import__(m)


# ── 2. 核心评估链路 ──
def check_assessment_pipeline():
    from app import run_assessment_from_form, assessment_to_dict, get_template_fields, compute_form_stats

    form = minimal_form()
    result = run_assessment_from_form(form)
    assert result.company_name == "AuditTestCo"
    template = get_template_fields()
    stats = compute_form_stats(form, template) if template else None
    payload = assessment_to_dict(result, stats=stats)
    assert payload.get("overall_score") is not None
    assert payload.get("analytics")
    assert payload.get("closed_loop") is not None
    assert payload.get("alerts") is not None
    assert payload.get("executive_brief") is not None
    deep = payload.get("deep_analysis") or {}
    assert deep.get("risk_register") is not None
    assert deep.get("monte_carlo") is not None


# ── 3. 闭环 / 时序 / 行动 ──
def check_closed_loop():
    from app import run_assessment_from_form
    from risk_analytics import enrich_assessment_full
    from action_planner import build_action_plans
    from risk_closed_loop import update_action_status

    form = minimal_form("ClosedLoopAudit")
    r = run_assessment_from_form(form)
    plans = build_action_plans(r)
    a1 = enrich_assessment_full(r, None, form["企业基本信息"], action_plans=plans)
    assert a1.get("closed_loop")
    prior = {
        "overall_score": r.overall_score,
        "dimensions": [{"name": d.name, "score": d.score} for d in r.dimensions.values()],
        "assessed_at": "2026-01-01",
    }
    r2 = run_assessment_from_form(form)
    a2 = enrich_assessment_full(r2, None, form["企业基本信息"], prior_assessment=prior, action_plans=plans)
    assert a2["closed_loop"].get("remediation_verification")
    if plans.get("action_items"):
        aid = plans["action_items"][0]["id"]
        update_action_status("ClosedLoopAudit", aid, "completed")
    from risk_timeseries import get_company_timeseries
    ts = get_company_timeseries("ClosedLoopAudit")
    assert ts.get("snapshot_count", 0) >= 1


# ── 4. 导出 ──
def check_exports():
    from app import run_assessment_from_form
    from report_word import WordReportGenerator
    from report_pdf import PDFReportGenerator
    from report_html import HTMLReportGenerator
    from report_markdown import MarkdownReportGenerator

    r = run_assessment_from_form(minimal_form("ExportDemo"))
    out = os.path.join(WEB, "exports", "_audit")
    os.makedirs(out, exist_ok=True)
    paths = [
        WordReportGenerator(r, os.path.join(out, "audit.docx")).generate(),
        PDFReportGenerator(r, os.path.join(out, "audit.pdf")).generate(),
        HTMLReportGenerator(r, os.path.join(out, "audit.html")).generate(),
        MarkdownReportGenerator(r, os.path.join(out, "audit.md")).generate(),
    ]
    for p in paths:
        assert os.path.isfile(p) and os.path.getsize(p) > 500, p
    with open(paths[2], encoding="utf-8") as f:
        assert "数据闭环" in f.read() or "评估概要" in f.read()
    with open(paths[3], encoding="utf-8") as f:
        assert len(f.read()) > 200


# ── 5. 集成 / 调度 / OAuth / 移动 ──
def check_integrations():
    from data_integration import parse_csv_financial, load_sync_schedule, execute_due_jobs_parallel
    from erp_oauth import load_oauth_providers, oauth_connection_status, build_authorization_url
    from risk_mobile_push import register_device, list_devices

    csv = "资产负债率,70\n流动比率,1.3\n"
    ext = parse_csv_financial(csv)
    assert "debt_ratio" in ext or len(ext) > 0
    sched = load_sync_schedule()
    assert "jobs" in sched
    providers = load_oauth_providers()
    assert len(providers.get("providers", [])) >= 3
    assert len(oauth_connection_status()) >= 3
    # authorize URL build (no network) — 临时注入 client_id 做结构验证
    from erp_oauth import update_provider
    update_provider("generic", {"client_id": "audit-test-client", "enabled": True})
    port = os.environ.get("ERM_PORT", "8088")
    url = build_authorization_url("generic", f"http://127.0.0.1:{port}/api/integrations/oauth/callback", "test")
    assert "authorization_url" in url and "client_id=" in url["authorization_url"]
    register_device("audit-device", "web", "audit")
    assert list_devices()["total"] >= 1


# ── 6. HTTP API（需服务运行） ──
def check_http_pages():
    for path in ["/ping", "/", "/data-entry", "/report", "/solution"]:
        code, _ = http("GET", path)
        assert code == 200, f"{path} -> {code}"


def check_http_apis():
    code, tpl = http("GET", "/api/template/fields")
    assert code == 200 and isinstance(tpl, dict) and tpl, "template empty"

    form = minimal_form("AuditTestCo")
    code, assess = http("POST", "/api/assess?save_history=1", form)
    assert code == 200, assess
    assert assess.get("overall_score") is not None
    assert assess.get("closed_loop") is not None

    code, sol = http("POST", "/api/solution", form)
    assert code == 200 and sol.get("solutions") is not None

    code, hist = http("GET", "/api/history")
    assert code == 200 and hist.get("records") is not None

    company = "AuditTestCo"
    for path in [
        f"/api/alerts?company={company}",
        f"/api/kpi/timeseries?company={company}",
        "/api/notifications",
        "/api/integrations",
        "/api/integrations/schedule",
        "/api/integrations/oauth/providers",
        "/api/notifications/devices",
        "/api/notifications/mobile-config",
        "/api/notifications/config",
    ]:
        code, body = http("GET", path)
        assert code == 200, f"{path} -> {code} {body}"

    code, _ = http("POST", "/api/notifications/read", {"mark_all": False, "ids": []})
    assert code == 200

    code, snap = http("POST", "/api/monitoring/snapshot", {"form_data": form})
    assert code == 200 and snap.get("kri_dashboard")

    code, scen = http("POST", "/api/scenario", form)
    assert code == 200 and scen.get("scenarios") is not None

    code, quant = http("POST", "/api/quant", {"form_data": form})
    assert code == 200

    csv_body = "资产负债率,65\n流动比率,1.4\n"
    code, csv_res = http("POST", "/api/integrations/csv", csv_body, content_type="text/plain")
    assert code == 200 and csv_res.get("form_data")

    code, fin = http("POST", "/api/integrations/financial", {"form_data": form, "asset_liability_ratio": 68})
    assert code == 200

    code, bayes = http("POST", "/api/bayesian", {"form_data": form})
    assert code == 200 and bayes.get("posterior_overall") is not None

    code, sched_run = http("POST", "/api/integrations/schedule/run")
    assert code == 200

    code, oauth_auth = http("GET", "/api/integrations/oauth/authorize?provider_id=generic&company=TestCo")
    assert code == 200 and oauth_auth.get("authorization_url")

    code, dev = http("POST", "/api/notifications/devices", {
        "token": "audit-sw-device", "platform": "web", "device_name": "audit",
    })
    assert code == 200 and dev.get("ok")

    if assess.get("action_plans", {}).get("action_items"):
        aid = assess["action_plans"]["action_items"][0]["id"]
        code, tr = http("POST", "/api/actions/track", {
            "company_name": company, "action_id": aid, "status": "completed",
        })
        assert code in (200, 401, 403)


def check_http_export():
    form = minimal_form("ExportApiCo")
    for fmt in ("html", "md", "docx", "pdf", "solution-docx"):
        code, _ = http("POST", f"/api/export/{fmt}", form)
        assert code == 200, f"export {fmt} failed"


def check_static_assets():
    for path in ["/static/css/common.css", "/static/js/common.js", "/static/sw.js", "/static/manifest.json"]:
        code, body = http("GET", path)
        assert code == 200, path
        if isinstance(body, str):
            assert len(body) > 100, path


def main():
    print("=" * 60)
    print("  企业风险动态评估系统 — 深度巡检")
    print(f"  服务地址: {BASE}")
    print("=" * 60)

    sections = [
        ("Python 模块导入", check_imports),
        ("评估分析全链路", check_assessment_pipeline),
        ("数据闭环/时序/行动", check_closed_loop),
        ("报告导出 (Word/PDF/HTML/MD)", check_exports),
        ("集成/OAuth/移动/调度", check_integrations),
    ]
    for name, fn in sections:
        print(f"\n>> {name}")
        run_check(name, fn)

    print("\n>> HTTP 页面")
    run_check("HTTP 四模块页面", check_http_pages)

    print("\n>> HTTP API")
    run_check("HTTP 核心 API", check_http_apis)
    run_check("HTTP 导出 API", check_http_export)
    run_check("静态资源", check_static_assets)

    print("\n" + "=" * 60)
    print(f"  通过: {len(PASSES)}  失败: {len(FAILURES)}")
    print("=" * 60)
    if FAILURES:
        print("\n失败项:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("\nALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
