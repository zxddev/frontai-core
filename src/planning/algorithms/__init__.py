"""
应急救灾协同决策系统 - 算法模块

模块结构:
- assessment/  灾情评估与预测
- matching/    能力匹配与资源选择  
- routing/     路径规划与调度
- optimization/ 多目标优化
- arbitration/ 冲突消解与仲裁
- scheduling/  任务调度
- simulation/  仿真评估
"""

from .base import AlgorithmBase, AlgorithmResult, AlgorithmStatus, Location, TimeWindow

# 评估模块
from .assessment import DisasterAssessment, SecondaryHazardPredictor, LossEstimator, ConfirmationScorer

# 匹配模块
from .matching import RescueTeamSelector, VehicleCargoMatcher, CapabilityMatcher

# 路径模块
from .routing import VehicleRoutingPlanner, OffroadEngine

# 优化模块
from .optimization import PymooOptimizer, MCTSPlanner

# 仲裁模块
from .arbitration import ConflictResolver, SceneArbitrator

# 调度模块
from .scheduling import TaskScheduler

# 仿真模块
from .simulation import DiscreteEventSimulator

__all__ = [
    # 基类
    "AlgorithmBase",
    "AlgorithmResult",
    "AlgorithmStatus",
    "Location",
    "TimeWindow",
    # 评估
    "DisasterAssessment",
    "SecondaryHazardPredictor", 
    "LossEstimator",
    "ConfirmationScorer",
    # 匹配
    "RescueTeamSelector",
    "VehicleCargoMatcher",
    "CapabilityMatcher",
    # 路径
    "VehicleRoutingPlanner",
    "OffroadEngine",
    # 优化
    "PymooOptimizer",
    "MCTSPlanner",
    # 仲裁
    "ConflictResolver",
    "SceneArbitrator",
    # 调度
    "TaskScheduler",
    # 仿真
    "DiscreteEventSimulator",
]
