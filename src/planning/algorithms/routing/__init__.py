"""
路径规划与调度模块

功能:
1. 多车辆路径规划(VRP) - 多车辆最优路径
2. 数据库路网规划 - 基于PostgreSQL路网的A*避障规划
3. 越野路径规划 - DEM坡度+水域+障碍物约束的A*（待改造）
"""

from .vehicle_routing import VehicleRoutingPlanner
from .offroad_engine import OffroadEngine, OffroadConfig
from .db_route_engine import (
    DatabaseRouteEngine,
    VehicleCapability,
    RouteEdge,
    DisasterArea,
    RouteResult,
    load_vehicle_capability,
    get_team_primary_vehicle,
)
from .bootstrap import RoutingResources, load_routing_resources, load_water_polygons
from .types import (
    Point,
    CapabilityMetrics,
    CapabilityProfileLocal,
    Obstacle,
    Audit,
    PathCandidate,
    PathSearchMetrics,
    PathPlanningError,
    MissingDataError,
    InfeasiblePathError,
    dedupe,
    slope_deg_to_percent,
    slope_percent_to_deg,
)

__all__ = [
    # 多车VRP调度
    "VehicleRoutingPlanner",
    # 越野路径规划（待改造）
    "OffroadEngine",
    "OffroadConfig",
    # 数据库路网规划
    "DatabaseRouteEngine",
    "VehicleCapability",
    "RouteEdge",
    "DisasterArea",
    "RouteResult",
    "load_vehicle_capability",
    "get_team_primary_vehicle",
    # 资源加载
    "RoutingResources",
    "load_routing_resources",
    "load_water_polygons",
    # 类型
    "Point",
    "CapabilityMetrics",
    "CapabilityProfileLocal",
    "Obstacle",
    "Audit",
    "PathCandidate",
    "PathSearchMetrics",
    "PathPlanningError",
    "MissingDataError",
    "InfeasiblePathError",
    "dedupe",
    # 工具函数
    "slope_deg_to_percent",
    "slope_percent_to_deg",
]
