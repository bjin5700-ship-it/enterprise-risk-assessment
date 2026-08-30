# -*- coding: utf-8 -*-
"""
个人/高净值家庭风险评估问卷生成器
Personal / High-Net-Worth Family Risk Assessment Form Generator

版本: 1.0.0
架构: 模块化多Sheet设计
模块数: 15个Sheet（12个核心模块 + 3个特色模块）
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import datetime
import os

# ── 样式常量 ──
TITLE_FONT = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
SECTION_FONT = Font(name="微软雅黑", size=11, bold=True, color="1F4E79")
FIELD_FONT = Font(name="微软雅黑", size=10)
NOTE_FONT = Font(name="微软雅黑", size=9, italic=True, color="666666")

TITLE_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FILL = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
SUB_HEADER_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
REQUIRED_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
RISK_HIGH_FILL = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
RISK_MED_FILL = PatternFill(start_color="FFD93D", end_color="FFD93D", fill_type="solid")
RISK_LOW_FILL = PatternFill(start_color="6BCB77", end_color="6BCB77", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style="thin", color="B4C6E7"),
    right=Side(style="thin", color="B4C6E7"),
    top=Side(style="thin", color="B4C6E7"),
    bottom=Side(style="thin", color="B4C6E7"),
)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)

def create_workbook():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    return wb


def write_field_table(ws, fields, start_row=4):
    """Write a structured field table to the worksheet."""
    col_widths = [5, 35, 18, 12, 45, 45, 45]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    headers = ["序号", "字段名称", "字段类型", "是否关键风险", "选项/说明", "填写内容", "备注"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER

    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)

    row = start_row + 1
    seq = 1
    for field in fields:
        if field.get("is_group"):
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
            cell = ws.cell(row=row, column=1, value=field["name"])
            cell.font = SECTION_FONT
            cell.fill = SUB_HEADER_FILL
            cell.alignment = LEFT_ALIGN
            cell.border = THIN_BORDER
            row += 1
            continue

        ws.cell(row=row, column=1, value=seq).font = FIELD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER

        cell_name = ws.cell(row=row, column=2, value=field["name"])
        cell_name.font = FIELD_FONT
        cell_name.alignment = LEFT_ALIGN
        cell_name.border = THIN_BORDER
        if field.get("key_risk"):
            cell_name.fill = REQUIRED_FILL

        field_type = field.get("type", "文本")
        ws.cell(row=row, column=3, value=field_type).font = FIELD_FONT
        ws.cell(row=row, column=3).alignment = CENTER_ALIGN
        ws.cell(row=row, column=3).border = THIN_BORDER

        is_key = "是" if field.get("key_risk") else ""
        ws.cell(row=row, column=4, value=is_key).font = FIELD_FONT
        ws.cell(row=row, column=4).alignment = CENTER_ALIGN
        ws.cell(row=row, column=4).border = THIN_BORDER

        note = field.get("note", "")
        choices = field.get("choices", [])
        if choices:
            option_text = " | ".join(choices)
        else:
            option_text = note

        ws.cell(row=row, column=5, value=option_text).font = NOTE_FONT
        ws.cell(row=row, column=5).alignment = LEFT_ALIGN
        ws.cell(row=row, column=5).border = THIN_BORDER

        cell_input = ws.cell(row=row, column=6)
        cell_input.font = FIELD_FONT
        cell_input.alignment = LEFT_ALIGN
        cell_input.border = THIN_BORDER

        if choices:
            dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(cell_input)

        ws.cell(row=row, column=7, value=note if choices else "").font = NOTE_FONT
        ws.cell(row=row, column=7).alignment = LEFT_ALIGN
        ws.cell(row=row, column=7).border = THIN_BORDER

        row += 1
        seq += 1
# ============================================================
# Sheet 1: 个人基本信息
# ============================================================
def create_basic_info_sheet(wb):
    ws = wb.create_sheet("个人基本信息", 0)
    ws.sheet_properties.tabColor = "1F4E79"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "一、个人基本信息"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = TITLE_FILL
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：收集个人基础信息，作为后续风险评估的基础数据。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"name": "姓名", "type": "文本", "key_risk": True},
        {"name": "性别", "type": "dropdown", "choices": ["男", "女"]},
        {"name": "年龄", "type": "数值", "key_risk": True},
        {"name": "出生日期", "type": "日期"},
        {"name": "婚姻状况", "type": "dropdown", "choices": ["未婚", "已婚无子女", "已婚有子女", "离异", "丧偶"], "key_risk": True},
        {"name": "国籍", "type": "文本"},
        {"name": "常住地", "type": "文本", "key_risk": True},
        {"name": "户籍", "type": "文本"},
        {"name": "身份证件类型", "type": "dropdown", "choices": ["居民身份证", "护照", "港澳台居民居住证", "其他"]},
        {"name": "证件号码", "type": "文本", "key_risk": True},
        {"name": "手机号码", "type": "文本"},
        {"name": "电子邮箱", "type": "文本"},
        {"name": "最高学历", "type": "dropdown", "choices": ["高中及以下", "大专", "本科", "硕士", "博士"]},
        {"name": "专业领域", "type": "文本"},
        {"name": "身高(cm)", "type": "数值"},
        {"name": "体重(kg)", "type": "数值"},
        {"name": "血型", "type": "dropdown", "choices": ["A型", "B型", "O型", "AB型", "未知"]},
        {"name": "语言能力", "type": "文本", "note": "如：普通话、英语(流利)、粤语等"},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 2: 家庭情况
# ============================================================
def create_family_sheet(wb):
    ws = wb.create_sheet("家庭情况", 1)
    ws.sheet_properties.tabColor = "00B0F0"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "二、家庭情况"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='00B0F0', end_color='00B0F0', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：家庭是个人风险的重要来源，评估家庭结构、资产、负债及稳定性。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "配偶信息"},
        {"name": "配偶姓名", "type": "文本"},
        {"name": "配偶年龄", "type": "数值"},
        {"name": "配偶职业", "type": "文本"},
        {"name": "配偶收入(万元/年)", "type": "数值"},
        {"name": "配偶健康状况", "type": "dropdown", "choices": ["良好", "一般", "有慢性病", "较差"], "key_risk": True},

        {"is_group": True, "name": "子女信息"},
        {"name": "子女数量", "type": "数值", "key_risk": True},
        {"name": "子女年龄分布", "type": "文本", "note": "如：3岁、8岁"},
        {"name": "子女教育阶段", "type": "dropdown", "choices": ["学龄前", "小学", "中学", "大学", "已工作"]},
        {"name": "子女健康状况", "type": "dropdown", "choices": ["良好", "一般", "有特殊需求"], "key_risk": True},
        {"name": "子女年教育支出(万元)", "type": "数值"},

        {"is_group": True, "name": "父母信息"},
        {"name": "父亲年龄", "type": "数值"},
        {"name": "母亲年龄", "type": "数值"},
        {"name": "父亲健康状况", "type": "dropdown", "choices": ["良好", "一般", "有慢性病", "需长期护理"], "key_risk": True},
        {"name": "母亲健康状况", "type": "dropdown", "choices": ["良好", "一般", "有慢性病", "需长期护理"], "key_risk": True},
        {"name": "是否赡养老人", "type": "dropdown", "choices": ["是", "否"]},
        {"name": "年赡养支出(万元)", "type": "数值"},

        {"is_group": True, "name": "家庭整体"},
        {"name": "家庭年总收入(万元)", "type": "数值", "key_risk": True},
        {"name": "家庭年总支出(万元)", "type": "数值", "key_risk": True},
        {"name": "家庭总资产(万元)", "type": "数值", "key_risk": True},
        {"name": "家庭总负债(万元)", "type": "数值", "key_risk": True},
        {"name": "家庭关系稳定性", "type": "dropdown", "choices": ["稳定", "一般", "不稳定"], "key_risk": True},
        {"name": "家庭应急资金(万元)", "type": "数值", "key_risk": True},
        {"name": "应急资金可覆盖月数", "type": "数值", "key_risk": True},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 3: 职业风险
# ============================================================
def create_career_risk_sheet(wb):
    ws = wb.create_sheet("职业风险", 2)
    ws.sheet_properties.tabColor = "ED7D31"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "三、职业风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='ED7D31', end_color='ED7D31', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估职业稳定性、收入可持续性及职业相关风险因素。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"name": "工作单位", "type": "文本"},
        {"name": "行业", "type": "dropdown", "choices": ["金融保险", "信息技术", "制造业", "医疗健康", "教育", "房地产建筑", "批发零售", "交通运输", "能源环保", "文化传媒", "政府/公共事业", "自由职业", "其他"], "key_risk": True},
        {"name": "岗位/职位", "type": "文本"},
        {"name": "工龄(年)", "type": "数值"},
        {"name": "就业状态", "type": "dropdown", "choices": ["全职", "兼职", "自由职业", "创业", "退休", "待业"], "key_risk": True},
        {"name": "是否创业", "type": "dropdown", "choices": ["是", "否"]},
        {"name": "是否公务员/事业单位", "type": "dropdown", "choices": ["是", "否"]},
        {"name": "是否高危职业", "type": "dropdown", "choices": ["是", "否"], "key_risk": True},
        {"name": "是否经常出差", "type": "dropdown", "choices": ["从不", "偶尔(月1-3天)", "经常(月>10天)", "长期驻外"], "key_risk": True},
        {"name": "是否境外工作", "type": "dropdown", "choices": ["是", "否"], "key_risk": True},
        {"name": "是否需夜班/倒班", "type": "dropdown", "choices": ["从不", "偶尔", "经常"]},
        {"name": "工作压力自评", "type": "dropdown", "choices": ["很小", "一般", "较大", "极大"], "key_risk": True},
        {"name": "晋升空间", "type": "dropdown", "choices": ["大", "一般", "小", "无"]},
        {"name": "收入稳定性", "type": "dropdown", "choices": ["非常稳定", "较稳定", "波动较大", "不稳定"], "key_risk": True},
        {"name": "失业风险评估", "type": "dropdown", "choices": ["低", "中", "高"], "key_risk": True},
    ]

    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 4: 收入与现金流
# ============================================================
def create_income_cashflow_sheet(wb):
    ws = wb.create_sheet("收入与现金流", 3)
    ws.sheet_properties.tabColor = "70AD47"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "四、收入与现金流"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='70AD47', end_color='70AD47', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估个人/家庭的收入来源、稳定性及现金流健康状况。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "收入来源"},
        {"name": "工资年收入(万元)", "type": "数值", "key_risk": True},
        {"name": "奖金/绩效(万元/年)", "type": "数值"},
        {"name": "分红收入(万元/年)", "type": "数值"},
        {"name": "房租收入(万元/年)", "type": "数值"},
        {"name": "投资收益(万元/年)", "type": "数值"},
        {"name": "兼职收入(万元/年)", "type": "数值"},
        {"name": "其他收入(万元/年)", "type": "数值"},
        {"name": "家庭月均收入(万元)", "type": "数值", "key_risk": True},
        {"name": "家庭年收入(万元)", "type": "数值", "key_risk": True},
        {"name": "收入增长率(近3年平均%)", "type": "数值"},
        {"name": "收入集中度", "type": "dropdown", "choices": ["单一来源", "双来源", "多元来源"], "key_risk": True, "note": "收入来源是否分散"},

        {"is_group": True, "name": "支出情况"},
        {"name": "每月固定支出(万元)", "type": "数值", "key_risk": True},
        {"name": "其中房贷月供(万元)", "type": "数值"},
        {"name": "其中生活开销(万元)", "type": "数值"},
        {"name": "其中教育支出(万元)", "type": "数值"},
        {"name": "其中保险保费(万元)", "type": "数值"},
        {"name": "收支平衡情况", "type": "dropdown", "choices": ["结余较多(>30%)", "略有结余(10-30%)", "基本平衡", "入不敷出"], "key_risk": True},
        {"name": "月均可支配收入(万元)", "type": "数值", "key_risk": True},
        {"name": "应急储备可覆盖月数", "type": "数值", "key_risk": True, "note": "无收入情况下可维持月数"},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 5: 资产情况
# ============================================================
def create_asset_sheet(wb):
    ws = wb.create_sheet("资产情况", 4)
    ws.sheet_properties.tabColor = "FFC000"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "五、资产情况"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='FFC000', end_color='FFC000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：全面盘点个人/家庭各类资产，评估资产结构与流动性。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "不动产"},
        {"name": "自住房产数量", "type": "数值"},
        {"name": "自住房产估值(万元)", "type": "数值", "key_risk": True},
        {"name": "投资房产数量", "type": "数值"},
        {"name": "投资房产估值(万元)", "type": "数值", "key_risk": True},
        {"name": "商铺/写字楼估值(万元)", "type": "数值"},
        {"name": "土地估值(万元)", "type": "数值"},
        {"name": "境外房产估值(万元)", "type": "数值"},

        {"is_group": True, "name": "金融资产"},
        {"name": "银行存款(万元)", "type": "数值", "key_risk": True},
        {"name": "股票市值(万元)", "type": "数值", "key_risk": True},
        {"name": "基金市值(万元)", "type": "数值"},
        {"name": "债券市值(万元)", "type": "数值"},
        {"name": "黄金/贵金属(万元)", "type": "数值"},
        {"name": "数字资产/加密货币(万元)", "type": "数值", "key_risk": True},
        {"name": "其他金融资产(万元)", "type": "数值"},

        {"is_group": True, "name": "实物资产"},
        {"name": "汽车估值(万元)", "type": "数值"},
        {"name": "收藏品估值(万元)", "type": "数值", "note": "艺术品、古董、字画等"},
        {"name": "珠宝首饰估值(万元)", "type": "数值"},
        {"name": "其他贵重物品(万元)", "type": "数值"},

        {"is_group": True, "name": "企业资产"},
        {"name": "企业股权估值(万元)", "type": "数值", "key_risk": True},
        {"name": "是否控股", "type": "dropdown", "choices": ["是", "否", "不适用"]},
        {"name": "合伙企业权益(万元)", "type": "数值"},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 6: 负债风险
# ============================================================
def create_liability_sheet(wb):
    ws = wb.create_sheet("负债风险", 5)
    ws.sheet_properties.tabColor = "FF6B6B"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "六、负债风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='FF6B6B', end_color='FF6B6B', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估个人/家庭负债水平、还款压力及偿债能力。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "负债明细"},
        {"name": "房贷余额(万元)", "type": "数值", "key_risk": True},
        {"name": "房贷月供(万元)", "type": "数值"},
        {"name": "车贷余额(万元)", "type": "数值"},
        {"name": "消费贷余额(万元)", "type": "数值", "key_risk": True},
        {"name": "信用卡欠款(万元)", "type": "数值", "key_risk": True},
        {"name": "经营贷款余额(万元)", "type": "数值"},
        {"name": "民间借贷(万元)", "type": "数值", "key_risk": True},
        {"name": "担保责任金额(万元)", "type": "数值", "key_risk": True},

        {"is_group": True, "name": "偿债能力"},
        {"name": "总负债(万元)", "type": "数值", "key_risk": True},
        {"name": "年还款总额(万元)", "type": "数值", "key_risk": True},
        {"name": "年还款/年收入(%)", "type": "数值", "key_risk": True, "note": "DSR=年还款额/年收入"},
        {"name": "资产负债率(%)", "type": "数值", "key_risk": True, "note": "总负债/总资产"},
        {"name": "还款压力评估", "type": "dropdown", "choices": ["轻松", "正常", "有压力", "困难"], "key_risk": True},
    ]

    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 7: 健康风险
# ============================================================
def create_health_risk_sheet(wb):
    ws = wb.create_sheet("健康风险", 6)
    ws.sheet_properties.tabColor = "9966FF"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "七、健康风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='9966FF', end_color='9966FF', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：健康风险是个人风险评估中最重要的模块之一，全面评估身体状况及健康管理。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "身体指标"},
        {"name": "身高(cm)", "type": "数值"},
        {"name": "体重(kg)", "type": "数值"},
        {"name": "BMI", "type": "数值", "key_risk": True, "note": "BMI=体重(kg)/身高(m)²"},
        {"name": "收缩压(mmHg)", "type": "数值", "key_risk": True},
        {"name": "舒张压(mmHg)", "type": "数值", "key_risk": True},
        {"name": "空腹血糖(mmol/L)", "type": "数值", "key_risk": True},
        {"name": "总胆固醇(mmol/L)", "type": "数值", "key_risk": True},
        {"name": "甘油三酯(mmol/L)", "type": "数值"},
        {"name": "肝功能是否正常", "type": "dropdown", "choices": ["正常", "轻度异常", "明显异常", "未检查"]},
        {"name": "肾功能是否正常", "type": "dropdown", "choices": ["正常", "轻度异常", "明显异常", "未检查"]},
        {"name": "心电图结果", "type": "dropdown", "choices": ["正常", "大致正常", "异常", "未检查"]},
        {"name": "心脏彩超结果", "type": "dropdown", "choices": ["正常", "异常", "未检查"]},
        {"name": "肺功能结果", "type": "dropdown", "choices": ["正常", "异常", "未检查"]},
        {"name": "胃肠镜检查", "type": "dropdown", "choices": ["正常", "有息肉/已处理", "有病变/待处理", "未检查"]},

        {"is_group": True, "name": "病史与习惯"},
        {"name": "慢性疾病", "type": "text", "note": "如高血压、糖尿病、冠心病等"},
        {"name": "手术史", "type": "text", "note": "时间及手术名称"},
        {"name": "住院史", "type": "text", "note": "近5年住院记录"},
        {"name": "家族遗传病史", "type": "text", "key_risk": True, "note": "直系亲属重大疾病史"},
        {"name": "是否吸烟", "type": "dropdown", "choices": ["从不", "已戒烟", "偶尔", "每天<10支", "每天>10支"], "key_risk": True},
        {"name": "饮酒频率", "type": "dropdown", "choices": ["从不", "偶尔社交", "每周1-3次", "每天", "过量"], "key_risk": True},
        {"name": "睡眠质量", "type": "dropdown", "choices": ["很好", "一般", "较差", "严重失眠"], "key_risk": True},
        {"name": "运动频率", "type": "dropdown", "choices": ["几乎不运动", "每周1-2次", "每周3-4次", "每周5次以上"], "key_risk": True},
        {"name": "长期用药情况", "type": "text", "note": "药品名称及用量"},
        {"name": "定期体检频率", "type": "dropdown", "choices": ["每年1次", "每2年1次", "不定期", "几乎不体检"]},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 8: 保险保障情况
# ============================================================
def create_insurance_sheet(wb):
    ws = wb.create_sheet("保险保障", 7)
    ws.sheet_properties.tabColor = "00B050"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "八、保险保障情况"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='00B050', end_color='00B050', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估保险保障是否充足，识别保障缺口。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "人身保障"},
        {"name": "社会医疗保险", "type": "dropdown", "choices": ["城镇职工医保", "城乡居民医保", "无"], "key_risk": True},
        {"name": "商业医疗保险", "type": "dropdown", "choices": ["百万医疗", "中端医疗", "高端医疗", "无"], "key_risk": True},
        {"name": "重疾保险保额(万元)", "type": "数值", "key_risk": True},
        {"name": "寿险保额(万元)", "type": "数值", "key_risk": True},
        {"name": "意外险保额(万元)", "type": "数值"},
        {"name": "失能收入保险", "type": "dropdown", "choices": ["有", "无"]},

        {"is_group": True, "name": "财产保障"},
        {"name": "家财险", "type": "dropdown", "choices": ["有", "无"]},
        {"name": "车辆保险", "type": "dropdown", "choices": ["交强险仅", "交强+三者", "全险", "无车"]},
        {"name": "车险保额(万元)", "type": "数值"},

        {"is_group": True, "name": "保障分析"},
        {"name": "年缴总保费(万元)", "type": "数值", "key_risk": True},
        {"name": "保费占年收入(%)", "type": "数值", "key_risk": True},
        {"name": "保障期限是否充足", "type": "dropdown", "choices": ["充足", "基本充足", "不足"], "key_risk": True},
        {"name": "受益人设置是否合理", "type": "dropdown", "choices": ["合理", "需更新", "未指定"], "key_risk": True},
        {"name": "是否有理赔记录", "type": "dropdown", "choices": ["无", "有-已赔付", "有-拒赔", "理赔中"]},
        {"name": "保障缺口分析", "type": "text", "key_risk": True, "note": "综合评估保障不足领域"},
    ]

    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 9: 法律与信用风险
# ============================================================
def create_legal_credit_sheet(wb):
    ws = wb.create_sheet("法律与信用风险", 8)
    ws.sheet_properties.tabColor = "7030A0"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "九、法律与信用风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='7030A0', end_color='7030A0', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估个人信用状况、法律纠纷风险及合规情况。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "信用状况"},
        {"name": "个人征信状况", "type": "dropdown", "choices": ["良好", "有轻微逾期", "有严重逾期", "失信被执行人"], "key_risk": True},
        {"name": "信用评分(如有)", "type": "数值", "note": "如芝麻信用分/百行征信分"},
        {"name": "近2年逾期次数", "type": "数值", "key_risk": True},
        {"name": "信用卡使用率(%)", "type": "数值", "note": "已用额度/总额度"},
        {"name": "是否被列入黑名单", "type": "dropdown", "choices": ["否", "是"], "key_risk": True},

        {"is_group": True, "name": "法律风险"},
        {"name": "是否涉及诉讼", "type": "dropdown", "choices": ["无", "作为原告", "作为被告", "作为担保人"], "key_risk": True},
        {"name": "是否有执行记录", "type": "dropdown", "choices": ["无", "有"], "key_risk": True},
        {"name": "是否担任企业法定代表人", "type": "dropdown", "choices": ["是", "否"]},
        {"name": "担任企业数量", "type": "数值"},
        {"name": "是否有行政处罚记录", "type": "dropdown", "choices": ["无", "有"], "key_risk": True},
        {"name": "是否涉及合同纠纷", "type": "dropdown", "choices": ["无", "有"], "key_risk": True},
        {"name": "是否存在重大债务争议", "type": "dropdown", "choices": ["无", "有"], "key_risk": True},
        {"name": "是否有限制消费令", "type": "dropdown", "choices": ["无", "有"], "key_risk": True},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 10: 投资风险
# ============================================================
def create_investment_risk_sheet(wb):
    ws = wb.create_sheet("投资风险", 9)
    ws.sheet_properties.tabColor = "C00000"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十、投资风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='C00000', end_color='C00000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估投资组合风险、风险承受能力及投资行为合理性。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "投资偏好"},
        {"name": "风险承受能力", "type": "dropdown", "choices": ["保守型", "稳健型", "平衡型", "进取型", "激进型"], "key_risk": True},
        {"name": "投资目标", "type": "dropdown", "choices": ["资产保值", "稳健增值", "高收益增长", "投机套利"], "key_risk": True},
        {"name": "投资期限偏好", "type": "dropdown", "choices": ["短期(<1年)", "中期(1-3年)", "长期(3-10年)", "超长期(>10年)"]},
        {"name": "投资经验年限", "type": "dropdown", "choices": ["无经验", "<3年", "3-10年", ">10年"]},

        {"is_group": True, "name": "资产配置"},
        {"name": "股票配置比例(%)", "type": "数值", "key_risk": True},
        {"name": "基金配置比例(%)", "type": "数值"},
        {"name": "固收产品比例(%)", "type": "数值"},
        {"name": "房地产投资比例(%)", "type": "数值"},
        {"name": "黄金配置比例(%)", "type": "数值"},
        {"name": "加密资产比例(%)", "type": "数值", "key_risk": True},
        {"name": "现金/存款比例(%)", "type": "数值"},

        {"is_group": True, "name": "风险指标"},
        {"name": "是否使用杠杆投资", "type": "dropdown", "choices": ["否", "是(融资融券)", "是(配资)", "是(其他)"], "key_risk": True},
        {"name": "杠杆比例", "type": "数值", "note": "如有杠杆，负债/本金比例"},
        {"name": "近3年投资收益率(%)", "type": "数值"},
        {"name": "最大回撤(%)", "type": "数值", "key_risk": True, "note": "历史最大亏损幅度"},
        {"name": "投资集中度风险", "type": "dropdown", "choices": ["分散", "适度集中", "高度集中(单一品种>50%)"], "key_risk": True},
        {"name": "流动性风险评估", "type": "dropdown", "choices": ["高流动性", "中等", "低流动性"], "key_risk": True},
    ]

    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 11: 养老与传承规划
# ============================================================
def create_retirement_planning_sheet(wb):
    ws = wb.create_sheet("养老与传承规划", 10)
    ws.sheet_properties.tabColor = "00A2E8"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十一、养老与传承规划"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='00A2E8', end_color='00A2E8', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估养老准备情况和财富传承安排。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"is_group": True, "name": "养老规划"},
        {"name": "计划退休年龄", "type": "dropdown", "choices": ["<50岁", "50-55岁", "55-60岁", "60-65岁", ">65岁"], "key_risk": True},
        {"name": "养老金主要来源", "type": "dropdown", "choices": ["社保养老金", "企业年金", "商业养老保险", "投资收益", "房租收入", "子女赡养"], "key_risk": True},
        {"name": "社保缴纳年限(年)", "type": "数值"},
        {"name": "社保缴纳基数(万元)", "type": "数值"},
        {"name": "是否有企业年金", "type": "dropdown", "choices": ["有", "无"]},
        {"name": "企业年金余额(万元)", "type": "数值"},
        {"name": "商业养老保险年缴(万元)", "type": "数值"},
        {"name": "预计退休后月支出(万元)", "type": "数值", "key_risk": True},
        {"name": "养老金替代率(%)", "type": "dropdown", "choices": ["<30%", "30-50%", "50-70%", ">70%", "未知"], "key_risk": True, "note": "退休后收入/退休前收入"},

        {"is_group": True, "name": "传承规划"},
        {"name": "是否立有遗嘱", "type": "dropdown", "choices": ["有-已公证", "有-未公证", "无"], "key_risk": True},
        {"name": "是否有家族信托", "type": "dropdown", "choices": ["有", "规划中", "无"]},
        {"name": "家族信托规模(万元)", "type": "数值"},
        {"name": "财产传承安排", "type": "text", "note": "简述传承意愿及安排"},
        {"name": "保险受益人是否指定", "type": "dropdown", "choices": ["已指定", "法定", "未指定"], "key_risk": True},
        {"name": "是否有遗产税筹划", "type": "dropdown", "choices": ["有", "无", "不适用"]},
    ]

    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 12: 生活方式与外部风险
# ============================================================
def create_lifestyle_risk_sheet(wb):
    ws = wb.create_sheet("生活方式与外部风险", 11)
    ws.sheet_properties.tabColor = "F4B084"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十二、生活方式与外部风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='F4B084', end_color='F4B084', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估日常生活方式带来的潜在风险。"
    ws['A2'].font = NOTE_FONT

    fields = [
        {"name": "居住环境", "type": "dropdown", "choices": ["城市中心", "城郊", "农村", "境外"], "key_risk": True},
        {"name": "住房类型", "type": "dropdown", "choices": ["自有住房", "租房", "公司提供"]},
        {"name": "通勤方式", "type": "dropdown", "choices": ["步行/骑行", "公共交通", "自驾", "公司班车", "打车"]},
        {"name": "通勤时间(分钟)", "type": "数值"},
        {"name": "驾驶习惯", "type": "dropdown", "choices": ["良好", "一般", "较差", "无驾照"]},
        {"name": "年均出行次数(国内)", "type": "数值"},
        {"name": "年均出境次数", "type": "数值"},
        {"name": "高风险兴趣爱好", "type": "text", "key_risk": True, "note": "如潜水、滑雪、攀岩、跳伞、赛车等"},
        {"name": "网络安全意识", "type": "dropdown", "choices": ["很强", "一般", "较弱"], "key_risk": True},
        {"name": "是否遭遇过网络诈骗", "type": "dropdown", "choices": ["从未", "偶尔收到诈骗信息", "曾上当受骗"], "key_risk": True},
        {"name": "社交媒体使用频率", "type": "dropdown", "choices": ["很少", "适度", "频繁", "过度依赖"]},
        {"name": "紧急联系人姓名", "type": "text"},
        {"name": "紧急联系人电话", "type": "text"},
        {"name": "家庭应急物资准备", "type": "dropdown", "choices": ["充分", "基本准备", "未准备"]},
    ]

    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 13: 综合风险评分
# ============================================================
def create_risk_scoring_sheet(wb):
    ws = wb.create_sheet("综合风险评分", 12)
    ws.sheet_properties.tabColor = "C55A11"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十三、综合风险评分"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='C55A11', end_color='C55A11', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：汇总各维度风险评分，生成综合风险画像。"
    ws['A2'].font = NOTE_FONT

    # Scoring table
    headers = ["序号", "风险类别", "权重(%)", "风险评分(1-5)", "风险等级", "主要风险点", "整改意见"]
    col_widths = [5, 25, 12, 15, 12, 40, 40]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER

    ws.freeze_panes = ws.cell(row=5, column=1)

    categories = [
        ("健康风险", 25),
        ("财务风险", 20),
        ("职业风险", 10),
        ("家庭风险", 10),
        ("法律与信用风险", 10),
        ("保险保障风险", 10),
        ("投资风险", 10),
        ("生活方式与外部风险", 5),
    ]

    row = 5
    for idx, (cat, weight) in enumerate(categories, 1):
        ws.cell(row=row, column=1, value=idx).font = FIELD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER

        ws.cell(row=row, column=2, value=cat).font = FIELD_FONT
        ws.cell(row=row, column=2).alignment = LEFT_ALIGN
        ws.cell(row=row, column=2).border = THIN_BORDER

        ws.cell(row=row, column=3, value=weight).font = FIELD_FONT
        ws.cell(row=row, column=3).alignment = CENTER_ALIGN
        ws.cell(row=row, column=3).border = THIN_BORDER

        score_cell = ws.cell(row=row, column=4)
        score_cell.font = FIELD_FONT
        score_cell.alignment = CENTER_ALIGN
        score_cell.border = THIN_BORDER
        score_dv = DataValidation(type="list", formula1='"1,2,3,4,5"', allow_blank=True)
        ws.add_data_validation(score_dv)
        score_dv.add(score_cell)

        risk_level_cell = ws.cell(row=row, column=5)
        risk_level_cell.font = FIELD_FONT
        risk_level_cell.alignment = CENTER_ALIGN
        risk_level_cell.border = THIN_BORDER
        rl_dv = DataValidation(type="list", formula1='"低,中,高,极高"', allow_blank=True)
        ws.add_data_validation(rl_dv)
        rl_dv.add(risk_level_cell)

        ws.cell(row=row, column=6).font = FIELD_FONT
        ws.cell(row=row, column=6).alignment = LEFT_ALIGN
        ws.cell(row=row, column=6).border = THIN_BORDER

        ws.cell(row=row, column=7).font = FIELD_FONT
        ws.cell(row=row, column=7).alignment = LEFT_ALIGN
        ws.cell(row=row, column=7).border = THIN_BORDER

        row += 1

    # Summary section
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    cell = ws.cell(row=row, column=1, value="综合评估结论")
    cell.font = SECTION_FONT
    cell.fill = SUB_HEADER_FILL
    cell.alignment = LEFT_ALIGN
    cell.border = THIN_BORDER

    row += 1
    summary_fields = [
        ("加权总分", "数值", "", "自动计算：∑(评分×权重)/5×100"),
        ("综合风险等级", "dropdown", "低,中,高,极高", "根据总分判定"),
        ("主要风险点识别", "text", "", "列出前3大风险"),
        ("优先整改建议", "text", "", "按优先级排序"),
        ("中长期风险管理规划", "text", "", "3-5年风险管理路线"),
    ]

    for idx, (name, ftype, choices, note) in enumerate(summary_fields, 1):
        ws.cell(row=row, column=1, value=idx).font = FIELD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER

        cn = ws.cell(row=row, column=2, value=name)
        cn.font = FIELD_FONT
        cn.alignment = LEFT_ALIGN
        cn.border = THIN_BORDER
        cn.fill = REQUIRED_FILL

        ws.cell(row=row, column=3, value=ftype).font = FIELD_FONT
        ws.cell(row=row, column=3).alignment = CENTER_ALIGN
        ws.cell(row=row, column=3).border = THIN_BORDER

        ws.cell(row=row, column=4).font = FIELD_FONT
        ws.cell(row=row, column=4).alignment = CENTER_ALIGN
        ws.cell(row=row, column=4).border = THIN_BORDER

        ws.cell(row=row, column=5, value=note).font = NOTE_FONT
        ws.cell(row=row, column=5).alignment = LEFT_ALIGN
        ws.cell(row=row, column=5).border = THIN_BORDER

        ci = ws.cell(row=row, column=6)
        ci.font = FIELD_FONT
        ci.alignment = LEFT_ALIGN
        ci.border = THIN_BORDER
        if choices:
            dv = DataValidation(type="list", formula1='"' + choices.replace(",", ",") + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(ci)

        ws.cell(row=row, column=7).font = NOTE_FONT
        ws.cell(row=row, column=7).alignment = LEFT_ALIGN
        ws.cell(row=row, column=7).border = THIN_BORDER

        row += 1

    # Merge columns 5-7 for last few summary rows
    ws.merge_cells(start_row=row-3, start_column=5, end_row=row-3, end_column=7)
    ws.merge_cells(start_row=row-2, start_column=5, end_row=row-2, end_column=7)
    ws.merge_cells(start_row=row-1, start_column=5, end_row=row-1, end_column=7)


# ============================================================
# Sheet 14: 生命周期风险地图
# ============================================================
def create_lifecycle_risk_sheet(wb):
    ws = wb.create_sheet("生命周期风险地图", 13)
    ws.sheet_properties.tabColor = "4472C4"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十四、生命周期风险地图"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：按不同人生阶段识别主要风险及管理重点。"
    ws['A2'].font = NOTE_FONT

    headers = ["生命周期阶段", "年龄范围", "主要风险类型", "风险等级(参考)", "管理重点", "当前准备情况", "建议措施"]
    col_widths = [18, 15, 30, 15, 35, 20, 40]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER

    ws.freeze_panes = ws.cell(row=5, column=1)

    lifecycle_data = [
        ("青年期(探索)", "18-25岁", "职业选择风险、意外伤害、信用记录", "中", "职业规划、基础保障、建立信用", "", ""),
        ("成家期(积累)", "26-35岁", "房贷压力、家庭责任、收入稳定性、健康透支", "高", "家庭保障、收入多元化、应急储备", "", ""),
        ("事业发展期", "36-50岁", "职业瓶颈、子女教育、父母赡养、投资风险", "高", "资产配置优化、教育金规划、养老启动", "", ""),
        ("成熟稳定期", "51-60岁", "健康风险、退休准备、财富传承、企业接班", "中高", "健康管理、退休金储备、传承规划", "", ""),
        ("退休期", "60岁以上", "医疗开支、长寿风险、资产保全、认知能力", "中", "医疗保障、养老现金流、遗产安排", "", ""),
    ]

    for r_idx, data in enumerate(lifecycle_data, 5):
        for c_idx, val in enumerate(data, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FIELD_FONT
            cell.alignment = LEFT_ALIGN if c_idx != 4 else CENTER_ALIGN
            cell.border = THIN_BORDER
            if c_idx == 1:
                cell.fill = SUB_HEADER_FILL


# ============================================================
# Sheet 15: 情景压力测试
# ============================================================
def create_stress_test_sheet(wb):
    ws = wb.create_sheet("情景压力测试", 14)
    ws.sheet_properties.tabColor = "A5A5A5"

    ws.merge_cells('A1:G1')
    ws['A1'].value = "十五、情景压力测试（Stress Test）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='A5A5A5', end_color='A5A5A5', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN

    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：模拟极端情景，评估个人/家庭抗风险能力及资金可持续性。"
    ws['A2'].font = NOTE_FONT

    headers = ["压力情景", "情景描述", "受影响模块", "影响程度(1-5)", "资金可持续月数", "现有应对措施", "改善建议"]
    col_widths = [20, 35, 20, 15, 18, 35, 40]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER

    ws.freeze_panes = ws.cell(row=5, column=1)

    stress_scenarios = [
        ("重大疾病", "本人或配偶罹患重大疾病，治疗费用50-100万，收入下降50%", "健康/财务/保险", "", "", "", ""),
        ("长期失业", "主要收入来源失业，持续12个月以上", "职业/现金流/负债", "", "", "", ""),
        ("家庭支柱身故", "家庭主要收入者意外身故", "家庭/财务/保险", "", "", "", ""),
        ("市场大幅波动", "股市下跌30%，资产缩水", "投资/资产", "", "", "", ""),
        ("婚姻变故", "离婚导致资产分割，收入减半", "家庭/财务/资产", "", "", "", ""),
        ("政策变化", "房产税/遗产税/CRS信息交换等", "资产/税务/传承", "", "", "", ""),
        ("多情景叠加", "以上2-3种情景同时发生", "全面影响", "", "", "", ""),
    ]

    for r_idx, data in enumerate(stress_scenarios, 5):
        for c_idx, val in enumerate(data, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FIELD_FONT
            cell.alignment = LEFT_ALIGN if c_idx not in [4, 5] else CENTER_ALIGN
            cell.border = THIN_BORDER
            if c_idx == 1:
                cell.fill = SUB_HEADER_FILL

            # Dropdowns for impact level
            if c_idx == 4:
                dv = DataValidation(type="list", formula1='"1,2,3,4,5"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(cell)


# ============================================================
# Main generation function
# ============================================================
def generate_form():
    wb = create_workbook()

    create_basic_info_sheet(wb)
    create_family_sheet(wb)
    create_career_risk_sheet(wb)
    create_income_cashflow_sheet(wb)
    create_asset_sheet(wb)
    create_liability_sheet(wb)
    create_health_risk_sheet(wb)
    create_insurance_sheet(wb)
    create_legal_credit_sheet(wb)
    create_investment_risk_sheet(wb)
    create_retirement_planning_sheet(wb)
    create_lifestyle_risk_sheet(wb)
    create_risk_scoring_sheet(wb)
    create_lifecycle_risk_sheet(wb)
    create_stress_test_sheet(wb)

    # Save
    output_dir = r"D:\_Work\02_Documents\信息搜集表格"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"个人家庭风险评估问卷_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    wb.save(filepath)
    print(f"✓ 文件已生成: {filepath}")
    print(f"  Sheet数量: {len(wb.sheetnames)}")
    for i, name in enumerate(wb.sheetnames, 1):
        print(f"    {i:2d}. {name}")

    return filepath


if __name__ == "__main__":
    generate_form()