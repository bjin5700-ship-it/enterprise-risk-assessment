# -*- coding: utf-8 -*-
"""行业深度方案库 — 对标国际实践的最佳整改路径"""

from __future__ import annotations

from typing import Dict, List

from risk_config import get_industry_profile
from risk_engine import AssessmentResult

INDUSTRY_PLAYBOOKS: Dict[str, dict] = {
    "制造业": {
        "priority_risks": ["供应链中断", "产能利用率", "安全生产", "环保合规"],
        "best_practices": [
            "推行 TPM/OEE 设备综合效率管理，降低非计划停机",
            "核心物料双供应商 + 安全库存策略（ABC 分类）",
            "ISO 45001 + 双重预防机制数字化",
        ],
        "regulatory_focus": ["环保排污许可", "安全生产法", "职业病防治"],
        "kpi_pack": ["产能利用率≥75%", "供应商集中度<50%", "工伤事故=0", "排放达标率100%"],
    },
    "房地产": {
        "priority_risks": ["流动性", "政策调控", "工程合规", "销售回款"],
        "best_practices": [
            "13 周现金流滚动预测 + 预售资金监管合规",
            "项目全周期合规清单（土地/规划/施工/销售）",
            "资产负债率分项目穿透管理",
        ],
        "regulatory_focus": ["三道红线", "预售资金监管", "建筑工程质量条例"],
        "kpi_pack": ["净负债率行业对标", "回款周期<180天", "竣工备案合规100%"],
    },
    "信息技术": {
        "priority_risks": ["数据安全", "人才流失", "技术迭代", "客户集中"],
        "best_practices": [
            "零信任架构 + SDLC 安全左移",
            "核心技术人员股权/项目绑定",
            "ISO 27001 / 等保 2.0 差距整改",
        ],
        "regulatory_focus": ["数据安全法", "PIPL", "等保 2.0"],
        "kpi_pack": ["安全事件=0", "核心流失率<10%", "研发资本化合规"],
    },
    "化工": {
        "priority_risks": ["危化品安全", "环保处罚", "周期波动", "供应链"],
        "best_practices": [
            "HAZOP/SIL 评估 + 重大危险源在线监测",
            "清洁生产审核与碳排放核算",
            "原料长协 + 期货套保组合",
        ],
        "regulatory_focus": ["危化品安全管理条例", "环保督察", "碳排放"],
        "kpi_pack": ["重大隐患=0", "环境处罚=0", "产能利用率>70%"],
    },
    "建筑": {
        "priority_risks": ["回款", "工程安全", "分包合规", "资金链"],
        "best_practices": [
            "项目现金流独立核算 + 业主资信评级",
            "分包商准入与农民工工资专户",
            "工程保险与担保结构优化",
        ],
        "regulatory_focus": ["建筑法", "招投标法", "农民工条例"],
        "kpi_pack": ["应收周转<120天", "安全事故=0", "分包合规率100%"],
    },
    "金融": {
        "priority_risks": ["信用风险", "流动性", "合规监管", "操作风险"],
        "best_practices": [
            "巴塞尔协议 III 流动性指标（LCR/NSFR 思路）",
            "全面风险管理（ERM）与压力测试",
            "反洗钱 KYC/交易监测",
        ],
        "regulatory_focus": ["银保监会监管", "反洗钱法", "资本管理办法"],
        "kpi_pack": ["不良贷款率", "流动性覆盖率", "合规事件=0"],
    },
    "能源": {
        "priority_risks": ["价格波动", "政策调控", "安全环保", "资本开支"],
        "best_practices": [
            "大宗商品套保 + 长协锁价组合",
            "重大设备完整性管理（RBI/RCM）",
            "碳排放与 ESG 披露对齐 TCFD",
        ],
        "regulatory_focus": ["能源法", "安全生产法", "碳排放交易管理办法"],
        "kpi_pack": ["单位能耗下降", "重大事故=0", "资本开支 ROI"],
    },
    "交通运输": {
        "priority_risks": ["运价波动", "燃油成本", "安全事故", "资产折旧"],
        "best_practices": [
            "运价/燃油对冲机制 + 动态定价",
            "车队 Telematics 安全监控",
            "线路盈利模型与空载率优化",
        ],
        "regulatory_focus": ["道路运输条例", "交通安全法", "超限超载治理"],
        "kpi_pack": ["空载率<15%", "事故率行业对标", "单车毛利"],
    },
    "批发零售": {
        "priority_risks": ["库存周转", "薄利竞争", "现金流", "渠道合规"],
        "best_practices": [
            "品类 ABC + 安全库存动态模型",
            "全渠道对账与预售/会员合规",
            "供应商账期与现金流 13 周预测",
        ],
        "regulatory_focus": ["消费者权益保护法", "电子商务法", "价格法"],
        "kpi_pack": ["库存周转天数", "毛利率", "应收周转"],
    },
    "医疗健康": {
        "priority_risks": ["医疗质量", "合规监管", "医保控费", "数据隐私"],
        "best_practices": [
            "JCI/等级评审对标 + 不良事件闭环",
            "药品/器械全流程追溯",
            "患者数据分级保护与 DPIA",
        ],
        "regulatory_focus": ["基本医疗卫生法", "药品管理法", "PIPL"],
        "kpi_pack": ["不良事件率", "合规检查通过率", "医疗纠纷=0"],
    },
    "物流": {
        "priority_risks": ["时效延误", "货损丢失", "运力成本", "客户集中"],
        "best_practices": [
            "TMS/WMS 一体化 + 在途可视化",
            "关键线路冗余运力与 SLA 分层",
            "货损率 KPI 与保险转移",
        ],
        "regulatory_focus": ["邮政法", "道路运输条例", "危险货物运输"],
        "kpi_pack": ["准时率≥95%", "货损率<0.1%", "单车成本"],
    },
    "新能源": {
        "priority_risks": ["政策补贴", "技术迭代", "供应链", "项目并网"],
        "best_practices": [
            "技术路线多元化 + 专利 FTO 评估",
            "关键材料（锂/硅）长协与库存策略",
            "项目 IRR 敏感性分析与并网合规",
        ],
        "regulatory_focus": ["可再生能源法", "并网管理办法", "碳排放"],
        "kpi_pack": ["LCOE 行业对标", "产能利用率", "并网合规100%"],
    },
    "教育": {
        "priority_risks": ["政策合规", "品牌声誉", "师资流失", "预收费"],
        "best_practices": [
            "预收费资金监管与退费机制",
            "教学质量评估与投诉闭环",
            "核心教师激励与继任计划",
        ],
        "regulatory_focus": ["民办教育促进法", "广告法", "未成年人保护法"],
        "kpi_pack": ["投诉率", "续费率", "合规检查=0 重大项"],
    },
    "农业": {
        "priority_risks": ["气候灾害", "价格波动", "生物安全", "补贴依赖"],
        "best_practices": [
            "农业保险 + 期货套保组合",
            "种养殖生物安全与溯源体系",
            "订单农业锁定销售渠道",
        ],
        "regulatory_focus": ["农产品质量安全法", "动物防疫法", "土地管理法"],
        "kpi_pack": ["单位产量", "损耗率", "补贴占比"],
    },
}

DEFAULT_PLAYBOOK = {
    "priority_risks": ["财务流动性", "合规", "经营", "人才"],
    "best_practices": [
        "建立 ERM 委员会与季度风险报告",
        "关键风险 KRI 仪表盘",
        "ISO 31000 风险登记与应对策略审批",
    ],
    "regulatory_focus": ["公司法", "合同法", "劳动法", "行业监管"],
    "kpi_pack": ["综合风险评分<2.5", "关键风险项季度下降", "数据完成度>75%"],
}


# 风险域关键词 → 维度名匹配
RISK_DIM_KEYWORDS = {
    "供应链": ["供应链", "生产运营"],
    "产能": ["生产运营", "经营"],
    "安全": ["安全生产", "生产运营"],
    "环保": ["环境", "ESG"],
    "流动性": ["财务", "信用"],
    "数据": ["技术", "数据隐私"],
    "人才": ["人力资源", "经营"],
    "合规": ["法律", "合规", "税务", "治理"],
    "信用": ["信用", "财务"],
    "声誉": ["战略", "声誉"],
}


def _match_dimensions(risk_label: str, high_dims: List[str]) -> List[str]:
    linked = []
    for kw, dim_keys in RISK_DIM_KEYWORDS.items():
        if kw in risk_label:
            for d in high_dims:
                if any(k in d for k in dim_keys) and d not in linked:
                    linked.append(d)
    if not linked:
        linked = [d for d in high_dims if any(c in d for c in risk_label[:2])]
    return linked or high_dims[:1]


def get_industry_playbook(industry: str) -> dict:
    profile = get_industry_profile(industry)
    key = profile.get("industry_key", "其他")
    pb = INDUSTRY_PLAYBOOKS.get(key, DEFAULT_PLAYBOOK)
    return {"industry": key, **pb}


def build_industry_action_plan(result: AssessmentResult, basic: dict = None) -> dict:
    """将行业最佳实践与当前高风险维度匹配，生成行业定制行动清单"""
    basic = basic or (result.all_raw_data or {}).get("企业基本信息", {})
    pb = get_industry_playbook(basic.get("所属行业", ""))

    high_dims = [
        d.name for d in sorted(result.dimensions.values(), key=lambda x: x.score, reverse=True)
        if d.score >= 2.3
    ]

    matched_practices = []
    for practice in pb["best_practices"]:
        relevance = "高" if high_dims else "中"
        matched_practices.append({
            "practice": practice,
            "relevance": relevance,
            "linked_dimensions": high_dims[:3],
        })

    priority_actions = []
    for i, risk in enumerate(pb["priority_risks"][:4], 1):
        linked = _match_dimensions(risk, high_dims)
        priority_actions.append({
            "id": f"IND-{i:02d}",
            "risk_area": risk,
            "action": pb["best_practices"][min(i - 1, len(pb["best_practices"]) - 1)],
            "linked_dimensions": linked,
            "regulatory": pb["regulatory_focus"][min(i - 1, len(pb["regulatory_focus"]) - 1)] if pb["regulatory_focus"] else "",
        })

    return {
        "industry": pb["industry"],
        "priority_risks": pb["priority_risks"],
        "best_practices": matched_practices,
        "regulatory_focus": pb["regulatory_focus"],
        "industry_kpis": pb["kpi_pack"],
        "priority_actions": priority_actions,
        "tailored_note": f"针对{pb['industry']}行业特征，结合当前高风险维度：{', '.join(high_dims[:3]) or '暂无'}",
    }
