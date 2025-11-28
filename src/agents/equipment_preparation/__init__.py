"""
出发前装备准备智能体 (Equipment Preparation Agent)

功能：
- 根据灾情自动分析所需装备
- 匹配仓库中的设备、模块、物资
- 生成装备推荐清单（含选择理由）
- 识别物资缺口并告警
- 生成装载方案建议

与 emergency_ai 的区别：
- emergency_ai: 现场救援阶段，调配现场可用资源
- equipment_preparation: 出发前准备阶段，从仓库选择携带装备
"""

from .graph import (
    build_equipment_preparation_graph,
    get_equipment_preparation_graph,
)
from .state import EquipmentPreparationState

__all__ = [
    "build_equipment_preparation_graph",
    "get_equipment_preparation_graph",
    "EquipmentPreparationState",
]
