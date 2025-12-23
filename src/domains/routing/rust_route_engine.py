"""
Rust 路由引擎适配器

目的：
- 让现有依赖 `DatabaseRouteEngine.plan_route()` 的业务代码（如驻扎点选址）
  在不改动核心调用逻辑的情况下，优先走 Rust 离线路径规划。
- 避免在路径规划阶段强依赖 PostGIS/数据库空间查询。
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.routing.schemas import Point as ServicePoint
from src.domains.routing.service import RoutePlanningService
from src.planning.algorithms.routing.db_route_engine import (
    RouteResult as EngineRouteResult,
    Point as EnginePoint,
)
from src.planning.algorithms.routing.types import InfeasiblePathError


class RustRouteEngine:
    """
    以 `DatabaseRouteEngine` 的接口形式暴露 Rust 规划能力。

    仅实现当前业务实际使用字段：distance/duration/path_points。
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self._service = RoutePlanningService(db)

    async def plan_route(
        self,
        *,
        start: EnginePoint,
        end: EnginePoint,
        vehicle: object,  # 兼容 DatabaseRouteEngine 签名；Rust 侧当前不强依赖车辆能力
        scenario_id: Optional[UUID] = None,  # noqa: ARG002 - 兼容签名
        search_radius_km: float = 100.0,  # noqa: ARG002 - 兼容签名
    ) -> EngineRouteResult:
        result = await self._service.plan_route(
            origin=ServicePoint(lon=start.lon, lat=start.lat),
            destination=ServicePoint(lon=end.lon, lat=end.lat),
        )
        if not result.success:
            raise InfeasiblePathError(result.error_message or "rust route planning failed")

        points = result.polyline or [ServicePoint(lon=start.lon, lat=start.lat), ServicePoint(lon=end.lon, lat=end.lat)]
        engine_points = [EnginePoint(lon=p.lon, lat=p.lat) for p in points]

        warnings: list[str] = []
        if result.source != "internal":
            warnings.append(f"route_source={result.source}")

        return EngineRouteResult(
            path_points=engine_points,
            distance_m=float(result.total_distance_m),
            duration_seconds=float(result.total_duration_s),
            path_edges=[],
            blocked_by_disaster=False,
            warnings=warnings,
        )

