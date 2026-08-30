# -*- coding: utf-8 -*-
"""
可执行行动方案引擎 — 基于 findings/key_risks 生成具可操作性整改计划
对齐 ISO 31000 处理（Treat）阶段 · COSO 风险应对
"""

from __future__ import annotations

from typing import Any, Dict, List

from risk_engine import AssessmentResult, RiskLevel
from risk_workflow import stable_item_id

# 关键风险 → 结构化行动模板
RISK_ACTION_TEMPLATES: Dict[str, dict] = {
    "资产负债率过高": {
        "title": "资产负债结构优化",
        "owner": "CFO / 财务总监",
        "timeline_days": 90,
        "framework": "ISO 31000 §6.5 · COSO 绩效审查",
        "steps": [
            "T+7：完成债务台账（期限/利率/担保/ covenant）",
            "T+30：与主要债权人沟通展期或置换方案",
            "T+60：制定降杠杆路径（资产处置/增资/利润留存）",
            "T+90：董事会审议资本结构目标与执行进度",
        ],
        "deliverables": ["债务结构分析报告", "90天降杠杆行动计划", "董事会决议"],
        "success_criteria": "资产负债率较基线下降 ≥5pp 或达成 covenant 要求",
        "budget": "中（顾问费+可能的财务成本）",
    },
    "流动性风险": {
        "title": "流动性应急与现金流管控",
        "owner": "CFO / 资金经理",
        "timeline_days": 30,
        "framework": "COSO ERM · 流动性管理",
        "steps": [
            "T+3：建立 13 周 rolling cash forecast（日更）",
            "T+7：冻结非必要 CAPEX，加速应收催收",
            "T+14：激活备用授信/过桥融资预案",
            "T+30：滚动更新 forecast 并汇报董事会",
        ],
        "deliverables": ["13周现金流预测表", "应收催收清单", "授信备用方案"],
        "success_criteria": "流动比率≥1.2 且经营现金流为正",
        "budget": "低",
    },
    "企业亏损": {
        "title": "盈利能力修复计划",
        "owner": "CEO / 运营副总裁",
        "timeline_days": 120,
        "framework": "COSO 战略与目标",
        "steps": [
            "T+14：产品线毛利贡献分析，确定止损清单",
            "T+30：启动成本削减（固定/可变分类）",
            "T+60：定价与渠道策略复盘",
            "T+120：实现单月扭亏或达成预算路径",
        ],
        "deliverables": ["产品毛利矩阵", "成本削减方案", "扭亏里程碑"],
        "success_criteria": "净利率转正或较基线改善 ≥3pp",
        "budget": "中",
    },
    "客户集中风险": {
        "title": "客户结构多元化",
        "owner": "销售总监 / CMO",
        "timeline_days": 180,
        "framework": "ISO 31000 风险应对",
        "steps": [
            "T+30：前五大客户合同条款与集中度分析",
            "T+90：新行业/新区域获客计划（目标 3+ 新客户）",
            "T+180：最大单一客户占比下降 ≥5pp",
        ],
        "deliverables": ["客户集中度仪表盘", "新客开发 KPI", "合同分散化方案"],
        "success_criteria": "前五大客户占比<50%",
        "budget": "中（市场投入）",
    },
    "核心人才流失": {
        "title": "关键人才保留计划",
        "owner": "CHRO / HR 总监",
        "timeline_days": 60,
        "framework": "COSO 治理与文化",
        "steps": [
            "T+7：识别关键岗位与继任者缺口",
            "T+21：核心员工 retention package（薪酬/股权/发展）",
            "T+45：敬业度调研与离职面谈机制",
            "T+60：核心人才离职率较基线下降",
        ],
        "deliverables": ["关键岗位清单", "保留方案", "继任计划"],
        "success_criteria": "核心人才离职率<10%",
        "budget": "中-高",
    },
    "网络安全事件": {
        "title": "网络安全加固与事件响应",
        "owner": "CIO / CISO",
        "timeline_days": 90,
        "framework": "ISO 27001 · NIST CSF",
        "steps": [
            "T+7：漏洞扫描与日志审计",
            "T+30：零信任/ MFA / 备份恢复演练",
            "T+60：IR  playbooks 与 tabletop 演练",
            "T+90：等保/ISO27001 差距整改计划",
        ],
        "deliverables": ["安全评估报告", "IR 手册", "演练记录"],
        "success_criteria": "高危漏洞清零，12 个月内零重大事件",
        "budget": "高",
    },
    "税务稽查风险": {
        "title": "税务合规Remediation",
        "owner": "CFO / 税务经理",
        "timeline_days": 60,
        "framework": "COSO 合规",
        "steps": [
            "T+7：聘请外部税务顾问评估敞口",
            "T+21：与税务机关沟通整改方案",
            "T+45：完善发票/转让定价/代扣代缴流程",
            "T+60：完成补缴或获得书面确认",
        ],
        "deliverables": ["税务风险评估", "整改时间表", "内控流程更新"],
        "success_criteria": "无未决重大税务争议",
        "budget": "中-高",
    },
}

DEFAULT_ACTION = {
    "title": "专项风险整改",
    "owner": "风险管理委员会 / 业务负责人",
    "timeline_days": 90,
    "framework": "ISO 31000 §6.5",
    "steps": [
        "T+7：成立跨部门工作小组，明确 RACI",
        "T+14：根因分析与目标 KPI 设定",
        "T+30：执行短期控制措施",
        "T+90：效果评估与制度化",
    ],
    "deliverables": ["整改方案", "进度周报", "复盘报告"],
    "success_criteria": "维度评分下降 ≥0.5 或 KPI 达标",
    "budget": "待评估",
}


def _match_template(key_risk: str) -> dict:
    for key, tpl in RISK_ACTION_TEMPLATES.items():
        if key in key_risk or key_risk in key:
            return tpl
    # 模糊匹配
    for key, tpl in RISK_ACTION_TEMPLATES.items():
        if any(w in key_risk for w in key.split() if len(w) >= 2):
            return tpl
    return DEFAULT_ACTION.copy()


def _priority_from_level(level: RiskLevel, score: float) -> str:
    if level == RiskLevel.CRITICAL or score >= 3.5:
        return "P0"
    if level == RiskLevel.HIGH or score >= 2.8:
        return "P1"
    if level == RiskLevel.MEDIUM or score >= 2.0:
        return "P2"
    return "P3"


def build_action_plans(result: AssessmentResult, solution_db: dict = None) -> dict:
    """生成带步骤、交付物、责任人的行动方案"""
    from solution_generator import SOLUTION_DB
    solution_db = solution_db or SOLUTION_DB

    action_items: List[dict] = []
    seen_titles = set()

    for dim in sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True):
        priority = _priority_from_level(dim.level, dim.score)
        if dim.score < 2.0 and priority == "P3":
            continue

        for kr in dim.key_risks:
            tpl = _match_template(kr)
            title = f"[{dim.name}] {tpl['title']}"
            if title in seen_titles:
                continue
            seen_titles.add(title)
            action_items.append({
                "id": stable_item_id("ACT", result.company_name, dim.name, tpl["title"]),
                "dimension": dim.name,
                "risk_trigger": kr,
                "priority": priority,
                "title": tpl["title"],
                "owner": tpl["owner"],
                "timeline_days": tpl["timeline_days"],
                "framework_ref": tpl["framework"],
                "steps": tpl["steps"],
                "deliverables": tpl["deliverables"],
                "success_criteria": tpl["success_criteria"],
                "budget_estimate": tpl["budget"],
                "current_score": dim.score,
                "target_score": max(1.0, round(dim.score - 0.8, 2)),
            })

        # 维度级方案库补充（仅高风险且 key_risk 未覆盖时）
        if dim.score >= 2.5 and dim.name in solution_db and len([a for a in action_items if a["dimension"] == dim.name]) < 2:
            sol = solution_db[dim.name]
            for measure, p, detail in sol.get("immediate", [])[:2]:
                action_items.append({
                    "id": stable_item_id("ACT", result.company_name, dim.name, measure),
                    "dimension": dim.name,
                    "risk_trigger": dim.findings[0] if dim.findings else dim.name,
                    "priority": "P0" if p in ("高", "紧急", "P0") else "P1",
                    "title": measure,
                    "owner": _owner_for_dimension(dim.name),
                    "timeline_days": 30,
                    "framework_ref": "COSO ERM · ISO 31000",
                    "steps": _expand_detail_to_steps(detail, "立即"),
                    "deliverables": [f"{measure}执行记录"],
                    "success_criteria": f"完成 {measure}",
                    "budget_estimate": "中",
                    "current_score": dim.score,
                    "source": "solution_db",
                })

    # 去重并限数量
    action_items = action_items[:40]
    p0 = sum(1 for a in action_items if a["priority"] == "P0")

    try:
        from risk_knowledge import lookup_citations
        industry = ""
        if result.all_raw_data:
            industry = (result.all_raw_data.get("企业基本信息") or {}).get("所属行业") or ""
        for a in action_items:
            high = a.get("priority") in ("P0", "P1") or float(a.get("current_score") or 0) >= 2.5
            if not high:
                continue
            cites = lookup_citations(a.get("dimension") or "", industry, limit=2)
            if cites:
                a["citations"] = cites
                a["regulatory_refs"] = [c["title"] for c in cites]
    except Exception:
        pass

    # 注入 ISO 31000 应对策略与根因（深度层）
    try:
        from risk_deep_analysis import build_risk_register
        reg_map = {r["dimension"]: r for r in build_risk_register(result)}
        for a in action_items:
            reg = reg_map.get(a["dimension"], {})
            if reg:
                a["treatment_strategy"] = reg.get("treatment_primary", "")
                a["root_causes"] = [rc["cause"] for rc in reg.get("root_causes", [])[:3]]
                if not a.get("citations"):
                    a["regulatory_refs"] = reg.get("regulatory_refs", [])
                a["residual_target"] = reg.get("residual_score")
    except Exception:
        pass

    return {
        "total_actions": len(action_items),
        "p0_count": p0,
        "action_items": action_items,
        "raci_note": "R：Responsible 执行 · A：Accountable 问责 · C：Consulted 咨询 · I：Informed 知会",
        "implementation_phases": [
            {"phase": "0-30天", "focus": "P0 立即行动、流动性/合规/安全", "actions": [a["id"] for a in action_items if a["priority"] == "P0"][:8]},
            {"phase": "31-90天", "focus": "P1 制度与流程建设", "actions": [a["id"] for a in action_items if a["priority"] == "P1"][:10]},
            {"phase": "91-365天", "focus": "P2/P3 持续优化与长效机制", "actions": [a["id"] for a in action_items if a["priority"] in ("P2", "P3")][:10]},
        ],
    }


def _owner_for_dimension(dim_name: str) -> str:
    owners = {
        "财务风险": "CFO", "法律与合规风险": "法务总监/合规官", "供应链风险": "供应链总监",
        "技术与信息安全风险": "CIO/CISO", "人力资源风险": "CHRO", "安全生产风险": "EHS 总监",
        "环境风险": "EHS/可持续发展负责人", "经营风险": "COO/销售总监", "税务风险": "税务经理",
    }
    return owners.get(dim_name, "业务负责人")


def _expand_detail_to_steps(detail: str, label: str) -> List[str]:
    parts = [p.strip() for p in detail.replace("；", ";").split(";") if p.strip()]
    if len(parts) >= 2:
        return [f"{label}：{p}" for p in parts[:4]]
    return [f"{label}：{detail}", f"{label}：跟踪执行并月度复盘"]
