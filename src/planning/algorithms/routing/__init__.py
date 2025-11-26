"""
路径规划与调度模块

功能:
1. 多车辆路径规划(VRP) - 多车辆最优路径
2. 物资调度优化 - 多仓库多目的地调度
3. 全地形路径规划 - DEM坡度+水域+障碍物约束的A*
4. 数据库路网规划 - 基于PostgreSQL路网的A*避障规划
"""

from .vehicle_routing import VehicleRoutingPlanner
from .logistics_scheduler import LogisticsScheduler
from .offroad_engine import OffroadEngine, OffroadConfig
from .road_engine import RoadNetworkEngine, RoadEngineConfig
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
)

__all__ = [
    "VehicleRoutingPlanner",
    "LogisticsScheduler",
    # 全地形路径规划
    "OffroadEngine",
    "OffroadConfig",
    "RoadNetworkEngine",
    "RoadEngineConfig",
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
]
