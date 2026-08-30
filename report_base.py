# -*- coding: utf-8 -*-
"""
报告基类 - Report Base
定义所有格式报告生成器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Optional
from risk_engine import AssessmentResult


class BaseReportGenerator(ABC):
    """所有报告生成器的抽象基类"""

    def __init__(self, result: AssessmentResult, output_path: Optional[str] = None):
        self.result = result
        self.output_path = output_path

    @abstractmethod
    def generate(self) -> str:
        """生成报告，返回输出文件路径"""
        ...

    def _sorted_dimensions(self):
        """按评分从高到低排序的维度列表"""
        return sorted(
            self.result.dimensions.values(),
            key=lambda d: d.score,
            reverse=True,
        )

    def _all_key_risks(self):
        """所有关键风险点列表"""
        risks = []
        for dim in self._sorted_dimensions():
            for kr in dim.key_risks:
                risks.append((dim.name, kr))
        return risks

    @staticmethod
    def _risk_color_hex(level_value: str) -> str:
        return {
            "低风险": "#6BCB77",
            "中等风险": "#FFD93D",
            "高风险": "#FF6B6B",
            "极高风险": "#C00000",
        }.get(level_value, "#808080")

    @staticmethod
    def _suggest_action(dim) -> str:
        s = dim.score
        if s >= 3.5:
            return "立即整改，最高优先级"
        elif s >= 2.5:
            return "制定专项整改计划"
        elif s >= 1.5:
            return "持续监控，完善制度"
        else:
            return "维持现状，定期复查"
