# -*- coding: utf-8 -*-
"""
蒙特卡洛评分不确定性 — ISO 31010
分数轨：维度评分扰动后的综合分分布（1–4），不是损失 VaR。
金额轨：仅在填报营收/资产时，把评分映射为经营冲击情景（万元），不是精算资本计量。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy.stats import scoreatpercentile

from risk_engine import AssessmentResult, _sf


def _level_from_score(s: float) -> str:
    if s < 1.5:
        return "低风险"
    if s < 2.5:
        return "中等风险"
    if s < 3.5:
        return "高风险"
    return "极高风险"


def run_monte_carlo(
    result: AssessmentResult,
    iterations: int = 2000,
    confidence_pct: float = 50.0,
    appetite_threshold: float = 2.5,
    seed: Optional[int] = None,
    basic: Optional[dict] = None,
) -> dict:
    """
    对加权综合评分做蒙特卡洛不确定性分析。
    扰动随数据置信度下降而增大；输出明确标注为「评分区间」，禁止解读为金额损失。
    """
    dims = list(result.dimensions.values())
    if not dims:
        return {"error": "无维度数据"}

    sigma = max(0.08, min(0.45, (100 - float(confidence_pct or 50)) / 100 * 0.4))
    names = [d.name for d in dims]
    scores = np.array([float(d.score) for d in dims], dtype=float)
    weights = np.array([float(d.weight) for d in dims], dtype=float)
    total_w = float(weights.sum()) or 1.0
    iterations = max(200, int(iterations))

    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, sigma, size=(iterations, len(dims)))
    perturbed = np.clip(scores + noise, 1.0, 4.0)
    samples = (perturbed * weights).sum(axis=1) / total_w

    p10 = float(scoreatpercentile(samples, 10))
    p50 = float(scoreatpercentile(samples, 50))
    p90 = float(scoreatpercentile(samples, 90))
    p95 = float(scoreatpercentile(samples, 95))
    mean = float(samples.mean())
    std = float(samples.std(ddof=0))
    tail = samples[samples >= p95]
    tail_mean = float(tail.mean()) if tail.size else float(p95)
    breach = float((samples > appetite_threshold).mean() * 100)
    critical = float((samples >= 3.5).mean() * 100)

    edges = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.01])
    labels = ["1.0-1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5-4.0"]
    counts, _ = np.histogram(samples, bins=edges)

    ci_low, ci_high = round(float(p10), 2), round(float(p90), 2)
    score_p95 = round(float(p95), 2)
    score_tail_mean = round(tail_mean, 2)
    mean_r = round(mean, 3)

    if basic is None:
        basic = (result.all_raw_data or {}).get("企业基本信息", {}) or {}
    money = _money_track(samples, basic)
    sensitivity = _sensitivity(names, scores, weights, sigma, seed)

    payload = {
        "track": "score",
        "unit": "综合评分（1–4，越高风险越大）",
        "iterations": iterations,
        "base_score": result.overall_score,
        "mean_score": mean_r,
        "std_dev": round(std, 3),
        "percentiles": {
            "p10": ci_low,
            "p50": round(float(p50), 2),
            "p90": ci_high,
        },
        "confidence_interval_80": [ci_low, ci_high],
        "score_p95": score_p95,
        "score_tail_mean": score_tail_mean,
        "var_95": score_p95,
        "cvar_95": score_tail_mean,
        "probability_breach_appetite_pct": round(breach, 1),
        "probability_critical_pct": round(critical, 1),
        "appetite_threshold": appetite_threshold,
        "uncertainty_sigma": round(sigma, 3),
        "distribution": {"labels": labels, "counts": [int(c) for c in counts]},
        "sensitivity": sensitivity,
        "money_track": money,
        "interpretation": _interpret_score(
            mean_r, breach, critical, ci_low, ci_high, score_p95, score_tail_mean, money
        ),
        "methodology": (
            "ISO 31010 蒙特卡洛 · 维度评分正态扰动（NumPy）· 输出为综合评分不确定性区间，"
            "不是损失 VaR/CVaR。P95 为评分高分位，尾部均值为评分 ≥P95 的条件均值。"
        ),
        "disclaimer": "本章分数轨不表示货币损失。金额轨仅在填报营收或资产时作为经营冲击情景，不能替代精算或资本计量。",
    }
    return payload


def _money_track(samples: np.ndarray, basic: dict) -> Optional[dict]:
    revenue = _sf(basic.get("年营业额(万元)"))
    assets = _sf(basic.get("资产总额(万元)"))
    if revenue is None and assets is None:
        return None
    # 评分 1→0% 承压，4→最多 25% 营收/资产冲击，线性映射（情景，非损失分布）
    pressure = np.clip((samples - 1.0) / 3.0 * 0.25, 0.0, 0.25)
    p10, p50, p90 = [round(float(scoreatpercentile(pressure, p) * 100), 1) for p in (10, 50, 90)]
    out: Dict[str, Any] = {
        "enabled": True,
        "unit": "万元",
        "pressure_pct": {"p10": p10, "p50": p50, "p90": p90},
        "disclaimer": "由综合评分线性映射的经营冲击情景（满分约对应 25% 营收/资产承压），不是保险赔付或监管资本。",
    }
    if revenue is not None and revenue > 0:
        shocked = revenue * pressure
        r10, r50, r90 = [round(float(scoreatpercentile(shocked, p)), 1) for p in (10, 50, 90)]
        out["revenue_base"] = revenue
        out["revenue_pressure"] = {"p10": r10, "p50": r50, "p90": r90}
    if assets is not None and assets > 0:
        shocked = assets * pressure
        a10, a50, a90 = [round(float(scoreatpercentile(shocked, p)), 1) for p in (10, 50, 90)]
        out["asset_base"] = assets
        out["asset_pressure"] = {"p10": a10, "p50": a50, "p90": a90}
    out["interpretation"] = _interpret_money(out)
    return out


def _interpret_money(money: dict) -> str:
    pct = money.get("pressure_pct") or {}
    parts = [
        f"经营冲击情景：承压幅度 P10/P50/P90 为 {pct.get('p10')}% / {pct.get('p50')}% / {pct.get('p90')}%。"
    ]
    if money.get("revenue_pressure"):
        rp = money["revenue_pressure"]
        parts.append(
            f"对应年营收承压约 {rp['p10']} / {rp['p50']} / {rp['p90']} 万元（基数 {money.get('revenue_base')} 万元）。"
        )
    if money.get("asset_pressure"):
        ap = money["asset_pressure"]
        parts.append(
            f"对应资产承压约 {ap['p10']} / {ap['p50']} / {ap['p90']} 万元（基数 {money.get('asset_base')} 万元）。"
        )
    parts.append("此为情景映射，不可写成货币损失或监管资本 VaR。")
    return "".join(parts)


def _sensitivity(
    names: Sequence[str],
    scores: np.ndarray,
    weights: np.ndarray,
    sigma: float,
    seed: Optional[int],
) -> List[dict]:
    """Morris μ*：哪个维度扰动对综合分影响最大。失败则退回权重×σ 近似。"""
    n = len(names)
    if n < 2:
        return []
    bounds = []
    for s in scores:
        lo = max(1.0, float(s) - 2.0 * sigma)
        hi = min(4.0, float(s) + 2.0 * sigma)
        if hi - lo < 0.05:
            hi = min(4.0, lo + 0.05)
        bounds.append([lo, hi])
    try:
        from SALib.analyze.morris import analyze as morris_analyze
        from SALib.sample.morris import sample as morris_sample

        problem = {"num_vars": n, "names": list(names), "bounds": bounds}
        x = morris_sample(problem, N=24, num_levels=4, seed=seed if seed is not None else 42)
        total_w = float(weights.sum()) or 1.0
        y = (x * weights).sum(axis=1) / total_w
        si = morris_analyze(problem, x, y, conf_level=0.95, print_to_console=False, seed=seed)
        mu_star = np.array(si["mu_star"], dtype=float)
        order = np.argsort(-mu_star)
        rows = []
        for i in order[:5]:
            rows.append({
                "dimension": names[int(i)],
                "mu_star": round(float(mu_star[i]), 4),
                "weight": round(float(weights[i]), 3),
                "base_score": round(float(scores[i]), 2),
            })
        return rows
    except Exception:
        impact = weights * sigma
        order = np.argsort(-impact)
        return [{
            "dimension": names[int(i)],
            "mu_star": round(float(impact[i]), 4),
            "weight": round(float(weights[i]), 3),
            "base_score": round(float(scores[i]), 2),
            "approx": True,
        } for i in order[:5]]


def _interpret_score(
    mean: float,
    breach: float,
    critical: float,
    lo: float,
    hi: float,
    p95: float,
    tail_mean: float,
    money: Optional[dict],
) -> str:
    parts = [
        f"综合评分不确定性：模拟均值 {mean:.2f}，80% 区间 [{lo:.2f}, {hi:.2f}]（评分 1–4，不是金额）。",
        f"高分位 P95={p95:.2f}，高于 P95 的条件均值 {tail_mean:.2f}（评分尾部均值，非货币损失）。",
    ]
    if breach >= 40:
        parts.append(f"模拟中 {breach:.0f}% 的路径综合分超出风险偏好阈值，建议董事会审议。")
    elif breach >= 20:
        parts.append(f"模拟中 {breach:.0f}% 的路径超出风险偏好，需加强监控。")
    else:
        parts.append(f"模拟中 {breach:.0f}% 的路径超出风险偏好，评分层面整体可控。")
    if critical >= 15:
        parts.append(f"落入极高风险评分带的路径占 {critical:.0f}%，须对照应急预案。")
    if money:
        parts.append(money.get("interpretation") or "")
    else:
        parts.append("未填年营收或资产总额，不展示经营冲击情景。")
    return "".join(parts)
