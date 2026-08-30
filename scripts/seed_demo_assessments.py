# -*- coding: utf-8 -*-
"""写入两条 DEMO 评估档案，供报告页审阅 18 章。不覆盖已有非 DEMO 记录。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "web_app"))

from data_external_risk import DEMO_CHEM_USCC, DEMO_MFG_USCC

os.chdir(ROOT)


def _mfg() -> dict:
    data = {
        "企业基本信息": {
            "企业名称": "DEMO-江东精密制造",
            "所属行业": "制造业",
            "年营业额(万元)": "86000",
            "资产总额(万元)": "124000",
            "员工总数(人)": "1860",
            "风险偏好": "稳健",
            "统一社会信用代码": DEMO_MFG_USCC,
        },
        "财务风险": {
            "资产负债率(%)": "71",
            "流动比率": "1.05",
            "速动比率": "0.72",
            "净利率(%)": "2.1",
            "毛利率(%)": "14",
            "净资产收益率ROE(%)": "4.2",
            "经营性现金流净额(万元)": "-3200",
            "自由现金流(万元)": "-1800",
            "利息保障倍数": "1.8",
            "短期借款占比(%)": "48",
            "近三年是否连续亏损": "否",
            "是否存在债务违约记录": "否",
        },
        "经营风险": {
            "市场地位": "区域前列",
            "前五大客户收入占比(%)": "62",
            "最大单一客户占比(%)": "28",
            "应收账款周转天数": "95",
            "前五大供应商采购占比(%)": "55",
            "最大单一供应商占比(%)": "22",
            "原材料价格波动影响": "高",
            "近三年营收增长率(%)": "3.5",
            "近三年利润增长率(%)": "-4",
            "季节性波动": "中",
            "经营许可证/资质": "齐全",
        },
        "生产运营风险": {
            "产能利用率(%)": "68",
            "设备平均役龄(年)": "11",
            "设备故障率(%)": "6.5",
            "产品合格率(%)": "98.2",
            "客诉率(件/万件)": "4.1",
            "质量事故记录": "无",
            "外协加工占比(%)": "18",
            "库存周转天数": "72",
            "原材料库存保障天数": "21",
            "产能瓶颈环节": "精加工",
        },
        "安全生产风险": {
            "安全管理人员占比(%)": "1.2",
            "安全投入占营收比(%)": "0.8",
            "安全生产标准化等级": "二级",
            "ISO45001认证": "有",
            "近三年工伤事故次数": "3",
            "近三年死亡事故次数": "0",
            "隐患整改率(%)": "92",
            "重大隐患数量": "1",
            "安全培训覆盖率(%)": "96",
            "特种作业人员持证率(%)": "100",
            "应急演练频次(次/年)": "2",
            "是否涉及危化品": "否",
        },
        "环境风险": {
            "环评批复情况": "已批复",
            "排污许可证": "有效",
            "近三年环境处罚次数": "1",
            "处罚金额累计(万元)": "18",
            "排放达标率(%)": "99.1",
            "ISO14001认证": "有",
            "环保设施运行率(%)": "97",
            "环境风险等级": "一般",
            "环境应急预案": "已备案",
        },
        "法律合规风险": {
            "在审案件数量": "2",
            "在审案件标的额(万元)": "640",
            "近三年败诉案件数": "0",
            "行政处罚次数(近三年)": "1",
            "合同审核率(%)": "88",
            "知识产权纠纷": "无",
            "专利数量": "46",
        },
        "供应链风险": {
            "核心供应商数量": "8",
            "单一来源采购占比(%)": "31",
            "进口依赖度(%)": "22",
            "物流中断风险": "中",
            "呆滞库存占比(%)": "7",
            "出口业务占比(%)": "18",
        },
        "技术与信息安全风险": {
            "研发投入占营收比(%)": "3.1",
            "研发人员占比(%)": "6",
            "专利数量(累计)": "46",
            "核心技术来源": "自主+引进",
            "数字化转型阶段": "局部",
            "信息系统安全等级": "等保二级",
            "网络安全事件次数(近三年)": "1",
            "信息安全认证": "无",
        },
        "人力资源风险": {
            "年离职率(%)": "18",
            "核心人才离职率(%)": "9",
            "关键岗位空缺数": "4",
            "招聘完成率(%)": "82",
            "劳动合同签订率(%)": "100",
            "社保缴纳合规性": "合规",
            "近三年劳资纠纷次数": "2",
            "绩效考核覆盖率(%)": "90",
            "薪酬竞争力": "中",
        },
        "信用风险": {
            "对外担保余额(万元)": "12000",
            "担保比率(%)": "14",
            "逾期付款记录": "无",
            "客户回款周期(天)": "88",
            "坏账率(%)": "1.6",
            "税务信用等级": "A",
            "行政处罚记录": "有",
        },
        "法律合规风险": {
            "在审案件数量": "2",
            "在审案件标的额(万元)": "640",
            "近三年败诉案件数": "0",
            "行政处罚次数(近三年)": "1",
            "合同审核率(%)": "88",
        },
    }
    return _stamp_matrix(data, _mfg_pi())


def _chem() -> dict:
    d = _mfg()
    d["企业基本信息"] = {
        "企业名称": "DEMO-滨海化工新材",
        "所属行业": "化工",
        "年营业额(万元)": "152000",
        "资产总额(万元)": "210000",
        "员工总数(人)": "980",
        "风险偏好": "稳健",
        "统一社会信用代码": DEMO_CHEM_USCC,
    }
    d["财务风险"]["资产负债率(%)"] = "64"
    d["财务风险"]["流动比率"] = "1.15"
    d["财务风险"]["净利率(%)"] = "5.4"
    d["安全生产风险"].update({
        "是否涉及危化品": "是",
        "危化品种类数": "6",
        "近三年工伤事故次数": "5",
        "重大隐患数量": "2",
        "ISO45001认证": "无",
    })
    d["环境风险"].update({
        "近三年环境处罚次数": "3",
        "处罚金额累计(万元)": "86",
        "环境风险等级": "较大",
        "ISO14001认证": "无",
    })
    d["供应链风险"]["进口依赖度(%)"] = "41"
    return _stamp_matrix(d, _chem_pi())


def _stamp_matrix(form: dict, overrides: dict) -> dict:
    for sheet, pair in overrides.items():
        if sheet not in form or not isinstance(form[sheet], dict):
            continue
        form[sheet]["可能性(1-5)"] = pair[0]
        form[sheet]["影响(1-5)"] = pair[1]
    return form


def _mfg_pi() -> dict:
    return {
        "财务风险": ("3 可能", "5 极严重"),
        "经营风险": ("4 很可能", "3 中等"),
        "生产运营风险": ("3 可能", "4 严重"),
        "安全生产风险": ("2 不太可能", "5 极严重"),
        "环境风险": ("2 不太可能", "4 严重"),
        "法律合规风险": ("3 可能", "3 中等"),
        "法律与合规风险": ("3 可能", "3 中等"),
        "供应链风险": ("4 很可能", "4 严重"),
        "技术风险": ("3 可能", "2 轻微"),
        "技术与信息安全风险": ("3 可能", "2 轻微"),
        "人力资源风险": ("5 几乎确定", "2 轻微"),
        "信用风险": ("2 不太可能", "3 中等"),
    }


def _chem_pi() -> dict:
    return {
        "财务风险": ("2 不太可能", "4 严重"),
        "经营风险": ("3 可能", "3 中等"),
        "生产运营风险": ("4 很可能", "4 严重"),
        "安全生产风险": ("4 很可能", "5 极严重"),
        "环境风险": ("5 几乎确定", "4 严重"),
        "法律合规风险": ("3 可能", "4 严重"),
        "法律与合规风险": ("3 可能", "4 严重"),
        "供应链风险": ("3 可能", "5 极严重"),
        "技术风险": ("2 不太可能", "3 中等"),
        "技术与信息安全风险": ("2 不太可能", "3 中等"),
        "人力资源风险": ("3 可能", "2 轻微"),
        "信用风险": ("2 不太可能", "2 轻微"),
    }


def _align_sheets(form: dict) -> dict:
    """Excel 页名 → 评分键。"""
    out = dict(form)
    if "技术与信息安全风险" in out:
        out["技术风险"] = out["技术与信息安全风险"]
    if "法律合规风险" in out:
        pass
    return out


def main() -> None:
    from app import (
        assessment_to_dict,
        compute_form_stats,
        get_template_fields,
        normalize_form_data,
        run_assessment_from_form,
    )

    template = get_template_fields()

    created = []
    for raw, note in ((_mfg(), "演示档案 · 制造业"), (_chem(), "演示档案 · 化工")):
        form = _align_sheets(raw)
        if template:
            form = normalize_form_data(form, template)
            # 写回演示值（normalize 会把未出现字段置空）
            for sheet, fields in raw.items():
                if sheet in form:
                    form[sheet].update(fields)
                elif sheet == "技术与信息安全风险" and "技术风险" in form:
                    form["技术风险"].update(fields)
        result = run_assessment_from_form(form)
        stats = compute_form_stats(form, template) if template else None
        payload = assessment_to_dict(result, stats=stats)
        rec = {
            "id": "demo-mfg" if "精密" in result.company_name else "demo-chem",
            "company_name": result.company_name,
            "overall_score": payload.get("overall_score"),
            "overall_level": payload.get("overall_level"),
            "report_date": payload.get("report_date"),
            "assessed_at": payload.get("assessed_at"),
            "note": note,
            "form_stats": payload.get("form_stats"),
            "assessment": payload,
        }
        created.append(rec)
        print(f"{rec['company_name']}  {rec['overall_level']}  {rec['overall_score']}  gate={ (payload.get('data_quality_gate') or payload.get('analytics') or {}).get('data_quality_gate', payload.get('overall_level')) }")

    from erm_store import delete_demo_assessments, upsert_assessment, init_store, backend_name
    init_store()
    delete_demo_assessments()
    for rec in created:
        upsert_assessment(rec)
        _seed_kri_history(rec)
        _seed_overdue_task(rec["company_name"])
    print(f"history written: {len(created)} demo via {backend_name()}")


def _seed_kri_history(rec: dict) -> None:
    """为演示企业写入 3 个 KPI 快照，使仪表盘趋势章可展示。"""
    from copy import deepcopy
    from datetime import datetime, timedelta
    from erm_store import delete_company_kri
    from risk_timeseries import analyze_timeseries, record_assessment_snapshot
    from app import run_assessment_from_form

    payload = rec.get("assessment") or {}
    form = deepcopy(payload.get("all_raw_data") or {})
    if not form:
        return
    company = rec["company_name"]
    delete_company_kri(company)
    result = run_assessment_from_form(form)
    base = datetime.now()
    debt = float((form.get("财务风险") or {}).get("资产负债率(%)") or 70)
    prefix = "mfg" if "精密" in company else "chem"
    for i, days in enumerate((90, 45, 0)):
        f2 = deepcopy(form)
        f2.setdefault("财务风险", {})["资产负债率(%)"] = str(round(debt - i * 1.2, 1))
        record_assessment_snapshot(
            result, f2,
            assessment_id=f"{prefix}-kri-{i}",
            assessed_at=(base - timedelta(days=days)).isoformat(),
        )
    ts = analyze_timeseries(company)
    print(f"  kri snapshots={ts.get('snapshot_count')} trend={ts.get('has_trend')} kpis={len(ts.get('kpi_trends') or [])}")


def _seed_overdue_task(company: str) -> None:
    from risk_tasks import sync_from_assessment
    sync_from_assessment(company, assessed_at="2025-01-01T00:00:00", basic={"评估复评周期(天)": "30"}, force_due=True)


if __name__ == "__main__":
    main()
