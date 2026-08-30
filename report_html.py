# -*- coding: utf-8 -*-
"""
HTML 风险报告生成器 - HTML Report Generator
生成带可视化图表的交互式 HTML 风险评估报告
"""

import os
import json
from datetime import datetime
from typing import Optional

from report_base import BaseReportGenerator
from risk_engine import AssessmentResult, RiskLevel


class HTMLReportGenerator(BaseReportGenerator):
    """HTML 格式风险评估报告生成器"""

    TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>企业风险评估报告 - {{ company_name }}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #333; }
  .page { max-width: 1100px; margin: 0 auto; padding: 20px; }

  /* 封面 */
  .cover { text-align: center; padding: 80px 40px 60px; background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%); color: #fff; border-radius: 12px; margin-bottom: 30px; }
  .cover h1 { font-size: 36px; font-weight: 700; letter-spacing: 4px; margin-bottom: 20px; }
  .cover .company { font-size: 24px; opacity: 0.95; margin-bottom: 40px; }
  .cover .meta { font-size: 14px; opacity: 0.7; line-height: 2; }

  /* 卡片 */
  .card { background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 28px; margin-bottom: 24px; }
  .card h2 { font-size: 20px; color: #1a3a5c; border-left: 4px solid #2d6a9f; padding-left: 12px; margin-bottom: 18px; }
  .card h3 { font-size: 16px; color: #555; margin-bottom: 12px; }

  /* 摘要卡片 */
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .summary-item { text-align: center; padding: 20px; border-radius: 8px; }
  .summary-item .label { font-size: 13px; color: #888; margin-bottom: 6px; }
  .summary-item .value { font-size: 28px; font-weight: 700; }
  .summary-item .sub { font-size: 13px; margin-top: 4px; }

  .bg-low { background: #e8f5e9; } .bg-low .value { color: #2e7d32; }
  .bg-medium { background: #fff8e1; } .bg-medium .value { color: #f57f17; }
  .bg-high { background: #ffebee; } .bg-high .value { color: #c62828; }
  .bg-critical { background: #fce4ec; } .bg-critical .value { color: #880e4f; }

  /* 图表行 */
  .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 768px) { .chart-row { grid-template-columns: 1fr; } }
  .chart-box { position: relative; height: 320px; }

  /* 维度评分表 */
  .dim-table { width: 100%; border-collapse: collapse; }
  .dim-table th { background: #1a3a5c; color: #fff; padding: 10px 14px; text-align: left; font-size: 13px; }
  .dim-table td { padding: 10px 14px; border-bottom: 1px solid #eee; font-size: 13px; }
  .dim-table tr:hover td { background: #f5f7fa; }

  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff; }
  .badge-low { background: #6BCB77; }
  .badge-medium { background: #FFD93D; color: #333; }
  .badge-high { background: #FF6B6B; }
  .badge-critical { background: #C00000; }

  .priority-bar { height: 8px; border-radius: 4px; background: #e0e0e0; overflow: hidden; }
  .priority-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }

  /* 关键风险 */
  .risk-list { list-style: none; }
  .risk-list li { padding: 8px 0 8px 20px; border-bottom: 1px solid #f0f0f0; position: relative; }
  .risk-list li::before { content: "⚠"; position: absolute; left: 0; color: #ff6b6b; }
  .risk-list .dim-tag { display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 4px; background: #e3f2fd; color: #1565c0; margin-right: 8px; }

  /* 附录折叠 */
  .appendix-item { margin-bottom: 12px; }
  .appendix-item summary { cursor: pointer; font-weight: 600; color: #2d6a9f; padding: 6px 0; }
  .appendix-item table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  .appendix-item th { background: #f5f5f5; padding: 6px 10px; text-align: left; font-size: 12px; }
  .appendix-item td { padding: 5px 10px; border-bottom: 1px solid #eee; font-size: 12px; }

  .footer { text-align: center; padding: 30px; color: #aaa; font-size: 12px; }
</style>
</head>
<body>
<div class="page">

  <!-- 封面 -->
  <div class="cover">
    <h1>企业风险评估报告</h1>
    <div class="company">{{ company_name }}</div>
    <div class="meta">
      <div>报告日期：{{ report_date }}</div>
      <div>本报告基于企业风险管理信息搜集表自动生成</div>
      <div>仅供内部管理参考，请勿外传</div>
    </div>
  </div>

  <!-- 评估概要 -->
  <div class="card">
    <h2>一、评估概要</h2>
    <p style="margin-bottom:18px;line-height:1.8;font-size:14px;color:#555;">
      本报告对 <strong>{{ company_name }}</strong> 的风险状况进行全面评估。
      评估基于企业风险管理信息搜集表所填数据，从财务、负债、行业市场、法律合规、税务、公司治理、
      供应链、技术信息、人力资源、ESG等17个维度进行系统性分析。
    </p>
    <div class="summary-grid">
      <div class="summary-item bg-{{ overall_level_css }}">
        <div class="label">综合风险评分</div>
        <div class="value">{{ overall_score }}</div>
        <div class="sub">/ 4.00</div>
      </div>
      <div class="summary-item bg-{{ overall_level_css }}">
        <div class="label">风险等级</div>
        <div class="value">{{ overall_level }}</div>
        <div class="sub">{{ overall_level_desc }}</div>
      </div>
      <div class="summary-item bg-low">
        <div class="label">评估维度</div>
        <div class="value">{{ dim_count }}</div>
        <div class="sub">个维度</div>
      </div>
      <div class="summary-item bg-high">
        <div class="label">关键风险点</div>
        <div class="value">{{ key_risk_count }}</div>
        <div class="sub">项待处理</div>
      </div>
    </div>
  </div>

  {% if executive_summary %}
  <div class="card">
    <h2>执行摘要（Executive Summary）</h2>
    <ul class="risk-list" style="margin-bottom:12px;">
      {% for line in executive_summary %}
      <li style="border:none;padding-left:0;">{{ line }}</li>
      {% endfor %}
    </ul>
    <p style="font-size:13px;color:#666;">ERM 成熟度 {{ erm_maturity_level }}/5（{{ erm_maturity_name }}）；评估置信度 {{ confidence_score }}%（{{ confidence_level }}）。{{ standards_footer }}</p>
    {% if cross_risk_alerts %}
    <p style="font-size:13px;color:#c62828;margin-top:8px;"><strong>交叉风险：</strong>{% for c in cross_risk_alerts %}{{ c.message }}{% if not loop.last %}；{% endif %}{% endfor %}</p>
    {% endif %}
  </div>
  {% endif %}

  <!-- 综合风险评分 + 图表 -->
  <div class="card">
    <h2>二、综合风险评分</h2>
    <div class="chart-row">
      <div class="chart-box">
        <canvas id="radarChart"></canvas>
      </div>
      <div class="chart-box">
        <canvas id="barChart"></canvas>
      </div>
    </div>
  </div>

  <!-- 各维度风险分析 -->
  <div class="card">
    <h2>三、各维度风险分析</h2>
    <table class="dim-table">
      <thead>
        <tr>
          <th style="width:22%">风险维度</th>
          <th style="width:10%">评分</th>
          <th style="width:10%">等级</th>
          <th style="width:38%">优先级</th>
          <th style="width:20%">建议行动</th>
        </tr>
      </thead>
      <tbody>
        {% for dim in dimensions %}
        <tr>
          <td><strong>{{ dim.name }}</strong></td>
          <td>{{ dim.score }}</td>
          <td><span class="badge badge-{{ dim.level_css }}">{{ dim.level }}</span></td>
          <td>
            <div class="priority-bar">
              <div class="priority-bar-fill" style="width:{{ dim.score_percent }}%;background:{{ dim.color_hex }};"></div>
            </div>
          </td>
          <td>{{ dim.action }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- 核心风险总结 -->
  <div class="card">
    <h2>四、核心风险总结</h2>
    {% if key_risks %}
    <p style="margin-bottom:12px;font-size:14px;color:#555;">共识别 <strong>{{ key_risks|length }}</strong> 项关键风险点：</p>
    <ul class="risk-list">
      {% for dim_name, kr in key_risks %}
      <li><span class="dim-tag">{{ dim_name }}</span>{{ kr }}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p style="color:#888;">未识别出关键风险点，整体风险可控。</p>
    {% endif %}
  </div>

  <!-- 深度分析 -->
  {% if deep_summary or mc_interpretation or tld_summary or playbook_note or bayes_interpretation %}
  <div class="card">
    <h2>五、深度量化与治理分析</h2>
    {% if deep_summary %}<p style="font-size:14px;line-height:1.8;margin-bottom:12px;">{{ deep_summary }}</p>{% endif %}
    {% if bayes_interpretation %}<h3>贝叶斯风险更新</h3><p style="font-size:13px;line-height:1.8;margin-bottom:12px;">{{ bayes_interpretation }}</p>{% endif %}
    {% if mc_interpretation %}<h3>蒙特卡洛量化（ISO 31010）</h3><p style="font-size:13px;line-height:1.8;margin-bottom:12px;">{{ mc_interpretation }}</p>{% endif %}
    {% if tld_summary %}<h3>COSO 三道防线</h3><p style="font-size:13px;line-height:1.8;margin-bottom:12px;">{{ tld_summary }}</p>{% endif %}
    {% if playbook_note %}<h3>行业方案路径</h3><p style="font-size:13px;line-height:1.8;">{{ playbook_note }}</p>{% endif %}
    {% if corr_count %}<p style="font-size:12px;color:#666;margin-top:8px;">识别 {{ corr_count }} 条显著风险传导路径。</p>{% endif %}
  </div>
  {% endif %}

  <!-- 整改行动路线图 -->
  {% if action_items %}
  <div class="card">
    <h2>{% if deep_summary or mc_interpretation %}六{% else %}五{% endif %}、整改行动路线图</h2>
    <p style="font-size:13px;color:#555;margin-bottom:12px;">共 {{ action_total }} 项可执行行动，P0 立即启动 {{ action_p0 }} 项。对齐 ISO 31000 风险处理流程。</p>
    <table class="dim-table">
      <thead><tr><th>编号</th><th>优先级</th><th>维度</th><th>行动</th><th>责任人</th><th>周期(天)</th></tr></thead>
      <tbody>
        {% for a in action_items %}
        <tr>
          <td>{{ a.id }}</td>
          <td><span class="badge badge-{{ 'critical' if a.priority == 'P0' else 'high' if a.priority == 'P1' else 'medium' }}">{{ a.priority }}</span></td>
          <td>{{ a.dimension }}</td>
          <td>{{ a.title }}</td>
          <td>{{ a.owner }}</td>
          <td>{{ a.timeline_days }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if closed_loop_show %}
  <div class="card">
    <h2>{% if action_items %}{% if deep_summary or mc_interpretation %}七{% else %}六{% endif %}{% elif deep_summary or mc_interpretation %}六{% else %}五{% endif %}、数据闭环与 KRI 告警</h2>
    {% if closed_loop_alert_summary %}
    <p style="font-size:14px;margin-bottom:10px;"><strong>告警摘要：</strong>{{ closed_loop_alert_summary }}</p>
    {% endif %}
    {% if closed_loop_alert_items %}
    <ul class="risk-list">
      {% for a in closed_loop_alert_items %}
      <li><span class="dim-tag">{{ a.severity }}</span><strong>{{ a.title }}</strong> — {{ a.message }}
        {% if a.action %}<div style="font-size:12px;color:#666;margin-top:4px;">建议：{{ a.action }}</div>{% endif %}
      </li>
      {% endfor %}
    </ul>
    {% endif %}
    <div class="summary-grid" style="margin-top:14px;">
      <div class="summary-item bg-medium">
        <div class="label">整改验证</div>
        <div class="value" style="font-size:18px;">{{ closed_loop_verification }}</div>
      </div>
      <div class="summary-item bg-low">
        <div class="label">评分变化</div>
        <div class="value" style="font-size:18px;">{{ closed_loop_delta }}</div>
        <div class="sub">{{ closed_loop_trend }}</div>
      </div>
      <div class="summary-item bg-high">
        <div class="label">行动完成率</div>
        <div class="value" style="font-size:18px;">{{ closed_loop_completion }}%</div>
        <div class="sub">{{ closed_loop_actions_done }}/{{ closed_loop_actions_total }} 项</div>
      </div>
      <div class="summary-item bg-low">
        <div class="label">KPI 快照</div>
        <div class="value" style="font-size:18px;">{{ closed_loop_snapshots }}</div>
      </div>
    </div>
    {% if closed_loop_recommendation %}<p style="font-size:13px;line-height:1.8;margin-top:12px;">{{ closed_loop_recommendation }}</p>{% endif %}
    {% if closed_loop_timeseries %}<p style="font-size:12px;color:#666;margin-top:8px;">{{ closed_loop_timeseries }}</p>{% endif %}
    {% if closed_loop_dim_changes %}
    <table class="dim-table" style="margin-top:12px;">
      <thead><tr><th>维度</th><th>前次</th><th>本次</th><th>Δ</th><th>趋势</th></tr></thead>
      <tbody>
        {% for d in closed_loop_dim_changes %}
        <tr><td>{{ d.dimension }}</td><td>{{ d.prior }}</td><td>{{ d.current }}</td><td>{{ d.delta }}</td><td>{{ d.trend }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
    {% endif %}
  </div>
  {% endif %}

  <!-- 附录 -->
  <div class="card">
    <h2>{% if closed_loop_show %}{% if action_items %}{% if deep_summary or mc_interpretation %}八{% else %}七{% endif %}{% elif deep_summary or mc_interpretation %}七{% else %}六{% endif %}{% elif action_items %}{% if deep_summary or mc_interpretation %}七{% else %}六{% endif %}{% elif deep_summary or mc_interpretation %}六{% else %}五{% endif %}、附录：原始数据摘要</h2>
    <p style="margin-bottom:14px;font-size:13px;color:#888;">以下为各Sheet中提取的关键数据字段摘要（点击展开）：</p>
    {% for sheet_name, items in raw_data_items %}
    <details class="appendix-item">
      <summary>{{ sheet_name }}</summary>
      {% if items %}
      <table>
        <thead><tr><th style="width:35%">字段</th><th>填写内容</th></tr></thead>
        <tbody>
          {% for k, v in items %}
          <tr><td>{{ k }}</td><td>{{ v }}</td></tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p style="color:#bbb;font-size:12px;padding:6px 0;">（无数据）</p>
      {% endif %}
    </details>
    {% endfor %}
  </div>

  <div class="footer">
    <p>企业风险管理系统 · 自动生成 · {{ report_date }}</p>
  </div>
</div>

<script>
const DIM_NAMES = {{ chart_dim_names }};
const DIM_SCORES = {{ chart_dim_scores }};
const DIM_COLORS = {{ chart_dim_colors }};

// 雷达图
new Chart(document.getElementById('radarChart'), {
  type: 'radar',
  data: {
    labels: DIM_NAMES,
    datasets: [{
      label: '风险评分',
      data: DIM_SCORES,
      backgroundColor: 'rgba(45, 106, 159, 0.15)',
      borderColor: 'rgba(45, 106, 159, 0.8)',
      borderWidth: 2,
      pointBackgroundColor: DIM_COLORS,
      pointRadius: 4,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: { min: 0, max: 4, ticks: { stepSize: 1 } }
    },
    plugins: {
      title: { display: true, text: '各维度风险评分雷达图', font: { size: 14 } },
      legend: { display: false }
    }
  }
});

// 柱状图
new Chart(document.getElementById('barChart'), {
  type: 'bar',
  data: {
    labels: DIM_NAMES,
    datasets: [{
      label: '风险评分',
      data: DIM_SCORES,
      backgroundColor: DIM_COLORS.map(c => c + 'CC'),
      borderColor: DIM_COLORS,
      borderWidth: 1,
      borderRadius: 4,
    }]
  },
  options: {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { min: 0, max: 4, ticks: { stepSize: 1 } }
    },
    plugins: {
      title: { display: true, text: '各维度风险评分排序', font: { size: 14 } },
      legend: { display: false }
    }
  }
});
</script>
</body>
</html>"""

    def generate(self) -> str:
        from jinja2 import Template

        sorted_dims = self._sorted_dimensions()
        key_risks = self._all_key_risks()

        # 构建维度数据
        dims_for_template = []
        chart_names = []
        chart_scores = []
        chart_colors = []

        for dim in sorted_dims:
            level_css = dim.level.value
            css_map = {"低风险": "low", "中等风险": "medium", "高风险": "high", "极高风险": "critical"}
            dims_for_template.append({
                "name": dim.name,
                "score": f"{dim.score:.2f}",
                "level": dim.level.value,
                "level_css": css_map.get(dim.level.value, "low"),
                "score_percent": f"{dim.score / 4.0 * 100:.0f}",
                "color_hex": self._risk_color_hex(dim.level.value),
                "action": self._suggest_action(dim),
            })
            chart_names.append(dim.name)
            chart_scores.append(dim.score)
            chart_colors.append(self._risk_color_hex(dim.level.value))

        # 原始数据
        raw_data_items = []
        for sheet_name, data in self.result.all_raw_data.items():
            if not data:
                continue
            items = [(k, v) for k, v in data.items() if v is not None and str(v).strip()]
            raw_data_items.append((sheet_name, items))

        # 等级描述
        level_desc_map = {
            "低风险": "风险可控，维持现有管理措施",
            "中等风险": "存在一定风险，需关注并适时改进",
            "高风险": "风险较高，需制定专项整改计划",
            "极高风险": "风险极高，必须立即采取行动",
        }

        overall_level_css_map = {"低风险": "low", "中等风险": "medium", "高风险": "high", "极高风险": "critical"}

        # 高级分析
        executive_summary = []
        cross_risk_alerts = []
        erm_maturity_level = ""
        erm_maturity_name = ""
        confidence_score = ""
        confidence_level = ""
        standards_footer = ""
        action_items = []
        action_total = 0
        action_p0 = 0
        deep_summary = ""
        mc_interpretation = ""
        tld_summary = ""
        playbook_note = ""
        bayes_interpretation = ""
        corr_count = 0
        try:
            from risk_analytics import enrich_assessment_full
            from action_planner import build_action_plans
            basic = (self.result.all_raw_data or {}).get("企业基本信息", {})
            analytics = enrich_assessment_full(self.result, basic_info=basic)
            executive_summary = analytics.get("executive_summary", [])
            cross_risk_alerts = analytics.get("cross_risk_alerts", [])
            mat = analytics.get("erm_maturity", {})
            conf = analytics.get("confidence", {})
            erm_maturity_level = mat.get("level", "")
            erm_maturity_name = mat.get("name", "")
            confidence_score = conf.get("score", "")
            confidence_level = conf.get("level", "")
            standards_footer = analytics.get("standards_footer", "")
            deep = analytics.get("deep_analysis") or {}
            deep_summary = deep.get("summary", "")
            mc_interpretation = (deep.get("monte_carlo") or {}).get("interpretation", "")
            bayes_interpretation = (analytics.get("bayesian_update") or {}).get("interpretation", "")
            corr_count = len(deep.get("correlation_insights") or [])
            tld = deep.get("three_lines_of_defense") or {}
            if tld:
                tld_summary = f"综合成熟度 {tld.get('overall_maturity')}，最弱防线：{tld.get('weakest_line')}"
            playbook_note = (deep.get("industry_playbook") or {}).get("tailored_note", "")
            plans = build_action_plans(self.result)
            action_items = plans.get("action_items", [])[:15]
            action_total = plans.get("total_actions", 0)
            action_p0 = plans.get("p0_count", 0)
        except Exception:
            pass

        closed_loop_show = False
        closed_loop_alert_summary = ""
        closed_loop_alert_items = []
        closed_loop_verification = ""
        closed_loop_delta = "—"
        closed_loop_trend = ""
        closed_loop_completion = 0
        closed_loop_actions_done = 0
        closed_loop_actions_total = 0
        closed_loop_recommendation = ""
        closed_loop_timeseries = ""
        closed_loop_snapshots = 0
        closed_loop_dim_changes = []
        try:
            from risk_closed_loop import build_export_closed_loop, format_closed_loop_for_report
            pkg = build_export_closed_loop(self.result)
            cl_fmt = format_closed_loop_for_report(pkg.get("closed_loop"), pkg.get("alerts"))
            closed_loop_show = cl_fmt.get("show", False)
            closed_loop_alert_summary = cl_fmt.get("alert_summary", "")
            closed_loop_alert_items = cl_fmt.get("alert_items", [])
            closed_loop_verification = cl_fmt.get("verification_label", "")
            od = cl_fmt.get("overall_delta")
            closed_loop_delta = f"{od:+.2f}" if od is not None else "—"
            closed_loop_trend = cl_fmt.get("overall_trend", "")
            closed_loop_completion = cl_fmt.get("completion_pct", 0)
            closed_loop_actions_done = cl_fmt.get("actions_completed", 0)
            closed_loop_actions_total = cl_fmt.get("actions_total", 0)
            closed_loop_recommendation = cl_fmt.get("recommendation", "") or cl_fmt.get("summary", "")
            if cl_fmt.get("timeseries_message"):
                closed_loop_timeseries = f"{cl_fmt['timeseries_message']}（{cl_fmt.get('timeseries_period', '')}）"
            closed_loop_snapshots = cl_fmt.get("snapshot_count", 0)
            closed_loop_dim_changes = cl_fmt.get("dim_changes", [])
        except Exception:
            pass

        template = Template(self.TEMPLATE)
        html = template.render(
            company_name=self.result.company_name,
            report_date=self.result.report_date,
            overall_score=f"{self.result.overall_score:.2f}",
            overall_level=self.result.overall_level.value,
            overall_level_css=overall_level_css_map.get(self.result.overall_level.value, "low"),
            overall_level_desc=level_desc_map.get(self.result.overall_level.value, ""),
            dim_count=len(self.result.dimensions),
            key_risk_count=len(key_risks),
            dimensions=dims_for_template,
            key_risks=key_risks,
            raw_data_items=raw_data_items,
            chart_dim_names=json.dumps(chart_names, ensure_ascii=False),
            chart_dim_scores=json.dumps(chart_scores),
            chart_dim_colors=json.dumps(chart_colors, ensure_ascii=False),
            executive_summary=executive_summary,
            cross_risk_alerts=cross_risk_alerts,
            erm_maturity_level=erm_maturity_level,
            erm_maturity_name=erm_maturity_name,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            standards_footer=standards_footer,
            action_items=action_items,
            action_total=action_total,
            action_p0=action_p0,
            deep_summary=deep_summary,
            mc_interpretation=mc_interpretation,
            tld_summary=tld_summary,
            playbook_note=playbook_note,
            bayes_interpretation=bayes_interpretation,
            corr_count=corr_count,
            closed_loop_show=closed_loop_show,
            closed_loop_alert_summary=closed_loop_alert_summary,
            closed_loop_alert_items=closed_loop_alert_items,
            closed_loop_verification=closed_loop_verification,
            closed_loop_delta=closed_loop_delta,
            closed_loop_trend=closed_loop_trend,
            closed_loop_completion=closed_loop_completion,
            closed_loop_actions_done=closed_loop_actions_done,
            closed_loop_actions_total=closed_loop_actions_total,
            closed_loop_recommendation=closed_loop_recommendation,
            closed_loop_timeseries=closed_loop_timeseries,
            closed_loop_snapshots=closed_loop_snapshots,
            closed_loop_dim_changes=closed_loop_dim_changes,
        )

        if self.output_path is None:
            output_dir = r"D:\_Work\02_Documents\信息搜集表格"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = os.path.join(output_dir, f"企业风险评估报告_{self.result.company_name}_{timestamp}.html")

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"OK HTML 风险评估报告已生成: {self.output_path}")
        return self.output_path
