# -*- coding: utf-8 -*-
"""
PDF 风险报告生成器 - PDF Report Generator
使用 reportlab 生成专业的 PDF 风险评估报告
"""

import os
from datetime import datetime
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

from report_base import BaseReportGenerator
from risk_engine import AssessmentResult, RiskLevel


# ── 尝试注册中文字体 ──
_FONT_NAME = "Helvetica"
_FONT_NAME_BOLD = "Helvetica-Bold"

# 查找系统中文字体
_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\msyh.ttc", "MicrosoftYaHei", "微软雅黑"),
    ("C:\\Windows\\Fonts\\msyhbd.ttc", "MicrosoftYaHeiBold", "微软雅黑粗体"),
    ("C:\\Windows\\Fonts\\simsun.ttc", "SimSun", "宋体"),
    ("C:\\Windows\\Fonts\\simhei.ttf", "SimHei", "黑体"),
]

try:
    for font_path, font_name, _ in _FONT_CANDIDATES:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            _FONT_NAME = font_name
            _FONT_NAME_BOLD = font_name
            break
except Exception:
    pass


class PDFReportGenerator(BaseReportGenerator):
    """PDF 格式风险评估报告生成器"""

    # 颜色方案
    PRIMARY = HexColor("#1a3a5c")
    SECONDARY = HexColor("#2d6a9f")
    RED = HexColor("#C00000")
    ORANGE = HexColor("#FF6B6B")
    YELLOW = HexColor("#FFD93D")
    GREEN = HexColor("#6BCB77")
    GRAY = HexColor("#808080")
    LIGHT_GRAY = HexColor("#f0f0f0")

    def _style(self):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            "CoverTitle", fontName=_FONT_NAME_BOLD, fontSize=26,
            textColor=self.PRIMARY, alignment=TA_CENTER, spaceAfter=10,
        ))
        styles.add(ParagraphStyle(
            "CoverCompany", fontName=_FONT_NAME_BOLD, fontSize=18,
            textColor=self.SECONDARY, alignment=TA_CENTER, spaceAfter=30,
        ))
        styles.add(ParagraphStyle(
            "CoverMeta", fontName=_FONT_NAME, fontSize=11,
            textColor=HexColor("#666666"), alignment=TA_CENTER, spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            "H1", fontName=_FONT_NAME_BOLD, fontSize=16,
            textColor=self.PRIMARY, spaceBefore=20, spaceAfter=12,
            borderWidth=0, borderPadding=0,
        ))
        styles.add(ParagraphStyle(
            "H2", fontName=_FONT_NAME_BOLD, fontSize=13,
            textColor=self.SECONDARY, spaceBefore=14, spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            "Body", fontName=_FONT_NAME, fontSize=10,
            leading=16, alignment=TA_JUSTIFY, spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            "TableCell", fontName=_FONT_NAME, fontSize=9, leading=13,
        ))
        styles.add(ParagraphStyle(
            "TableHeader", fontName=_FONT_NAME_BOLD, fontSize=9,
            textColor=white, leading=13,
        ))
        return styles

    def _risk_color(self, level_value: str):
        return {
            "低风险": self.GREEN,
            "中等风险": self.YELLOW,
            "高风险": self.ORANGE,
            "极高风险": self.RED,
        }.get(level_value, self.GRAY)

    def _header_table(self, text: str, level=1):
        """返回带左边框的标题行"""
        s = self._style()
        style = s["H1"] if level == 1 else s["H2"]
        color = self.PRIMARY if level == 1 else self.SECONDARY
        return Table(
            [[Paragraph(text, style)]],
            colWidths=[170*mm],
            style=TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("LINEBEFORE", (0, 0), (-1, -1), 3, color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        )

    def _make_table(self, headers, rows, col_widths=None, header_bg=None):
        """通用表格构建"""
        s = self._style()
        if header_bg is None:
            header_bg = self.PRIMARY

        data = [[Paragraph(h, s["TableHeader"]) for h in headers]]
        for row in rows:
            data.append([Paragraph(str(c), s["TableCell"]) for c in row])

        if col_widths is None:
            col_widths = [170*mm / len(headers)] * len(headers)

        t = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        # 给风险等级行上色
        for i, row in enumerate(rows):
            if len(row) >= 3 and isinstance(row[2], str):
                level_color = self._risk_color(row[2])
                style_cmds.append(("BACKGROUND", (2, i+1), (2, i+1), level_color))

        t.setStyle(TableStyle(style_cmds))
        return t

    def generate(self) -> str:
        if self.output_path is None:
            output_dir = r"D:\_Work\02_Documents\信息搜集表格"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = os.path.join(
                output_dir, f"企业风险评估报告_{self.result.company_name}_{timestamp}.pdf"
            )

        doc = SimpleDocTemplate(
            self.output_path, pagesize=A4,
            topMargin=25*mm, bottomMargin=20*mm,
            leftMargin=22*mm, rightMargin=22*mm,
        )

        s = self._style()
        story = []
        sorted_dims = self._sorted_dimensions()
        key_risks = self._all_key_risks()

        # ── 封面 ──
        story.append(Spacer(1, 80*mm))
        story.append(Paragraph("企业风险评估报告", s["CoverTitle"]))
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph(self.result.company_name, s["CoverCompany"]))
        story.append(Spacer(1, 20*mm))
        story.append(Paragraph(f"报告日期：{self.result.report_date}", s["CoverMeta"]))
        story.append(Paragraph("本报告基于企业风险管理信息搜集表自动生成", s["CoverMeta"]))
        story.append(Paragraph("仅供内部管理参考，请勿外传", s["CoverMeta"]))
        story.append(PageBreak())

        # ── 一、评估概要 ──
        story.append(self._header_table("一、评估概要"))
        story.append(Paragraph(
            f"本报告对 <b>{self.result.company_name}</b> 的风险状况进行全面评估。"
            "评估基于企业风险管理信息搜集表所填数据，从财务、负债、行业市场、法律合规、税务、"
            "公司治理、供应链、技术信息、人力资源、ESG等17个维度进行系统性分析。",
            s["Body"],
        ))
        story.append(Spacer(1, 4*mm))

        # 摘要信息
        summary_data = [
            ["综合风险评分", f"{self.result.overall_score:.2f} / 4.00"],
            ["风险等级", self.result.overall_level.value],
            ["评估维度", f"{len(self.result.dimensions)} 个维度"],
            ["关键风险点", f"{len(key_risks)} 项待处理"],
        ]
        summary_table = Table(
            [[Paragraph(f"<b>{r[0]}</b>", s["TableCell"]),
              Paragraph(r[1], s["TableCell"])] for r in summary_data],
            colWidths=[50*mm, 50*mm],
        )
        summary_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#eeeeee")),
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#e8f0f8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 6*mm))

        # 执行摘要
        try:
            from risk_analytics import enrich_assessment
            basic = (self.result.all_raw_data or {}).get("企业基本信息", {})
            analytics = enrich_assessment(self.result, basic_info=basic)
            story.append(self._header_table("执行摘要（Executive Summary）"))
            for line in analytics.get("executive_summary", []):
                story.append(Paragraph(f"• {line}", s["Body"]))
            mat = analytics.get("erm_maturity", {})
            conf = analytics.get("confidence", {})
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                f"ERM 成熟度：{mat.get('level', '—')}/5（{mat.get('name', '')}）；"
                f"评估置信度：{conf.get('score', '—')}%（{conf.get('level', '')}）。"
                f" {analytics.get('standards_footer', '')}",
                s["Body"],
            ))
            cross = analytics.get("cross_risk_alerts", [])
            if cross:
                story.append(Paragraph(
                    "交叉风险提示：" + "；".join(c["message"] for c in cross[:3]),
                    ParagraphStyle("CrossRisk", fontName=_FONT_NAME, fontSize=10,
                                   textColor=self.RED, spaceAfter=6),
                ))
            story.append(Spacer(1, 4*mm))
        except Exception:
            pass

        # ── 二、各维度风险评分 ──
        story.append(self._header_table("二、各维度风险评分"))
        story.append(Paragraph("以下按风险评分从高到低排序：", s["Body"]))
        story.append(Spacer(1, 3*mm))

        dim_headers = ["风险维度", "评分", "等级", "建议行动"]
        dim_rows = []
        for dim in sorted_dims:
            dim_rows.append([
                dim.name,
                f"{dim.score:.2f}",
                dim.level.value,
                self._suggest_action(dim),
            ])
        dim_table = self._make_table(
            dim_headers, dim_rows,
            col_widths=[50*mm, 20*mm, 30*mm, 70*mm],
        )
        story.append(dim_table)
        story.append(PageBreak())

        # ── 三、各维度详细分析 ──
        story.append(self._header_table("三、各维度详细分析"))
        story.append(Spacer(1, 3*mm))

        for dim in sorted_dims:
            color = self._risk_color(dim.level.value)
            dim_title = f"<font color='{color.hexval()}'>{dim.name}</font>"
            dim_header = Table(
                [[Paragraph(
                    f"<b>{dim.name}</b>　评分：{dim.score:.2f}　等级：{dim.level.value}",
                    ParagraphStyle("DimHeader", fontName=_FONT_NAME_BOLD, fontSize=11,
                                   textColor=color, spaceBefore=6, spaceAfter=4),
                )]],
                colWidths=[170*mm],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f8f9fa")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BOX", (0, 0), (-1, -1), 0.5, color),
                ]),
            )
            story.append(dim_header)
            story.append(Spacer(1, 2*mm))

            if dim.findings:
                for finding in dim.findings:
                    story.append(Paragraph(f"• {finding}", s["Body"]))
            else:
                story.append(Paragraph("（无详细发现项）", s["Body"]))

            if dim.key_risks:
                story.append(Spacer(1, 2*mm))
                risk_text = "；".join(dim.key_risks)
                story.append(Paragraph(
                    f"<b>关键风险：</b>{risk_text}",
                    ParagraphStyle("KeyRisk", fontName=_FONT_NAME, fontSize=10,
                                   textColor=self.RED, spaceAfter=6),
                ))

            story.append(Spacer(1, 3*mm))

        story.append(PageBreak())

        # ── 四、核心风险总结 ──
        story.append(self._header_table("四、核心风险总结"))
        if key_risks:
            story.append(Paragraph(f"共识别 <b>{len(key_risks)}</b> 项关键风险点：", s["Body"]))
            story.append(Spacer(1, 3*mm))

            kr_headers = ["序号", "所属维度", "关键风险点"]
            kr_rows = []
            for i, (dim_name, kr) in enumerate(key_risks, 1):
                kr_rows.append([str(i), dim_name, kr])

            kr_table = self._make_table(
                kr_headers, kr_rows,
                col_widths=[15*mm, 40*mm, 115*mm],
                header_bg=self.RED,
            )
            story.append(kr_table)
        else:
            story.append(Paragraph("未识别出关键风险点，整体风险可控。", s["Body"]))

        story.append(PageBreak())

        # ── 五、深度量化与治理分析 ──
        try:
            from risk_deep_analysis import run_deep_analysis
            from risk_analytics import compute_confidence
            basic = (self.result.all_raw_data or {}).get("企业基本信息", {})
            conf = compute_confidence(getattr(self.result, "form_stats", None)).get("score", 50)
            deep = run_deep_analysis(self.result, basic, confidence_pct=conf)
            if deep.get("summary") or deep.get("monte_carlo") or deep.get("three_lines_of_defense"):
                story.append(self._header_table("五、深度量化与治理分析"))
                if deep.get("summary"):
                    story.append(Paragraph(deep["summary"], s["Body"]))
                mc = deep.get("monte_carlo")
                if mc:
                    story.append(Paragraph(f"<b>蒙特卡洛：</b>{mc.get('interpretation', '')}", s["Body"]))
                tld = deep.get("three_lines_of_defense")
                if tld:
                    story.append(Paragraph(
                        f"<b>三道防线：</b>综合成熟度 {tld.get('overall_maturity')}，最弱防线 {tld.get('weakest_line')}",
                        s["Body"],
                    ))
                pb = deep.get("industry_playbook")
                if pb and pb.get("tailored_note"):
                    story.append(Paragraph(f"<b>行业路径：</b>{pb['tailored_note']}", s["Body"]))
                story.append(PageBreak())
        except Exception:
            pass

        # ── 六、整改行动路线图 ──
        try:
            from action_planner import build_action_plans
            plans = build_action_plans(self.result)
            if plans.get("action_items"):
                story.append(self._header_table("六、整改行动路线图"))
                story.append(Paragraph(
                    f"共 {plans.get('total_actions', 0)} 项可执行行动，P0 立即启动 {plans.get('p0_count', 0)} 项。"
                    "以下按 ISO 31000 风险处理流程编制。",
                    s["Body"],
                ))
                story.append(Spacer(1, 3*mm))
                act_headers = ["编号", "优先级", "维度", "行动", "责任人", "周期"]
                act_rows = []
                for a in plans.get("action_items", [])[:15]:
                    act_rows.append([
                        a.get("id", ""),
                        a.get("priority", ""),
                        a.get("dimension", ""),
                        a.get("title", "")[:30],
                        a.get("owner", ""),
                        str(a.get("timeline_days", "")),
                    ])
                story.append(self._make_table(
                    act_headers, act_rows,
                    col_widths=[18*mm, 15*mm, 30*mm, 55*mm, 30*mm, 22*mm],
                ))
                story.append(PageBreak())
        except Exception:
            pass

        # ── 七、数据闭环与 KRI 告警 ──
        try:
            from risk_closed_loop import build_export_closed_loop
            pkg = build_export_closed_loop(self.result)
            cl = pkg.get("closed_loop") or {}
            alerts = pkg.get("alerts") or {}
            v = cl.get("remediation_verification") or {}
            ts = cl.get("timeseries") or {}
            if cl or alerts.get("alerts"):
                story.append(self._header_table("七、数据闭环与 KRI 告警"))
                if alerts.get("alerts"):
                    story.append(Paragraph(f"<b>告警摘要：</b>{alerts.get('summary', '')}", s["Body"]))
                    for a in alerts.get("alerts", [])[:8]:
                        story.append(Paragraph(
                            f"• [{a.get('severity', '').upper()}] {a.get('title')} — {a.get('message')}",
                            s["Body"],
                        ))
                if v:
                    story.append(Paragraph(
                        f"<b>整改验证：</b>{v.get('verification_label', '—')}；"
                        f"评分变化 {v.get('overall_delta', '—')}；"
                        f"行动完成率 {v.get('actions_tracked', {}).get('completion_pct', 0)}%。",
                        s["Body"],
                    ))
                    if v.get("recommendation"):
                        story.append(Paragraph(v["recommendation"], s["Body"]))
                if ts.get("has_trend"):
                    story.append(Paragraph(f"<b>KPI 时序：</b>{ts.get('message', '')}（{ts.get('period', '')}）", s["Body"]))
                if cl.get("summary"):
                    story.append(Paragraph(cl["summary"], s["Body"]))
                story.append(PageBreak())
        except Exception:
            pass

        # ── 附录：原始数据摘要 ──
        story.append(self._header_table("附录：原始数据摘要"))
        story.append(Paragraph("以下为各Sheet中提取的关键数据字段摘要：", s["Body"]))
        story.append(Spacer(1, 3*mm))

        for sheet_name, data in self.result.all_raw_data.items():
            if not data:
                continue
            items = [(k, v) for k, v in data.items() if v is not None and str(v).strip()]
            if not items:
                continue

            story.append(Paragraph(f"<b>{sheet_name}</b>", s["H2"]))
            appendix_headers = ["字段", "填写内容"]
            appendix_rows = [(str(k), str(v)) for k, v in items]
            appendix_table = self._make_table(
                appendix_headers, appendix_rows,
                col_widths=[60*mm, 110*mm],
                header_bg=self.GRAY,
            )
            story.append(appendix_table)
            story.append(Spacer(1, 4*mm))

        # ── 构建PDF ──
        doc.build(story)
        print(f"OK PDF 风险评估报告已生成: {self.output_path}")
        return self.output_path
