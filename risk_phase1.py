# -*- coding: utf-8 -*-
"""
Phase-1 增量增强（不改框架）
- 数据完整度 / 置信度门禁与决策影响说明
- 多文件包分类与补充材料清单
- 行业分位对标（在现有 benchmark 上增强）
- 高风险维度可验证行动包（验收标准 / 证据 / 复验方法）
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

from risk_config import get_industry_profile
from risk_engine import AssessmentResult

# 同业风险评分分布（规则校准模型：分越低越好）
# mean/std 表示同业综合风险分的中心与离散度，用于分位估计，非虚构企业名单。
PEER_SCORE_DIST: Dict[str, Dict[str, float]] = {
    "制造业": {"mean": 1.95, "std": 0.55},
    "化工": {"mean": 2.15, "std": 0.60},
    "能源": {"mean": 2.05, "std": 0.58},
    "建筑": {"mean": 2.25, "std": 0.62},
    "交通运输": {"mean": 2.00, "std": 0.55},
    "信息技术": {"mean": 1.70, "std": 0.50},
    "金融": {"mean": 1.85, "std": 0.48},
    "批发零售": {"mean": 1.90, "std": 0.52},
    "房地产": {"mean": 2.40, "std": 0.65},
    "医疗健康": {"mean": 1.80, "std": 0.50},
    "物流": {"mean": 2.00, "std": 0.55},
    "新能源": {"mean": 2.10, "std": 0.58},
    "教育": {"mean": 1.75, "std": 0.48},
    "农业": {"mean": 2.05, "std": 0.58},
    "其他": {"mean": 2.00, "std": 0.55},
}

CRITICAL_SHEETS = [
    "企业基本信息",
    "财务风险",
    "经营风险",
    "法律合规风险",
    "安全生产风险",
]


def _norm_cdf(x: float, mean: float, std: float) -> float:
    if std <= 1e-9:
        return 1.0 if x >= mean else 0.0
    z = (x - mean) / (std * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def build_data_quality_gate(
    form_stats: Optional[dict],
    form_data: Optional[dict] = None,
    template: Optional[dict] = None,
) -> dict:
    """完整度门禁：pass / caution / block + 对结论可信度的影响说明。"""
    stats = form_stats or {}
    key_pct = float(stats.get("key_completion_pct") or 0)
    total_pct = float(stats.get("completion_pct") or 0)
    scoring_total = int(stats.get("scoring_sheets_total") or 1) or 1
    scoring_filled = int(stats.get("scoring_sheets_filled") or 0)
    scoring_ratio = scoring_filled / scoring_total * 100

    conf = round(min(100, max(5, key_pct * 0.45 + total_pct * 0.35 + scoring_ratio * 0.20)), 1)
    if conf < 35 or key_pct < 25 or scoring_filled == 0:
        gate = "block"
        gate_label = "数据不足 · 不建议直接决策"
    elif conf < 60 or key_pct < 50:
        gate = "caution"
        gate_label = "可用作管理参考 · 建议补充后再定案"
    else:
        gate = "pass"
        gate_label = "数据充分 · 结论可用于经营与风控决策"

    missing_keys: List[str] = []
    empty_critical_sheets: List[str] = []
    sheet_stats = stats.get("sheet_stats") or {}
    form_data = form_data or {}

    if template:
        for sheet_name, info in template.items():
            for f in info.get("fields", []):
                if not f.get("is_key"):
                    continue
                val = (form_data.get(sheet_name) or {}).get(f["name"], "")
                if val is None or not str(val).strip():
                    missing_keys.append(f"{sheet_name} / {f['name']}")
                    if len(missing_keys) >= 12:
                        break
            if len(missing_keys) >= 12:
                break

    for sn in CRITICAL_SHEETS:
        st = sheet_stats.get(sn) or {}
        # template sheet names may vary slightly
        matched = sn
        if sn not in sheet_stats:
            for k in sheet_stats:
                if sn[:4] in k or k in sn:
                    matched = k
                    st = sheet_stats[k]
                    break
        if int(st.get("filled") or 0) <= 0:
            empty_critical_sheets.append(matched)

    impact = []
    if gate == "block":
        impact.append("当前置信度偏低，综合评分与整改优先级可能偏差较大，勿作为董事会终局依据。")
        impact.append("优先补齐企业基本信息、财务、经营、合规、安全等高权重表。")
    elif gate == "caution":
        impact.append("结论可用于内部排期与试点整改，重大资本/保险决策前请提高关键字段完成度。")
    else:
        impact.append("数据支撑度较好，可结合可验证行动包推进 90 天闭环。")

    if empty_critical_sheets:
        impact.append("未填关键表：" + "、".join(empty_critical_sheets[:5]))

    return {
        "gate": gate,
        "gate_label": gate_label,
        "confidence_score": conf,
        "key_completion_pct": key_pct,
        "completion_pct": total_pct,
        "scoring_sheets_filled": scoring_filled,
        "scoring_sheets_total": scoring_total,
        "missing_key_fields": missing_keys[:12],
        "empty_critical_sheets": empty_critical_sheets,
        "decision_impact": impact,
        "recommended_min_key_pct": 50,
        "recommended_min_confidence": 60,
    }


def classify_supplement_file(filename: str, size_bytes: int = 0) -> dict:
    """补充材料分类（轻量，不依赖重型解析库）。"""
    name = os.path.basename(filename or "")
    lower = name.lower()
    ext = os.path.splitext(lower)[1]
    category = "其他材料"
    role = "参考"
    if ext in (".xlsx", ".xlsm", ".xls"):
        category = "风险搜集表/结构化表"
        role = "主数据"
    elif ext in (".pdf",):
        category = "PDF 报告/制度/合同"
        role = "证据"
    elif ext in (".docx", ".doc"):
        category = "Word 制度/说明"
        role = "证据"
    elif ext in (".csv", ".txt", ".md"):
        category = "文本/明细数据"
        role = "补充"
    elif ext in (".png", ".jpg", ".jpeg", ".webp"):
        category = "证照/影像"
        role = "证据"

    hints = []
    for kw, tip in [
        ("财报", "疑似财务报表"),
        ("审计", "疑似审计报告"),
        ("保单", "疑似保险保单"),
        ("合同", "疑似合同文本"),
        ("制度", "疑似内控/制度文件"),
        ("ISO", "疑似认证/体系文件"),
        ("安全", "疑似安全相关材料"),
        ("ESG", "疑似 ESG/环境材料"),
    ]:
        if kw.lower() in lower or kw in name:
            hints.append(tip)

    return {
        "filename": name,
        "ext": ext,
        "size_kb": round(max(0, size_bytes) / 1024.0, 1),
        "category": category,
        "role": role,
        "hints": hints[:3],
    }


def extract_text_preview(filepath: str, max_chars: int = 8000) -> str:
    """尽力提取文本预览：PDF 文字层 → OCR，Word，纯文本。"""
    lower = filepath.lower()
    try:
        if lower.endswith((".txt", ".md", ".csv")):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        if lower.endswith((".docx",)):
            try:
                from docx import Document  # type: ignore
                doc = Document(filepath)
                text = "\n".join(p.text for p in doc.paragraphs if p.text)
                return text[:max_chars]
            except Exception:
                return ""
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
            try:
                from ocr_engine import ocr_images
                with open(filepath, "rb") as f:
                    result = ocr_images([f.read()])
                return (result.get("text") or "")[:max_chars]
            except Exception:
                return ""
        if lower.endswith(".pdf"):
            text = ""
            try:
                from pypdf import PdfReader  # type: ignore
            except Exception:
                try:
                    from PyPDF2 import PdfReader  # type: ignore
                except Exception:
                    PdfReader = None  # type: ignore
            if PdfReader is not None:
                try:
                    reader = PdfReader(filepath)
                    chunks = []
                    for page in reader.pages[:6]:
                        chunks.append(page.extract_text() or "")
                        if sum(len(c) for c in chunks) >= max_chars:
                            break
                    text = "".join(chunks)[:max_chars]
                except Exception:
                    text = ""
            compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            if len(compact) >= 80:
                return compact[:max_chars]
            try:
                from ocr_engine import ocr_images, render_pdf_pages
                with open(filepath, "rb") as f:
                    data = f.read()
                images = render_pdf_pages(data)
                if images:
                    ocr = ocr_images(images)
                    ocr_text = ocr.get("text") or ""
                    if ocr_text:
                        return ocr_text[:max_chars]
            except Exception:
                pass
            return compact[:max_chars]
    except Exception:
        return ""
    return ""


def build_supplement_package(file_infos: List[dict]) -> dict:
    """汇总补充材料对评估的贡献说明。"""
    items = file_infos or []
    roles = {}
    for it in items:
        roles[it.get("role", "参考")] = roles.get(it.get("role", "参考"), 0) + 1
    coverage = []
    cats = {it.get("category") for it in items}
    if any("搜集表" in (c or "") for c in cats):
        coverage.append("已含结构化主表")
    if any("PDF" in (c or "") or "Word" in (c or "") for c in cats):
        coverage.append("已含制度/合同/报告类证据材料")
    if any("文本" in (c or "") for c in cats):
        coverage.append("已含明细文本数据")
    if not coverage:
        coverage.append("暂无补充材料，建议上传财报/保单/制度以提高证据链完整度")

    return {
        "file_count": len(items),
        "role_counts": roles,
        "files": items[:30],
        "coverage_notes": coverage,
        "next_step": "主表驱动评分；补充材料用于证据链与复评核验，不直接改写维度分。",
    }


def enhance_industry_benchmark(result: AssessmentResult, basic: Optional[dict], base_benchmark: Optional[dict] = None) -> dict:
    """在现有行业对标上增加分位估计与维度对照。"""
    basic = basic or {}
    profile = get_industry_profile(basic.get("所属行业"))
    industry = profile.get("industry_key", "其他")
    dist = PEER_SCORE_DIST.get(industry, PEER_SCORE_DIST["其他"])
    mean, std = dist["mean"], dist["std"]

    # 比本公司风险更高的同业占比 ≈ 更优分位
    worse_share = (1.0 - _norm_cdf(result.overall_score, mean, std)) * 100.0
    better_than_pct = round(max(1.0, min(99.0, worse_share)), 1)
    if result.overall_score <= mean - 0.6 * std:
        band = "优于多数同业（低风险区）"
    elif result.overall_score <= mean + 0.3 * std:
        band = "接近同业中位"
    elif result.overall_score <= mean + 1.0 * std:
        band = "高于同业中位风险"
    else:
        band = "显著高于同业风险中枢"

    dim_peers = []
    for d in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True)[:8]:
        # 维度级：略抬高运营类行业均值
        d_mean = mean + (0.15 if "安全" in d.name or "环境" in d.name else 0.0)
        d_worse = (1.0 - _norm_cdf(d.score, d_mean, std)) * 100.0
        dim_peers.append({
            "dimension": d.name,
            "score": d.score,
            "level": d.level.value,
            "better_than_peers_pct": round(max(1.0, min(99.0, d_worse)), 1),
            "peer_mean_est": round(d_mean, 2),
        })

    out = dict(base_benchmark or {})
    out.update({
        "industry": industry,
        "profile_description": profile.get("description", out.get("profile_description", "")),
        "percentile": {
            "better_than_peers_pct": better_than_pct,
            "peer_mean_est": mean,
            "peer_std_est": std,
            "band": band,
            "method_note": "基于行业校准分布的分位估计，用于管理对标；非交易所披露同业样本。",
        },
        "dimension_peer_positions": dim_peers,
        "thresholds": {
            "debt_ratio_warn": profile.get("debt_ratio_warn"),
            "current_ratio_low": profile.get("current_ratio_low"),
            "customer_conc_warn": profile.get("customer_conc_warn"),
            "gross_margin_floor": profile.get("gross_margin_floor"),
        },
    })
    if "benchmarks" not in out:
        out["benchmarks"] = (base_benchmark or {}).get("benchmarks", [])
    if "overall_vs_industry" not in out:
        out["overall_vs_industry"] = band
    return out


def build_verifiable_action_packs(result: AssessmentResult, action_plans: Optional[dict] = None, form_stats: Optional[dict] = None) -> dict:
    """把行动项升级为可验证包：基线→目标→证据→验收→复验。"""
    plans = action_plans or {}
    items = list(plans.get("action_items") or [])
    # 若行动项为空，从高风险维度生成最小包
    if not items:
        for dim in sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True):
            if dim.score < 2.0:
                continue
            items.append({
                "id": f"ACT-AUTO-{dim.name}",
                "dimension": dim.name,
                "priority": "P1" if dim.score >= 2.8 else "P2",
                "title": f"{dim.name}专项整改",
                "owner": "业务负责人 / 风险管理委员会",
                "timeline_days": 90 if dim.score < 2.8 else 60,
                "steps": [
                    "T+7：成立工作组并确认 RACI",
                    "T+30：完成根因与控制缺口清单",
                    "T+60：落实关键控制措施",
                    "T+90：复评验证评分与 KPI",
                ],
                "deliverables": ["整改方案", "证据清单", "复评报告"],
                "success_criteria": f"{dim.name}评分下降 ≥0.5",
                "current_score": dim.score,
                "target_score": max(1.0, round(dim.score - 0.8, 2)),
                "risk_trigger": (dim.key_risks[0] if dim.key_risks else dim.name),
            })
            if len(items) >= 5:
                break

    packs = []
    for a in items[:12]:
        dim_name = a.get("dimension") or ""
        dim = result.dimensions.get(dim_name)
        baseline = float(a.get("current_score") or (dim.score if dim else 0) or 0)
        target = float(a.get("target_score") or max(1.0, round(baseline - 0.8, 2)))
        evidence = []
        if dim and dim.findings:
            evidence.append("评估发现：" + "；".join(dim.findings[:2]))
        if dim and dim.key_risks:
            evidence.append("关键风险触发：" + "、".join(dim.key_risks[:3]))
        evidence.extend([f"交付物：{d}" for d in (a.get("deliverables") or [])[:3]])
        if form_stats and form_stats.get("key_completion_pct", 100) < 60:
            evidence.append("复评前补齐该维度关键字段，确保验收可比")

        packs.append({
            "id": a.get("id"),
            "dimension": dim_name,
            "priority": a.get("priority", "P2"),
            "title": a.get("title"),
            "owner": a.get("owner"),
            "deadline_days": a.get("timeline_days", 90),
            "baseline_score": baseline,
            "target_score": target,
            "delta_target": round(baseline - target, 2),
            "milestones": a.get("steps") or [],
            "deliverables": a.get("deliverables") or [],
            "evidence_needed": evidence[:6],
            "acceptance_criteria": a.get("success_criteria") or f"{dim_name}评分降至 {target}",
            "verification_method": (
                f"到期复评：维度评分 ≤ {target}，且交付物齐全；"
                f"建议纳入 KRI 仪表盘按月跟踪。"
            ),
            "framework_ref": a.get("framework_ref") or a.get("framework") or "ISO 31000 §6.5",
            "treatment_strategy": a.get("treatment_strategy"),
            "root_causes": a.get("root_causes") or [],
        })

    p0 = sum(1 for p in packs if p.get("priority") == "P0")
    return {
        "total": len(packs),
        "p0_count": p0,
        "packs": packs,
        "howto": "每个行动包必须具备：基线分、目标分、证据、验收标准、复验方法。完成后请复评验证 Δ评分。",
    }


def build_phase1_package(
    result: AssessmentResult,
    form_stats: Optional[dict] = None,
    basic_info: Optional[dict] = None,
    action_plans: Optional[dict] = None,
    deep_analysis: Optional[dict] = None,
    template: Optional[dict] = None,
    supplements: Optional[dict] = None,
) -> dict:
    """汇总 Phase-1 增强包，供 enrich_assessment_full 挂载。"""
    basic = basic_info or (result.all_raw_data or {}).get("企业基本信息", {}) or {}
    gate = build_data_quality_gate(form_stats, result.all_raw_data or {}, template)
    base_bench = None
    if deep_analysis and isinstance(deep_analysis, dict):
        base_bench = deep_analysis.get("industry_benchmark")
    if base_bench is None:
        try:
            from risk_deep_analysis import build_industry_benchmark
            base_bench = build_industry_benchmark(result, basic)
        except Exception:
            base_bench = {}

    benchmark = enhance_industry_benchmark(result, basic, base_bench)
    verifiable = build_verifiable_action_packs(result, action_plans, form_stats)

    # 回写增强后的 benchmark 到 deep_analysis（若存在）
    if deep_analysis is not None and isinstance(deep_analysis, dict):
        deep_analysis["industry_benchmark"] = benchmark

    summary_lines = [
        f"数据门禁：{gate['gate_label']}（置信度 {gate['confidence_score']}%）。",
        f"行业对标：优于约 {benchmark.get('percentile', {}).get('better_than_peers_pct', '--')}% 同业（{benchmark.get('percentile', {}).get('band', '')}）。",
        f"可验证行动包 {verifiable['total']} 项（P0 {verifiable['p0_count']}）。",
    ]
    if supplements:
        summary_lines.append(f"补充材料 {supplements.get('file_count', 0)} 份：" + "；".join(supplements.get("coverage_notes") or [])[:120])

    return {
        "version": "phase1",
        "data_quality_gate": gate,
        "industry_benchmark": benchmark,
        "verifiable_actions": verifiable,
        "supplements": supplements,
        "summary_lines": summary_lines,
        "standards_note": "Phase-1 增强对齐 ISO 31000 处理与监控 · COSO 绩效审查 · 证据链可审计",
    }
