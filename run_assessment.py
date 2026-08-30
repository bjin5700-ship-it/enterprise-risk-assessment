# -*- coding: utf-8 -*-
"""
企业风险管理系统 - 主入口
自动解析Excel数据 → 风险评分 → 生成多格式评估报告 + 解决方案报告
支持格式：Word (.docx), PDF, HTML, Markdown (.md)
"""

import os
import sys
import argparse
from datetime import datetime

from risk_engine import run_assessment, extract_all_data
from solution_generator import generate_solution_report

from report_word import WordReportGenerator
from report_html import HTMLReportGenerator
from report_pdf import PDFReportGenerator
from report_markdown import MarkdownReportGenerator


REPORT_FORMATS = {
    "docx": "Word (.docx) 格式 - 适合编辑和打印",
    "pdf": "PDF 格式 - 适合正式交付和分发",
    "html": "HTML 格式 - 带交互式图表的网页报告",
    "md": "Markdown 格式 - 适合版本控制和在线预览",
    "all": "全部格式（同时生成 docx + pdf + html + md）",
}


def print_banner():
    print("=" * 65)
    print("  企业风险管理系统 (Enterprise Risk Assessment System)")
    print("  基于风险管理信息搜集表 → 自动生成评估报告 + 解决方案")
    print("=" * 65)


def print_summary(result):
    """在控制台打印评估摘要"""
    print(f"\n{'─' * 55}")
    print(f"  企业名称: {result.company_name}")
    print(f"  综合评分: {result.overall_score:.2f} / 4.00")
    print(f"  风险等级: {result.overall_level.value}")
    print(f"  评估日期: {result.report_date}")
    print(f"{'─' * 55}")
    print(f"  {'维度':<20} {'评分':<8} {'等级':<10} {'关键风险数':<10}")
    print(f"{'─' * 55}")

    sorted_dims = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)
    for dim in sorted_dims:
        print(f"  {dim.name:<20} {dim.score:<8.2f} {dim.level.value:<10} {len(dim.key_risks):<10}")

    print(f"{'─' * 55}")

    all_key_risks = []
    for dim in sorted_dims:
        for kr in dim.key_risks:
            all_key_risks.append((dim.name, kr))

    if all_key_risks:
        print(f"\n  关键风险点 ({len(all_key_risks)}项):")
        for i, (dim_name, kr) in enumerate(all_key_risks, 1):
            print(f"    {i}. [{dim_name}] {kr}")

    print()


def _make_output_path(output_dir: str, prefix: str, company_name: str, ext: str = ".docx") -> str:
    """生成带时间戳的输出文件路径"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in company_name if c.isalnum() or c in " _-()（）").strip()
    filename = f"{prefix}_{safe_name}_{timestamp}{ext}"
    return os.path.join(output_dir, filename)


def generate_report(result, format_type: str, output_dir: str) -> list:
    """根据指定格式生成报告，返回 (格式名, 路径) 列表"""
    generators = []

    if format_type in ("docx", "all"):
        def gen_docx():
            path = _make_output_path(output_dir, "企业风险评估报告", result.company_name, ".docx")
            return WordReportGenerator(result, output_path=path).generate()
        generators.append(("Word (.docx)", gen_docx))
    if format_type in ("pdf", "all"):
        def gen_pdf():
            path = _make_output_path(output_dir, "企业风险评估报告", result.company_name, ".pdf")
            return PDFReportGenerator(result, output_path=path).generate()
        generators.append(("PDF", gen_pdf))
    if format_type in ("html", "all"):
        def gen_html():
            path = _make_output_path(output_dir, "企业风险评估报告", result.company_name, ".html")
            return HTMLReportGenerator(result, output_path=path).generate()
        generators.append(("HTML", gen_html))
    if format_type in ("md", "all"):
        def gen_md():
            path = _make_output_path(output_dir, "企业风险评估报告", result.company_name, ".md")
            return MarkdownReportGenerator(result, output_path=path).generate()
        generators.append(("Markdown", gen_md))

    outputs = []
    for name, gen_func in generators:
        print(f"  [DOC] 正在生成 {name} 格式报告...")
        path = gen_func()
        outputs.append((name, path))

    return outputs


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="企业风险管理系统")
    parser.add_argument("input", nargs="?", help="Excel表格路径（企业风险管理信息搜集表）")
    parser.add_argument("--name", "-n", help="企业名称（可选，默认从表格读取）")
    parser.add_argument("--report-only", "-r", action="store_true", help="仅生成评估报告")
    parser.add_argument("--solution-only", "-s", action="store_true", help="仅生成解决方案报告")
    parser.add_argument("--output-dir", "-o", help="输出目录（默认同目录）")
    parser.add_argument(
        "--format", "-f", choices=list(REPORT_FORMATS.keys()), default="docx",
        help=f"报告输出格式（默认: docx）\n"
             f"  docx - Word格式，适合编辑和打印\n"
             f"  pdf  - PDF格式，适合正式交付\n"
             f"  html - HTML格式，带交互式图表\n"
             f"  md   - Markdown格式，适合版本控制\n"
             f"  all  - 同时生成全部格式",
    )

    args = parser.parse_args()

    # 如果没有传入文件路径，查找最新的Excel文件
    if not args.input:
        search_dir = r"D:\_Work\02_Documents\信息搜集表格"
        xlsx_files = [f for f in os.listdir(search_dir) if f.endswith(".xlsx") and "企业风险" in f]
        if not xlsx_files:
            print("[X] 未找到企业风险管理信息搜集表，请指定文件路径")
            sys.exit(1)
        xlsx_files.sort(reverse=True)
        args.input = os.path.join(search_dir, xlsx_files[0])
        print(f"[DIR] 自动选择最新文件: {args.input}")

    if not os.path.exists(args.input):
        print(f"[X] 文件不存在: {args.input}")
        sys.exit(1)

    print(f"\n[DIR] 输入文件: {args.input}")
    print(f"[SCAN] 正在解析数据并评估风险...\n")

    # 运行风险评估
    result = run_assessment(args.input, args.name or "")

    # 打印摘要
    print_summary(result)

    # 生成报告
    gen_report = not args.solution_only
    gen_solution = not args.report_only

    output_dir = args.output_dir or os.path.dirname(args.input)

    all_reports = []

    if gen_report:
        print(f"\n[DOC] 正在生成 {REPORT_FORMATS.get(args.format, '')} 格式评估报告...")
        report_outputs = generate_report(result, args.format, output_dir)
        all_reports.extend(report_outputs)

    if gen_solution:
        print("\n[DOC] 正在生成解决方案报告...")
        solution_path = _make_output_path(output_dir, "企业风险解决方案报告", result.company_name)
        solution_path = generate_solution_report(result, output_path=solution_path)
        all_reports.append(("解决方案报告", solution_path))

    print(f"\n{'=' * 65}")
    print(f"  [OK] 全部完成！")
    for name, path in all_reports:
        print(f"     [DOC] {name}: {path}")
    print(f"{'=' * 65}")
    print(f"  提示：可将此流程集成到定时任务中，实现定期自动评估")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
