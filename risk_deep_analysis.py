# -*- coding: utf-8 -*-
"""
深度风险分析引擎 — 对齐国际先进 ERM 实践
ISO 31000 风险登记 · 固有/残余风险 · 应对策略 · 根因分析 · 控制缺口
COSO ERM 2017 · TCFD · ISO 31010 分析技术
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from risk_config import get_industry_profile
from risk_engine import AssessmentResult, RiskLevel
from risk_framework import DIMENSION_FRAMEWORK_MAP
from risk_matrix import resolve_prob_impact
from risk_workflow import stable_item_id

# ISO 31000:2018 §6.5 风险处理选项
TREATMENT_OPTIONS = ("规避 Avoid", "降低 Reduce", "转移 Share", "接受 Retain")

# 维度 → 默认应对策略倾向（score>=2.5 时）
TREATMENT_MAP: Dict[str, dict] = {
    "财务风险": {"primary": "降低 Reduce", "secondary": "转移 Share", "rationale": "通过资本结构优化与流动性管控降低敞口，必要时引入战略投资者分担"},
    "法律与合规风险": {"primary": "降低 Reduce", "secondary": "规避 Avoid", "rationale": "强化合规体系；对高风险业务条线考虑剥离或暂停"},
    "安全生产风险": {"primary": "降低 Reduce", "secondary": "转移 Share", "rationale": "工程控制与管理控制；通过保险转移残余物理风险"},
    "环境风险": {"primary": "降低 Reduce", "secondary": "规避 Avoid", "rationale": "环保设施升级；对无法达标产能实施关停或搬迁"},
    "供应链风险": {"primary": "降低 Reduce", "secondary": "转移 Share", "rationale": "供应商多元化与库存缓冲；关键物料长期协议锁定"},
    "技术与信息安全风险": {"primary": "降低 Reduce", "secondary": "转移 Share", "rationale": "零信任架构与备份；网络安全保险"},
    "战略与声誉风险": {"primary": "降低 Reduce", "secondary": "接受 Retain", "rationale": "舆情监测与危机公关；对低概率声誉事件设定接受阈值"},
    "数据隐私合规风险": {"primary": "降低 Reduce", "secondary": "规避 Avoid", "rationale": "DPIA 与数据最小化；高风险数据处理活动暂停"},
    "公司治理风险": {"primary": "降低 Reduce", "secondary": "接受 Retain", "rationale": "三道防线与董事会治理强化"},
    "反贿赂道德合规风险": {"primary": "规避 Avoid", "secondary": "降低 Reduce", "rationale": "对高风险市场/第三方采取零容忍或强化 DD"},
}

ROOT_CAUSE_PATTERNS: Dict[str, List[str]] = {
    "财务": ["资本结构激进", "盈利模型薄弱", "现金流管理缺失", "预算与预测体系不健全"],
    "流动性": ["应收管理失控", "存货积压", "短债长投", "授信储备不足"],
    "合规": ["合规职能薄弱", "制度更新滞后", "培训与监督不足", "高层 tone-at-the-top 不足"],
    "安全": ["安全投入不足", "隐患闭环失效", "承包商管理薄弱", "应急演练形式化"],
    "供应链": ["单一来源依赖", "地缘政治暴露", "库存策略激进", "供应商准入宽松"],
    "技术": ["IT 治理缺失", "补丁与权限管理薄弱", "备份与 DR 未验证", "人员安全意识不足"],
    "人才": ["薪酬竞争力不足", "继任计划缺失", "文化认同弱", "关键岗位过度集中"],
    "声誉": ["舆情监测缺失", "危机预案未演练", "ESG 披露不足", "客户体验管理弱"],
    "治理": ["董事会监督不足", "风险职能未独立", "内审影响力弱", "风险偏好未量化"],
}

REGULATORY_REFS: Dict[str, List[str]] = {
    "财务风险": ["企业会计准则", "银行贷款 covenant", "巴塞尔流动性原则（参考）"],
    "法律与合规风险": ["民法典", "公司法", "行业监管条例", "劳动法"],
    "安全生产风险": ["安全生产法", "危险化学品安全管理条例", "ISO 45001"],
    "环境风险": ["环境保护法", "排污许可管理条例", "ISO 14001", "TCFD 披露"],
    "数据隐私合规风险": ["个人信息保护法 PIPL", "数据安全法", "GDPR（跨境）"],
    "反贿赂道德合规风险": ["反不正当竞争法", "ISO 37001", "FCPA/UK Bribery Act（涉外）"],
    "税务风险": ["税收征管法", "企业所得税法", "转让定价规则"],
    "供应链风险": ["商务部供应链安全指引", "出口管制条例"],
}


def _infer_root_causes(dimension: str, key_risks: List[str], findings: List[str]) -> List[dict]:
    text = " ".join(key_risks + findings)
    causes = []
    for tag, patterns in ROOT_CAUSE_PATTERNS.items():
        if any(k in text for k in (tag, dimension[:2])) or tag in dimension:
            for i, p in enumerate(patterns[:2], 1):
                causes.append({"level": i, "cause": p, "category": tag})
    if not causes and findings:
        causes.append({"level": 1, "cause": findings[0], "category": "直接发现"})
    if not causes:
        causes.append({"level": 1, "cause": f"{dimension}管控体系待完善", "category": "系统性"})
    return causes[:4]


def _control_effectiveness(score: float, key_count: int) -> dict:
    """控制有效性估计（COSO 控制活动）"""
    if score < 1.8 and key_count == 0:
        eff, gap = "有效", "低"
    elif score < 2.5:
        eff, gap = "基本有效", "中"
    elif score < 3.0:
        eff, gap = "部分有效", "高"
    else:
        eff, gap = "无效/重大缺口", "极高"
    return {
        "effectiveness": eff,
        "gap_level": gap,
        "recommended_controls": _suggest_controls(score),
    }


def _suggest_controls(score: float) -> List[str]:
    if score >= 3.0:
        return ["董事会层面专项督导", "独立第三方诊断", "暂停相关高风险活动直至整改"]
    if score >= 2.5:
        return ["增设 KRI 预警阈值", "月度风险委员会审议", "强化第二道防线复核"]
    if score >= 2.0:
        return ["完善 SOP 与培训", "季度自评与抽查", "明确责任人 KPI"]
    return ["维持现有控制", "年度复评"]


def build_risk_register(result: AssessmentResult) -> List[dict]:
    """ISO 31000 风险登记册"""
    form = result.all_raw_data or {}
    register = []
    for i, dim in enumerate(sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True), 1):
        cell = resolve_prob_impact(dim, form)
        prob, impact = cell["probability"], cell["impact"]
        rating = cell["matrix_rating"]
        treatment = TREATMENT_MAP.get(dim.name, {
            "primary": "降低 Reduce", "secondary": "接受 Retain",
            "rationale": "按 ISO 31000 优先降低风险至可接受水平",
        })
        ctrl = _control_effectiveness(dim.score, len(dim.key_risks))
        inherent = round(dim.score, 2)
        residual = round(max(1.0, dim.score - (0.6 if ctrl["gap_level"] == "极高" else 0.3 if ctrl["gap_level"] == "高" else 0.1)), 2)

        register.append({
            "id": stable_item_id("R", result.company_name, dim.name),
            "seq": f"R-{i:03d}",
            "dimension": dim.name,
            "risk_description": "；".join(dim.key_risks[:3]) or "；".join(dim.findings[:2]) or dim.name,
            "probability": prob,
            "impact": impact,
            "pi_source": cell["source"],
            "inherent_score": inherent,
            "residual_score": residual,
            "risk_rating": rating,
            "level": dim.level.value,
            "weight": dim.weight,
            "treatment_primary": treatment["primary"],
            "treatment_secondary": treatment["secondary"],
            "treatment_rationale": treatment["rationale"],
            "control_effectiveness": ctrl["effectiveness"],
            "control_gap": ctrl["gap_level"],
            "recommended_controls": ctrl["recommended_controls"],
            "root_causes": _infer_root_causes(dim.name, dim.key_risks, dim.findings),
            "regulatory_refs": REGULATORY_REFS.get(dim.name, ["ISO 31000:2018"]),
            "owner": _default_owner(dim.name),
            "review_cycle": "月度" if dim.score >= 3.0 else "季度" if dim.score >= 2.5 else "半年度",
        })
    return register


def _default_owner(dim: str) -> str:
    owners = {
        "财务风险": "CFO", "法律与合规风险": "首席合规官", "供应链风险": "供应链总监",
        "技术与信息安全风险": "CISO", "安全生产风险": "EHS 总监", "环境风险": "EHS 负责人",
        "公司治理风险": "董事会/审计委员会", "数据隐私合规风险": "DPO/法务",
        "战略与声誉风险": "CEO/品牌负责人", "业务连续性风险": "COO",
    }
    return owners.get(dim, "风险管理委员会")


def build_correlation_insights(result: AssessmentResult) -> List[dict]:
    """维度关联洞察（基于已知风险传导路径）"""
    sm = {d.name: d.score for d in result.dimensions.values()}
    paths = [
        ("财务风险", "信用风险", "流动性恶化导致违约上升"),
        ("供应链风险", "生产运营风险", "断供引发生产停滞"),
        ("法律与合规风险", "战略与声誉风险", "合规事件损害品牌"),
        ("技术与信息安全风险", "数据隐私合规风险", "安全事件触发隐私违规"),
        ("公司治理风险", "关联方与集团风险", "治理薄弱加剧关联交易风险"),
        ("行业与市场风险", "经营风险", "市场下行传导至经营指标"),
        ("财务风险", "经营风险", "资金链紧张制约经营扩张"),
        ("生产运营风险", "安全生产风险", "赶工增产放大安全隐患"),
        ("税务风险", "法律与合规风险", "税务争议引发监管连锁反应"),
        ("人力资源风险", "经营风险", "核心人才流失影响交付能力"),
        ("环境风险", "战略与声誉风险", "环保处罚冲击品牌形象"),
        ("供应链风险", "财务风险", "原材料涨价挤压利润与现金流"),
    ]
    insights = []
    for a, b, msg in paths:
        sa, sb = sm.get(a), sm.get(b)
        if sa is None or sb is None:
            continue
        if sa >= 2.3 and sb >= 2.3:
            strength = "强" if sa >= 2.8 and sb >= 2.8 else "中"
            insights.append({
                "from": a, "to": b, "message": msg,
                "scores": f"{sa:.2f} → {sb:.2f}", "strength": strength,
            })
    return insights[:12]


def build_correlation_network(
    result: AssessmentResult,
    insights: Optional[List[dict]] = None,
    cross_alerts: Optional[List[dict]] = None,
) -> dict:
    """构建风险关联网络（节点 + 边），供前端力导向/环形图渲染"""
    insights = insights if insights is not None else build_correlation_insights(result)
    cross_alerts = cross_alerts or []

    level_color = {
        "低风险": "#6BCB77", "中等风险": "#FFD93D",
        "高风险": "#FF6B6B", "极高风险": "#C00000",
    }
    nodes = []
    for d in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True):
        nodes.append({
            "id": d.name,
            "label": d.name.replace("风险", ""),
            "score": d.score,
            "level": d.level.value,
            "color": level_color.get(d.level.value, "#2d6a9f"),
            "size": round(10 + d.score * 8, 1),
        })

    edges = []
    seen = set()
    for i, ins in enumerate(insights):
        key = (ins["from"], ins["to"])
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "id": f"path-{i}",
            "source": ins["from"],
            "target": ins["to"],
            "label": ins["message"],
            "strength": ins.get("strength", "中"),
            "type": "causal",
            "weight": 3 if ins.get("strength") == "强" else 2,
        })

    for ci, alert in enumerate(cross_alerts):
        dims = alert.get("dimensions") or []
        for j in range(len(dims)):
            for k in range(j + 1, len(dims)):
                a, b = dims[j], dims[k]
                key = tuple(sorted([a, b]))
                if key in seen:
                    continue
                seen.add(key)
                edges.append({
                    "id": f"cluster-{ci}-{j}-{k}",
                    "source": a,
                    "target": b,
                    "label": alert.get("cluster", "交叉风险"),
                    "strength": alert.get("severity", "中"),
                    "type": "cluster",
                    "weight": 1,
                })

    active_nodes = {e["source"] for e in edges} | {e["target"] for e in edges}
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "active_nodes": len(active_nodes),
            "causal_paths": sum(1 for e in edges if e["type"] == "causal"),
            "cluster_links": sum(1 for e in edges if e["type"] == "cluster"),
        },
    }


def build_industry_benchmark(result: AssessmentResult, basic: dict) -> dict:
    profile = get_industry_profile(basic.get("所属行业"))
    industry = profile.get("industry_key", "其他")
    benchmarks = []

    fin = result.dimensions.get("财务风险")
    if fin:
        debt_warn = profile.get("debt_ratio_warn", 65)
        raw = fin.raw_data or {}
        debt = _sf(raw.get("资产负债率(%)"))
        if debt is not None:
            benchmarks.append({
                "metric": "资产负债率",
                "value": debt,
                "industry_threshold": debt_warn,
                "status": "超标" if debt > debt_warn else "达标",
                "note": f"{industry}行业参考阈值 {debt_warn}%",
            })

    op = result.dimensions.get("经营风险")
    if op:
        raw = op.raw_data or {}
        conc = _sf(raw.get("前五大客户收入占比(%)"))
        cw = profile.get("customer_conc_warn", 50)
        if conc is not None:
            benchmarks.append({
                "metric": "客户集中度",
                "value": conc,
                "industry_threshold": cw,
                "status": "超标" if conc > cw else "达标",
                "note": f"{industry}行业前五大客户占比参考 <{cw}%",
            })

    return {
        "industry": industry,
        "profile_description": profile.get("description", ""),
        "benchmarks": benchmarks,
        "overall_vs_industry": _overall_industry_position(result.overall_score, industry),
    }


def _overall_industry_position(score: float, industry: str) -> str:
    # 行业差异化总体判断
    tight_industries = {"房地产", "建筑", "化工"}
    if industry in tight_industries and score >= 2.3:
        return "高于行业典型承受度，建议董事会关注"
    if score >= 2.8:
        return "显著偏离稳健经营区间"
    if score >= 2.0:
        return "处于行业中等风险区间，需持续监控"
    return "整体处于行业可接受区间"


def _sf(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def build_board_recommendations(result: AssessmentResult, register: List[dict]) -> List[dict]:
    recs = []
    if result.overall_score >= 2.8:
        recs.append({
            "priority": "P0",
            "title": "召开董事会风险专项会议",
            "detail": "审议综合风险评级、风险 appetite 偏离项及 90 天整改路线图",
            "framework": "COSO 治理 · 董事会监督",
        })
    high_regs = [r for r in register if r["risk_rating"] in ("极高", "高")][:5]
    for r in high_regs:
        recs.append({
            "priority": "P1" if r["risk_rating"] == "高" else "P0",
            "title": f"{r['dimension']} — {r['treatment_primary']}",
            "detail": f"{r['treatment_rationale']}；控制缺口：{r['control_gap']}",
            "framework": "ISO 31000 §6.5",
        })
    if not recs:
        recs.append({
            "priority": "P3",
            "title": "维持季度风险复评机制",
            "detail": "当前风险整体可控，建议持续 KRI 监控与年度情景分析更新",
            "framework": "COSO 监控活动",
        })
    return recs[:10]


def build_deep_solutions(result: AssessmentResult) -> List[dict]:
    """科学、可操作的深度解决方案包"""
    from solution_generator import SOLUTION_DB

    packages = []
    for dim in sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True):
        if dim.score < 2.0:
            continue
        sol = SOLUTION_DB.get(dim.name, {})
        treatment = TREATMENT_MAP.get(dim.name, {"primary": "降低 Reduce", "rationale": "系统性降低风险暴露"})
        rca = _infer_root_causes(dim.name, dim.key_risks, dim.findings)

        packages.append({
            "dimension": dim.name,
            "score": dim.score,
            "level": dim.level.value,
            "title": sol.get("title", f"{dim.name}深度整改方案"),
            "scientific_basis": [
                DIMENSION_FRAMEWORK_MAP.get(dim.name, {}).get("iso31000", "ISO 31000"),
                f"应对策略：{treatment.get('primary', '降低 Reduce')}",
                *REGULATORY_REFS.get(dim.name, [])[:2],
            ],
            "root_cause_analysis": rca,
            "problem_statement": _build_problem_statement(dim),
            "solution_hypothesis": f"通过{treatment.get('primary', '降低')}措施，预计 6–12 个月内维度评分从 {dim.score:.2f} 降至 {max(1.0, dim.score - 0.8):.2f}",
            "immediate_actions": _enrich_measures(sol.get("immediate", []), "立即", dim.name),
            "short_term_actions": _enrich_measures(sol.get("short_term", []), "短期", dim.name),
            "medium_term_actions": _enrich_measures(sol.get("medium_term", []), "中期", dim.name),
            "kpis": [{"name": k, "target": t, "freq": f} for k, t, f in sol.get("kpi", [])],
            "success_metrics": _success_metrics(dim),
            "resources": _resource_estimate(dim.score),
            "monitoring": f"纳入 KRI 仪表盘，{ '月度' if dim.score >= 2.8 else '季度' }向风险委员会汇报",
        })
        try:
            from risk_knowledge import lookup_citations
            industry = ((result.all_raw_data or {}).get("企业基本信息") or {}).get("所属行业") or ""
            packages[-1]["citations"] = lookup_citations(dim.name, industry, limit=2)
        except Exception:
            packages[-1]["citations"] = []
    return packages[:12]


def _build_problem_statement(dim) -> str:
    parts = dim.key_risks[:2] or dim.findings[:2]
    if parts:
        return f"{dim.name}方面存在：{'；'.join(parts)}，综合评分 {dim.score:.2f}/4.00（{dim.level.value}）。"
    return f"{dim.name}评分 {dim.score:.2f}，需按 ISO 31000 流程启动风险处理。"


def _enrich_measures(items: list, phase: str, dim_name: str) -> List[dict]:
    owner = _default_owner(dim_name)
    out = []
    for item in items[:4]:
        if len(item) >= 3:
            measure, priority, detail = item[0], item[1], item[2]
            out.append({
                "phase": phase,
                "measure": measure,
                "priority": priority,
                "detail": detail,
                "owner": owner,
                "verification": f"交付物验收 + {phase}复盘会议",
            })
    return out


def _success_metrics(dim) -> List[str]:
    m = [f"{dim.name}评分下降 ≥0.5", "关键风险项清零或降级"]
    if dim.key_risks:
        m.append(f"针对「{dim.key_risks[0]}」建立专项 KPI")
    return m


def _resource_estimate(score: float) -> dict:
    if score >= 3.0:
        return {"budget": "高", "fte": "2-5 人专项组", "external": "建议外部顾问/审计"}
    if score >= 2.5:
        return {"budget": "中", "fte": "1-3 人", "external": "按需引入"}
    return {"budget": "低-中", "fte": "兼职工作组", "external": "一般不需要"}


def run_deep_analysis(
    result: AssessmentResult,
    basic: dict = None,
    confidence_pct: float = 50.0,
    cross_alerts: Optional[List[dict]] = None,
) -> dict:
    basic = basic or (result.all_raw_data or {}).get("企业基本信息", {})
    register = build_risk_register(result)
    insights = build_correlation_insights(result)

    quant = three_lines = industry_plan = None
    try:
        from risk_quant import run_monte_carlo
        appetite = 2.5
        for k, v in [("保守", 1.8), ("稳健", 2.2), ("平衡", 2.6), ("积极", 3.0)]:
            if k in str(basic.get("风险承受度", "")):
                appetite = v
                break
        quant = run_monte_carlo(
            result, confidence_pct=confidence_pct, appetite_threshold=appetite, basic=basic,
        )
    except Exception:
        pass
    try:
        from risk_three_lines import assess_three_lines
        three_lines = assess_three_lines(result, result.all_raw_data)
    except Exception:
        pass
    try:
        from industry_playbooks import build_industry_action_plan
        industry_plan = build_industry_action_plan(result, basic)
    except Exception:
        pass
    try:
        from risk_correlation import build_correlation_matrix
        corr_matrix = build_correlation_matrix(result)
    except Exception:
        corr_matrix = None

    return {
        "risk_register": register,
        "correlation_insights": insights,
        "correlation_network": build_correlation_network(result, insights, cross_alerts),
        "correlation_matrix": corr_matrix,
        "industry_benchmark": build_industry_benchmark(result, basic),
        "board_recommendations": build_board_recommendations(result, register),
        "deep_solutions": build_deep_solutions(result),
        "monte_carlo": quant,
        "three_lines_of_defense": three_lines,
        "industry_playbook": industry_plan,
        "methodology": {
            "standards": ["ISO 31000:2018", "ISO 31010", "COSO ERM 2017", "TCFD", "IIA", "ISO 22301"],
            "techniques": ["风险登记", "5×5矩阵", "根因分析", "蒙特卡洛", "贝叶斯更新", "关联网络", "三道防线", "情景分析", "KRI", "行业对标"],
            "risk_formula": "先验 → 新观测 → 贝叶斯后验 → 关联网络验证 → ISO 31000 应对",
        },
        "summary": _analysis_summary(result, register),
    }


def _analysis_summary(result: AssessmentResult, register: List[dict]) -> str:
    high = sum(1 for r in register if r["risk_rating"] in ("极高", "高"))
    return (
        f"共登记 {len(register)} 项风险，其中高/极高 {high} 项。"
        f"综合评分 {result.overall_score:.2f}，建议按 ISO 31000 流程完成应对策略审批与 residual risk 监控。"
    )
