"""
路径规划智能体

基于LangGraph实现的动态路径规划智能体，采用双频架构：
- 高频层：纯算法计算（A*/VRP）
- 低频层：LLM决策（场景分析、策略选择、结果评估）

特性：
1. LLM参与场景理解和策略决策
2. 评估-重规划循环
3. 支持自然语言交互
4. 生成路径解释

参考论文：
- DynamicRouteGPT (2024): 基于LLM的实时多车辆动态导航
- PlanAgent (2024): 多模态LLM Agent闭环规划
- LeAD (2025): 双频架构LLM增强自动驾驶规划
"""
from .agent import invoke
from .state import (
    RoutePlanningState,
    Point,
    VehicleInfo,
    TaskPoint,
    RouteConstraint,
    DisasterContext,
    PlanningStrategy,
    create_initial_state,
)
from .graph import get_route_planning_graph, build_route_planning_graph

__all__ = [
    # 入口函数
    "invoke",
    # 状态类型
    "RoutePlanningState",
    "Point",
    "VehicleInfo",
    "TaskPoint",
    "RouteConstraint",
    "DisasterContext",
    "PlanningStrategy",
    "create_initial_state",
    # 图
    "get_route_planning_graph",
    "build_route_planning_graph",
]
