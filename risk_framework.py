# -*- coding: utf-8 -*-
"""ERM 国际标准框架映射与维度体系"""

from typing import Dict, List

DIMENSION_FRAMEWORK_MAP: Dict[str, dict] = {
    "经营风险": {"iso31000": "战略与经营目标风险", "coso_component": "战略与目标设定", "tcfd": "战略韧性"},
    "财务风险": {"iso31000": "财务与流动性风险", "coso_component": "业绩与风险审查", "tcfd": "财务影响"},
    "生产运营风险": {"iso31000": "运营与流程风险", "coso_component": "运营", "tcfd": "运营韧性"},
    "安全生产风险": {"iso31000": "健康与安全风险", "coso_component": "运营", "tcfd": "物理风险"},
    "环境风险": {"iso31000": "环境与社会风险", "coso_component": "合规", "tcfd": "环境风险"},
    "法律与合规风险": {"iso31000": "合规与法律风险", "coso_component": "合规", "tcfd": "监管披露"},
    "供应链风险": {"iso31000": "外部依赖风险", "coso_component": "运营", "tcfd": "供应链韧性"},
    "技术与信息安全风险": {"iso31000": "技术与数据风险", "coso_component": "信息", "tcfd": "转型风险"},
    "人力资源风险": {"iso31000": "组织与人力风险", "coso_component": "运营", "tcfd": "人力资本"},
    "信用风险": {"iso31000": "交易对手风险", "coso_component": "业绩审查", "tcfd": "信用暴露"},
    "行业与市场风险": {"iso31000": "宏观环境风险", "coso_component": "战略", "tcfd": "市场风险"},
    "税务风险": {"iso31000": "税务合规风险", "coso_component": "合规", "tcfd": "披露准确性"},
    "关联方与集团风险": {"iso31000": "治理与关联交易", "coso_component": "治理", "tcfd": "治理披露"},
    "项目投资风险": {"iso31000": "资本配置风险", "coso_component": "战略", "tcfd": "资本效率"},
    "战略与声誉风险": {"iso31000": "声誉与战略风险", "coso_component": "战略", "tcfd": "声誉风险"},
    "业务连续性风险": {"iso31000": "业务中断风险", "coso_component": "运营", "tcfd": "运营韧性"},
    "数据隐私合规风险": {"iso31000": "数据与隐私风险", "coso_component": "合规", "tcfd": "转型风险"},
    "公司治理风险": {"iso31000": "治理风险", "coso_component": "治理", "tcfd": "治理披露"},
    "反贿赂道德合规风险": {"iso31000": "道德与合规风险", "coso_component": "合规", "tcfd": "监管风险"},
    "综合评估": {"iso31000": "综合风险视图", "coso_component": "绩效与风险审查", "tcfd": "综合披露"},
}

RECOMMENDED_EXTENSION_DOMAINS: List[dict] = [
    {"domain": "战略与声誉风险", "gap": "已纳入模板", "recommendation": "持续更新舆情与ESG评级", "framework": "COSO ERM", "status": "covered"},
    {"domain": "业务连续性 BCM", "gap": "已纳入模板", "recommendation": "年度BC演练与RTO/RPO验证", "framework": "ISO 22301", "status": "covered"},
    {"domain": "数据隐私合规", "gap": "已纳入模板", "recommendation": "PIPL/GDPR定期评估与DPIA", "framework": "PIPL/GDPR", "status": "covered"},
    {"domain": "公司治理", "gap": "已纳入模板", "recommendation": "三道防线成熟度年度自评", "framework": "COSO 治理", "status": "covered"},
    {"domain": "反贿赂道德合规", "gap": "已纳入模板", "recommendation": "第三方DD与举报机制测试", "framework": "ISO 37001", "status": "covered"},
]

COSO_COMPONENTS = ["治理与文化", "战略与目标设定", "绩效与风险审查", "审阅与修订", "信息沟通与报告"]
ISO31000_PRINCIPLES = ["整合性", "结构化", "定制化", "包容性", "动态性", "最佳信息", "人文因素", "持续改进"]
MATURITY_LEVELS = {
    1: {"name": "初始级", "desc": "被动应对"},
    2: {"name": "可重复级", "desc": "局部流程"},
    3: {"name": "已定义级", "desc": "有政策与定期评估"},
    4: {"name": "量化管理级", "desc": "KRI 与情景分析"},
    5: {"name": "优化级", "desc": "持续改进与战略整合"},
}
