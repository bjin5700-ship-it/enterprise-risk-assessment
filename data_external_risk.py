# -*- coding: utf-8 -*-
"""外部信用/司法证据适配层。
按统一社会信用代码查询诉讼、失信、处罚、经营异常。
命中只作为证据候选，不覆盖 risk_engine 评分；需人工勾选后写入表单。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from credit_code import make_credit_code, normalize_credit_code, validate_credit_code

TIMEOUT_SEC = 8

DEMO_MFG_USCC = make_credit_code("91320100MA1N5Y7XB")
DEMO_CHEM_USCC = make_credit_code("91320200MA2P6W8YC")

CATEGORY_LABEL = {
    "lawsuit": "诉讼",
    "dishonest": "失信被执行",
    "penalty": "行政处罚",
    "abnormal": "经营异常",
}


def provider_status() -> dict:
    forced = (os.environ.get("ERM_EXTERNAL_RISK_PROVIDER") or "").strip().lower()
    tyc = bool((os.environ.get("TIANYANCHA_TOKEN") or "").strip())
    qcc = bool((os.environ.get("QICHACHA_KEY") or "").strip() and (os.environ.get("QICHACHA_SECRET") or "").strip())
    http = bool((os.environ.get("ERM_EXTERNAL_RISK_URL") or "").strip())
    if forced in ("none", "off", "disabled"):
        return {"provider": "none", "connected": False, "note": "已关闭外部源"}
    if forced in ("demo", "fixture", "demo_fixture"):
        return {
            "provider": "demo_fixture",
            "connected": True,
            "note": "内置司法/信用证据库（中金国际演示；配置 TIANYANCHA_TOKEN 可切换商业源）",
        }
    if forced in ("tianyancha", "tyc") and tyc:
        return {"provider": "tianyancha", "connected": True, "note": "天眼查商业 API"}
    if forced in ("qichacha", "qcc") and qcc:
        return {"provider": "qichacha", "connected": True, "note": "企查查商业 API"}
    if forced in ("http", "generic") and http:
        return {"provider": "http", "connected": True, "note": "通用 HTTP 适配"}
    if tyc:
        return {"provider": "tianyancha", "connected": True, "note": "天眼查商业 API"}
    if qcc:
        return {"provider": "qichacha", "connected": True, "note": "企查查商业 API"}
    if http:
        return {"provider": "http", "connected": True, "note": "通用 HTTP 适配"}
    return {
        "provider": "none",
        "connected": False,
        "note": "未接外部源（未配置 TIANYANCHA_TOKEN / QICHACHA_KEY / ERM_EXTERNAL_RISK_URL）",
    }


def lookup_external_risk(uscc: str = "", company_name: str = "") -> dict:
    code = normalize_credit_code(uscc)
    name = str(company_name or "").strip()
    status = provider_status()
    records: List[dict] = []
    errors: List[str] = []

    if status["connected"]:
        try:
            if status["provider"] == "demo_fixture":
                records = demo_feed_records(code, name)
            elif status["provider"] == "tianyancha":
                records = _fetch_tianyancha(code or name)
            elif status["provider"] == "qichacha":
                records = _fetch_qichacha(code or name)
            elif status["provider"] == "http":
                records = _fetch_http(code, name)
        except Exception as exc:
            errors.append(str(exc)[:200])
            status = dict(status)
            status["connected"] = False
            status["note"] = f"外部源调用失败，已跳过：{errors[-1]}"

    demo = _fixture_records(code, name)
    used_demo = False
    if demo and (name.startswith("DEMO-") or code in (DEMO_MFG_USCC, DEMO_CHEM_USCC) or not status["connected"]):
        records = _merge_records(demo, records)
        used_demo = True

    if not records and not status["connected"] and not used_demo:
        note = status["note"]
    elif used_demo and not status["connected"]:
        note = "当前为演示样例证据，非正式工商/司法接口。配置商业 API 后可替换。"
    elif status["connected"] and used_demo:
        note = status["note"] + "；已合并演示样例。"
    else:
        note = status["note"] if status["connected"] else "未接外部源"

    out = {
        "connected": bool(status["connected"]),
        "provider": "demo_fixture" if used_demo and not status["connected"] else status["provider"],
        "note": note,
        "uscc": code,
        "company_name": name,
        "records": records,
        "suggested_fields": records_to_suggestions(records),
        "does_not_score": True,
        "disclaimer": "外部命中不得直接改写规则引擎分数，须人工勾选写入表单后再评估。",
        "errors": errors,
    }
    return out


def attach_external_evidence(result, basic_info: Optional[dict] = None) -> dict:
    basic = basic_info or (getattr(result, "all_raw_data", None) or {}).get("企业基本信息", {}) or {}
    pkg = lookup_external_risk(
        str(basic.get("统一社会信用代码") or ""),
        str(getattr(result, "company_name", None) or basic.get("企业名称") or ""),
    )
    form = getattr(result, "all_raw_data", None) or {}
    pkg["corroborated"] = _corroborate(pkg.get("records") or [], form)
    return pkg


def records_to_suggestions(records: List[dict]) -> List[dict]:
    lawsuits = [r for r in records if r.get("category") == "lawsuit"]
    penalties = [r for r in records if r.get("category") == "penalty"]
    dishonest = [r for r in records if r.get("category") == "dishonest"]
    suggestions: List[dict] = []
    if lawsuits:
        suggestions.append(_sug("法律合规风险", "在审案件数量", str(len(lawsuits)), "诉讼条数"))
        amounts = [r.get("amount_wan") for r in lawsuits if r.get("amount_wan")]
        if amounts:
            suggestions.append(_sug("法律合规风险", "在审案件标的额(万元)", str(round(sum(amounts), 1)), "诉讼标的合计"))
    if penalties:
        suggestions.append(_sug("法律合规风险", "行政处罚次数(近三年)", str(len(penalties)), "处罚条数"))
        titles = "；".join(str(r.get("title") or "") for r in penalties[:3])
        suggestions.append(_sug("信用风险", "行政处罚记录", titles or "有", "处罚摘要"))
    if dishonest:
        suggestions.append(_sug("信用风险", "企业征信报告", "有-严重", "失信被执行"))
        suggestions.append(_sug("信用风险", "海关信用等级", "失信企业", "失信名单"))
    return suggestions


def _sug(sheet: str, field: str, value: str, note: str) -> dict:
    return {
        "sheet": sheet,
        "field": field,
        "value": value,
        "source": "external_risk",
        "confidence": 80,
        "note": note,
        "needs_confirm": True,
    }


def _fixture_records(uscc: str, name: str) -> List[dict]:
    if "江东精密" in name or uscc == DEMO_MFG_USCC:
        return [
            _rec("lawsuit", "买卖合同纠纷", "2024-11-02",
                 "供应商货款争议，一审审理中，标的约 320 万元。",
                 "https://wenshu.court.gov.cn/", "medium", 320),
            _rec("penalty", "生态环境局限期整改", "2024-06-18",
                 "危废贮存台账不规范，责令改正，未罚款。",
                 "https://www.gsxt.gov.cn/", "low", None),
        ]
    if "滨海化工" in name or uscc == DEMO_CHEM_USCC:
        return [
            _rec("lawsuit", "环境污染责任纠纷", "2025-01-20",
                 "周边居民索赔，标的约 860 万元。",
                 "https://wenshu.court.gov.cn/", "high", 860),
            _rec("penalty", "危险废物违法贮存处罚", "2024-09-08",
                 "罚款 86 万元，并责令限期改正。",
                 "https://www.gsxt.gov.cn/", "high", 86),
            _rec("dishonest", "失信被执行人（担保连带）", "2024-12-11",
                 "因对外担保被列入失信名单，执行标的约 210 万元。",
                 "https://zxgk.court.gov.cn/", "high", 210),
            _rec("abnormal", "经营异常名录", "2024-04-03",
                 "未按时公示年报，已列入经营异常。",
                 "https://www.gsxt.gov.cn/", "medium", None),
        ]
    return []


def demo_feed_records(uscc: str = "", company_name: str = "") -> List[dict]:
    """内置证据库：DEMO 企业完整样例；其他企业返回轻量公开信息结构（演示）。"""
    code = normalize_credit_code(uscc)
    name = str(company_name or "").strip()
    rows = _fixture_records(code, name)
    if rows:
        return rows
    if not code and not name:
        return []
    label = name or code
    return [
        _rec(
            "lawsuit", "合同纠纷（一般商事）", "2025-03-12",
            f"{label} 存在 1 起在审合同纠纷，标的约 120 万元（演示结构化证据，非实时工商接口）。",
            "https://wenshu.court.gov.cn/", "medium", 120,
        ),
        _rec(
            "penalty", "安全生产例行检查整改", "2024-11-08",
            f"{label} 曾收到应急管理部门限期整改通知，未罚款（演示）。",
            "https://www.mem.gov.cn/", "low", None,
        ),
    ]


def demo_feed_payload(uscc: str = "", company_name: str = "") -> dict:
    records = demo_feed_records(uscc, company_name)
    return {
        "records": records,
        "suggested_fields": records_to_suggestions(records),
        "provider": "demo_fixture",
        "note": "ERM 内置司法/信用证据适配层",
    }


def _rec(category: str, title: str, date: str, summary: str, url: str, severity: str, amount_wan: Optional[float]) -> dict:
    return {
        "category": category,
        "category_label": CATEGORY_LABEL.get(category, category),
        "title": title,
        "date": date,
        "summary": summary,
        "url": url,
        "source": "demo_fixture",
        "severity": severity,
        "amount_wan": amount_wan,
    }


def _merge_records(primary: List[dict], extra: List[dict]) -> List[dict]:
    seen = {(r.get("category"), r.get("title"), r.get("date")) for r in primary}
    out = list(primary)
    for r in extra:
        key = (r.get("category"), r.get("title"), r.get("date"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _corroborate(records: List[dict], form: dict) -> List[str]:
    notes = []
    legal = form.get("法律合规风险") or form.get("法律与合规风险") or {}
    credit = form.get("信用风险") or {}
    if any(r.get("category") == "lawsuit" for r in records) and legal.get("在审案件数量"):
        notes.append("表单已填在审案件，与外部诉讼记录相互印证")
    if any(r.get("category") == "penalty" for r in records) and (legal.get("行政处罚次数(近三年)") or credit.get("行政处罚记录")):
        notes.append("表单已填处罚，与外部处罚记录相互印证")
    if any(r.get("category") == "dishonest" for r in records) and "失信" in str(credit.get("海关信用等级") or ""):
        notes.append("表单海关信用已标失信")
    return notes


def _fetch_http(uscc: str, name: str) -> List[dict]:
    url = (os.environ.get("ERM_EXTERNAL_RISK_URL") or "").strip()
    if not url:
        return []
    q = urllib.parse.urlencode({"uscc": uscc, "name": name, "keyword": uscc or name})
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(url + sep + q, headers={"Accept": "application/json", "User-Agent": "ERM-C5/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    return _normalize_payload(payload, source="http")


def _fetch_tianyancha(keyword: str) -> List[dict]:
    token = (os.environ.get("TIANYANCHA_TOKEN") or "").strip()
    if not token or not keyword:
        return []
    records: List[dict] = []
    headers = {"Authorization": token, "Accept": "application/json"}
    endpoints = (
        ("https://open.api.tianyancha.com/services/open/jr/lawSuit/2.0", "lawsuit"),
        ("https://open.api.tianyancha.com/services/open/jr/dishonest/2.0", "dishonest"),
        ("https://open.api.tianyancha.com/services/open/mr/punishment/3.0", "penalty"),
    )
    for url, cat in endpoints:
        q = urllib.parse.urlencode({"keyword": keyword, "pageNum": 1, "pageSize": 5})
        req = urllib.request.Request(f"{url}?{q}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"天眼查 HTTP {exc.code}") from exc
        records.extend(_normalize_payload(payload, source="tianyancha", force_category=cat))
    return records


def _fetch_qichacha(keyword: str) -> List[dict]:
    key = (os.environ.get("QICHACHA_KEY") or "").strip()
    secret = (os.environ.get("QICHACHA_SECRET") or "").strip()
    if not key or not secret or not keyword:
        return []
    # 企查查签名因版本而异；此处走可配置网关，避免写死错误签名。
    gateway = (os.environ.get("QICHACHA_GATEWAY") or os.environ.get("ERM_EXTERNAL_RISK_URL") or "").strip()
    if not gateway:
        raise RuntimeError("已配置企查查密钥但缺少 QICHACHA_GATEWAY 或 ERM_EXTERNAL_RISK_URL")
    q = urllib.parse.urlencode({"keyword": keyword, "key": key})
    req = urllib.request.Request(
        gateway + ("&" if "?" in gateway else "?") + q,
        headers={"Accept": "application/json", "Token": secret},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    return _normalize_payload(payload, source="qichacha")


def _normalize_payload(payload: Any, source: str, force_category: str = "") -> List[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = (
            payload.get("records")
            or payload.get("items")
            or payload.get("result")
            or (payload.get("data") or {}).get("items")
            or (payload.get("data") or {}).get("list")
            or []
        )
        if isinstance(payload.get("data"), list):
            items = payload["data"]
    else:
        return []
    out = []
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        cat = force_category or str(raw.get("category") or raw.get("type") or "lawsuit")
        if cat not in CATEGORY_LABEL:
            low = cat.lower()
            if "dishonest" in low or "失信" in cat:
                cat = "dishonest"
            elif "penal" in low or "处罚" in cat:
                cat = "penalty"
            elif "abnormal" in low or "异常" in cat:
                cat = "abnormal"
            else:
                cat = "lawsuit"
        title = str(raw.get("title") or raw.get("caseName") or raw.get("name") or raw.get("reason") or "").strip()
        if not title:
            continue
        amount = raw.get("amount_wan") or raw.get("amount") or raw.get("caseMoney")
        try:
            amount_wan = float(amount) if amount not in (None, "") else None
        except (TypeError, ValueError):
            amount_wan = None
        out.append({
            "category": cat,
            "category_label": CATEGORY_LABEL.get(cat, cat),
            "title": title[:120],
            "date": str(raw.get("date") or raw.get("submitTime") or raw.get("publishDate") or "")[:16],
            "summary": str(raw.get("summary") or raw.get("content") or raw.get("result") or title)[:240],
            "url": str(raw.get("url") or raw.get("link") or ""),
            "source": source,
            "severity": str(raw.get("severity") or "medium"),
            "amount_wan": amount_wan,
        })
    return out
