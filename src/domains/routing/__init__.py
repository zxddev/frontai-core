"""路径规划服务模块"""

from .service import RoutePlanningService, get_routing_service
from .schemas import RouteResult, RouteSegment, Point, AvoidArea
from .router import router as routing_router
from .unified_service import UnifiedRoutePlanningService
from .air_service import AirRoutePlanningService, get_air_routing_service
from .risk_detection import RiskDetectionService, RiskAreaInfo
from .alternative_routes import AlternativeRoutesService, AlternativeRoute
from .planned_route_repository import PlannedRouteRepository, PlannedRouteRecord
from .planned_route_service import PlannedRouteService

__all__ = [
    # 原有导出
    "RoutePlanningService",
    "get_routing_service",
    "RouteResult",
    "RouteSegment",
    "Point",
    "AvoidArea",
    # 统一路径规划
    "routing_router",
    "UnifiedRoutePlanningService",
    "AirRoutePlanningService",
    "get_air_routing_service",
    # 风险检测和绕行方案
    "RiskDetectionService",
    "RiskAreaInfo",
    "AlternativeRoutesService",
    "AlternativeRoute",
    # 路径存储
    "PlannedRouteRepository",
    "PlannedRouteRecord",
    "PlannedRouteService",
]
