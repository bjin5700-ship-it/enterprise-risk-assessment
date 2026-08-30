# -*- coding: utf-8 -*-
"""
风险引擎 - Risk Engine v4
适配实际Excel表格结构，合理评分区间
"""

import openpyxl
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class RiskLevel(Enum):
    LOW = "低风险"
    MEDIUM = "中等风险"
    HIGH = "高风险"
    CRITICAL = "极高风险"

    @classmethod
    def from_score(cls, s: float) -> "RiskLevel":
        if s < 1.5: return cls.LOW
        elif s < 2.5: return cls.MEDIUM
        elif s < 3.5: return cls.HIGH
        else: return cls.CRITICAL


@dataclass
class RiskDimension:
    name: str
    weight: float
    score: float
    level: RiskLevel
    findings: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssessmentResult:
    company_name: str
    overall_score: float
    overall_level: RiskLevel
    dimensions: Dict[str, RiskDimension]
    all_raw_data: Dict[str, Dict[str, Any]]
    report_date: str = ""


# ── 数据提取 ──
def extract_sheet_data(ws) -> Dict[str, Any]:
    if (ws.title or "") == "综合评估":
        return extract_overall_sheet(ws)
    data = {}
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, min_col=2, max_col=6):
        field_name = None
        field_value = None
        for cell in row:
            if cell.column == 2:
                val = cell.value
                if val and isinstance(val, str):
                    field_name = val.strip()
            if cell.column == 6:
                field_value = cell.value
        if field_name and field_value is not None:
            data[field_name] = field_value
    return data


def extract_overall_sheet(ws) -> Dict[str, Any]:
    """综合评估：表格式 P×I + 底部结论字段。"""
    data: Dict[str, Any] = {}
    summary_names = {
        "整体风险等级", "主要风险领域", "风险缓解措施", "建议尽调深度",
        "尽调优先级", "是否建议推进", "备注/特殊关注事项", "综合评估结论",
    }
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, min_col=1, max_col=7):
        cells = [c.value for c in row]
        while len(cells) < 7:
            cells.append(None)
        seq, area, level, prob, impact, desc, extra = cells[:7]
        area_s = str(area).strip() if area else ""
        if not area_s or area_s in summary_names:
            if area_s in summary_names:
                val = level if level not in (None, "") else extra
                if val not in (None, ""):
                    data[area_s] = val
            continue
        if isinstance(seq, (int, float)) or area_s:
            if prob not in (None, ""):
                data[f"{area_s}_发生概率"] = prob
            if impact not in (None, ""):
                data[f"{area_s}_影响程度"] = impact
            if level not in (None, ""):
                data[f"{area_s}_风险等级"] = level
            if desc not in (None, "") and area_s not in data:
                data[area_s] = desc
    return data


def extract_all_data(filepath: str) -> Dict[str, Dict[str, Any]]:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    all_data = {}
    for ws in wb.worksheets:
        all_data[ws.title] = extract_sheet_data(ws)
    wb.close()
    return all_data


def _sf(v) -> Optional[float]:
    if v is None: return None
    try: return float(str(v).replace(",", "").replace(" ", "").replace("%", ""))
    except: return None

def _ss(v) -> str:
    if v is None: return ""
    return str(v).strip()


# ── 评分函数 ──

def score_financial(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    profile = data.get("_industry_profile") or {}
    debt_warn = profile.get("debt_ratio_warn", 65)
    debt_crit = profile.get("debt_ratio_crit", 80)
    cur_low = profile.get("current_ratio_low", 1.2)
    cur_crit = profile.get("current_ratio_crit", 0.9)
    industry_key = profile.get("industry_key", "")

    debt_ratio = _sf(data.get("资产负债率(%)"))
    current_r = _sf(data.get("流动比率"))
    quick_r = _sf(data.get("速动比率"))
    net_profit_r = _sf(data.get("净利率(%)"))
    gross_r = _sf(data.get("毛利率(%)"))
    roe = _sf(data.get("净资产收益率ROE(%)"))
    ocf = _sf(data.get("经营性现金流净额(万元)"))
    fcf = _sf(data.get("自由现金流(万元)"))
    interest_coverage = _sf(data.get("利息保障倍数"))
    short_debt_ratio = _sf(data.get("短期借款占比(%)"))
    consecutive_loss = _ss(data.get("近三年是否连续亏损"))
    default_record = _ss(data.get("是否存在债务违约记录"))

    if debt_ratio is not None:
        if debt_ratio > debt_crit:
            score += 0.8
            findings.append(f"资产负债率{debt_ratio}%，超过{industry_key or '行业'}警戒线{debt_crit}%")
            key_risks.append("资产负债率过高")
        elif debt_ratio > debt_warn:
            score += 0.5
            findings.append(f"资产负债率{debt_ratio}%，高于{industry_key or '行业'}参考值{debt_warn}%")
        elif debt_ratio > debt_warn - 15:
            score += 0.2

    if current_r is not None:
        if current_r < cur_crit:
            score += 0.8; findings.append(f"流动比率{current_r}，短期偿债风险高"); key_risks.append("流动性风险")
        elif current_r < cur_low:
            score += 0.5; findings.append(f"流动比率{current_r}，低于{industry_key or '行业'}安全线{cur_low}")
        elif current_r < cur_low + 0.3:
            score += 0.3

    if quick_r is not None:
        if quick_r < 0.5: score += 0.4; findings.append(f"速动比率{quick_r}，低于0.5")
        elif quick_r < 0.8: score += 0.2

    if net_profit_r is not None:
        if net_profit_r < 0: score += 1.0; findings.append(f"净利率{net_profit_r}%，企业亏损"); key_risks.append("企业亏损")
        elif net_profit_r < 3: score += 0.5; findings.append(f"净利率仅{net_profit_r}%，盈利能力弱")
        elif net_profit_r < 8: score += 0.2; findings.append(f"净利率{net_profit_r}%，偏低")

    if gross_r is not None and gross_r < 15: score += 0.2; findings.append(f"毛利率{gross_r}%，低于15%")
    if roe is not None and roe < 3: score += 0.2
    if ocf is not None and ocf < 0: score += 0.6; findings.append("经营性现金流为负"); key_risks.append("现金流风险")
    if fcf is not None and fcf < 0: score += 0.4; findings.append("自由现金流为负")

    if interest_coverage is not None:
        if interest_coverage < 1.0: score += 0.8; findings.append(f"利息保障倍数{interest_coverage}，无法覆盖利息"); key_risks.append("偿债能力不足")
        elif interest_coverage < 2.0: score += 0.4; findings.append(f"利息保障倍数{interest_coverage}，偏弱")
        elif interest_coverage < 3.0: score += 0.1

    if short_debt_ratio is not None and short_debt_ratio > 60: score += 0.3; findings.append(f"短期借款占比{short_debt_ratio}%，短期压力大")
    if "是" in consecutive_loss: score += 0.8; findings.append("近三年连续亏损"); key_risks.append("连续亏损")
    if "是" in default_record: score += 1.2; findings.append("存在债务违约记录"); key_risks.append("债务违约")

    score = round(min(score, 4.0), 2)
    return RiskDimension("财务风险", weight=20, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_legal_compliance(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    case_count = _sf(data.get("在审案件数量"))
    case_amount = _sf(data.get("在审案件标的额(万元)"))
    lose_count = _sf(data.get("近三年败诉案件数"))
    penalty_count = _sf(data.get("行政处罚次数(近三年)"))
    contract_audit = _sf(data.get("合同审核率(%)"))
    ip_dispute = _ss(data.get("知识产权纠纷"))
    patent_count = _sf(data.get("专利数量"))
    supervision = _ss(data.get("行业监管检查结果"))

    if case_count is not None and case_count > 0:
        if case_count >= 3: score += 0.6; findings.append(f"在审案件{case_count}起，数量较多"); key_risks.append("诉讼风险")
        else: score += 0.3; findings.append(f"存在{case_count}起在审案件")
    if case_amount is not None and case_amount > 500: score += 0.4
    if lose_count is not None and lose_count > 0: score += 0.3; findings.append(f"近三年败诉{lose_count}起")
    if penalty_count is not None and penalty_count > 0:
        if penalty_count >= 2: score += 0.6; findings.append(f"近三年行政处罚{penalty_count}次"); key_risks.append("多次行政处罚")
        else: score += 0.3; findings.append("存在行政处罚记录")
    if contract_audit is not None and contract_audit < 90: score += 0.1
    if "有" in ip_dispute: score += 0.5; findings.append("存在知识产权纠纷"); key_risks.append("知识产权风险")
    if patent_count is not None and patent_count < 3: score += 0.2
    if "不合格" in supervision: score += 0.5; findings.append("行业监管检查不合格"); key_risks.append("监管不合规")

    score = round(min(score, 4.0), 2)
    return RiskDimension("法律与合规风险", weight=12, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_supply_chain(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    core_suppliers = _sf(data.get("核心供应商数量"))
    single_source = _sf(data.get("单一来源采购占比(%)"))
    import_depend = _sf(data.get("进口依赖度(%)"))
    logistics_risk = _ss(data.get("物流中断风险"))
    tariff = _ss(data.get("关税影响程度"))
    exchange_rate = _ss(data.get("汇率波动影响"))
    dead_stock = _sf(data.get("呆滞库存占比(%)"))
    export_ratio = _sf(data.get("出口业务占比(%)"))

    if core_suppliers is not None and core_suppliers <= 3: score += 0.5; findings.append(f"核心供应商仅{core_suppliers}家，集中度高"); key_risks.append("供应商集中风险")
    if single_source is not None and single_source > 30: score += 0.5; findings.append(f"单一来源采购占比{single_source}%，依赖度高"); key_risks.append("单一来源依赖")
    if import_depend is not None and import_depend > 50: score += 0.8; findings.append(f"进口依赖度{import_depend}%，过高"); key_risks.append("进口依赖风险")
    elif import_depend is not None and import_depend > 20: score += 0.4; findings.append(f"进口依赖度{import_depend}%，较高")
    if "高" in logistics_risk: score += 0.5; findings.append("物流中断风险高"); key_risks.append("物流中断风险")
    elif "中" in logistics_risk: score += 0.2
    if "高" in tariff: score += 0.3
    if "高" in exchange_rate: score += 0.4; findings.append("汇率波动影响大"); key_risks.append("汇率风险")
    elif "中" in exchange_rate: score += 0.2
    if dead_stock is not None and dead_stock > 10: score += 0.2
    if export_ratio is not None and export_ratio > 30: score += 0.2

    score = round(min(score, 4.0), 2)
    return RiskDimension("供应链风险", weight=12, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_technology(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    rd_ratio = _sf(data.get("研发投入占营收比(%)"))
    rd_personnel = _sf(data.get("研发人员占比(%)"))
    patent_count = _sf(data.get("专利数量(累计)"))
    core_source = _ss(data.get("核心技术来源"))
    tech_lifecycle = _ss(data.get("技术所处生命周期"))
    substitute = _ss(data.get("替代技术威胁"))
    digital_stage = _ss(data.get("数字化转型阶段"))
    security_level = _ss(data.get("信息系统安全等级"))
    security_incidents = _sf(data.get("网络安全事件次数(近三年)"))
    security_cert = _ss(data.get("信息安全认证"))

    if rd_ratio is not None:
        if rd_ratio < 1: score += 0.7; findings.append(f"研发投入占比仅{rd_ratio}%，严重不足"); key_risks.append("研发投入严重不足")
        elif rd_ratio < 3: score += 0.4; findings.append(f"研发投入占比{rd_ratio}%，偏低")
        elif rd_ratio < 5: score += 0.1
    if rd_personnel is not None and rd_personnel < 5: score += 0.2
    if patent_count is not None and patent_count < 3: score += 0.4; findings.append(f"累计专利仅{patent_count}项，技术壁垒弱"); key_risks.append("专利不足")
    elif patent_count is not None and patent_count < 10: score += 0.2
    if "部分" in core_source or "依赖" in core_source: score += 0.5; findings.append("核心技术部分依赖外部"); key_risks.append("核心技术依赖")
    if "衰退" in tech_lifecycle: score += 0.5; findings.append("技术处于衰退期"); key_risks.append("技术落后风险")
    if "高" in substitute: score += 0.5; findings.append("替代技术威胁高"); key_risks.append("替代技术风险")
    elif "中" in substitute: score += 0.2
    if "起步" in digital_stage: score += 0.2
    if "弱" in security_level or "一般" in security_level: score += 0.3
    if security_incidents is not None and security_incidents > 0: score += 0.5; findings.append(f"近三年发生{security_incidents}起网络安全事件"); key_risks.append("网络安全事件")
    if "无" in security_cert: score += 0.1

    score = round(min(score, 4.0), 2)
    return RiskDimension("技术与信息安全风险", weight=10, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_hr(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    turnover = _sf(data.get("年离职率(%)"))
    key_turnover = _sf(data.get("核心人才离职率(%)"))
    key_vacancy = _sf(data.get("关键岗位空缺数"))
    hiring_rate = _sf(data.get("招聘完成率(%)"))
    contract_rate = _sf(data.get("劳动合同签订率(%)"))
    social_security = _ss(data.get("社保缴纳合规性"))
    labor_disputes = _sf(data.get("近三年劳资纠纷次数"))
    perf_coverage = _sf(data.get("绩效考核覆盖率(%)"))
    salary_compet = _ss(data.get("薪酬竞争力"))
    equity = _ss(data.get("股权激励/员工持股"))

    if turnover is not None:
        if turnover > 30: score += 0.7; findings.append(f"年离职率{turnover}%，人员极不稳定"); key_risks.append("人才流失风险")
        elif turnover > 20: score += 0.4; findings.append(f"年离职率{turnover}%，偏高")
        elif turnover > 10: score += 0.1
    if key_turnover is not None and key_turnover > 15: score += 0.5; findings.append(f"核心人才离职率{key_turnover}%，核心技术人才流失严重"); key_risks.append("核心人才流失")
    if key_vacancy is not None and key_vacancy > 2: score += 0.2
    if hiring_rate is not None and hiring_rate < 80: score += 0.2
    if contract_rate is not None and contract_rate < 100: score += 0.3
    if "不合规" in social_security or "未" in social_security: score += 0.7; findings.append("社保缴纳不合规"); key_risks.append("社保合规风险")
    if labor_disputes is not None and labor_disputes > 0: score += 0.2
    if perf_coverage is not None and perf_coverage < 80: score += 0.1
    if "低" in salary_compet: score += 0.4; findings.append("薪酬竞争力低"); key_risks.append("薪酬竞争力不足")
    elif "中" in salary_compet: score += 0.1
    if "无" in equity: score += 0.1

    score = round(min(score, 4.0), 2)
    return RiskDimension("人力资源风险", weight=8, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_tax(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    tax_check = _ss(data.get("税务稽查记录"))
    transfer_pricing = _ss(data.get("转让定价风险"))
    invoice = _ss(data.get("增值税发票管理"))
    cross_border = _ss(data.get("跨境税务风险"))
    planning = _ss(data.get("筹划方案合规性"))

    if "问题" in tax_check and "未整改" in tax_check: score += 1.0; findings.append("税务稽查重大问题未整改"); key_risks.append("税务稽查风险")
    elif "问题" in tax_check: score += 0.4; findings.append("税务稽查存在问题（已整改）")
    if "高" in transfer_pricing: score += 0.8; findings.append("转让定价风险高"); key_risks.append("转让定价风险")
    elif "中" in transfer_pricing: score += 0.4
    if "不规范" in invoice: score += 0.6; findings.append("增值税发票管理不规范"); key_risks.append("发票管理风险")
    if "高" in cross_border: score += 0.6
    elif "中" in cross_border: score += 0.3
    if "不合规" in planning: score += 1.0; findings.append("税务筹划方案不合规"); key_risks.append("税务筹划不合规")
    elif "争议" in planning: score += 0.5

    score = round(min(score, 4.0), 2)
    return RiskDimension("税务风险", weight=8, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_industry_policy(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    policy_change = _ss(data.get("行业监管政策变化"))
    policy_impact = _ss(data.get("政策变化影响评估"))
    policy_support = _ss(data.get("产业政策支持"))
    lifecycle = _ss(data.get("行业生命周期"))
    barrier = _ss(data.get("行业进入壁垒"))
    substitute = _ss(data.get("替代品威胁"))
    profit_trend = _ss(data.get("行业利润率趋势"))
    economy_sensitivity = _ss(data.get("经济周期敏感性"))
    interest_impact = _ss(data.get("利率变化影响"))
    inflation_impact = _ss(data.get("通货膨胀影响"))

    if "趋严" in policy_change: score += 0.5; findings.append("行业监管政策趋严"); key_risks.append("监管趋严风险")
    if "高" in policy_impact: score += 0.5; findings.append("政策变化影响大"); key_risks.append("政策影响风险")
    elif "中" in policy_impact: score += 0.2
    if "不支持" in policy_support or "有限" in policy_support: score += 0.3; findings.append(f"产业政策支持力度：{policy_support}")
    if "衰退" in lifecycle: score += 0.8; findings.append("行业处于衰退期"); key_risks.append("行业衰退风险")
    elif "成熟" in lifecycle: score += 0.2; findings.append("行业处于成熟期")
    if "低" in barrier: score += 0.2
    if "高" in substitute: score += 0.5; findings.append("替代品威胁高"); key_risks.append("替代品威胁")
    elif "中" in substitute: score += 0.2
    if "下降" in profit_trend: score += 0.3; findings.append("行业利润率呈下降趋势")
    if "高" in economy_sensitivity: score += 0.4; findings.append("经济周期敏感度高"); key_risks.append("经济周期风险")
    elif "中" in economy_sensitivity: score += 0.2
    if "高" in interest_impact: score += 0.3
    if "高" in inflation_impact: score += 0.3

    score = round(min(score, 4.0), 2)
    return RiskDimension("行业与市场风险", weight=10, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_comprehensive(data: Dict[str, Any]) -> RiskDimension:
    findings = []; key_risks = []; score = 1.0

    overall = _ss(data.get("整体风险等级"))
    main_risks = _ss(data.get("主要风险领域"))
    mitigation = _ss(data.get("风险缓解措施"))

    if "高" in overall: score += 0.8; findings.append(f"企业自评整体风险等级为{overall}"); key_risks.append("高风险自评")
    elif "中" in overall: score += 0.3; findings.append(f"企业自评整体风险等级为{overall}")
    elif "低" in overall: score -= 0.2
    if main_risks: findings.append(f"主要风险领域：{main_risks}")
    if mitigation: findings.append(f"风险缓解措施：{mitigation}")

    score = round(min(score, 4.0), 2)
    return RiskDimension("综合评估", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


# ── 主入口 ──


def score_operation(data: Dict[str, Any]) -> RiskDimension:
    """经营风险评分"""
    findings = []; key_risks = []; score = 1.0

    market_pos = _ss(data.get("市场地位"))
    customer_conc = _sf(data.get("前五大客户收入占比(%)"))
    profile = data.get("_industry_profile") or {}
    cust_warn = profile.get("customer_conc_warn", 50)
    max_customer = _sf(data.get("最大单一客户占比(%)"))
    ar_days = _sf(data.get("应收账款周转天数"))
    supplier_conc = _sf(data.get("前五大供应商采购占比(%)"))
    max_supplier = _sf(data.get("最大单一供应商占比(%)"))
    price_volatility = _ss(data.get("原材料价格波动影响"))
    revenue_growth = _sf(data.get("近三年营收增长率(%)"))
    profit_growth = _sf(data.get("近三年利润增长率(%)"))
    seasonal = _ss(data.get("季节性波动"))
    license = _ss(data.get("经营许可证/资质"))

    if "弱" in market_pos or "低" in market_pos: score += 0.5; findings.append("市场地位偏弱"); key_risks.append("市场地位弱")
    if customer_conc is not None and customer_conc > cust_warn + 10:
        score += 0.6; findings.append(f"前五大客户收入占比{customer_conc}%，客户集中度高"); key_risks.append("客户集中风险")
    elif customer_conc is not None and customer_conc > cust_warn:
        score += 0.3
    if max_customer is not None and max_customer > 30: score += 0.5; findings.append(f"最大单一客户占比{max_customer}%，依赖度高"); key_risks.append("单一客户依赖")
    elif max_customer is not None and max_customer > 15: score += 0.2
    if ar_days is not None and ar_days > 120: score += 0.6; findings.append(f"应收账款周转天数{ar_days}天，回款周期过长"); key_risks.append("回款风险")
    elif ar_days is not None and ar_days > 90: score += 0.3
    if supplier_conc is not None and supplier_conc > 60: score += 0.4
    if max_supplier is not None and max_supplier > 40: score += 0.4; findings.append(f"最大单一供应商占比{max_supplier}%，依赖度高"); key_risks.append("供应商依赖")
    if "高" in price_volatility: score += 0.5; findings.append("原材料价格波动影响大"); key_risks.append("原材料价格风险")
    elif "中" in price_volatility: score += 0.2
    if revenue_growth is not None:
        if revenue_growth < -10: score += 0.8; findings.append(f"近三年营收增长率{revenue_growth}%，大幅下滑"); key_risks.append("营收下滑")
        elif revenue_growth < 0: score += 0.4; findings.append(f"近三年营收增长率{revenue_growth}%，负增长")
        elif revenue_growth < 5: score += 0.1
    if profit_growth is not None:
        if profit_growth < -20: score += 0.8; findings.append(f"近三年利润增长率{profit_growth}%，大幅下滑"); key_risks.append("利润下滑")
        elif profit_growth < 0: score += 0.4
    if "明显" in seasonal: score += 0.3
    if "无" in license or "缺失" in license: score += 1.0; findings.append("经营许可证/资质缺失"); key_risks.append("资质缺失")
    elif "过期" in license: score += 0.5

    score = round(min(score, 4.0), 2)
    return RiskDimension("经营风险", weight=8, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_production(data: Dict[str, Any]) -> RiskDimension:
    """生产运营风险评分"""
    findings = []; key_risks = []; score = 1.0

    capacity_util = _sf(data.get("产能利用率(%)"))
    equip_age = _sf(data.get("设备平均役龄(年)"))
    equip_failure = _sf(data.get("设备故障率(%)"))
    quality_rate = _sf(data.get("产品合格率(%)"))
    complaint_rate = _sf(data.get("客诉率(件/万件)"))
    quality_incident = _ss(data.get("质量事故记录"))
    outsourcing = _sf(data.get("外协加工占比(%)"))
    inv_days = _sf(data.get("库存周转天数"))
    raw_inv_days = _sf(data.get("原材料库存保障天数"))
    bottleneck = _ss(data.get("产能瓶颈环节"))

    if capacity_util is not None:
        if capacity_util < 50: score += 0.6; findings.append(f"产能利用率仅{capacity_util}%，严重不足"); key_risks.append("产能利用率低")
        elif capacity_util < 70: score += 0.3; findings.append(f"产能利用率{capacity_util}%，偏低")
        elif capacity_util > 95: score += 0.3; findings.append(f"产能利用率{capacity_util}%，接近满负荷")
    if equip_age is not None and equip_age > 15: score += 0.6; findings.append(f"设备平均役龄{equip_age}年，设备老化严重"); key_risks.append("设备老化")
    elif equip_age is not None and equip_age > 10: score += 0.3
    if equip_failure is not None and equip_failure > 5: score += 0.4
    if quality_rate is not None and quality_rate < 95: score += 0.5; findings.append(f"产品合格率{quality_rate}%，低于95%"); key_risks.append("质量风险")
    elif quality_rate is not None and quality_rate < 98: score += 0.2
    if complaint_rate is not None and complaint_rate > 5: score += 0.3
    if "有" in quality_incident: score += 0.8; findings.append("存在质量事故记录"); key_risks.append("质量事故")
    if outsourcing is not None and outsourcing > 40: score += 0.4; findings.append(f"外协加工占比{outsourcing}%，偏高"); key_risks.append("外协依赖风险")
    if inv_days is not None and inv_days > 90: score += 0.3
    if raw_inv_days is not None and raw_inv_days < 7: score += 0.3; findings.append(f"原材料库存保障仅{raw_inv_days}天，供应风险")
    if bottleneck: score += 0.3; findings.append(f"存在产能瓶颈：{bottleneck}")

    score = round(min(score, 4.0), 2)
    return RiskDimension("生产运营风险", weight=7, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_safety(data: Dict[str, Any]) -> RiskDimension:
    """安全生产风险评分"""
    findings = []; key_risks = []; score = 1.0

    safety_staff_ratio = _sf(data.get("安全管理人员占比(%)"))
    safety_invest = _sf(data.get("安全投入占营收比(%)"))
    std_level = _ss(data.get("安全生产标准化等级"))
    iso45001 = _ss(data.get("ISO45001认证"))
    injury_count = _sf(data.get("近三年工伤事故次数"))
    death_count = _sf(data.get("近三年死亡事故次数"))
    injury_rate = _sf(data.get("百万工时伤害率"))
    hazard_rectify = _sf(data.get("隐患整改率(%)"))
    major_hazard = _sf(data.get("重大隐患数量"))
    train_coverage = _sf(data.get("安全培训覆盖率(%)"))
    cert_rate = _sf(data.get("特种作业人员持证率(%)"))
    drill_freq = _sf(data.get("应急演练频次(次/年)"))
    hazmat = _ss(data.get("是否涉及危化品"))
    hazmat_types = _sf(data.get("危化品种类数"))

    if safety_staff_ratio is not None and safety_staff_ratio < 1: score += 0.3
    if safety_invest is not None and safety_invest < 0.5: score += 0.4; findings.append("安全投入占营收比不足0.5%")
    if "未达标" in std_level or "无" in std_level: score += 0.5; findings.append("未达到安全生产标准化"); key_risks.append("安全标准化未达标")
    if "无" in iso45001: score += 0.3
    if injury_count is not None and injury_count > 5: score += 0.8; findings.append(f"近三年工伤事故{injury_count}次，频发"); key_risks.append("工伤事故频发")
    elif injury_count is not None and injury_count > 0: score += 0.3
    if death_count is not None and death_count > 0: score += 2.0; findings.append("近三年发生死亡事故"); key_risks.append("死亡事故")
    if injury_rate is not None and injury_rate > 10: score += 0.5
    if hazard_rectify is not None and hazard_rectify < 90: score += 0.5; findings.append(f"隐患整改率{hazard_rectify}%，低于90%"); key_risks.append("隐患整改不足")
    if major_hazard is not None and major_hazard > 0: score += 0.8; findings.append(f"存在{major_hazard}项重大隐患"); key_risks.append("重大隐患")
    if train_coverage is not None and train_coverage < 80: score += 0.3
    if cert_rate is not None and cert_rate < 100: score += 0.3
    if drill_freq is not None and drill_freq < 1: score += 0.3
    if "是" in hazmat or "有" in hazmat: score += 0.5; findings.append("涉及危化品"); key_risks.append("危化品风险")
    if hazmat_types is not None and hazmat_types > 3: score += 0.3

    score = round(min(score, 4.0), 2)
    return RiskDimension("安全生产风险", weight=7, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_environment(data: Dict[str, Any]) -> RiskDimension:
    """环境风险评分"""
    findings = []; key_risks = []; score = 1.0

    eia = _ss(data.get("环评批复情况"))
    permit = _ss(data.get("排污许可证"))
    env_penalty = _sf(data.get("近三年环境处罚次数"))
    penalty_amount = _sf(data.get("处罚金额累计(万元)"))
    env_lawsuit = _sf(data.get("环境诉讼案件数"))
    compliance_rate = _sf(data.get("排放达标率(%)"))
    iso14001 = _ss(data.get("ISO14001认证"))
    facility_rate = _sf(data.get("环保设施运行率(%)"))
    env_risk_level = _ss(data.get("环境风险等级"))
    env_plan = _ss(data.get("环境应急预案"))

    if "无" in eia or "未" in eia: score += 1.5; findings.append("未完成环评批复"); key_risks.append("环评缺失")
    if "无" in permit or "未" in permit: score += 1.5; findings.append("未取得排污许可证"); key_risks.append("排污许可缺失")
    if env_penalty is not None and env_penalty > 0:
        if env_penalty >= 2: score += 1.0; findings.append(f"近三年环境处罚{env_penalty}次"); key_risks.append("多次环境处罚")
        else: score += 0.5
    if penalty_amount is not None and penalty_amount > 50: score += 0.5
    if env_lawsuit is not None and env_lawsuit > 0: score += 1.0; findings.append("存在环境诉讼"); key_risks.append("环境诉讼")
    if compliance_rate is not None and compliance_rate < 95: score += 0.8; findings.append(f"排放达标率{compliance_rate}%，低于95%"); key_risks.append("排放不达标")
    elif compliance_rate is not None and compliance_rate < 100: score += 0.2
    if "无" in iso14001: score += 0.3
    if facility_rate is not None and facility_rate < 90: score += 0.3
    if "高" in env_risk_level: score += 0.8; findings.append(f"环境风险等级为{env_risk_level}"); key_risks.append("环境风险高")
    elif "中" in env_risk_level: score += 0.3
    if "无" in env_plan: score += 0.5; findings.append("未制定环境应急预案"); key_risks.append("应急预案缺失")

    score = round(min(score, 4.0), 2)
    return RiskDimension("环境风险", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_credit(data: Dict[str, Any]) -> RiskDimension:
    """信用风险评分"""
    findings = []; key_risks = []; score = 1.0

    guarantee_bal = _sf(data.get("对外担保余额(万元)"))
    guarantee_ratio = _sf(data.get("担保比率(%)"))
    pay_cycle = _sf(data.get("供应商付款周期(天)"))
    overdue = _ss(data.get("逾期付款记录"))
    collect_cycle = _sf(data.get("客户回款周期(天)"))
    bad_debt = _sf(data.get("坏账率(%)"))
    related_ratio = _sf(data.get("关联交易占比(%)"))
    tax_credit = _ss(data.get("税务信用等级"))
    customs_credit = _ss(data.get("海关信用等级"))
    industry_rating = _ss(data.get("行业信用评级"))
    penalty_record = _ss(data.get("行政处罚记录"))

    if guarantee_bal is not None and guarantee_bal > 5000: score += 0.5; findings.append(f"对外担保余额{guarantee_bal}万元，金额较大"); key_risks.append("担保风险")
    elif guarantee_bal is not None and guarantee_bal > 1000: score += 0.2
    if guarantee_ratio is not None and guarantee_ratio > 50: score += 0.5
    if pay_cycle is not None and pay_cycle > 90: score += 0.4
    if "有" in overdue: score += 0.6; findings.append("存在逾期付款记录"); key_risks.append("逾期付款")
    if collect_cycle is not None and collect_cycle > 120: score += 0.5; findings.append(f"客户回款周期{collect_cycle}天，过长"); key_risks.append("回款周期长")
    elif collect_cycle is not None and collect_cycle > 90: score += 0.2
    if bad_debt is not None and bad_debt > 5: score += 0.6; findings.append(f"坏账率{bad_debt}%，偏高"); key_risks.append("坏账风险")
    elif bad_debt is not None and bad_debt > 2: score += 0.2
    if related_ratio is not None and related_ratio > 30: score += 0.4; findings.append(f"关联交易占比{related_ratio}%，偏高"); key_risks.append("关联交易风险")
    if "D" in tax_credit: score += 1.0; findings.append(f"税务信用等级为{tax_credit}，信用差"); key_risks.append("税务信用差")
    elif "C" in tax_credit: score += 0.5
    if "D" in customs_credit: score += 0.8
    if "差" in industry_rating or "低" in industry_rating: score += 0.5
    if "有" in penalty_record: score += 0.8; findings.append("存在行政处罚记录"); key_risks.append("行政处罚")

    score = round(min(score, 4.0), 2)
    return RiskDimension("信用风险", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_related_party(data: Dict[str, Any]) -> RiskDimension:
    """关联方与集团风险评分"""
    findings = []; key_risks = []; score = 1.0

    related_count = _sf(data.get("关联企业数量"))
    group_guarantee = _sf(data.get("集团内部担保金额(万元)"))
    group_fund = _sf(data.get("集团内部资金往来(万元)"))
    related_purchase = _sf(data.get("关联采购占比(%)"))
    related_sales = _sf(data.get("关联销售占比(%)"))
    fund_occupation = _sf(data.get("关联方资金占用(万元)"))
    occupation_days = _sf(data.get("资金占用天数"))
    occupation_rate = _sf(data.get("资金占用利率(%)"))

    if related_count is not None and related_count > 5: score += 0.3; findings.append(f"关联企业{related_count}家，关联关系较复杂"); key_risks.append("关联关系复杂")
    if group_guarantee is not None and group_guarantee > 5000: score += 0.5; findings.append(f"集团内部担保金额{group_guarantee}万元，金额较大"); key_risks.append("集团担保风险")
    elif group_guarantee is not None and group_guarantee > 1000: score += 0.2
    if group_fund is not None and group_fund > 3000: score += 0.4
    if related_purchase is not None and related_purchase > 30: score += 0.4; findings.append(f"关联采购占比{related_purchase}%，偏高"); key_risks.append("关联采购风险")
    if related_sales is not None and related_sales > 30: score += 0.4; findings.append(f"关联销售占比{related_sales}%，偏高"); key_risks.append("关联销售风险")
    if fund_occupation is not None and fund_occupation > 1000: score += 0.6; findings.append(f"关联方资金占用{fund_occupation}万元，金额重大"); key_risks.append("资金占用风险")
    elif fund_occupation is not None and fund_occupation > 100: score += 0.2
    if occupation_days is not None and occupation_days > 180: score += 0.4
    if occupation_rate is not None and occupation_rate < 3: score += 0.2

    score = round(min(score, 4.0), 2)
    return RiskDimension("关联方与集团风险", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_project_investment(data: Dict[str, Any]) -> RiskDimension:
    """项目投资风险评分"""
    findings = []; key_risks = []; score = 1.0

    project_count = _sf(data.get("在建项目数量"))
    total_invest = _sf(data.get("在建项目总投资(万元)"))
    schedule_dev = _sf(data.get("项目进度偏差(%)"))
    budget_dev = _sf(data.get("预算偏差(%)"))
    long_term_inv = _sf(data.get("长期股权投资(万元)"))
    invest_return = _sf(data.get("投资收益率(%)"))
    impairment = _ss(data.get("投资减值风险"))
    financing_need = _sf(data.get("近期融资需求(万元)"))

    if project_count is not None and project_count > 3: score += 0.3
    if total_invest is not None and total_invest > 10000: score += 0.3; findings.append(f"在建项目总投资{total_invest}万元，金额重大"); key_risks.append("投资金额大")
    if schedule_dev is not None:
        if abs(schedule_dev) > 20: score += 0.6; findings.append(f"项目进度偏差{schedule_dev}%，严重滞后"); key_risks.append("项目进度滞后")
        elif abs(schedule_dev) > 10: score += 0.3
    if budget_dev is not None:
        if abs(budget_dev) > 20: score += 0.6; findings.append(f"预算偏差{budget_dev}%，超支严重"); key_risks.append("预算超支")
        elif abs(budget_dev) > 10: score += 0.3
    if long_term_inv is not None and long_term_inv > 5000: score += 0.3
    if invest_return is not None and invest_return < 0: score += 0.5; findings.append(f"投资收益率为{invest_return}%，亏损"); key_risks.append("投资亏损")
    elif invest_return is not None and invest_return < 3: score += 0.2
    if "高" in impairment: score += 0.6; findings.append("投资减值风险高"); key_risks.append("减值风险")
    elif "中" in impairment: score += 0.3
    if financing_need is not None and financing_need > 5000: score += 0.3; findings.append(f"近期融资需求{financing_need}万元，资金压力大"); key_risks.append("融资压力")

    score = round(min(score, 4.0), 2)
    return RiskDimension("项目投资风险", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)

SHEET_SCORERS = {
    "财务风险": score_financial,
    "负债与偿债风险": score_financial,
    "法律与合规风险": score_legal_compliance,
    "供应链风险": score_supply_chain,
    "技术与信息安全风险": score_technology,
    "人力资源风险": score_hr,
    "税务风险": score_tax,
    "行业与市场风险": score_industry_policy,
    "经营风险": score_operation,
    "生产运营风险": score_production,
    "安全生产风险": score_safety,
    "环境风险": score_environment,
    "信用风险": score_credit,
    "关联方与集团风险": score_related_party,
    "项目投资风险": score_project_investment,
    "公司治理风险": score_legal_compliance,
    "ESG与可持续发展风险": score_environment,
    "综合评估": score_comprehensive,
}

try:
    from risk_extensions import (
        score_reputation, score_bcm, score_data_privacy,
        score_governance, score_anti_bribery,
    )
    SHEET_SCORERS.update({
        "战略与声誉风险": score_reputation,
        "业务连续性风险": score_bcm,
        "数据隐私合规风险": score_data_privacy,
        "公司治理风险": score_governance,
        "反贿赂道德合规风险": score_anti_bribery,
    })
except ImportError:
    pass

def run_assessment(filepath: str, company_name: str = "") -> AssessmentResult:
    all_data = extract_all_data(filepath)

    if not company_name:
        basic = all_data.get("企业基本信息", {})
        company_name = _ss(basic.get("企业名称")) or "未命名企业"

    dimensions = {}
    total_weighted = 0.0
    total_weight = 0.0

    for sheet_name, scorer in SHEET_SCORERS.items():
        data = all_data.get(sheet_name, {})
        dim = scorer(data)
        dimensions[dim.name] = dim
        total_weighted += dim.score * dim.weight
        total_weight += dim.weight

    # 兜底：未注册的维度默认低风险
    for dim_name, weight in {}.items():
        if dim_name not in dimensions:
            dim = RiskDimension(dim_name, weight=weight, score=1.0, level=RiskLevel.LOW,
                                findings=[], key_risks=[], raw_data={})
            dimensions[dim_name] = dim
            total_weighted += dim.score * dim.weight
            total_weight += dim.weight

    overall_score = total_weighted / total_weight if total_weight > 0 else 1.0
    overall_level = RiskLevel.from_score(overall_score)

    from datetime import date
    report_date = date.today().strftime("%Y年%m月%d日")

    return AssessmentResult(
        company_name=company_name,
        overall_score=round(overall_score, 2),
        overall_level=overall_level,
        dimensions=dimensions,
        all_raw_data=all_data,
        report_date=report_date,
    )
