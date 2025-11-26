"""
能力匹配与资源选择模块

功能:
1. 救援队伍智能选择 - 根据灾情特征选择最佳队伍组合
2. 车辆-物资匹配 - 根据物资类型、距离选择最优车辆
3. 能力-资源CSP匹配 - 约束满足问题求解
"""

from .rescue_team_selector import RescueTeamSelector, CapabilityMappingProvider
from .vehicle_cargo_matcher import VehicleCargoMatcher
from .capability_matcher import CapabilityMatcher

__all__ = [
    "RescueTeamSelector", 
    "CapabilityMappingProvider",
    "VehicleCargoMatcher", 
    "CapabilityMatcher"
]
