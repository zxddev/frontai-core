"""
能力匹配与资源选择模块

功能:
1. 车辆-物资匹配 - 根据物资类型、距离选择最优车辆
2. 能力-资源CSP匹配 - 约束满足问题求解

注: RescueTeamSelector 已删除，其功能由 EmergencyAI Agent 的
    reasoning.py (能力推断) + ResourceSchedulingCore (资源调度) 替代
"""

from .vehicle_cargo_matcher import VehicleCargoMatcher
from .capability_matcher import CapabilityMatcher

__all__ = [
    "VehicleCargoMatcher", 
    "CapabilityMatcher"
]
