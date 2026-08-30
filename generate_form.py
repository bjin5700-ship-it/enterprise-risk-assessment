# -*- coding: utf-8 -*-
"""
企业风险信息搜集表生成器
Enterprise Risk Information Collection Form Generator

版本: 1.0.0
架构: 模块化多Sheet设计
模块数: 17个Sheet（12大核心模块 + 5个扩展模块）
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import datetime
import os

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
THIN_BORDER = Border(left=Side(style="thin",color="B4C6E7"),right=Side(style="thin",color="B4C6E7"),top=Side(style="thin",color="B4C6E7"),bottom=Side(style="thin",color="B4C6E7"))
CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)
def create_workbook():
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    return wb


def write_field_table(ws, fields, start_row=4):
    """Write a structured field table to the worksheet."""
    try:
        from risk_matrix import MATRIX_FIELDS, is_matrix_sheet
        if is_matrix_sheet(ws.title) and not any(f.get("name") == "可能性(1-5)" for f in fields):
            fields = list(fields) + MATRIX_FIELDS
    except Exception:
        pass
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
    
    ws.freeze_panes = ws.cell(row=start_row+1, column=1)
    
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
# Sheet 1: 企业基本信息
# ============================================================
def create_basic_info_sheet(wb):
    ws = wb.create_sheet("企业基本信息", 0)
    ws.sheet_properties.tabColor = "1F4E79"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "一、企业基本信息"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = TITLE_FILL
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：本模块收集企业基础信息，用于风险评估的初步分类与定位。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "企业概况"},
        {"name": "企业名称", "type": "文本", "key_risk": True, "note": "工商注册全称"},
        {"name": "统一社会信用代码", "type": "文本", "key_risk": True, "note": "18位统一代码"},
        {"name": "成立日期", "type": "文本", "note": "YYYY-MM-DD"},
        {"name": "注册资本(万元)", "type": "数值"},
        {"name": "企业类型", "type": "下拉", "choices": ["国有企业", "民营企业", "外资企业", "合资企业", "其他"]},
        {"name": "所属行业", "type": "下拉", "choices": ["制造业", "化工", "能源", "建筑", "交通运输", "信息技术", "金融", "批发零售", "房地产", "其他"]},
        {"name": "主营业务", "type": "文本", "key_risk": True, "note": "简要描述主营业务"},
        {"name": "员工总数(人)", "type": "数值"},
        
        {"is_group": True, "name": "联系方式"},
        {"name": "企业地址", "type": "文本"},
        {"name": "法定代表人", "type": "文本"},
        {"name": "联系人", "type": "文本"},
        {"name": "联系电话", "type": "文本"},
        {"name": "电子邮箱", "type": "文本"},
        
        {"is_group": True, "name": "企业规模"},
        {"name": "占地面积(亩)", "type": "数值"},
        {"name": "建筑面积(㎡)", "type": "数值"},
        {"name": "年营业额(万元)", "type": "数值", "key_risk": True},
        {"name": "资产总额(万元)", "type": "数值", "key_risk": True},
        {"name": "是否上市公司", "type": "下拉", "choices": ["是", "否"]},
        {"name": "上市代码(如适用)", "type": "文本"},
        
        {"is_group": True, "name": "风险管理偏好"},
        {"name": "风险承受度", "type": "下拉", "choices": ["保守", "稳健", "平衡", "积极", "激进"], "key_risk": True},
        {"name": "风险偏好", "type": "下拉", "choices": ["低风险", "中低风险", "中等风险", "中高风险", "高风险"]},
        {"name": "评估复评周期(天)", "type": "数值", "note": "默认90天，建议30-365"},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 2: 经营风险
# ============================================================
def create_business_risk_sheet(wb):
    ws = wb.create_sheet("经营风险", 1)
    ws.sheet_properties.tabColor = "C55A11"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "二、经营风险分析"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='C55A11', end_color='C55A11', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业面临的经营环境风险、市场风险及竞争风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "市场与竞争"},
        {"name": "市场地位", "type": "下拉", "choices": ["行业龙头", "主要参与者", "中等规模", "小型参与者"], "key_risk": True},
        {"name": "主要竞争对手", "type": "text", "note": "列举3-5个主要竞争对手"},
        {"name": "行业景气度", "type": "下拉", "choices": ["高速增长", "稳定增长", "成熟期", "衰退期"], "key_risk": True},
        {"name": "市场集中度(CR5)", "type": "下拉", "choices": ["<20%(分散)", "20-40%(较低)", "40-60%(中等)", "60-80%(较高)", ">80%(高度集中)"]},
        
        {"is_group": True, "name": "客户风险"},
        {"name": "前五大客户收入占比(%)", "type": "数值", "key_risk": True, "note": "客户集中度风险指标"},
        {"name": "最大单一客户占比(%)", "type": "数值", "key_risk": True},
        {"name": "客户行业分布", "type": "下拉", "choices": ["单一行业", "2-3个行业", "3个以上行业"], "key_risk": True},
        {"name": "客户合同期限", "type": "下拉", "choices": ["长期合同(>3年)", "中期合同(1-3年)", "短期合同(<1年)", "无固定合同"]},
        {"name": "应收账款周转天数", "type": "数值", "note": "天"},
        
        {"is_group": True, "name": "供应商风险"},
        {"name": "前五大供应商采购占比(%)", "type": "数值", "key_risk": True, "note": "供应商集中度风险指标"},
        {"name": "最大单一供应商占比(%)", "type": "数值", "key_risk": True},
        {"name": "供应商地域分布", "type": "下拉", "choices": ["全部国内", "国内为主+少量进口", "国内外均衡", "进口为主"], "key_risk": True},
        {"name": "原材料价格波动影响", "type": "下拉", "choices": ["影响大", "影响中等", "影响小"], "key_risk": True},
        {"name": "主要原材料", "type": "text", "note": "列举主要原材料及价格走势"},
        
        {"is_group": True, "name": "经营稳定性"},
        {"name": "近三年营收增长率(%)", "type": "数值", "key_risk": True, "note": "分别填写2021/2022/2023年数据"},
        {"name": "近三年利润增长率(%)", "type": "数值", "key_risk": True},
        {"name": "季节性波动", "type": "下拉", "choices": ["无显著波动", "有-但可控", "有-影响较大"]},
        {"name": "经营许可证/资质", "type": "text", "note": "列举核心经营资质及有效期"},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 3: 财务风险
# ============================================================
def create_financial_risk_sheet(wb):
    ws = wb.create_sheet("财务风险", 2)
    ws.sheet_properties.tabColor = "C00000"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "三、财务风险分析"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='C00000', end_color='C00000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：分析企业财务健康状况，识别偿债、盈利、现金流等方面的风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "偿债能力"},
        {"name": "资产负债率(%)", "type": "数值", "key_risk": True, "note": "=总负债/总资产"},
        {"name": "流动比率", "type": "数值", "key_risk": True, "note": "=流动资产/流动负债"},
        {"name": "速动比率", "type": "数值", "key_risk": True, "note": "=(流动资产-存货)/流动负债"},
        {"name": "利息保障倍数", "type": "数值", "note": "=息税前利润/利息费用"},
        {"name": "短期借款占比(%)", "type": "数值", "note": "短期借款/总负债"},
        {"name": "有息负债率(%)", "type": "数值", "key_risk": True, "note": "有息负债/总资产"},
        
        {"is_group": True, "name": "盈利能力"},
        {"name": "毛利率(%)", "type": "数值", "key_risk": True},
        {"name": "净利率(%)", "type": "数值", "key_risk": True},
        {"name": "净资产收益率ROE(%)", "type": "数值", "key_risk": True},
        {"name": "总资产报酬率ROA(%)", "type": "数值"},
        {"name": "近三年是否连续亏损", "type": "下拉", "choices": ["是", "否"], "key_risk": True},
        
        {"is_group": True, "name": "现金流风险"},
        {"name": "经营性现金流净额(万元)", "type": "数值", "key_risk": True, "note": "最近一年数据"},
        {"name": "自由现金流(万元)", "type": "数值", "key_risk": True},
        {"name": "现金流是否覆盖利息", "type": "下拉", "choices": ["完全覆盖", "基本覆盖", "无法覆盖"], "key_risk": True},
        
        {"is_group": True, "name": "外部融资能力"},
        {"name": "银行授信额度(万元)", "type": "数值"},
        {"name": "已使用授信额度(万元)", "type": "数值"},
        {"name": "外部信用评级", "type": "下拉", "choices": ["AAA/AA", "A/BBB", "BB及以下", "无评级"]},
        {"name": "是否存在债务违约记录", "type": "下拉", "choices": ["无", "有-已解决", "有-未解决"], "key_risk": True},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 4: 生产运营风险
# ============================================================
def create_production_risk_sheet(wb):
    ws = wb.create_sheet("生产运营风险", 3)
    ws.sheet_properties.tabColor = "BF8F00"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "四、生产运营风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='BF8F00', end_color='BF8F00', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估生产过程中面临的运营风险，包括生产流程、设备、产能等。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "生产概况"},
        {"name": "主要生产工艺", "type": "text", "key_risk": True, "note": "简要描述核心生产工艺流程"},
        {"name": "年产能", "type": "text", "note": "按主要产品填写"},
        {"name": "产能利用率(%)", "type": "数值", "key_risk": True},
        {"name": "生产班次", "type": "下拉", "choices": ["单班制", "两班制", "三班制", "灵活排班"]},
        
        {"is_group": True, "name": "设备管理"},
        {"name": "主要设备数量(台套)", "type": "数值"},
        {"name": "设备平均役龄(年)", "type": "数值", "key_risk": True},
        {"name": "关键设备国产化率(%)", "type": "数值"},
        {"name": "设备故障率(%)", "type": "数值", "key_risk": True},
        {"name": "大修周期(月)", "type": "数值"},
        
        {"is_group": True, "name": "质量控制"},
        {"name": "质量管理体系", "type": "下拉", "choices": ["ISO9001", "IATF16949", "ISO13485", "AS9100", "无认证", "其他"], "key_risk": True},
        {"name": "产品合格率(%)", "type": "数值", "key_risk": True},
        {"name": "客诉率(件/万件)", "type": "数值"},
        {"name": "质量事故记录", "type": "text", "key_risk": True, "note": "近三年重大质量事故描述"},
        
        {"is_group": True, "name": "产能与供应链"},
        {"name": "产能瓶颈环节", "type": "text", "key_risk": True, "note": "识别生产瓶颈"},
        {"name": "外协加工占比(%)", "type": "数值"},
        {"name": "库存周转天数", "type": "数值"},
        {"name": "原材料库存保障天数", "type": "数值", "key_risk": True},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 5: 安全生产风险
# ============================================================
def create_safety_risk_sheet(wb):
    ws = wb.create_sheet("安全生产风险", 4)
    ws.sheet_properties.tabColor = "FF0000"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "五、安全生产风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业安全生产管理体系及实际风险状况。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "安全管理体系"},
        {"name": "安全管理制度", "type": "下拉", "choices": ["完善", "基本完善", "不完善", "无"], "key_risk": True},
        {"name": "安全管理人员数量", "type": "数值"},
        {"name": "安全管理人员占比(%)", "type": "数值"},
        {"name": "安全投入占营收比(%)", "type": "数值", "key_risk": True},
        {"name": "安全生产标准化等级", "type": "下拉", "choices": ["一级", "二级", "三级", "未评级"]},
        {"name": "ISO45001认证", "type": "下拉", "choices": ["已认证", "认证中", "未认证"]},
        
        {"is_group": True, "name": "事故与隐患"},
        {"name": "近三年工伤事故次数", "type": "数值", "key_risk": True},
        {"name": "近三年死亡事故次数", "type": "数值", "key_risk": True, "note": "如有请详细说明"},
        {"name": "百万工时伤害率", "type": "数值", "key_risk": True},
        {"name": "隐患整改率(%)", "type": "数值", "key_risk": True},
        {"name": "重大隐患数量", "type": "数值", "key_risk": True},
        {"name": "隐患平均整改周期(天)", "type": "数值"},
        
        {"is_group": True, "name": "安全培训与应急"},
        {"name": "安全培训覆盖率(%)", "type": "数值"},
        {"name": "特种作业人员持证率(%)", "type": "数值"},
        {"name": "应急预案数量", "type": "数值"},
        {"name": "应急演练频次(次/年)", "type": "数值"},
        {"name": "应急物资储备", "type": "下拉", "choices": ["充足", "基本满足", "不足"], "key_risk": True},
        
        {"is_group": True, "name": "危化品管理"},
        {"name": "是否涉及危化品", "type": "下拉", "choices": ["是", "否"], "key_risk": True},
        {"name": "危化品种类数", "type": "数值"},
        {"name": "危化品最大存储量(吨)", "type": "数值"},
        {"name": "危化品存储条件", "type": "下拉", "choices": ["符合标准", "基本符合", "不符合"], "key_risk": True},
        {"name": "危化品运输资质", "type": "下拉", "choices": ["自有资质", "委托有资质单位", "无"], "key_risk": True},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 6: 环境风险
# ============================================================
def create_environmental_risk_sheet(wb):
    ws = wb.create_sheet("环境风险", 5)
    ws.sheet_properties.tabColor = "00B050"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "六、环境风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='00B050', end_color='00B050', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业环境合规性及环境管理风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "环境合规"},
        {"name": "环评批复情况", "type": "下拉", "choices": ["已取得", "办理中", "未办理", "豁免"], "key_risk": True},
        {"name": "排污许可证", "type": "下拉", "choices": ["已取得", "办理中", "未办理"], "key_risk": True},
        {"name": "近三年环境处罚次数", "type": "数值", "key_risk": True},
        {"name": "处罚金额累计(万元)", "type": "数值", "key_risk": True},
        {"name": "环境诉讼案件数", "type": "数值", "key_risk": True},
        
        {"is_group": True, "name": "污染物排放"},
        {"name": "废水年排放量(万吨)", "type": "数值"},
        {"name": "废气年排放量(万标立方米)", "type": "数值"},
        {"name": "固废年产生量(吨)", "type": "数值"},
        {"name": "危废年产生量(吨)", "type": "数值", "key_risk": True},
        {"name": "排放达标率(%)", "type": "数值", "key_risk": True},
        {"name": "碳排放量(吨CO2/年)", "type": "数值"},
        
        {"is_group": True, "name": "环境管理体系"},
        {"name": "ISO14001认证", "type": "下拉", "choices": ["已认证", "认证中", "未认证"]},
        {"name": "环境监测频次", "type": "下拉", "choices": ["在线连续监测", "月度", "季度", "年度", "不定期"]},
        {"name": "环保投入(万元/年)", "type": "数值", "key_risk": True},
        {"name": "环保设施运行率(%)", "type": "数值"},
        
        {"is_group": True, "name": "环境风险管控"},
        {"name": "环境风险评估", "type": "下拉", "choices": ["已开展", "未开展"], "key_risk": True},
        {"name": "环境应急预案", "type": "下拉", "choices": ["已编制备案", "已编制未备案", "未编制"], "key_risk": True},
        {"name": "环境风险等级", "type": "下拉", "choices": ["重大", "较大", "一般", "低"]},
        {"name": "周边敏感目标", "type": "text", "note": "居民区/学校/水源地等距离"},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 7: 法律合规风险
# ============================================================
def create_legal_risk_sheet(wb):
    ws = wb.create_sheet("法律合规风险", 6)
    ws.sheet_properties.tabColor = "7030A0"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "七、法律合规风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='7030A0', end_color='7030A0', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业法律合规状况，识别诉讼、合同、知识产权等风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "诉讼仲裁"},
        {"name": "在审案件数量", "type": "数值", "key_risk": True},
        {"name": "在审案件标的额(万元)", "type": "数值", "key_risk": True},
        {"name": "近三年败诉案件数", "type": "数值", "key_risk": True},
        {"name": "败诉金额累计(万元)", "type": "数值", "key_risk": True},
        
        {"is_group": True, "name": "合同管理"},
        {"name": "合同管理制度", "type": "下拉", "choices": ["完善", "基本完善", "不完善", "无"], "key_risk": True},
        {"name": "合同审核率(%)", "type": "数值"},
        {"name": "重大合同履行异常", "type": "text", "key_risk": True, "note": "描述异常情况"},
        
        {"is_group": True, "name": "知识产权"},
        {"name": "专利数量", "type": "text", "note": "发明专利/实用新型/外观设计"},
        {"name": "商标数量", "type": "数值"},
        {"name": "知识产权纠纷", "type": "下拉", "choices": ["无", "有-已解决", "有-未解决"], "key_risk": True},
        
        {"is_group": True, "name": "合规管理"},
        {"name": "反商业贿赂制度", "type": "下拉", "choices": ["完善", "有但不完善", "无"], "key_risk": True},
        {"name": "数据合规措施", "type": "下拉", "choices": ["完善", "有但不完善", "无"]},
        {"name": "行业监管检查结果", "type": "下拉", "choices": ["合格", "基本合格", "不合格", "未检查"], "key_risk": True},
        {"name": "行政处罚次数(近三年)", "type": "数值", "key_risk": True},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 8: 供应链风险
# ============================================================
def create_supply_chain_risk_sheet(wb):
    ws = wb.create_sheet("供应链风险", 7)
    ws.sheet_properties.tabColor = "ED7D31"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "八、供应链风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='ED7D31', end_color='ED7D31', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估供应链上下游风险，包括供应商依赖、物流、地缘政治等。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "供应商管理"},
        {"name": "供应商总数", "type": "数值"},
        {"name": "核心供应商数量", "type": "数值", "key_risk": True},
        {"name": "单一来源采购占比(%)", "type": "数值", "key_risk": True, "note": "独家供应商采购比例"},
        {"name": "供应商认证体系", "type": "下拉", "choices": ["完善", "基本完善", "不完善", "无"], "key_risk": True},
        {"name": "供应商更换周期", "type": "下拉", "choices": ["<1年", "1-3年", ">3年"]},
        
        {"is_group": True, "name": "物流与运输"},
        {"name": "主要运输方式", "type": "下拉", "choices": ["公路", "铁路", "水路", "航空", "多式联运"]},
        {"name": "物流成本占比(%)", "type": "数值"},
        {"name": "自有运输车辆(辆)", "type": "数值"},
        {"name": "物流中断风险", "type": "下拉", "choices": ["低", "中", "高"], "key_risk": True},
        
        {"is_group": True, "name": "地缘与贸易风险"},
        {"name": "进口依赖度(%)", "type": "数值", "key_risk": True},
        {"name": "进口来源国", "type": "text", "key_risk": True},
        {"name": "关税影响程度", "type": "下拉", "choices": ["影响大", "影响中等", "影响小", "无影响"], "key_risk": True},
        {"name": "出口业务占比(%)", "type": "数值"},
        {"name": "出口目的地国", "type": "text"},
        {"name": "汇率波动影响", "type": "下拉", "choices": ["影响大", "影响中等", "影响小", "无影响"]},
        
        {"is_group": True, "name": "库存管理"},
        {"name": "原材料库存周转天数", "type": "数值"},
        {"name": "成品库存周转天数", "type": "数值"},
        {"name": "安全库存覆盖天数", "type": "数值", "key_risk": True},
        {"name": "呆滞库存占比(%)", "type": "数值"},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 9: 技术风险
# ============================================================
def create_technology_risk_sheet(wb):
    ws = wb.create_sheet("技术风险", 8)
    ws.sheet_properties.tabColor = "4472C4"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "九、技术风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业技术研发能力、知识产权保护及技术迭代风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "研发能力"},
        {"name": "研发人员数量", "type": "数值"},
        {"name": "研发人员占比(%)", "type": "数值", "key_risk": True},
        {"name": "研发投入占营收比(%)", "type": "数值", "key_risk": True},
        {"name": "核心技术来源", "type": "下拉", "choices": ["自主研发", "合作研发", "外部引进", "许可使用"], "key_risk": True},
        {"name": "研发周期(月)", "type": "数值"},
        
        {"is_group": True, "name": "技术保护"},
        {"name": "专利数量(累计)", "type": "数值", "key_risk": True, "note": "发明专利/实用新型/外观设计"},
        {"name": "软件著作权数量", "type": "数值"},
        {"name": "技术秘密保护措施", "type": "下拉", "choices": ["完善", "基本完善", "不完善", "无"], "key_risk": True},
        {"name": "核心技术流失风险", "type": "下拉", "choices": ["低", "中", "高"], "key_risk": True},
        
        {"is_group": True, "name": "技术迭代"},
        {"name": "技术所处生命周期", "type": "下拉", "choices": ["导入期", "成长期", "成熟期", "衰退期"], "key_risk": True},
        {"name": "替代技术威胁", "type": "下拉", "choices": ["低", "中", "高"], "key_risk": True},
        {"name": "数字化转型阶段", "type": "下拉", "choices": ["领先", "跟进", "起步", "未启动"]},
        {"name": "信息系统安全等级", "type": "下拉", "choices": ["等保三级", "等保二级", "未定级"]},
        
        {"is_group": True, "name": "数据安全"},
        {"name": "数据备份机制", "type": "下拉", "choices": ["完善", "基本完善", "不完善", "无"], "key_risk": True},
        {"name": "网络安全事件次数(近三年)", "type": "数值", "key_risk": True},
        {"name": "信息安全认证", "type": "下拉", "choices": ["ISO27001", "等保认证", "无认证"]},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 10: 人力资源风险
# ============================================================
def create_hr_risk_sheet(wb):
    ws = wb.create_sheet("人力资源风险", 9)
    ws.sheet_properties.tabColor = "FF69B4"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十、人力资源风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='FF69B4', end_color='FF69B4', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业人力资源管理风险，包括人才流失、劳资关系等。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "人员结构"},
        {"name": "员工总数", "type": "数值"},
        {"name": "管理人员占比(%)", "type": "数值"},
        {"name": "技术人员占比(%)", "type": "数值"},
        {"name": "生产人员占比(%)", "type": "数值"},
        {"name": "本科以上学历占比(%)", "type": "数值"},
        {"name": "平均工龄(年)", "type": "数值"},
        
        {"is_group": True, "name": "人才流失"},
        {"name": "年离职率(%)", "type": "数值", "key_risk": True},
        {"name": "核心人才离职率(%)", "type": "数值", "key_risk": True},
        {"name": "关键岗位空缺数", "type": "数值", "key_risk": True},
        {"name": "招聘完成率(%)", "type": "数值"},
        
        {"is_group": True, "name": "劳资关系"},
        {"name": "劳动合同签订率(%)", "type": "数值"},
        {"name": "社保缴纳合规性", "type": "下拉", "choices": ["全额合规", "基本合规", "不合规"], "key_risk": True},
        {"name": "近三年劳资纠纷次数", "type": "数值", "key_risk": True},
        {"name": "工会建立情况", "type": "下拉", "choices": ["已建立", "未建立"]},
        
        {"is_group": True, "name": "绩效考核"},
        {"name": "绩效考核覆盖率(%)", "type": "数值"},
        {"name": "薪酬竞争力", "type": "下拉", "choices": ["高于行业", "与行业持平", "低于行业"], "key_risk": True},
        {"name": "股权激励/员工持股", "type": "下拉", "choices": ["已实施", "计划中", "无"]},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 11: 信用风险
# ============================================================
def create_credit_risk_sheet(wb):
    ws = wb.create_sheet("信用风险", 10)
    ws.sheet_properties.tabColor = "A5A5A5"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十一、信用风险"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='A5A5A5', end_color='A5A5A5', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业的信用状况，包括征信记录、履约能力等。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "征信记录"},
        {"name": "企业征信报告", "type": "下拉", "choices": ["无不良记录", "有-轻微", "有-严重"], "key_risk": True},
        {"name": "征信查询次数(近半年)", "type": "数值"},
        {"name": "对外担保余额(万元)", "type": "数值", "key_risk": True},
        {"name": "担保比率(%)", "type": "数值", "key_risk": True, "note": "对外担保/净资产"},
        
        {"is_group": True, "name": "付款履约"},
        {"name": "供应商付款周期(天)", "type": "数值"},
        {"name": "逾期付款记录", "type": "下拉", "choices": ["无", "有-偶尔", "有-经常"], "key_risk": True},
        {"name": "客户回款周期(天)", "type": "数值"},
        {"name": "坏账率(%)", "type": "数值", "key_risk": True},
        
        {"is_group": True, "name": "关联交易"},
        {"name": "关联交易占比(%)", "type": "数值", "key_risk": True},
        {"name": "关联方类型", "type": "text", "note": "关联方关系描述"},
        {"name": "关联交易定价公允性", "type": "下拉", "choices": ["公允", "基本公允", "不公允"], "key_risk": True},
        
        {"is_group": True, "name": "外部信用"},
        {"name": "税务信用等级", "type": "下拉", "choices": ["A级", "B级", "C级", "D级", "未评级"], "key_risk": True},
        {"name": "海关信用等级", "type": "下拉", "choices": ["高级认证", "一般认证", "失信企业", "不适用"]},
        {"name": "行业信用评级", "type": "text", "note": "如AAA/AA/A等"},
        {"name": "行政处罚记录", "type": "text", "key_risk": True, "note": "近三年记录"},
    ]
    
    write_field_table(ws, fields, start_row=4)
# ============================================================
# Sheet 12: 综合评估
# ============================================================
def create_overall_assessment_sheet(wb):
    ws = wb.create_sheet("综合评估", 11)
    ws.sheet_properties.tabColor = "000000"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十二、综合风险评估"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='000000', end_color='000000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：综合各模块风险评估结果，形成整体风险评价。"
    ws['A2'].font = NOTE_FONT
    
    col_widths = [5, 35, 18, 18, 18, 45, 45]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    
    headers = ["序号", "风险领域", "风险等级", "发生概率", "影响程度", "风险描述", "应对措施建议"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER
    
    risk_areas = [
        ("经营风险", "市场地位、客户集中度、营收稳定性"),
        ("财务风险", "偿债能力、盈利能力、现金流"),
        ("生产运营风险", "产能利用率、设备状态、质量"),
        ("安全生产风险", "事故率、隐患管理、危化品"),
        ("环境风险", "合规性、排放管理、环保投入"),
        ("法律合规风险", "诉讼、合同、知识产权"),
        ("供应链风险", "供应商依赖、物流、地缘"),
        ("技术风险", "研发能力、技术迭代、数据安全"),
        ("人力资源风险", "人才流失、劳资关系"),
        ("信用风险", "征信记录、履约能力"),
    ]
    
    risk_levels = ["高风险", "中高风险", "中等风险", "中低风险", "低风险"]
    prob_levels = ["很高(>80%)", "较高(60-80%)", "中等(40-60%)", "较低(20-40%)", "很低(<20%)"]
    impact_levels = ["极严重", "严重", "中等", "轻微", "可忽略"]
    
    for i, (area, desc) in enumerate(risk_areas, 1):
        row = 4 + i
        ws.cell(row=row, column=1, value=i).font = FIELD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER
        
        ws.cell(row=row, column=2, value=area).font = FIELD_FONT
        ws.cell(row=row, column=2).alignment = LEFT_ALIGN
        ws.cell(row=row, column=2).border = THIN_BORDER
        
        cell_risk = ws.cell(row=row, column=3)
        cell_risk.font = FIELD_FONT
        cell_risk.alignment = CENTER_ALIGN
        cell_risk.border = THIN_BORDER
        dv = DataValidation(type="list", formula1='"' + ",".join(risk_levels) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(cell_risk)
        
        cell_prob = ws.cell(row=row, column=4)
        cell_prob.font = FIELD_FONT
        cell_prob.alignment = CENTER_ALIGN
        cell_prob.border = THIN_BORDER
        dv2 = DataValidation(type="list", formula1='"' + ",".join(prob_levels) + '"', allow_blank=True)
        ws.add_data_validation(dv2)
        dv2.add(cell_prob)
        
        cell_impact = ws.cell(row=row, column=5)
        cell_impact.font = FIELD_FONT
        cell_impact.alignment = CENTER_ALIGN
        cell_impact.border = THIN_BORDER
        dv3 = DataValidation(type="list", formula1='"' + ",".join(impact_levels) + '"', allow_blank=True)
        ws.add_data_validation(dv3)
        dv3.add(cell_impact)
        
        ws.cell(row=row, column=6, value=desc).font = NOTE_FONT
        ws.cell(row=row, column=6).alignment = LEFT_ALIGN
        ws.cell(row=row, column=6).border = THIN_BORDER
        
        ws.cell(row=row, column=7).font = NOTE_FONT
        ws.cell(row=row, column=7).alignment = LEFT_ALIGN
        ws.cell(row=row, column=7).border = THIN_BORDER
    
    # Summary section
    summary_row = 4 + len(risk_areas) + 2
    ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=7)
    ws.cell(row=summary_row, column=1, value="综合评估结论").font = TITLE_FONT
    ws.cell(row=summary_row, column=1).fill = TITLE_FILL
    ws.cell(row=summary_row, column=1).alignment = CENTER_ALIGN
    
    summary_fields = [
        ("整体风险等级", "dropdown", ["低风险", "中低风险", "中等风险", "中高风险", "高风险"], True),
        ("主要风险领域", "text", [], True, "列出前3个主要风险领域"),
        ("风险缓解措施", "text", [], True, "总体风险应对策略"),
        ("建议尽调深度", "dropdown", ["标准尽调", "全面尽调", "专项尽调", "简易尽调"], False),
        ("尽调优先级", "dropdown", ["高优先级", "中优先级", "低优先级"], True),
        ("是否建议推进", "dropdown", ["建议推进", "有条件推进", "暂缓推进", "不建议推进"], True),
        ("备注/特殊关注事项", "text", [], False),
    ]
    
    for i, (name, ftype, choices, is_key, *note) in enumerate(summary_fields):
        row = summary_row + 1 + i
        ws.cell(row=row, column=1, value=i+1).font = FIELD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER
        
        cell = ws.cell(row=row, column=2, value=name)
        cell.font = FIELD_FONT
        cell.alignment = LEFT_ALIGN
        cell.border = THIN_BORDER
        if is_key:
            cell.fill = REQUIRED_FILL
        
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=5)
        if choices:
            cell_input = ws.cell(row=row, column=3)
            dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(cell_input)
        else:
            cell_input = ws.cell(row=row, column=3)
        
        cell_input.font = FIELD_FONT
        cell_input.alignment = LEFT_ALIGN
        cell_input.border = THIN_BORDER
        ws.cell(row=row, column=4).border = THIN_BORDER
        ws.cell(row=row, column=5).border = THIN_BORDER
        
        note_text = note[0] if note else ""
        ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=7)
        ws.cell(row=row, column=6, value=note_text).font = NOTE_FONT
        ws.cell(row=row, column=6).alignment = LEFT_ALIGN
        ws.cell(row=row, column=6).border = THIN_BORDER
        ws.cell(row=row, column=7).border = THIN_BORDER
# ============================================================
# Sheet 13 (扩展): 关联方与集团风险
# ============================================================
def create_related_party_sheet(wb):
    ws = wb.create_sheet("关联方与集团风险", 12)
    ws.sheet_properties.tabColor = "00B0F0"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十三、关联方与集团风险（扩展模块）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='00B0F0', end_color='00B0F0', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估关联方交易、集团内部担保、资金往来等风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "关联企业"},
        {"name": "关联企业数量", "type": "数值"},
        {"name": "关联企业关系说明", "type": "text", "key_risk": True, "note": "简要描述关联企业及关系"},
        {"name": "集团内部担保金额(万元)", "type": "数值", "key_risk": True},
        {"name": "集团内部资金往来(万元)", "type": "数值", "key_risk": True},
        
        {"is_group": True, "name": "关联交易"},
        {"name": "关联采购占比(%)", "type": "数值", "key_risk": True},
        {"name": "关联销售占比(%)", "type": "数值", "key_risk": True},
        {"name": "关联交易定价依据", "type": "下拉", "choices": ["市场价", "协议价", "成本加成", "无明确依据"], "key_risk": True},
        
        {"is_group": True, "name": "资金占用"},
        {"name": "关联方资金占用(万元)", "type": "数值", "key_risk": True},
        {"name": "资金占用天数", "type": "数值"},
        {"name": "资金占用利率(%)", "type": "数值"},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 14 (扩展): 项目/投资风险
# ============================================================
def create_project_risk_sheet(wb):
    ws = wb.create_sheet("项目投资风险", 13)
    ws.sheet_properties.tabColor = "FFC000"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十四、项目/投资风险（扩展模块）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='FFC000', end_color='FFC000', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估正在进行的重大项目和投资活动的风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "在建项目"},
        {"name": "在建项目数量", "type": "数值"},
        {"name": "在建项目总投资(万元)", "type": "数值", "key_risk": True},
        {"name": "已完成投资(万元)", "type": "数值", "key_risk": True},
        {"name": "项目进度偏差(%)", "type": "数值", "key_risk": True, "note": "正数表示超进度，负数表示滞后"},
        {"name": "预算偏差(%)", "type": "数值", "key_risk": True, "note": "正数表示超预算"},
        
        {"is_group": True, "name": "对外投资"},
        {"name": "长期股权投资(万元)", "type": "数值"},
        {"name": "金融资产投资(万元)", "type": "数值"},
        {"name": "投资收益率(%)", "type": "数值", "key_risk": True},
        {"name": "投资减值风险", "type": "下拉", "choices": ["低", "中", "高"], "key_risk": True},
        
        {"is_group": True, "name": "融资计划"},
        {"name": "近期融资需求(万元)", "type": "数值"},
        {"name": "融资用途", "type": "text"},
        {"name": "拟融资方式", "type": "下拉", "choices": ["银行贷款", "股权融资", "债券发行", "融资租赁", "其他"]},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 15 (扩展): 行业与政策风险
# ============================================================
def create_industry_policy_risk_sheet(wb):
    ws = wb.create_sheet("行业政策风险", 14)
    ws.sheet_properties.tabColor = "70AD47"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十五、行业与政策风险（扩展模块）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='70AD47', end_color='70AD47', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估行业政策变化、监管环境对企业的潜在影响。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "政策环境"},
        {"name": "行业监管政策变化", "type": "下拉", "choices": ["趋严", "稳定", "放宽", "不确定"], "key_risk": True},
        {"name": "政策变化影响评估", "type": "text", "key_risk": True, "note": "具体影响分析"},
        {"name": "产业政策支持", "type": "下拉", "choices": ["重点支持", "一般支持", "限制类", "淘汰类"], "key_risk": True},
        
        {"is_group": True, "name": "行业趋势"},
        {"name": "行业生命周期", "type": "下拉", "choices": ["导入期", "成长期", "成熟期", "衰退期"], "key_risk": True},
        {"name": "行业进入壁垒", "type": "下拉", "choices": ["高", "中", "低"]},
        {"name": "替代品威胁", "type": "下拉", "choices": ["高", "中", "低"], "key_risk": True},
        {"name": "行业利润率趋势", "type": "下拉", "choices": ["上升", "稳定", "下降"], "key_risk": True},
        
        {"is_group": True, "name": "宏观经济"},
        {"name": "经济周期敏感性", "type": "下拉", "choices": ["敏感", "一般", "不敏感"], "key_risk": True},
        {"name": "利率变化影响", "type": "下拉", "choices": ["影响大", "影响中等", "影响小"]},
        {"name": "通货膨胀影响", "type": "下拉", "choices": ["影响大", "影响中等", "影响小"]},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 16 (扩展): 税务风险
# ============================================================
def create_tax_risk_sheet(wb):
    ws = wb.create_sheet("税务风险", 15)
    ws.sheet_properties.tabColor = "9966FF"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十六、税务风险（扩展模块）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='9966FF', end_color='9966FF', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：评估企业税务合规性及税务筹划风险。"
    ws['A2'].font = NOTE_FONT
    
    fields = [
        {"is_group": True, "name": "税务合规"},
        {"name": "近三年纳税总额(万元)", "type": "数值"},
        {"name": "实际税率(%)", "type": "数值", "key_risk": True},
        {"name": "税收优惠类型", "type": "text", "note": "高新技术企业/西部大开发/出口退税等"},
        {"name": "税收优惠金额(万元)", "type": "数值"},
        {"name": "税务稽查记录", "type": "下拉", "choices": ["无问题", "有-已整改", "有-未整改", "稽查中"], "key_risk": True},
        
        {"is_group": True, "name": "税务风险点"},
        {"name": "转让定价风险", "type": "下拉", "choices": ["低", "中", "高"], "key_risk": True},
        {"name": "增值税发票管理", "type": "下拉", "choices": ["规范", "基本规范", "不规范"], "key_risk": True},
        {"name": "个税代扣代缴合规性", "type": "下拉", "choices": ["合规", "基本合规", "不合规"]},
        {"name": "跨境税务风险", "type": "下拉", "choices": ["无跨境业务", "低", "中", "高"]},
        
        {"is_group": True, "name": "税务筹划"},
        {"name": "税务筹划方案", "type": "text", "note": "简要描述"},
        {"name": "筹划方案合规性", "type": "下拉", "choices": ["合规", "存在争议", "不合规"], "key_risk": True},
        {"name": "税务代理机构", "type": "text"},
    ]
    
    write_field_table(ws, fields, start_row=4)


# ============================================================
# Sheet 17 (扩展): 其他补充信息
# ============================================================
def create_other_info_sheet(wb):
    ws = wb.create_sheet("其他补充信息", 22)
    ws.sheet_properties.tabColor = "808080"
    
    ws.merge_cells('A1:G1')
    ws['A1'].value = "十七、其他补充信息（扩展模块）"
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color='808080', end_color='808080', fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：补充其他未尽事宜及特殊关注事项。"
    ws['A2'].font = NOTE_FONT
    
    col_widths = [5, 35, 18, 12, 45, 45, 45]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    
    headers = ["序号", "补充事项", "涉及领域", "重要性", "详细说明", "参考来源", "处理建议"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER
    
    ws.freeze_panes = ws.cell(row=5, column=1)
    
    # Add empty rows for data entry
    for row in range(5, 25):
        for col in range(1, 8):
            cell = ws.cell(row=row, column=col)
            cell.font = FIELD_FONT
            cell.alignment = LEFT_ALIGN
            cell.border = THIN_BORDER
    
    # Add dropdown for importance column
    dv = DataValidation(type="list", formula1='"高,中,低"', allow_blank=True)
    ws.add_data_validation(dv)
    for row in range(5, 25):
        dv.add(ws.cell(row=row, column=4))
    
    # Note at bottom
    note_row = 26
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=7)
    ws.cell(row=note_row, column=1, value="提示：可在此补充其他未尽事宜，如媒体负面报道、特殊经营风险等。").font = NOTE_FONT
    ws.cell(row=note_row, column=1).fill = SUB_HEADER_FILL


# ============================================================
# Sheet 18-22: Phase B 扩展域
# ============================================================
def _extension_sheet(wb, title, tab_color, fields, index):
    ws = wb.create_sheet(title, index)
    ws.sheet_properties.tabColor = tab_color
    ws.merge_cells('A1:G1')
    ws['A1'].value = title
    ws['A1'].font = TITLE_FONT
    ws['A1'].fill = PatternFill(start_color=tab_color, end_color=tab_color, fill_type='solid')
    ws['A1'].alignment = CENTER_ALIGN
    ws.merge_cells('A2:G2')
    ws['A2'].value = "说明：本模块对齐国际 ERM 扩展域，用于董事会级风险评估。"
    ws['A2'].font = NOTE_FONT
    write_field_table(ws, fields, start_row=4)
    return ws


def create_reputation_risk_sheet(wb):
    fields = [
        {"is_group": True, "name": "声誉与品牌"},
        {"name": "舆情监测机制", "type": "下拉", "choices": ["有（系统化）", "有（人工）", "无"], "key_risk": True},
        {"name": "近12个月负面报道次数", "type": "数值", "key_risk": True},
        {"name": "品牌危机事件记录", "type": "下拉", "choices": ["有", "无"]},
        {"name": "ESG评级/评分", "type": "文本", "note": "如 MSCI/商道融绿等"},
        {"name": "客户净推荐值NPS", "type": "数值"},
        {"name": "社交媒体投诉量(件/月)", "type": "数值"},
        {"name": "危机公关响应机制", "type": "下拉", "choices": ["有", "无"]},
    ]
    _extension_sheet(wb, "战略与声誉风险", "7030A0", fields, 17)


def create_bcm_risk_sheet(wb):
    fields = [
        {"is_group": True, "name": "业务连续性 BCM（ISO 22301）"},
        {"name": "业务影响分析BIA", "type": "下拉", "choices": ["已完成", "进行中", "无"], "key_risk": True},
        {"name": "关键系统RTO(小时)", "type": "数值", "key_risk": True, "note": "恢复时间目标"},
        {"name": "关键数据RPO(小时)", "type": "数值", "note": "恢复点目标"},
        {"name": "灾备中心等级", "type": "下拉", "choices": ["同城双活", "异地灾备", "一级", "无"]},
        {"name": "BC演练频次(次/年)", "type": "数值", "key_risk": True},
        {"name": "业务连续性计划BCP", "type": "下拉", "choices": ["有且定期更新", "有", "无"]},
        {"name": "关键数据备份策略", "type": "下拉", "choices": ["完善", "部分", "无"]},
        {"name": "单点故障环节", "type": "文本"},
    ]
    _extension_sheet(wb, "业务连续性风险", "00838F", fields, 18)


def create_data_privacy_sheet(wb):
    fields = [
        {"is_group": True, "name": "数据隐私（PIPL/GDPR）"},
        {"name": "数据分级分类", "type": "下拉", "choices": ["已建立", "部分", "无"], "key_risk": True},
        {"name": "PIPL合规评估", "type": "下拉", "choices": ["合规", "部分合规", "未评估/不合规"], "key_risk": True},
        {"name": "数据出境评估", "type": "下拉", "choices": ["已完成", "需要但未完成", "不涉及"]},
        {"name": "DPIA隐私影响评估", "type": "下拉", "choices": ["有", "无"]},
        {"name": "近3年数据泄露事件数", "type": "数值", "key_risk": True},
        {"name": "用户同意管理机制", "type": "下拉", "choices": ["有", "无"]},
        {"name": "数据保护官DPO", "type": "下拉", "choices": ["有", "无"]},
    ]
    _extension_sheet(wb, "数据隐私合规风险", "1565C0", fields, 19)


def create_governance_risk_sheet(wb):
    fields = [
        {"is_group": True, "name": "公司治理（COSO 治理）"},
        {"name": "董事会风险委员会", "type": "下拉", "choices": ["有", "无"], "key_risk": True},
        {"name": "首席风险官CRO建制", "type": "下拉", "choices": ["有", "无"], "key_risk": True},
        {"name": "三道防线成熟度", "type": "下拉", "choices": ["优化级", "量化管理级", "已定义级", "部分建立", "初始/无"], "key_risk": True},
        {"name": "内部审计独立性", "type": "下拉", "choices": ["强", "一般", "弱/无"]},
        {"name": "风险管理政策", "type": "下拉", "choices": ["有且董事会批准", "有", "无"]},
        {"name": "风险信息披露机制", "type": "下拉", "choices": ["有", "无"]},
        {"name": "关联交易治理", "type": "下拉", "choices": ["完善", "一般", "不完善/无"]},
    ]
    _extension_sheet(wb, "公司治理风险", "1F4E79", fields, 20)


def create_anti_bribery_sheet(wb):
    fields = [
        {"is_group": True, "name": "反贿赂道德合规（ISO 37001）"},
        {"name": "反贿赂合规政策", "type": "下拉", "choices": ["有", "无"], "key_risk": True},
        {"name": "ISO37001认证", "type": "下拉", "choices": ["有", "无"]},
        {"name": "举报机制", "type": "下拉", "choices": ["有（含匿名）", "有", "无"], "key_risk": True},
        {"name": "第三方尽职调查", "type": "下拉", "choices": ["系统化", "部分", "无"]},
        {"name": "礼品招待政策", "type": "下拉", "choices": ["有", "无"]},
        {"name": "合规培训覆盖率(%)", "type": "数值"},
        {"name": "近3年贿赂违规事件数", "type": "数值", "key_risk": True},
    ]
    _extension_sheet(wb, "反贿赂道德合规风险", "C00000", fields, 21)


# ============================================================
# Main - Generate the workbook
# ============================================================
def main():
    wb = create_workbook()
    
    # Core modules (12)
    create_basic_info_sheet(wb)
    create_business_risk_sheet(wb)
    create_financial_risk_sheet(wb)
    create_production_risk_sheet(wb)
    create_safety_risk_sheet(wb)
    create_environmental_risk_sheet(wb)
    create_legal_risk_sheet(wb)
    create_supply_chain_risk_sheet(wb)
    create_technology_risk_sheet(wb)
    create_hr_risk_sheet(wb)
    create_credit_risk_sheet(wb)
    create_overall_assessment_sheet(wb)
    
    # Extension modules (5 original + 5 Phase B)
    create_related_party_sheet(wb)
    create_project_risk_sheet(wb)
    create_industry_policy_risk_sheet(wb)
    create_tax_risk_sheet(wb)
    create_reputation_risk_sheet(wb)
    create_bcm_risk_sheet(wb)
    create_data_privacy_sheet(wb)
    create_governance_risk_sheet(wb)
    create_anti_bribery_sheet(wb)
    create_other_info_sheet(wb)
    
    # Set active sheet to first
    wb.active = 0
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"企业风险信息搜集表_{timestamp}.xlsx"
    
    wb.save(filename)
    print(f"OK file generated: {filename}")
    print(f"Sheets ({len(wb.sheetnames)}): {', '.join(wb.sheetnames)}")
    return filename


if __name__ == "__main__":
    main()