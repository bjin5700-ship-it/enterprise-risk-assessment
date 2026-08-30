# -*- coding: utf-8 -*-
"""
解决方案报告生成器 - Solution Generator
基于风险评估结果，生成针对性的整改建议和解决方案报告
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from datetime import datetime
import os

from risk_engine import AssessmentResult, RiskLevel


def _set_cell_shading(cell, color_hex: str):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


def _add_run(paragraph, text: str, bold=False, size=10, color=None, font_name="微软雅黑"):
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return run


def _risk_color(level: RiskLevel) -> str:
    return {"低风险": "6BCB77", "中等风险": "FFD93D", "高风险": "FF6B6B", "极高风险": "C00000"}.get(level.value, "808080")


# ── 解决方案数据库 ──
SOLUTION_DB = {
    "财务风险": {
        "title": "财务风险解决方案",
        "description": "针对财务结构、盈利能力、流动性等方面的问题，提出系统性改善方案。",
        "immediate": [
            ("现金流紧急管理", "高", "立即盘点现金及应收账款，制定90天现金流预测；暂停非必要资本支出；与银行协商短期授信额度"),
            ("应收账款催收", "高", "成立专项催收小组，对超期账款逐笔跟踪；对恶意拖欠客户启动法律程序"),
        ],
        "short_term": [
            ("优化资本结构", "紧急", "评估债务重组可能性；引入战略投资者或财务投资者；优化长短期负债比例"),
            ("成本控制计划", "高", "全面成本审计，识别浪费环节；推行精益管理；优化采购流程降低采购成本"),
            ("盈利能力提升", "高", "分析产品/服务利润率，淘汰低毛利业务；优化定价策略；开发高附加值产品"),
        ],
        "medium_term": [
            ("财务数字化建设", "中", "实施财务ERP系统；建立财务预警指标体系；实现业财一体化"),
            ("多元化融资渠道", "中", "拓展银行授信、债券发行、股权融资等多种渠道；优化融资结构"),
            ("全面预算管理体系", "中", "建立全面预算管理制度；实施滚动预测；加强预算执行监控"),
        ],
        "kpi": [
            ("流动比率", "≥1.5", "季度"),
            ("速动比率", "≥1.0", "季度"),
            ("净利润率", "≥5%", "年度"),
            ("营收增长率", "≥10%", "年度"),
            ("经营活动现金流", "为正", "月度"),
        ],
    },
    "负债与偿债风险": {
        "title": "负债与偿债风险解决方案",
        "description": "针对负债规模、偿债能力、担保风险等方面提出改善方案。",
        "immediate": [
            ("债务盘点与分类", "高", "全面梳理所有债务，按利率、期限、担保方式分类；识别高成本债务和即将到期债务"),
            ("偿债计划制定", "高", "制定详细的偿债时间表；优先偿还高息债务；与债权人协商展期或重组"),
        ],
        "short_term": [
            ("负债规模控制", "高", "设定负债率上限红线；控制新增负债；通过增资扩股降低杠杆"),
            ("担保风险排查", "高", "全面排查对外担保情况；要求被担保方提供反担保措施；逐步退出非必要担保"),
        ],
        "medium_term": [
            ("债务结构优化", "中", "增加长期负债比例，降低短期偿债压力；利用低息债务置换高息债务"),
            ("建立偿债基金", "中", "设立专项偿债基金账户；按比例定期存入资金"),
        ],
        "kpi": [
            ("资产负债率", "≤60%", "年度"),
            ("DSR（年还款/年收入）", "≤50%", "年度"),
            ("流动比率", "≥1.5", "季度"),
            ("对外担保/净资产", "≤30%", "年度"),
        ],
    },
    "行业与市场风险": {
        "title": "行业与市场风险解决方案",
        "description": "针对行业竞争、市场地位、政策变化等方面提出应对策略。",
        "immediate": [
            ("市场情报体系", "高", "建立行业动态监控机制；定期分析竞争对手策略变化；关注政策法规更新"),
        ],
        "short_term": [
            ("差异化竞争策略", "高", "明确核心竞争优势；聚焦细分市场；打造差异化产品/服务体系"),
            ("客户结构优化", "高", "拓展新客户群体；降低单一客户依赖度；提升客户粘性"),
        ],
        "medium_term": [
            ("新市场拓展", "中", "评估新地域/新行业进入机会；制定市场进入策略；建立本地化团队"),
            ("品牌建设", "中", "制定品牌战略；加大品牌投入；提升行业影响力"),
            ("政策应对机制", "中", "建立政策研究团队；参与行业标准制定；提前布局政策变化"),
        ],
        "kpi": [
            ("市场占有率", "逐年提升", "年度"),
            ("客户数量增长率", "≥10%", "年度"),
            ("新业务收入占比", "≥15%", "年度"),
        ],
    },
    "法律与合规风险": {
        "title": "法律与合规风险解决方案",
        "description": "针对诉讼风险、合规管理、知识产权等方面提出整改方案。",
        "immediate": [
            ("诉讼案件处理", "高", "聘请专业律师团队评估现有案件；制定应诉策略；积极寻求庭外和解"),
            ("合规体检", "高", "全面合规审查，覆盖经营许可、环保、劳动、数据安全等领域"),
        ],
        "short_term": [
            ("合规体系建设", "高", "建立合规管理制度；设立合规部门或岗位；制定合规手册"),
            ("知识产权保护", "高", "清理现有知识产权；及时申请专利/商标；建立知识产权保护机制"),
        ],
        "medium_term": [
            ("合同管理规范化", "中", "建立合同标准化模板；实施合同全生命周期管理；加强合同审核"),
            ("法律风险预警", "中", "建立法律风险数据库；实施法律风险定期评估；建立法律风险预警机制"),
        ],
        "kpi": [
            ("诉讼案件数量", "逐年下降", "年度"),
            ("合规培训覆盖率", "100%", "半年度"),
            ("合同审核率", "100%", "月度"),
        ],
    },
    "税务风险": {
        "title": "税务风险解决方案",
        "description": "针对税务稽查、转让定价、发票管理等方面提出合规方案。",
        "immediate": [
            ("税务稽查应对", "高", "配合税务机关稽查；聘请税务顾问评估风险；准备完整资料应对检查"),
            ("发票管理整改", "高", "全面检查发票管理流程；整改不规范行为；建立发票管理制度"),
        ],
        "short_term": [
            ("转让定价文档准备", "高", "准备完整的转让定价同期资料；评估关联交易定价合理性"),
            ("税务筹划合规审查", "高", "审查现有税务筹划方案合规性；调整存在争议的筹划方案"),
        ],
        "medium_term": [
            ("税务管理数字化", "中", "实施税务管理系统；实现发票电子化；建立税务数据仓库"),
            ("跨境税务管理", "中", "了解跨境税收协定；合理利用税收优惠；防范跨境税务风险"),
        ],
        "kpi": [
            ("税务稽查问题数", "0", "年度"),
            ("发票合规率", "100%", "月度"),
            ("税务申报及时率", "100%", "月度"),
        ],
    },
    "公司治理风险": {
        "title": "公司治理风险解决方案",
        "description": "针对治理结构、内控制度、审计问题等方面提出改进方案。",
        "immediate": [
            ("内控制度建设", "高", "评估现有内控缺陷；优先建立财务、采购、销售等核心流程内控"),
            ("审计问题整改", "高", "针对审计意见制定整改计划；逐项落实整改措施"),
        ],
        "short_term": [
            ("治理结构优化", "高", "完善董事会/监事会构成；引入独立董事；明确三会一层权责"),
            ("关联交易规范", "高", "建立关联交易管理制度；重大关联交易需经董事会/股东会审批"),
        ],
        "medium_term": [
            ("全面内控体系", "中", "建立COSO内控框架；实施内控自评；聘请外部内控审计"),
            ("信息披露透明化", "中", "建立信息披露制度；定期向利益相关方披露经营情况"),
        ],
        "kpi": [
            ("内控缺陷数量", "逐年下降", "年度"),
            ("董事会召开次数", "≥4次/年", "年度"),
            ("审计意见类型", "标准无保留", "年度"),
        ],
    },
    "供应链风险": {
        "title": "供应链风险解决方案",
        "description": "针对供应商/客户集中度、进口依赖、供应链稳定性等问题提出方案。",
        "immediate": [
            ("供应链评估", "高", "全面评估供应链各环节风险；识别关键瓶颈和单点故障"),
        ],
        "short_term": [
            ("供应商多元化", "高", "开发备选供应商；降低前5大供应商占比至60%以下"),
            ("客户多元化", "高", "拓展新客户；降低前5大客户占比至60%以下"),
        ],
        "medium_term": [
            ("供应链数字化", "中", "实施供应链管理系统；建立供应商绩效评价体系；实现供应链可视化"),
            ("战略库存管理", "中", "建立安全库存机制；关键物料保持2-3个月库存"),
            ("本地化替代", "中", "评估进口物料本地化替代方案；降低进口依赖度"),
        ],
        "kpi": [
            ("前5大供应商占比", "≤60%", "年度"),
            ("前5大客户占比", "≤60%", "年度"),
            ("订单交付及时率", "≥95%", "月度"),
        ],
    },
    "技术与信息安全风险": {
        "title": "技术与信息安全风险解决方案",
        "description": "针对研发投入、技术依赖、数据安全等方面提出改进方案。",
        "immediate": [
            ("数据安全评估", "高", "全面数据安全审计；识别数据泄露风险点；立即修补安全漏洞"),
        ],
        "short_term": [
            ("研发投入提升", "高", "制定研发投入计划；确保研发占比不低于行业平均水平"),
            ("知识产权布局", "高", "制定知识产权战略；加大专利申请力度；建立技术壁垒"),
        ],
        "medium_term": [
            ("核心技术自主化", "中", "评估核心技术依赖风险；制定自主替代路线图；加大自主研发"),
            ("信息安全体系建设", "中", "建立ISMS信息安全管理体系；通过ISO27001认证"),
            ("数字化转型", "中", "制定数字化转型路线图；推进智能制造/智慧管理"),
        ],
        "kpi": [
            ("研发投入占比", "≥3%", "年度"),
            ("专利数量增长率", "≥20%", "年度"),
            ("信息安全事件数", "0", "月度"),
        ],
    },
    "人力资源风险": {
        "title": "人力资源风险解决方案",
        "description": "针对人才流失、关键人员依赖、劳动争议等方面提出解决方案。",
        "immediate": [
            ("关键人才保留", "高", "识别关键岗位人才；制定留人计划；提供有竞争力的薪酬和股权激励"),
            ("劳动争议处理", "高", "积极处理现有劳动争议；完善劳动合同；规范用工管理"),
        ],
        "short_term": [
            ("薪酬体系优化", "高", "进行薪酬市场调研；优化薪酬结构；建立绩效导向的激励机制"),
            ("社保合规整改", "高", "全面检查社保缴纳情况；补缴欠款；确保全员合规参保"),
        ],
        "medium_term": [
            ("人才梯队建设", "中", "建立人才储备机制；实施导师制；制定员工职业发展通道"),
            ("企业文化建设", "中", "明确企业价值观；加强内部沟通；提升员工归属感"),
        ],
        "kpi": [
            ("员工流失率", "≤15%", "年度"),
            ("关键岗位空缺率", "≤5%", "月度"),
            ("培训覆盖率", "100%", "年度"),
        ],
    },
    "ESG与可持续发展风险": {
        "title": "ESG与可持续发展风险解决方案",
        "description": "针对环保合规、安全生产、社会责任等方面提出改善方案。",
        "immediate": [
            ("环保整改", "高", "针对环保处罚问题立即整改；建立环保合规管理制度"),
            ("安全生产检查", "高", "全面安全检查；整改安全隐患；完善安全生产制度"),
        ],
        "short_term": [
            ("ESG体系建设", "高", "建立ESG管理框架；设立ESG委员会；制定ESG战略目标"),
            ("碳排放管理", "中", "核算企业碳排放；制定碳减排计划；探索碳交易机会"),
        ],
        "medium_term": [
            ("绿色运营", "中", "推行绿色办公；优化能源结构；发展循环经济"),
            ("社会责任报告", "中", "编制年度ESG/社会责任报告；提升企业社会形象"),
        ],
        "kpi": [
            ("环保处罚次数", "0", "年度"),
            ("安全事故率", "0", "月度"),
            ("碳排放强度", "逐年下降", "年度"),
        ],
    },
    "经营风险": {
        "title": "经营风险解决方案",
        "description": "针对市场地位、客户集中度、营收增长、经营资质等方面提出改善方案。",
        "immediate": [
            ("经营资质排查", "高", "全面排查经营许可证/资质有效期；及时续期缺失或过期的资质文件"),
            ("应收账款催收", "高", "针对超120天应收账款启动专项催收；评估坏账计提充分性"),
        ],
        "short_term": [
            ("客户结构优化", "高", "开发新客户降低单一客户依赖度；目标最大客户占比降至30%以下"),
            ("营收下滑应对", "高", "分析营收下滑原因；制定业务复苏计划；开发新收入增长点"),
        ],
        "medium_term": [
            ("市场地位提升", "中", "制定市场拓展战略；提升品牌影响力；扩大市场份额"),
            ("供应链议价权提升", "中", "优化供应商结构；集中采购提升议价能力；降低原材料成本波动影响"),
        ],
        "kpi": [
            ("前5大客户收入占比", "≤40%", "年度"),
            ("营收增长率", "≥5%", "年度"),
            ("应收账款周转天数", "≤90天", "季度"),
        ],
    },
    "生产运营风险": {
        "title": "生产运营风险解决方案",
        "description": "针对产能利用、设备老化、产品质量、库存管理等方面提出改善方案。",
        "immediate": [
            ("设备抢修与维护", "高", "对故障率高的关键设备立即安排检修；制定设备维护计划"),
            ("质量事故处理", "高", "成立质量事故调查组；追溯问题根源；落实整改措施"),
        ],
        "short_term": [
            ("设备更新计划", "高", "评估老旧设备更新方案；制定设备投资计划；优先替换超15年役龄设备"),
            ("产能优化", "高", "分析产能瓶颈环节；优化生产排程；考虑外协或扩产方案"),
        ],
        "medium_term": [
            ("质量管理体系升级", "中", "推进全面质量管理（TQM）；通过ISO9001认证升级；建立质量追溯系统"),
            ("智能制造转型", "中", "引入自动化/数字化生产设备；建设智能工厂；提升生产效率"),
            ("库存管理优化", "中", "实施精益库存管理；建立安全库存模型；降低库存周转天数"),
        ],
        "kpi": [
            ("设备综合效率(OEE)", "≥85%", "月度"),
            ("产品合格率", "≥98%", "月度"),
            ("库存周转天数", "≤60天", "季度"),
        ],
    },
    "安全生产风险": {
        "title": "安全生产风险解决方案",
        "description": "针对安全管理体系、事故预防、隐患整改等方面提出系统性改善方案。",
        "immediate": [
            ("重大隐患整改", "高", "立即制定重大隐患整改方案；挂牌督办；限期完成整改"),
            ("死亡事故预防", "高", "如发生死亡事故立即停产整顿；全面安全排查；追究管理责任"),
        ],
        "short_term": [
            ("安全生产标准化建设", "高", "推进安全生产标准化达标；完善安全管理制度和操作规程"),
            ("安全培训全覆盖", "高", "确保安全培训覆盖率100%；特种作业人员100%持证上岗"),
        ],
        "medium_term": [
            ("安全管理体系认证", "中", "推进ISO45001职业健康安全管理体系认证"),
            ("应急管理体系建设", "中", "完善应急预案；定期组织应急演练（≥2次/年）；建立应急物资储备"),
            ("安全文化建设", "中", "建立安全绩效考核机制；推行安全行为观察；营造安全第一的企业文化"),
        ],
        "kpi": [
            ("工伤事故次数", "0", "月度"),
            ("百万工时伤害率", "≤5", "年度"),
            ("隐患整改率", "100%", "月度"),
            ("安全培训覆盖率", "100%", "季度"),
        ],
    },
    "环境风险": {
        "title": "环境风险解决方案",
        "description": "针对环评合规、排污许可、环境处罚、排放达标等方面提出整改方案。",
        "immediate": [
            ("环评手续补办", "高", "立即启动环评批复申请；配合环保部门完成环境影响评价"),
            ("排污许可证办理", "高", "立即申请排污许可证；确保排放口规范化；安装在线监测设备"),
        ],
        "short_term": [
            ("环境处罚整改", "高", "针对处罚事项逐项整改；建立环保合规管理制度；避免再次受罚"),
            ("排放达标整治", "高", "升级治污设施；确保排放达标率100%；建立排放日常监测机制"),
        ],
        "medium_term": [
            ("环境管理体系认证", "中", "推进ISO14001环境管理体系认证；建立环境管理长效机制"),
            ("环境应急预案完善", "中", "制定/修订环境应急预案；定期组织应急演练；建立应急物资储备"),
            ("绿色低碳转型", "中", "制定碳减排路线图；优化能源结构；探索清洁能源替代方案"),
        ],
        "kpi": [
            ("排放达标率", "100%", "月度"),
            ("环境处罚次数", "0", "年度"),
            ("碳排放强度", "逐年下降", "年度"),
        ],
    },
    "信用风险": {
        "title": "信用风险解决方案",
        "description": "针对担保风险、付款信用、税务信用、行政处罚等方面提出改善方案。",
        "immediate": [
            ("担保风险排查", "高", "全面排查对外担保余额；评估被担保方偿债能力；要求追加反担保措施"),
            ("行政处罚应对", "高", "针对行政处罚事项立即整改；建立合规检查机制避免再次受罚"),
        ],
        "short_term": [
            ("税务信用修复", "高", "排查税务不合规事项；及时补缴欠税；恢复税务信用等级"),
            ("逾期付款整改", "高", "制定逾期付款清偿计划；优化付款流程；恢复供应商信任"),
        ],
        "medium_term": [
            ("信用管理体系", "中", "建立客户信用评估体系；实施信用额度管理；完善应收款管理制度"),
            ("关联交易规范", "中", "规范关联交易定价机制；确保关联交易公允性；降低关联交易占比"),
        ],
        "kpi": [
            ("税务信用等级", "B级以上", "年度"),
            ("坏账率", "≤2%", "年度"),
            ("供应商付款周期", "≤60天", "季度"),
        ],
    },
    "关联方与集团风险": {
        "title": "关联方与集团风险解决方案",
        "description": "针对关联交易、资金占用、集团担保等方面提出规范方案。",
        "immediate": [
            ("关联方资金占用清理", "高", "立即清查关联方资金占用情况；制定资金回收计划；限期归还"),
            ("集团担保规范", "高", "全面梳理集团内部担保；评估担保风险；建立担保审批制度"),
        ],
        "short_term": [
            ("关联交易规范", "高", "完善关联交易管理制度；确保关联交易定价公允；按规定履行信息披露"),
            ("关联关系梳理", "高", "全面梳理关联企业清单；理清股权和控制关系；规范关联企业管理"),
        ],
        "medium_term": [
            ("集团资金集中管理", "中", "建立资金池集中管理；优化内部资金调配；降低资金占用风险"),
            ("关联方风险监控", "中", "建立关联方风险预警机制；定期评估关联方信用状况"),
        ],
        "kpi": [
            ("关联方资金占用余额", "逐年下降", "季度"),
            ("关联交易占比", "≤20%", "年度"),
            ("集团担保/净资产", "≤30%", "年度"),
        ],
    },
    "项目投资风险": {
        "title": "项目投资风险解决方案",
        "description": "针对在建项目管理、投资效益、融资需求等方面提出管控方案。",
        "immediate": [
            ("在建项目评估", "高", "全面评估在建项目进度和预算执行情况；识别偏差原因；制定纠偏措施"),
            ("投资减值评估", "高", "评估投资项目的减值风险；足额计提减值准备"),
        ],
        "short_term": [
            ("项目进度管控", "高", "制定项目进度追赶计划；加强项目调度；确保关键节点按时完成"),
            ("预算控制", "高", "严格预算审批；控制超支项目支出；建立预算偏差预警机制"),
        ],
        "medium_term": [
            ("投资决策机制", "中", "完善投资决策流程；建立项目评估标准；加强投前尽职调查"),
            ("投后管理", "中", "建立投后管理制度；定期跟踪投资效益；及时退出低效投资"),
            ("融资规划", "中", "制定中长期融资计划；拓展融资渠道；确保项目资金保障"),
        ],
        "kpi": [
            ("项目进度偏差", "≤10%", "月度"),
            ("预算偏差", "≤10%", "月度"),
            ("投资收益率", "≥5%", "年度"),
        ],
    },
    "战略与声誉风险": {
        "title": "战略与声誉风险解决方案",
        "description": "建立舆情监测、品牌危机应对与ESG声誉管理体系。",
        "immediate": [
            ("舆情监测启动", "P0", "部署舆情监测系统；设定负面关键词预警；24小时响应机制"),
            ("危机公关预案", "P0", "更新危机公关手册；明确发言人与媒体应对流程"),
        ],
        "short_term": [
            ("ESG披露提升", "P1", "对标行业ESG评级要求；补齐环境社会治理披露"),
            ("客户口碑改善", "P1", "NPS调研与投诉闭环；关键客户回访计划"),
        ],
        "medium_term": [
            ("声誉风险KRI", "P2", "建立声誉风险仪表盘；季度董事会汇报"),
        ],
        "kpi": [("负面报道次数", "≤1次/季", "季度"), ("NPS", "≥30", "半年度")],
    },
    "业务连续性风险": {
        "title": "业务连续性 BCM 解决方案",
        "description": "对齐 ISO 22301，完善 BIA、BCP 与灾备演练。",
        "immediate": [
            ("BIA关键业务识别", "P0", "识别关键业务流程；定义RTO/RPO目标"),
            ("应急指挥体系", "P0", "成立BCM小组；明确升级路径与联系人"),
        ],
        "short_term": [
            ("灾备验证", "P1", "完成核心系统灾备切换测试；修复单点故障"),
            ("BC演练", "P1", "至少1次全要素演练；输出改进清单"),
        ],
        "medium_term": [
            ("BCP年度更新", "P2", "结合业务变化更新BCP；纳入新员工培训"),
        ],
        "kpi": [("BC演练", "≥2次/年", "年度"), ("RTO达标率", "100%", "年度")],
    },
    "数据隐私合规风险": {
        "title": "数据隐私合规解决方案",
        "description": "PIPL/GDPR 合规与数据安全体系建设。",
        "immediate": [
            ("数据分级", "P0", "完成数据资产盘点与分级分类"),
            ("泄露应急响应", "P0", "建立数据泄露72小时通报流程"),
        ],
        "short_term": [
            ("PIPL评估", "P1", "完成个人信息保护影响评估；整改差距项"),
            ("出境合规", "P1", "数据出境安全评估/标准合同备案"),
        ],
        "medium_term": [
            ("隐私治理体系", "P2", "设立DPO；年度隐私培训与审计"),
        ],
        "kpi": [("数据泄露事件", "0", "年度"), ("DPIA覆盖", "100%高风险处理", "年度")],
    },
    "公司治理风险": {
        "title": "公司治理与三道防线解决方案",
        "description": "强化董事会风险治理与COSO三道防线建设。",
        "immediate": [
            ("风控委员会", "P0", "董事会设立/激活风险管理委员会"),
            ("风险政策", "P0", "发布风险管理政策并由董事会批准"),
        ],
        "short_term": [
            ("CRO建制", "P1", "明确首席风险官职责与汇报线"),
            ("三道防线评估", "P1", "开展三道防线成熟度自评与差距整改"),
        ],
        "medium_term": [
            ("治理披露", "P2", "完善风险信息披露；年度治理报告"),
        ],
        "kpi": [("董事会风险议题", "≥4次/年", "年度"), ("内审独立性", "达标", "年度")],
    },
    "反贿赂道德合规风险": {
        "title": "反贿赂道德合规解决方案",
        "description": "ISO 37001 反贿赂体系与第三方合规管理。",
        "immediate": [
            ("反贿赂政策", "P0", "发布反贿赂政策；高层承诺声明"),
            ("举报渠道", "P0", "开通匿名举报热线/邮箱；保护举报人"),
        ],
        "short_term": [
            ("第三方DD", "P1", "高风险第三方尽职调查100%覆盖"),
            ("合规培训", "P1", "全员反贿赂培训；销售/采购重点考核"),
        ],
        "medium_term": [
            ("ISO37001认证", "P2", "推进反贿赂管理体系认证"),
        ],
        "kpi": [("贿赂违规", "0", "年度"), ("合规培训覆盖率", "≥95%", "年度")],
    },
}


def generate_solution_report(result: AssessmentResult, output_path: str = None) -> str:
    """生成解决方案报告（Word格式）"""
    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # ── 封面 ──
    for _ in range(6):
        doc.add_paragraph()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(title, "企业风险解决方案报告", bold=True, size=26, color=(0, 100, 0))

    doc.add_paragraph()

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(sub, result.company_name, bold=True, size=18, color=(46, 117, 182))

    doc.add_paragraph()
    doc.add_paragraph()

    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(info, f"报告日期：{result.report_date}", size=12, color=(100, 100, 100))

    info2 = doc.add_paragraph()
    info2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(info2, "本报告基于风险评估结果，针对各维度风险提出系统性整改建议", size=11, color=(130, 130, 130))

    info3 = doc.add_paragraph()
    info3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(info3, "建议按「紧急→短期→中期」优先级逐步落实", size=10, color=(180, 180, 180))

    doc.add_page_break()

    # ── 目录 ──
    toc_title = doc.add_heading("目  录", level=1)
    for run in toc_title.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    toc_items = [
        "一、概述",
        "二、整改优先级矩阵",
        "三、各维度详细解决方案",
    ]
    for dim_name in SOLUTION_DB:
        toc_items.append(f"    {dim_name}解决方案")
    toc_items.append("四、KPI监控指标汇总")
    toc_items.append("五、实施路线图")

    for item in toc_items:
        p = doc.add_paragraph()
        _add_run(p, item, size=12, color=(50, 50, 50))

    doc.add_page_break()

    # ── 一、概述 ──
    h1 = doc.add_heading("一、概述", level=1)
    for run in h1.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    p = doc.add_paragraph()
    _add_run(p, "本解决方案报告基于", size=11)
    _add_run(p, result.company_name, bold=True, size=11)
    _add_run(p, f"的风险评估结果（综合评分 {result.overall_score:.2f}/4.00，{result.overall_level.value}），针对各风险维度提出系统性整改建议和解决方案。", size=11)

    p = doc.add_paragraph()
    _add_run(p, "报告结构：", bold=True, size=11)
    p = doc.add_paragraph(style="List Bullet")
    _add_run(p, "每个风险维度按「紧急措施→短期措施→中期措施」分层给出建议", size=10)
    p = doc.add_paragraph(style="List Bullet")
    _add_run(p, "每个维度附KPI监控指标，便于跟踪整改效果", size=10)
    p = doc.add_paragraph(style="List Bullet")
    _add_run(p, "最后提供整体实施路线图，明确时间节点和责任人", size=10)

    doc.add_page_break()

    # ── 二、整改优先级矩阵 ──
    h2 = doc.add_heading("二、整改优先级矩阵", level=1)
    for run in h2.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    p = doc.add_paragraph()
    _add_run(p, "以下按风险评分从高到低排列，评分越高的维度越应优先处理：", size=11)

    doc.add_paragraph()

    sorted_dims = sorted(result.dimensions.values(), key=lambda d: d.score, reverse=True)
    pri_table = doc.add_table(rows=len(sorted_dims) + 1, cols=5, style="Table Grid")
    pri_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    pri_headers = ["优先级", "风险维度", "评分", "风险等级", "建议整改周期"]
    for i, h in enumerate(pri_headers):
        cell = pri_table.cell(0, i)
        _add_run(cell.paragraphs[0], h, bold=True, size=10, color=(255, 255, 255))
        _set_cell_shading(cell, "00B050")

    for r_idx, dim in enumerate(sorted_dims, 1):
        if dim.score >= 3.0:
            priority = "P0-紧急"
            cycle = "立即启动，1个月内"
        elif dim.score >= 2.0:
            priority = "P1-高优先"
            cycle = "1-3个月内"
        elif dim.score >= 1.5:
            priority = "P2-中优先"
            cycle = "3-6个月内"
        else:
            priority = "P3-常规"
            cycle = "6-12个月内"

        row_data = [priority, dim.name, f"{dim.score:.2f}", dim.level.value, cycle]
        for c_idx, val in enumerate(row_data):
            cell = pri_table.cell(r_idx, c_idx)
            _add_run(cell.paragraphs[0], val, size=10)
            if c_idx == 0:
                color_map = {"P0": "C00000", "P1": "FF6B6B", "P2": "FFD93D", "P3": "6BCB77"}
                prefix = priority.split("-")[0]
                _set_cell_shading(cell, color_map.get(prefix, "808080"))

    doc.add_page_break()

    # ── 三、各维度解决方案 ──
    h3 = doc.add_heading("三、各维度详细解决方案", level=1)
    for run in h3.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    for dim_name, solution in SOLUTION_DB.items():
        dim = result.dimensions.get(dim_name)
        dim_score = dim.score if dim else 0
        dim_level = dim.level.value if dim else "未评估"

        # 维度标题
        h_dim = doc.add_heading(f"  {solution['title']}", level=2)
        for run in h_dim.runs:
            run.font.color.rgb = RGBColor(46, 117, 182)

        p = doc.add_paragraph()
        _add_run(p, f"当前评分：{dim_score:.2f}/4.00  |  风险等级：{dim_level}", size=11,
                 color=(180, 0, 0) if dim and dim.score >= 2.0 else (0, 100, 0))

        p = doc.add_paragraph()
        _add_run(p, solution["description"], size=10, color=(80, 80, 80))

        # 紧急措施
        if solution.get("immediate"):
            p = doc.add_paragraph()
            _add_run(p, "▎紧急措施（立即执行）", bold=True, size=11, color=(200, 0, 0))
            for item_name, priority, detail in solution["immediate"]:
                p = doc.add_paragraph()
                _add_run(p, f"  ■ {item_name}", bold=True, size=10)
                _add_run(p, f"  [{priority}]", size=9, color=(200, 0, 0))
                p2 = doc.add_paragraph()
                _add_run(p2, f"    {detail}", size=10, color=(60, 60, 60))

        # 短期措施
        if solution.get("short_term"):
            p = doc.add_paragraph()
            _add_run(p, "▎短期措施（1-3个月）", bold=True, size=11, color=(200, 100, 0))
            for item_name, priority, detail in solution["short_term"]:
                p = doc.add_paragraph()
                _add_run(p, f"  ■ {item_name}", bold=True, size=10)
                _add_run(p, f"  [{priority}]", size=9, color=(200, 100, 0))
                p2 = doc.add_paragraph()
                _add_run(p2, f"    {detail}", size=10, color=(60, 60, 60))

        # 中期措施
        if solution.get("medium_term"):
            p = doc.add_paragraph()
            _add_run(p, "▎中期措施（3-12个月）", bold=True, size=11, color=(0, 100, 0))
            for item_name, priority, detail in solution["medium_term"]:
                p = doc.add_paragraph()
                _add_run(p, f"  ■ {item_name}", bold=True, size=10)
                _add_run(p, f"  [{priority}]", size=9, color=(0, 100, 0))
                p2 = doc.add_paragraph()
                _add_run(p2, f"    {detail}", size=10, color=(60, 60, 60))

        # KPI
        if solution.get("kpi"):
            p = doc.add_paragraph()
            _add_run(p, "▎KPI监控指标", bold=True, size=11, color=(46, 117, 182))
            kpi_table = doc.add_table(rows=len(solution["kpi"]) + 1, cols=3, style="Table Grid")
            kpi_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, h in enumerate(["指标", "目标值", "监控频率"]):
                cell = kpi_table.cell(0, i)
                _add_run(cell.paragraphs[0], h, bold=True, size=9, color=(255, 255, 255))
                _set_cell_shading(cell, "4472C4")
            for r_idx, (kpi_name, target, freq) in enumerate(solution["kpi"], 1):
                _add_run(kpi_table.cell(r_idx, 0).paragraphs[0], kpi_name, size=9)
                _add_run(kpi_table.cell(r_idx, 1).paragraphs[0], target, size=9)
                _add_run(kpi_table.cell(r_idx, 2).paragraphs[0], freq, size=9)

        doc.add_paragraph()
        doc.add_paragraph()

    doc.add_page_break()

    # ── 四、KPI监控指标汇总 ──
    h4 = doc.add_heading("四、KPI监控指标汇总", level=1)
    for run in h4.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    p = doc.add_paragraph()
    _add_run(p, "以下汇总所有维度的KPI监控指标，建议建立定期跟踪机制：", size=11)

    doc.add_paragraph()

    all_kpis = []
    for dim_name, solution in SOLUTION_DB.items():
        if solution.get("kpi"):
            for kpi_name, target, freq in solution["kpi"]:
                all_kpis.append((dim_name, kpi_name, target, freq))

    kpi_table = doc.add_table(rows=len(all_kpis) + 1, cols=4, style="Table Grid")
    kpi_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    kpi_headers = ["所属维度", "指标", "目标值", "监控频率"]
    for i, h in enumerate(kpi_headers):
        cell = kpi_table.cell(0, i)
        _add_run(cell.paragraphs[0], h, bold=True, size=9, color=(255, 255, 255))
        _set_cell_shading(cell, "00B050")

    for r_idx, (dim_name, kpi_name, target, freq) in enumerate(all_kpis, 1):
        _add_run(kpi_table.cell(r_idx, 0).paragraphs[0], dim_name, size=9)
        _add_run(kpi_table.cell(r_idx, 1).paragraphs[0], kpi_name, size=9)
        _add_run(kpi_table.cell(r_idx, 2).paragraphs[0], target, size=9)
        _add_run(kpi_table.cell(r_idx, 3).paragraphs[0], freq, size=9)

    doc.add_page_break()

    # ── 五、实施路线图 ──
    h5 = doc.add_heading("五、实施路线图", level=1)
    for run in h5.runs:
        run.font.color.rgb = RGBColor(0, 100, 0)

    p = doc.add_paragraph()
    _add_run(p, "建议按以下三个阶段推进整改工作：", size=11)

    phases = [
        ("第一阶段：紧急处置", "第1个月",
         [
             "启动所有P0优先级整改事项",
             "成立风险管理委员会",
             "建立风险监控日报/周报机制",
             "完成现金流紧急管理",
             "启动重大诉讼/稽查应对",
             "完成关键人才保留方案",
         ]),
        ("第二阶段：体系搭建", "第2-3个月",
         [
             "完成所有P1优先级整改事项",
             "建立各维度管理制度和流程",
             "启动合规体系、内控体系建设",
             "完成供应商/客户多元化方案",
             "启动数字化转型项目",
             "建立KPI监控体系",
         ]),
        ("第三阶段：持续优化", "第4-12个月",
         [
             "完成P2/P3优先级整改事项",
             "全面运行新的管理体系",
             "定期进行风险复评（季度）",
             "持续优化和改进",
             "编制年度风险管理报告",
             "形成风险管理长效机制",
         ]),
    ]

    for phase_name, timeline, items in phases:
        p = doc.add_paragraph()
        _add_run(p, f"▎{phase_name}", bold=True, size=12, color=(31, 78, 121))
        _add_run(p, f"  ({timeline})", size=10, color=(100, 100, 100))

        for item in items:
            p = doc.add_paragraph(style="List Bullet")
            _add_run(p, item, size=10)

        doc.add_paragraph()

    # 结尾
    p = doc.add_paragraph()
    _add_run(p, "风险管理是一个持续改进的过程，建议每季度进行一次风险复评，每年进行一次全面风险评估，", size=11)
    _add_run(p, "确保风险管理的持续有效性。", size=11)

    # ── 保存 ──
    if output_path is None:
        output_dir = r"D:\_Work\02_Documents\信息搜集表格"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"企业风险解决方案报告_{result.company_name}_{timestamp}.docx")

    doc.save(output_path)
    print(f"✓ 解决方案报告已生成: {output_path}")