# -*- coding: utf-8 -*-
"""Phase B 扩展维度评分 — 声誉/BCM/数据隐私/治理/反贿赂"""

from __future__ import annotations

from typing import Any, Dict

from risk_engine import RiskDimension, RiskLevel, _sf, _ss


def score_reputation(data: Dict[str, Any]) -> RiskDimension:
    findings, key_risks, score = [], [], 1.0

    sentiment = _ss(data.get("舆情监测机制"))
    negative_news = _sf(data.get("近12个月负面报道次数"))
    brand_incident = _ss(data.get("品牌危机事件记录"))
    esg_rating = _ss(data.get("ESG评级/评分"))
    customer_nps = _sf(data.get("客户净推荐值NPS"))
    social_complaint = _sf(data.get("社交媒体投诉量(件/月)"))
    media_response = _ss(data.get("危机公关响应机制"))

    if "无" in sentiment or "未" in sentiment:
        score += 0.6; findings.append("未建立舆情监测机制"); key_risks.append("声誉监测缺失")
    if negative_news is not None and negative_news >= 5:
        score += 0.8; findings.append(f"近12个月负面报道{negative_news}次"); key_risks.append("负面舆情")
    elif negative_news is not None and negative_news >= 2:
        score += 0.4
    if "有" in brand_incident:
        score += 1.0; findings.append("存在品牌危机事件记录"); key_risks.append("品牌危机")
    if esg_rating and ("C" in esg_rating or "D" in esg_rating or "低" in esg_rating):
        score += 0.5; findings.append(f"ESG评级偏低：{esg_rating}"); key_risks.append("ESG评级低")
    if customer_nps is not None and customer_nps < 0:
        score += 0.5; findings.append(f"NPS为{customer_nps}，客户口碑差"); key_risks.append("客户口碑风险")
    if social_complaint is not None and social_complaint > 10:
        score += 0.4
    if "无" in media_response:
        score += 0.4; findings.append("无危机公关响应机制")

    score = round(min(score, 4.0), 2)
    return RiskDimension("战略与声誉风险", weight=6, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_bcm(data: Dict[str, Any]) -> RiskDimension:
    findings, key_risks, score = [], [], 1.0

    bia = _ss(data.get("业务影响分析BIA"))
    rto = _sf(data.get("关键系统RTO(小时)"))
    rpo = _sf(data.get("关键数据RPO(小时)"))
    dr_site = _ss(data.get("灾备中心等级"))
    drill = _sf(data.get("BC演练频次(次/年)"))
    plan = _ss(data.get("业务连续性计划BCP"))
    backup = _ss(data.get("关键数据备份策略"))
    single_point = _ss(data.get("单点故障环节"))

    if "无" in bia or "未" in bia:
        score += 0.8; findings.append("未开展业务影响分析"); key_risks.append("BIA缺失")
    if rto is not None and rto > 24:
        score += 0.6; findings.append(f"关键系统RTO {rto}小时，恢复目标偏慢"); key_risks.append("RTO不达标")
    elif rto is not None and rto > 8:
        score += 0.3
    if rpo is not None and rpo > 4:
        score += 0.5; findings.append(f"关键数据RPO {rpo}小时，数据丢失窗口过大")
    if "无" in dr_site or "一级" not in dr_site:
        score += 0.4; findings.append(f"灾备等级：{dr_site or '未建立'}")
    if drill is not None and drill < 1:
        score += 0.6; findings.append("BC演练不足1次/年"); key_risks.append("BC演练缺失")
    if "无" in plan or "未" in plan:
        score += 0.8; findings.append("无业务连续性计划"); key_risks.append("BCP缺失")
    if "无" in backup:
        score += 0.5; findings.append("关键数据备份策略不完善")
    if single_point:
        score += 0.4; findings.append(f"存在单点故障：{single_point}"); key_risks.append("单点故障")

    score = round(min(score, 4.0), 2)
    return RiskDimension("业务连续性风险", weight=6, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_data_privacy(data: Dict[str, Any]) -> RiskDimension:
    findings, key_risks, score = [], [], 1.0

    classification = _ss(data.get("数据分级分类"))
    pipl = _ss(data.get("PIPL合规评估"))
    cross_border = _ss(data.get("数据出境评估"))
    dpia = _ss(data.get("DPIA隐私影响评估"))
    breach = _sf(data.get("近3年数据泄露事件数"))
    consent = _ss(data.get("用户同意管理机制"))
    dpo = _ss(data.get("数据保护官DPO"))

    if "无" in classification or "未" in classification:
        score += 0.6; findings.append("未建立数据分级分类"); key_risks.append("数据分级缺失")
    if "未" in pipl or "不合规" in pipl:
        score += 1.0; findings.append("PIPL合规存在缺口"); key_risks.append("PIPL不合规")
    if "需要" in cross_border and "未" in cross_border:
        score += 0.8; findings.append("数据出境评估未完成"); key_risks.append("出境合规风险")
    if "无" in dpia:
        score += 0.4
    if breach is not None and breach > 0:
        score += 1.2; findings.append(f"近3年数据泄露事件{breach}次"); key_risks.append("数据泄露")
    if "无" in consent:
        score += 0.4
    if "无" in dpo:
        score += 0.3; findings.append("未指定数据保护官")

    score = round(min(score, 4.0), 2)
    return RiskDimension("数据隐私合规风险", weight=6, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_governance(data: Dict[str, Any]) -> RiskDimension:
    findings, key_risks, score = [], [], 1.0

    board_risk = _ss(data.get("董事会风险委员会"))
    cro = _ss(data.get("首席风险官CRO建制"))
    three_lines = _ss(data.get("三道防线成熟度"))
    internal_audit = _ss(data.get("内部审计独立性"))
    risk_policy = _ss(data.get("风险管理政策"))
    disclosure = _ss(data.get("风险信息披露机制"))
    related_gov = _ss(data.get("关联交易治理"))

    if "无" in board_risk or "未" in board_risk:
        score += 0.6; findings.append("未设立董事会风险委员会"); key_risks.append("治理架构不足")
    if "无" in cro:
        score += 0.5; findings.append("未设立CRO"); key_risks.append("CRO缺失")
    if "初始" in three_lines or "无" in three_lines:
        score += 0.8; findings.append(f"三道防线成熟度：{three_lines or '未建立'}"); key_risks.append("三道防线薄弱")
    elif "部分" in three_lines:
        score += 0.4
    if "弱" in internal_audit or "无" in internal_audit:
        score += 0.5; findings.append("内部审计独立性不足")
    if "无" in risk_policy or "未" in risk_policy:
        score += 0.6; findings.append("无正式风险管理政策"); key_risks.append("风险政策缺失")
    if "无" in disclosure:
        score += 0.3
    if "不完善" in related_gov or "无" in related_gov:
        score += 0.4; findings.append("关联交易治理不完善")

    score = round(min(score, 4.0), 2)
    return RiskDimension("公司治理风险", weight=7, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)


def score_anti_bribery(data: Dict[str, Any]) -> RiskDimension:
    findings, key_risks, score = [], [], 1.0

    policy = _ss(data.get("反贿赂合规政策"))
    iso37001 = _ss(data.get("ISO37001认证"))
    whistleblower = _ss(data.get("举报机制"))
    third_party_dd = _ss(data.get("第三方尽职调查"))
    gift_policy = _ss(data.get("礼品招待政策"))
    training = _sf(data.get("合规培训覆盖率(%)"))
    violation = _sf(data.get("近3年贿赂违规事件数"))

    if "无" in policy or "未" in policy:
        score += 0.8; findings.append("无反贿赂合规政策"); key_risks.append("反贿赂政策缺失")
    if "无" in iso37001:
        score += 0.3
    if "无" in whistleblower:
        score += 0.6; findings.append("无举报机制"); key_risks.append("举报机制缺失")
    if "无" in third_party_dd or "未" in third_party_dd:
        score += 0.5; findings.append("第三方尽职调查不足"); key_risks.append("第三方合规风险")
    if "无" in gift_policy:
        score += 0.3
    if training is not None and training < 80:
        score += 0.4; findings.append(f"合规培训覆盖率{training}%")
    if violation is not None and violation > 0:
        score += 1.5; findings.append(f"近3年贿赂违规{violation}次"); key_risks.append("贿赂违规")

    score = round(min(score, 4.0), 2)
    return RiskDimension("反贿赂道德合规风险", weight=5, score=score, level=RiskLevel.from_score(score),
                         findings=findings, key_risks=key_risks, raw_data=data)
