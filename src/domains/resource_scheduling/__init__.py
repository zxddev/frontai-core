"""
资源调度模块

跨人装物多维度编组与再分配系统:
- 人员调度（队伍选择 + 路径规划）
- 装备调度（无人设备 + 传统装备）
- 物资调度（消耗品）
- 车辆装载优化

三层架构:
- Layer 1: Core (纯算法)
- Layer 2: Service (API封装)
- Layer 3: Agent (LangGraph, 可选)
"""

from .equipment_schemas import (
    EquipmentType,
    EquipmentPriority,
    LocationType,
    EquipmentRequirement,
    EquipmentCandidate,
    EquipmentAllocation,
    EquipmentSchedulingResult,
    SupplyRequirement,
    SupplyAllocation,
    SupplySchedulingResult,
)

from .equipment_scheduler import EquipmentScheduler
from .demand_calculator import SupplyDemandCalculator, DemandCalculationResult

from .schemas import (
    PriorityLevel,
    CapabilityRequirement,
    SchedulingConstraints,
    SchedulingObjectives,
    ResourceCandidate,
    ResourceType,
    RouteInfo,
    ResourceAllocation,
    SchedulingSolution,
    SchedulingResult,
)

from .core import ResourceSchedulingCore

from .integrated_core import (
    DisasterContext,
    IntegratedSchedulingRequest,
    IntegratedSchedulingResult,
    IntegratedResourceSchedulingCore,
)

__all__ = [
    # 枚举
    "EquipmentType",
    "EquipmentPriority",
    "LocationType",
    "ResourceType",
    "PriorityLevel",
    # 装备数据模型
    "EquipmentRequirement",
    "EquipmentCandidate",
    "EquipmentAllocation",
    "EquipmentSchedulingResult",
    "SupplyRequirement",
    "SupplyAllocation",
    "SupplySchedulingResult",
    "DemandCalculationResult",
    # 队伍调度数据模型
    "CapabilityRequirement",
    "SchedulingConstraints",
    "SchedulingObjectives",
    "ResourceCandidate",
    "RouteInfo",
    "ResourceAllocation",
    "SchedulingSolution",
    "SchedulingResult",
    # 整合调度数据模型
    "DisasterContext",
    "IntegratedSchedulingRequest",
    "IntegratedSchedulingResult",
    # 调度器
    "EquipmentScheduler",
    "SupplyDemandCalculator",
    "ResourceSchedulingCore",
    "IntegratedResourceSchedulingCore",
]
