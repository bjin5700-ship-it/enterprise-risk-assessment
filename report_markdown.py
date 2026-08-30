import os
from datetime import datetime
from typing import List, Optional

from risk_engine import RiskLevel, AssessmentResult


class MarkdownReportGenerator:
    def __init__(self, result: AssessmentResult, output_path: Optional[str] = None):
        self.result = result
        self.output_path = output_path or self._default_path()

    def _default_path(self) -> str:
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self.result.company_name.replace(' ', '_').replace('/', '_')
        return os.path.join(os.getcwd(), f'企业风险评估报告_{safe_name}_{now}.md')

    def generate(self) -> str:
        lines: List[str] = []
        _ = lines.append

        _('# 企业风险评估报告')
        _('')
        _(f'**企业名称：** {self.result.company_name}')
        _(f'**报告日期：** {self.result.report_date}')
        _('')
        _('> 本报告基于企业风险管理信息搜集表自动生成')
        _('> 仅供内部管理参考，请勿外传')
        _('')
        _('---')
        _('')

        _('## 一、评估概要')
        _('')
        _('| 项目 | 内容 |')
        _('|------|------|')
        _(f'| 企业名称 | {self.result.company_name} |')
        _(f'| 综合评分 | {self.result.overall_score:.2f} / 4.00 |')
        _(f'| 风险等级 | {self.result.overall_level.value} |')
        _(f'| 评估日期 | {self.result.report_date} |')
        _(f'| 评估维度数 | {len(self.result.dimensions)} |')
        _('')

        try:
            from risk_analytics import enrich_assessment_full
            from action_planner import build_action_plans
            basic = (self.result.all_raw_data or {}).get("企业基本信息", {})
            plans = build_action_plans(self.result)
            analytics = enrich_assessment_full(self.result, basic_info=basic, action_plans=plans, record_snapshot=False)
            if analytics.get("executive_summary"):
                _('### 执行摘要')
                _('')
                for line in analytics["executive_summary"]:
                    _(f'- {line}')
                _('')
        except Exception:
            pass

        _('## 二、各维度评分')
        _('')
        _('| 维度 | 评分 | 等级 |')
        _('|------|------|------|')
        for dim in sorted(self.result.dimensions.values(), key=lambda d: d.score, reverse=True):
            _(f'| {dim.name} | {dim.score:.2f} | {dim.level.value} |')
        _('')
        _('---')
        _('')

        _('## 三、关键风险详情')
        _('')
        all_risks = [(d.name, r) for d in self.result.dimensions.values() for r in d.key_risks]
        if all_risks:
            for dim_name, risk_text in all_risks:
                _(f'- **[{dim_name}]** {risk_text}')
            _('')
        else:
            _('暂无关键风险项。')
            _('')
        _('---')
        _('')

        section = 4
        try:
            from action_planner import build_action_plans
            plans = build_action_plans(self.result)
            if plans.get("action_items"):
                _(f'## {self._zh(section)}、整改行动路线图')
                section += 1
                _('')
                _(f'共 {plans.get("total_actions", 0)} 项可执行行动，P0 立即启动 {plans.get("p0_count", 0)} 项。')
                _('')
                _('| 编号 | 优先级 | 维度 | 行动 | 责任人 | 周期(天) |')
                _('|------|--------|------|------|--------|----------|')
                for a in plans.get("action_items", [])[:15]:
                    _(f'| {a.get("id", "")} | {a.get("priority", "")} | {a.get("dimension", "")} | {a.get("title", "")} | {a.get("owner", "")} | {a.get("timeline_days", "")} |')
                _('')
                _('---')
                _('')
        except Exception:
            pass

        try:
            from risk_closed_loop import build_export_closed_loop, format_closed_loop_for_report
            pkg = build_export_closed_loop(self.result)
            cl = format_closed_loop_for_report(pkg.get("closed_loop"), pkg.get("alerts"))
            if cl.get("show"):
                _(f'## {self._zh(section)}、数据闭环与 KRI 告警')
                section += 1
                _('')
                if cl.get("alert_summary"):
                    _(f'**告警摘要：** {cl["alert_summary"]}')
                    _('')
                for a in cl.get("alert_items", []):
                    _(f'- **[{a.get("severity", "").upper()}] {a.get("title", "")}** — {a.get("message", "")}')
                    if a.get("action"):
                        _(f'  - 建议：{a["action"]}')
                _('')
                od = cl.get("overall_delta")
                od_str = f"{od:+.2f}" if od is not None else "—"
                _('| 指标 | 值 |')
                _('|------|-----|')
                _(f'| 整改验证 | {cl.get("verification_label", "—")} |')
                _(f'| 评分变化 | {od_str} ({cl.get("overall_trend", "")}) |')
                _(f'| 行动完成率 | {cl.get("completion_pct", 0)}% ({cl.get("actions_completed", 0)}/{cl.get("actions_total", 0)}) |')
                _(f'| KPI 快照 | {cl.get("snapshot_count", 0)} 次 |')
                _('')
                if cl.get("recommendation"):
                    _(f'**建议：** {cl["recommendation"]}')
                    _('')
                if cl.get("timeseries_message"):
                    _(f'**KPI 时序：** {cl["timeseries_message"]}（{cl.get("timeseries_period", "")}）')
                    _('')
                if cl.get("dim_changes"):
                    _('| 维度 | 前次 | 本次 | Δ | 趋势 |')
                    _('|------|------|------|---|------|')
                    for d in cl["dim_changes"]:
                        delta = d.get("delta", 0)
                        _(f'| {d.get("dimension", "")} | {d.get("prior", "")} | {d.get("current", "")} | {delta:+.2f} | {d.get("trend", "")} |')
                    _('')
                _('---')
                _('')
        except Exception:
            pass

        _(f'## {self._zh(section)}、评估结论')
        _('')
        conclusions = self._generate_conclusions()
        for c in conclusions:
            _(f'- {c}')
        _('')
        _('---')
        _('')
        _('*本报告由企业风险管理系统自动生成*')
        _('*报告时间: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '*')

        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f'OK Markdown 风险评估报告已生成: {self.output_path}')
        return self.output_path

    @staticmethod
    def _zh(n: int) -> str:
        nums = "零一二三四五六七八九十"
        if n <= 10:
            return nums[n]
        return str(n)

    def _generate_conclusions(self) -> List[str]:
        conclusions = []
        score = self.result.overall_score
        if score <= 1.5:
            conclusions.append('企业整体风险较低，运营状况良好。')
        elif score <= 2.5:
            conclusions.append('企业存在一定风险，建议关注中等风险维度并制定应对措施。')
        elif score <= 3.0:
            conclusions.append('企业风险偏高，需重点关注高风险维度并尽快采取整改措施。')
        else:
            conclusions.append('企业风险极高，建议进行全面风险排查并启动应急预案。')

        high_risk_dims = [d.name for d in self.result.dimensions.values()
                          if d.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
        if high_risk_dims:
            dim_names = '、'.join(high_risk_dims)
            conclusions.append(f'需重点关注以下高风险维度: {dim_names}')

        return conclusions
