# -*- coding: utf-8 -*-
"""KPI 时序入库 — PostgreSQL（无 Timescale 时用普通表）或 JSON 回退。"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from risk_engine import AssessmentResult, _sf
from risk_kri import KRI_FIELD_MAP, build_kri_dashboard

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "web_app", "data", "kpi_timeseries.json"
)
MAX_SNAPSHOTS_PER_COMPANY = 48
MIN_TREND_SNAPSHOTS = 3


def _company_key(name: str) -> str:
    return (name or "未命名企业").strip()


def load_timeseries_db(path: str = None) -> dict:
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_timeseries_db(db: dict, path: str = None) -> None:
    path = path or DEFAULT_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _extract_kpis(form_data: dict) -> Dict[str, float]:
    kpis = {}
    for sheet, field, name, unit, target, direction in KRI_FIELD_MAP:
        raw = (form_data.get(sheet) or {}).get(field)
        val = _sf(raw)
        if val is not None:
            kpis[name] = val
    return kpis


def _use_store(path: str = None) -> bool:
    if path:
        return False
    try:
        from erm_store import using_postgres
        return using_postgres()
    except Exception:
        return False


def record_assessment_snapshot(
    result: AssessmentResult,
    form_data: dict = None,
    assessment_id: str = None,
    path: str = None,
    assessed_at: str = None,
) -> dict:
    """每次评估写入一条 KPI + 评分快照。"""
    form_data = form_data or result.all_raw_data or {}
    key = _company_key(result.company_name)
    kri = build_kri_dashboard(result, form_data)
    snapshot = {
        "id": assessment_id or str(uuid.uuid4())[:8],
        "assessed_at": assessed_at or datetime.now().isoformat(),
        "overall_score": result.overall_score,
        "overall_level": result.overall_level.value,
        "dimensions": {d.name: round(d.score, 3) for d in result.dimensions.values()},
        "kpis": _extract_kpis(form_data),
        "kri_health": kri.get("health_score"),
        "kri_red": (kri.get("summary") or {}).get("red", 0),
        "kri_amber": (kri.get("summary") or {}).get("amber", 0),
        "company_name": result.company_name,
    }
    if _use_store(path):
        from erm_store import insert_kri_snapshot
        insert_kri_snapshot(snapshot)
        return snapshot

    db = load_timeseries_db(path)
    entry = db.setdefault(key, {"company_name": result.company_name, "snapshots": []})
    entry["snapshots"].insert(0, snapshot)
    entry["snapshots"] = entry["snapshots"][:MAX_SNAPSHOTS_PER_COMPANY]
    entry["updated_at"] = datetime.now().isoformat()
    save_timeseries_db(db, path)
    return snapshot


def get_company_timeseries(company_name: str, path: str = None) -> dict:
    key = _company_key(company_name)
    if _use_store(path):
        from erm_store import list_kri_snapshots
        snaps = list_kri_snapshots(key)
    else:
        db = load_timeseries_db(path)
        entry = db.get(key, {})
        snaps = list(reversed(entry.get("snapshots", [])))
    return {
        "company_name": company_name,
        "snapshot_count": len(snaps),
        "snapshots": snaps,
        "first_at": snaps[0]["assessed_at"] if snaps else None,
        "last_at": snaps[-1]["assessed_at"] if snaps else None,
    }


def analyze_timeseries(company_name: str, path: str = None) -> dict:
    ts = get_company_timeseries(company_name, path)
    snaps = ts.get("snapshots") or []
    insufficient = {
        "has_trend": False,
        "snapshot_count": len(snaps),
        "message": "样本不足",
        "score_trend": [],
        "kpi_trends": [],
        "score_trend_label": "样本不足",
        "statistical_correlation": None,
        "min_required": MIN_TREND_SNAPSHOTS,
    }
    if len(snaps) < MIN_TREND_SNAPSHOTS:
        insufficient["message"] = f"样本不足（已有 {len(snaps)} 次，至少 {MIN_TREND_SNAPSHOTS} 次评估后展示趋势）"
        return insufficient

    score_trend = [
        {"date": str(s["assessed_at"])[:10], "score": s["overall_score"], "level": s["overall_level"]}
        for s in snaps
    ]
    first, last = snaps[0], snaps[-1]
    score_delta = round(float(last["overall_score"]) - float(first["overall_score"]), 3)

    kpi_trends = []
    all_kpi_names = set()
    for s in snaps:
        all_kpi_names.update((s.get("kpis") or {}).keys())

    for name in sorted(all_kpi_names):
        series = []
        for s in snaps:
            v = (s.get("kpis") or {}).get(name)
            if v is not None:
                series.append({"date": str(s["assessed_at"])[:10], "value": v})
        if len(series) >= MIN_TREND_SNAPSHOTS:
            delta = round(series[-1]["value"] - series[0]["value"], 3)
            direction = "上升" if delta > 0 else "下降" if delta < 0 else "稳定"
            worsening = _is_kpi_worsening(name, delta)
            kpi_trends.append({
                "kpi": name,
                "points": len(series),
                "delta": delta,
                "direction": direction,
                "worsening": worsening,
                "series": series[-6:],
            })

    kpi_trends.sort(key=lambda x: (x["worsening"], abs(x["delta"])), reverse=True)
    stat_corr = _dimension_correlation_from_snapshots(snaps)

    return {
        "has_trend": True,
        "snapshot_count": len(snaps),
        "period": f"{str(first['assessed_at'])[:10]} → {str(last['assessed_at'])[:10]}",
        "score_delta": score_delta,
        "score_trend_label": "改善" if score_delta < -0.08 else "恶化" if score_delta > 0.08 else "稳定",
        "score_trend": score_trend[-12:],
        "kpi_trends": kpi_trends[:12],
        "worsening_kpis": [k["kpi"] for k in kpi_trends if k["worsening"]][:5],
        "improving_kpis": [k["kpi"] for k in kpi_trends if not k["worsening"] and k["delta"] != 0][:5],
        "statistical_correlation": stat_corr,
        "min_required": MIN_TREND_SNAPSHOTS,
        "message": f"共 {len(snaps)} 次快照，综合评分变化 {score_delta:+.2f}",
    }


def _is_kpi_worsening(name: str, delta: float) -> bool:
    if abs(delta) < 0.01:
        return False
    lower_better = {
        "资产负债率", "客户集中度", "应收周转天数", "供应商集中度", "工伤事故",
        "在审诉讼", "重大处罚", "安全事件", "核心流失率", "坏账率", "数据泄露",
    }
    higher_better = {"流动比率", "净利率", "排放达标率", "BC演练"}
    if name in lower_better:
        return delta > 0
    if name in higher_better:
        return delta < 0
    return delta > 0


def _dimension_correlation_from_snapshots(snaps: List[dict]) -> Optional[dict]:
    """基于历史快照的维度评分 Pearson 相关（至少 3 点）"""
    if len(snaps) < 3:
        return None
    dim_names = list(snaps[-1].get("dimensions", {}).keys())
    if len(dim_names) < 2:
        return None

    matrix = []
    high_pairs = []
    for i, da in enumerate(dim_names):
        row = []
        series_a = [s["dimensions"].get(da) for s in snaps if da in s.get("dimensions", {})]
        for j, db in enumerate(dim_names):
            if i == j:
                row.append(1.0)
                continue
            series_b = [s["dimensions"].get(db) for s in snaps if db in s.get("dimensions", {})]
            n = min(len(series_a), len(series_b))
            if n < 3:
                row.append(0.0)
                continue
            sa = series_a[-n:]
            sb = series_b[-n:]
            corr = _pearson(sa, sb)
            row.append(round(corr, 2))
            if i < j and abs(corr) >= 0.65:
                high_pairs.append({
                    "dim_a": da, "dim_b": db,
                    "correlation": round(corr, 2),
                    "basis": f"历史 {n} 期",
                    "strength": "强" if abs(corr) >= 0.8 else "中",
                })
        matrix.append(row)

    return {
        "labels": dim_names,
        "matrix": matrix,
        "high_pairs": sorted(high_pairs, key=lambda x: abs(x["correlation"]), reverse=True)[:8],
        "snapshot_basis": len(snaps),
        "methodology": "历史评估快照 · Pearson 相关系数",
    }


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return max(-1.0, min(1.0, num / (den_x * den_y)))
