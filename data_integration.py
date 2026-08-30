# -*- coding: utf-8 -*-
"""Phase D — 外部数据集成与实时监控层"""

from __future__ import annotations

import csv
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

INTEGRATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "integrations")
SYNC_SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "sync_schedule.json")
os.makedirs(INTEGRATION_DIR, exist_ok=True)

# 字段映射：外部系统字段 → 表单 Sheet.字段
ERP_FIELD_MAP = {
    "debt_ratio": ("财务风险", "资产负债率(%)"),
    "asset_liability_ratio": ("财务风险", "资产负债率(%)"),
    "current_ratio": ("财务风险", "流动比率"),
    "quick_ratio": ("财务风险", "速动比率"),
    "net_margin": ("财务风险", "净利率(%)"),
    "gross_margin": ("财务风险", "毛利率(%)"),
    "roe": ("财务风险", "净资产收益率ROE(%)"),
    "revenue": ("企业基本信息", "年营业额(万元)"),
    "total_assets": ("企业基本信息", "资产总额(万元)"),
    "ocf": ("财务风险", "经营性现金流净额(万元)"),
    "operating_cash_flow": ("财务风险", "经营性现金流净额(万元)"),
    "fcf": ("财务风险", "自由现金流(万元)"),
    "employee_count": ("企业基本信息", "员工总数(人)"),
    "interest_coverage": ("财务风险", "利息保障倍数"),
    "short_debt_ratio": ("财务风险", "短期借款占比(%)"),
    "ar_days": ("经营风险", "应收账款周转天数"),
    "customer_conc": ("经营风险", "前五大客户收入占比(%)"),
    "supplier_conc": ("供应链风险", "最大单一供应商占比(%)"),
    "company_name": ("企业基本信息", "企业名称"),
    "credit_code": ("企业基本信息", "统一社会信用代码"),
    "industry": ("企业基本信息", "所属行业"),
}

FINANCIAL_API_MAP = dict(ERP_FIELD_MAP)


def list_connectors() -> List[dict]:
    return [
        {
            "id": "csv_import",
            "name": "CSV/Excel 财务快照",
            "type": "file",
            "status": "ready",
            "description": "上传 CSV 财务指标文件，自动映射至评估表单",
            "endpoint": "/api/integrations/csv",
        },
        {
            "id": "erp_webhook",
            "name": "ERP 系统 Webhook",
            "type": "webhook",
            "status": "ready",
            "description": "接收 ERP/财务系统 JSON 推送，增量更新表单字段",
            "endpoint": "/api/integrations/erp",
        },
        {
            "id": "financial_api",
            "name": "财务数据 API",
            "type": "api",
            "status": "ready",
            "description": "REST JSON 拉取财务 KPI（可对接用友/金蝶/自研 BI）",
            "endpoint": "/api/integrations/financial",
        },
        {
            "id": "oauth_erp",
            "name": "OAuth ERP 直连",
            "type": "oauth",
            "status": "ready",
            "description": "OAuth2 授权连接用友/金蝶/通用 ERP",
            "endpoint": "/api/integrations/oauth/authorize",
        },
        {
            "id": "mobile_push",
            "name": "移动端 App 推送",
            "type": "push",
            "status": "ready",
            "description": "FCM / 自定义 Push URL / Service Worker",
            "endpoint": "/api/notifications/devices",
        },
        {
            "id": "scheduled_sync",
            "name": "定时 ERP 同步",
            "type": "scheduler",
            "status": "ready",
            "description": "按配置间隔自动拉取 CSV/财务 API 并可选自动评估",
            "endpoint": "/api/integrations/schedule",
        },
    ]


def merge_external_into_form(form_data: dict, external: dict, field_map: dict) -> dict:
    """将外部数据合并进 form_data，不覆盖已有非空值（除非 force）"""
    merged = {k: dict(v) for k, v in form_data.items()}
    force = external.pop("_force", False)

    for ext_key, (sheet, field) in field_map.items():
        if ext_key not in external:
            continue
        val = external[ext_key]
        if val is None:
            continue
        merged.setdefault(sheet, {})
        existing = merged[sheet].get(field, "")
        if force or not str(existing).strip():
            merged[sheet][field] = str(val)
    return merged


def parse_csv_financial(content: str) -> dict:
    """CSV 格式：metric,value 或 字段名,值"""
    reader = csv.reader(content.strip().splitlines())
    rows = list(reader)
    if not rows:
        return {}

    external = {}
    alias = {
        "资产负债率": "debt_ratio", "资产负债率(%)": "debt_ratio",
        "流动比率": "current_ratio", "速动比率": "quick_ratio",
        "净利率": "net_margin", "净利率(%)": "net_margin",
        "毛利率": "gross_margin", "毛利率(%)": "gross_margin",
        "roe": "roe", "净资产收益率": "roe", "净资产收益率ROE(%)": "roe",
        "年营业额": "revenue", "资产总额": "total_assets",
        "经营性现金流": "ocf", "经营性现金流净额": "ocf",
        "自由现金流": "fcf", "员工总数": "employee_count",
        "利息保障倍数": "interest_coverage",
        "短期借款占比": "short_debt_ratio",
        "应收账款周转天数": "ar_days",
        "前五大客户收入占比": "customer_conc",
        "最大单一供应商占比": "supplier_conc",
        "统一社会信用代码": "credit_code",
        "所属行业": "industry",
        "企业名称": "company_name",
    }
    for row in rows:
        if len(row) < 2:
            continue
        key, val = row[0].strip(), row[1].strip()
        ext_key = alias.get(key, key)
        if ext_key in ERP_FIELD_MAP:
            external[ext_key] = val
        else:
            try:
                external[key] = float(val.replace("%", ""))
            except ValueError:
                external[key] = val
    return external


def apply_erp_payload(payload: dict) -> dict:
    return {k: payload[k] for k in ERP_FIELD_MAP if k in payload}


def apply_financial_api_payload(payload: dict) -> dict:
    data = payload.get("data") or payload.get("metrics") or payload
    return {k: data[k] for k in FINANCIAL_API_MAP if k in data}


def save_integration_log(source: str, payload: dict, result: dict) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(INTEGRATION_DIR, f"{source}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": source, "payload": payload, "result": result, "at": ts}, f, ensure_ascii=False, indent=2)
    return path


def load_latest_external_snapshot() -> Optional[dict]:
    if not os.path.isdir(INTEGRATION_DIR):
        return None
    files = sorted([f for f in os.listdir(INTEGRATION_DIR) if f.endswith(".json")], reverse=True)
    if not files:
        return None
    with open(os.path.join(INTEGRATION_DIR, files[0]), "r", encoding="utf-8") as f:
        return json.load(f)


def _default_job(job_id: str = None) -> dict:
    return {
        "id": job_id or str(uuid.uuid4())[:8],
        "enabled": True,
        "interval_minutes": 60,
        "source_type": "csv_file",
        "source_path": "",
        "source_url": "",
        "oauth_provider_id": "",
        "api_headers": {},
        "company_name": "",
        "auto_assess": True,
        "auto_notify": True,
        "auto_save_history": False,
        "last_run_at": None,
        "next_run_at": None,
        "last_status": None,
        "last_message": None,
        "last_fields_updated": 0,
    }


def _default_sync_schedule() -> dict:
    return {
        "global_enabled": False,
        "max_parallel_jobs": 4,
        "jobs": [],
    }


def normalize_schedule(raw: dict = None) -> dict:
    """兼容旧版单任务配置，统一为多 job 结构。"""
    raw = raw or {}
    if raw.get("jobs") is not None:
        sched = _default_sync_schedule()
        sched["global_enabled"] = bool(raw.get("global_enabled", raw.get("enabled", False)))
        sched["max_parallel_jobs"] = max(1, min(16, int(raw.get("max_parallel_jobs") or 4)))
        sched["jobs"] = [dict(_default_job(j.get("id")), **j) for j in raw.get("jobs", [])]
        return sched
    # 旧版单任务迁移
    if raw.get("company_name") or raw.get("source_path") or raw.get("source_url") or raw.get("enabled"):
        job = _default_job("default")
        for k in job:
            if k in raw:
                job[k] = raw[k]
        job["enabled"] = bool(raw.get("enabled", False))
        return {
            "global_enabled": bool(raw.get("enabled", False)),
            "max_parallel_jobs": 4,
            "jobs": [job],
        }
    return _default_sync_schedule()


def load_sync_schedule(path: str = None) -> dict:
    path = path or SYNC_SCHEDULE_FILE
    if not os.path.exists(path):
        cfg = _default_sync_schedule()
        save_sync_schedule(cfg, path)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = normalize_schedule(data if isinstance(data, dict) else {})
    except (json.JSONDecodeError, OSError):
        return _default_sync_schedule()
    if sanitize_schedule_inplace(cfg):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return cfg


def _sample_csv_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "erp_sample.csv")


def _looks_windows_path(path: str) -> bool:
    p = path or ""
    return bool(re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("\\\\"))


def sanitize_schedule_inplace(cfg: dict) -> bool:
    """把本机 Windows 路径改写为服务器示例 CSV，避免 Linux 上空转。返回是否改写。"""
    sample = _sample_csv_path()
    changed = False
    for job in cfg.get("jobs") or []:
        if job.get("source_type") != "csv_file":
            continue
        path = str(job.get("source_path") or "").strip()
        if not _looks_windows_path(path):
            continue
        if os.path.isfile(sample):
            job["source_path"] = sample
            job["last_message"] = "已将 Windows 路径改写为服务器示例 CSV"
            job["error_count"] = 0
            changed = True
        else:
            job["enabled"] = False
            job["last_status"] = "disabled"
            job["last_message"] = "Windows 路径在 Linux 上不可用，已停用"
            changed = True
    return changed


def save_sync_schedule(cfg: dict, path: str = None) -> None:
    path = path or SYNC_SCHEDULE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized = normalize_schedule(cfg)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def upsert_sync_job(job: dict) -> dict:
    sched = load_sync_schedule()
    job = dict(_default_job(job.get("id")), **job)
    found = False
    for i, j in enumerate(sched["jobs"]):
        if j.get("id") == job["id"]:
            sched["jobs"][i] = job
            found = True
            break
    if not found:
        sched["jobs"].append(job)
    save_sync_schedule(sched)
    return job


def delete_sync_job(job_id: str) -> bool:
    sched = load_sync_schedule()
    before = len(sched["jobs"])
    sched["jobs"] = [j for j in sched["jobs"] if j.get("id") != job_id]
    save_sync_schedule(sched)
    return len(sched["jobs"]) < before


def _update_job_status(job_id: str, updates: dict) -> None:
    sched = load_sync_schedule()
    for i, j in enumerate(sched["jobs"]):
        if j.get("id") == job_id:
            sched["jobs"][i].update(updates)
            save_sync_schedule(sched)
            return


def _is_job_due(job: dict, now: datetime = None) -> bool:
    now = now or datetime.now()
    if not job.get("enabled"):
        return False
    last = job.get("last_run_at")
    interval = max(5, int(job.get("interval_minutes") or 60))
    if not last:
        return True
    try:
        return now - datetime.fromisoformat(last) >= timedelta(minutes=interval)
    except ValueError:
        return True


def fetch_url_content(url: str, headers: dict = None, timeout: int = 20) -> str:
    from urllib import request, error

    hdrs = {"User-Agent": "ERM-Sync/1.0"}
    if headers:
        hdrs.update({str(k): str(v) for k, v in headers.items()})
    req = request.Request(url.strip(), headers=hdrs, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig", errors="ignore")


def fetch_external_payload(cfg: dict) -> dict:
    """按 source_type 拉取外部原始 payload。"""
    stype = cfg.get("source_type", "csv_file")
    if stype == "csv_file":
        path = (cfg.get("source_path") or "").strip()
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"CSV 文件不存在: {path}")
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
        return {"type": "csv", "external": parse_csv_financial(content), "raw": content[:500]}
    if stype == "csv_url":
        url = (cfg.get("source_url") or "").strip()
        if not url:
            raise ValueError("缺少 source_url")
        content = fetch_url_content(url, cfg.get("api_headers") or {})
        return {"type": "csv", "external": parse_csv_financial(content), "raw": content[:500]}
    if stype == "financial_api_url":
        url = (cfg.get("source_url") or "").strip()
        if not url:
            raise ValueError("缺少 financial API URL")
        content = fetch_url_content(url, cfg.get("api_headers") or {})
        body = json.loads(content)
        return {"type": "financial_api", "external": apply_financial_api_payload(body), "raw": body}
    if stype == "erp_json_url":
        url = (cfg.get("source_url") or "").strip()
        if not url:
            raise ValueError("缺少 ERP JSON URL")
        content = fetch_url_content(url, cfg.get("api_headers") or {})
        body = json.loads(content)
        return {"type": "erp", "external": apply_erp_payload(body), "raw": body}
    if stype == "oauth_erp":
        provider_id = (cfg.get("oauth_provider_id") or "").strip()
        if not provider_id:
            raise ValueError("缺少 oauth_provider_id")
        from erp_oauth import fetch_oauth_erp_payload
        return fetch_oauth_erp_payload(provider_id)
    raise ValueError(f"不支持的 source_type: {stype}")


def _load_base_form_for_company(company_name: str, template: dict) -> dict:
    """优先从历史档案恢复表单，否则返回空模板结构。"""
    base = {sheet: {} for sheet in template}
    if not company_name:
        return base
    try:
        from erm_store import load_history
        records = load_history()
        for rec in records:
            if rec.get("company_name") == company_name:
                assessment = rec.get("assessment") or {}
                fd = assessment.get("all_raw_data") or assessment.get("form_data")
                if fd:
                    for sheet, fields in fd.items():
                        base.setdefault(sheet, {}).update(fields or {})
                    return base
    except Exception:
        pass
    return base


def execute_scheduled_sync(cfg: dict = None, force: bool = False, job_id: str = None) -> dict:
    """执行单个同步任务；cfg 为 job 字典。"""
    sched = load_sync_schedule()
    if cfg is None:
        jobs = sched.get("jobs", [])
        if job_id:
            cfg = next((j for j in jobs if j.get("id") == job_id), None)
        elif jobs:
            cfg = jobs[0]
        else:
            return {"skipped": True, "reason": "no_jobs"}
    if cfg is None:
        return {"skipped": True, "reason": "job_not_found"}

    job_id = cfg.get("id") or "unknown"
    now = datetime.now()
    interval = max(5, int(cfg.get("interval_minutes") or 60))

    if not force:
        if not sched.get("global_enabled") or not cfg.get("enabled"):
            return {"skipped": True, "reason": "disabled", "job_id": job_id}
        if not _is_job_due(cfg, now):
            return {"skipped": True, "reason": "not_due", "job_id": job_id, "next_run_at": cfg.get("next_run_at")}

    result = {"skipped": False, "at": now.isoformat(), "job_id": job_id}
    status_updates = {}
    try:
        fetched = fetch_external_payload(cfg)
        external = fetched.get("external") or {}
        if not external:
            raise ValueError("外部数据源未返回可映射字段")

        import sys
        web_app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app")
        if web_app_dir not in sys.path:
            sys.path.insert(0, web_app_dir)
        from app import get_template_fields, normalize_form_data, run_assessment_from_form, assessment_to_dict, add_history_record

        template = get_template_fields()
        if not template:
            raise RuntimeError("Excel 模板未加载")

        company = (cfg.get("company_name") or "").strip()
        base_form = _load_base_form_for_company(company, template)
        base_form = normalize_form_data(base_form, template)
        ftype = fetched.get("type", "csv")
        field_map = ERP_FIELD_MAP if ftype in ("csv", "erp", "oauth_erp") else FINANCIAL_API_MAP
        merged = merge_external_into_form(base_form, {**external, "_force": True}, field_map)

        if company:
            merged.setdefault("企业基本信息", {})["企业名称"] = company
        elif merged.get("企业基本信息", {}).get("企业名称"):
            company = str(merged["企业基本信息"]["企业名称"]).strip()

        result["fields_updated"] = len(external)
        result["company_name"] = company or "未命名企业"
        save_integration_log("scheduled_sync", {"job_id": job_id, "source_type": cfg.get("source_type")}, {"fields": len(external)})

        if cfg.get("auto_assess", True):
            assess_result = run_assessment_from_form(merged)
            payload = assessment_to_dict(assess_result)
            result["overall_score"] = payload.get("overall_score")
            result["overall_level"] = payload.get("overall_level")
            result["alerts"] = payload.get("alerts")
            result["closed_loop"] = payload.get("closed_loop")

            if cfg.get("auto_save_history"):
                rec = add_history_record(payload, note=f"定时同步 · {job_id}")
                result["history_id"] = rec.get("id")

            if cfg.get("auto_notify", True) and payload.get("alerts"):
                from risk_notifications import emit_assessment_alerts
                emit_assessment_alerts(
                    result["company_name"],
                    payload.get("alerts"),
                    payload.get("closed_loop"),
                    source="scheduled_sync",
                )

        status_updates = {
            "last_run_at": now.isoformat(),
            "next_run_at": (now + timedelta(minutes=interval)).isoformat(),
            "last_status": "ok",
            "last_message": f"已同步 {len(external)} 个字段",
            "last_fields_updated": len(external),
            "error_count": 0,
        }
        _update_job_status(job_id, status_updates)
        result["status"] = "ok"
        result["message"] = status_updates["last_message"]
        return result
    except Exception as exc:
        error_count = int(cfg.get("error_count") or 0) + 1
        status_updates = {
            "last_run_at": now.isoformat(),
            "next_run_at": (now + timedelta(minutes=interval)).isoformat(),
            "last_status": "error",
            "last_message": str(exc),
            "error_count": error_count,
        }
        if error_count >= 3:
            status_updates["enabled"] = False
            status_updates["last_message"] = f"{exc} · 连续失败 {error_count} 次已停用"
            status_updates["last_status"] = "disabled"
        _update_job_status(job_id, status_updates)
        result["status"] = "error"
        result["message"] = str(exc)
        try:
            from erm_store import audit
            audit("scheduler.job_failed", "sync_job", str(job_id or ""), {"message": str(exc)[:400]})
        except Exception:
            pass
        return result


def execute_due_jobs_parallel(force: bool = False, job_ids: List[str] = None) -> dict:
    """并行执行所有到期任务（多企业）。"""
    sched = load_sync_schedule()
    if not force and not sched.get("global_enabled"):
        return {"skipped": True, "reason": "global_disabled", "results": []}

    now = datetime.now()
    due: List[dict] = []
    for job in sched.get("jobs", []):
        if job_ids and job.get("id") not in job_ids:
            continue
        if force or _is_job_due(job, now):
            if force or job.get("enabled", True):
                due.append(job)

    if not due:
        return {"skipped": True, "reason": "no_due_jobs", "results": []}

    max_workers = max(1, min(16, int(sched.get("max_parallel_jobs") or 4)))
    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(due))) as pool:
        futures = {pool.submit(execute_scheduled_sync, job, force): job for job in due}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                r = fut.result()
            except Exception as exc:
                r = {"job_id": job.get("id"), "status": "error", "message": str(exc)}
                try:
                    from erm_store import audit
                    audit("scheduler.job_failed", "sync_job", str(job.get("id") or ""), {"message": str(exc)[:400]})
                except Exception:
                    pass
            results.append(r)

    ok = sum(1 for r in results if r.get("status") == "ok")
    return {
        "skipped": False,
        "jobs_run": len(results),
        "jobs_ok": ok,
        "max_parallel": max_workers,
        "results": results,
        "at": now.isoformat(),
    }

