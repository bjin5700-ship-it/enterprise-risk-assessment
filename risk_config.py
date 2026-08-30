# -*- coding: utf-8 -*-
"""行业差异化阈值与 ERM 配置 — Phase B"""

from __future__ import annotations

from typing import Any, Dict, Optional

# 行业财务/运营阈值（资产负债率%、流动比率下限、客户集中度% 等）
INDUSTRY_PROFILES: Dict[str, dict] = {
    "制造业": {
        "debt_ratio_warn": 65, "debt_ratio_crit": 80,
        "current_ratio_low": 1.2, "current_ratio_crit": 0.9,
        "customer_conc_warn": 50, "gross_margin_floor": 15,
        "description": "资本密集、供应链与产能波动敏感",
    },
    "化工": {
        "debt_ratio_warn": 60, "debt_ratio_crit": 75,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.8,
        "customer_conc_warn": 45, "gross_margin_floor": 12,
        "description": "安全环保合规权重高、周期性强",
    },
    "能源": {
        "debt_ratio_warn": 70, "debt_ratio_crit": 85,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.7,
        "customer_conc_warn": 40, "gross_margin_floor": 10,
        "description": "政策与大宗商品价格敏感",
    },
    "建筑": {
        "debt_ratio_warn": 75, "debt_ratio_crit": 88,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.8,
        "customer_conc_warn": 55, "gross_margin_floor": 8,
        "description": "高杠杆、回款周期长为常态",
    },
    "交通运输": {
        "debt_ratio_warn": 68, "debt_ratio_crit": 82,
        "current_ratio_low": 1.1, "current_ratio_crit": 0.85,
        "customer_conc_warn": 45, "gross_margin_floor": 10,
        "description": "燃油/运价波动、资产折旧压力大",
    },
    "信息技术": {
        "debt_ratio_warn": 50, "debt_ratio_crit": 70,
        "current_ratio_low": 1.5, "current_ratio_crit": 1.0,
        "customer_conc_warn": 35, "gross_margin_floor": 25,
        "description": "轻资产、研发与人才依赖度高",
    },
    "金融": {
        "debt_ratio_warn": 85, "debt_ratio_crit": 92,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.9,
        "customer_conc_warn": 30, "gross_margin_floor": 20,
        "description": "杠杆为业务特征，关注资本充足与流动性",
    },
    "批发零售": {
        "debt_ratio_warn": 60, "debt_ratio_crit": 78,
        "current_ratio_low": 1.2, "current_ratio_crit": 0.9,
        "customer_conc_warn": 40, "gross_margin_floor": 5,
        "description": "薄利、库存与现金流周转关键",
    },
    "房地产": {
        "debt_ratio_warn": 78, "debt_ratio_crit": 90,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.7,
        "customer_conc_warn": 50, "gross_margin_floor": 15,
        "description": "高杠杆行业，预售与政策风险并重",
    },
    "其他": {
        "debt_ratio_warn": 65, "debt_ratio_crit": 80,
        "current_ratio_low": 1.2, "current_ratio_crit": 0.9,
        "customer_conc_warn": 50, "gross_margin_floor": 15,
        "description": "通用阈值",
    },
    "医疗健康": {
        "debt_ratio_warn": 55, "debt_ratio_crit": 72,
        "current_ratio_low": 1.3, "current_ratio_crit": 1.0,
        "customer_conc_warn": 35, "gross_margin_floor": 20,
        "description": "合规与医疗质量风险权重高",
    },
    "物流": {
        "debt_ratio_warn": 68, "debt_ratio_crit": 82,
        "current_ratio_low": 1.1, "current_ratio_crit": 0.85,
        "customer_conc_warn": 45, "gross_margin_floor": 8,
        "description": "运价波动、燃油与资产周转敏感",
    },
    "新能源": {
        "debt_ratio_warn": 62, "debt_ratio_crit": 78,
        "current_ratio_low": 1.2, "current_ratio_crit": 0.9,
        "customer_conc_warn": 40, "gross_margin_floor": 12,
        "description": "政策补贴、技术路线与资本开支风险",
    },
    "教育": {
        "debt_ratio_warn": 50, "debt_ratio_crit": 68,
        "current_ratio_low": 1.4, "current_ratio_crit": 1.0,
        "customer_conc_warn": 30, "gross_margin_floor": 18,
        "description": "政策监管与品牌声誉敏感",
    },
    "农业": {
        "debt_ratio_warn": 60, "debt_ratio_crit": 75,
        "current_ratio_low": 1.0, "current_ratio_crit": 0.8,
        "customer_conc_warn": 50, "gross_margin_floor": 10,
        "description": "气候、价格周期与生物资产风险",
    },
}

DEFAULT_PROFILE = INDUSTRY_PROFILES["其他"]
REASSESSMENT_INTERVAL_DAYS = 90
KRI_WARNING_THRESHOLD = 2.5
KRI_CRITICAL_THRESHOLD = 3.0


def get_industry_profile(industry: Optional[str]) -> dict:
    if not industry:
        return {**DEFAULT_PROFILE, "industry_key": "其他"}
    text = str(industry).strip()
    for key, profile in INDUSTRY_PROFILES.items():
        if key in text:
            return {**profile, "industry_key": key}
    return {**DEFAULT_PROFILE, "industry_key": "其他"}


def get_reassessment_interval_days(basic: dict) -> int:
    custom = basic.get("评估复评周期(天)") or basic.get("复评周期(天)")
    try:
        if custom:
            return max(30, min(365, int(float(str(custom).replace("天", "")))))
    except (ValueError, TypeError):
        pass
    return REASSESSMENT_INTERVAL_DAYS
