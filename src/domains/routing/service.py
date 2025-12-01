"""
路径规划服务

封装高德API + 内部路径规划的fallback机制。
遵循架构规范：Agent Node → Service → Algorithm/External API
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point, RouteResult, RouteSegment, AvoidArea
from src.infra.clients.amap.route_planning import (
    amap_route_planning_async,
    amap_route_planning_with_avoidance_async,
)

logger = logging.getLogger(__name__)


class RoutePlanningService:
    """
    路径规划服务
    
    提供统一的路径规划接口，内部实现：
    1. 优先调用高德API
    2. 高德失败时fallback到内部DatabaseRouteEngine
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        self._db = db
    
    async def plan_route(
        self,
        origin: Point,
        destination: Point,
        strategy: int = 32,
    ) -> RouteResult:
        """
        普通路径规划
        
        Args:
            origin: 起点
            destination: 终点
            strategy: 高德路径策略 (32=默认, 33=躲避拥堵, 34=高速优先)
            
        Returns:
            路径规划结果
        """
        logger.info(f"路径规划: ({origin.lon},{origin.lat}) → ({destination.lon},{destination.lat})")
        
        # Step 1: 尝试高德API
        try:
            result = await amap_route_planning_async(
                origin_lon=origin.lon,
                origin_lat=origin.lat,
                dest_lon=destination.lon,
                dest_lat=destination.lat,
                strategy=strategy,
            )
            
            if result.get("paths"):
                return self._parse_amap_result(origin, destination, result, "amap")
                
        except Exception as e:
            logger.warning(f"高德API失败: {e}")
        
        # Step 2: Fallback到内部路径规划
        return await self._internal_route(origin, destination)
    
    async def plan_route_with_avoidance(
        self,
        origin: Point,
        destination: Point,
        avoid_areas: List[AvoidArea],
        strategy: int = 32,
    ) -> RouteResult:
        """
        避障路径规划
        
        Args:
            origin: 起点
            destination: 终点
            avoid_areas: 避让区域列表
            strategy: 高德路径策略
            
        Returns:
            路径规划结果
        """
        logger.info(
            f"避障路径规划: ({origin.lon},{origin.lat}) → ({destination.lon},{destination.lat}), "
            f"避让区域数={len(avoid_areas)}"
        )
        
        # 转换避让区域为高德格式
        avoid_polygons = [
            [(p.lon, p.lat) for p in area.polygon]
            for area in avoid_areas
            if area.severity == "hard"
        ]
        
        # Step 1: 尝试高德API
        if avoid_polygons:
            try:
                result = await amap_route_planning_with_avoidance_async(
                    origin_lon=origin.lon,
                    origin_lat=origin.lat,
                    dest_lon=destination.lon,
                    dest_lat=destination.lat,
                    avoid_polygons=avoid_polygons,
                    strategy=strategy,
                )
                
                if result.get("paths"):
                    return self._parse_amap_result(origin, destination, result, "amap")
                    
            except Exception as e:
                logger.warning(f"高德避障API失败: {e}")
        else:
            # 无避让区域，使用普通规划
            return await self.plan_route(origin, destination, strategy)
        
        # Step 2: Fallback到内部路径规划
        return await self._internal_route_with_avoidance(origin, destination, avoid_areas)
    
    async def _internal_route(
        self,
        origin: Point,
        destination: Point,
    ) -> RouteResult:
        """内部路径规划（DatabaseRouteEngine）"""
        logger.info("使用内部路径规划引擎")
        
        if self._db is None:
            return RouteResult(
                source="fallback",
                success=False,
                origin=origin,
                destination=destination,
                total_distance_m=0,
                total_duration_s=0,
                error_message="数据库连接不可用",
            )
        
        try:
            from src.planning.algorithms.routing import DatabaseRouteEngine
            from src.planning.algorithms.routing.types import Point as RoutingPoint
            
            engine = DatabaseRouteEngine(self._db)
            
            start = RoutingPoint(lon=origin.lon, lat=origin.lat)
            end = RoutingPoint(lon=destination.lon, lat=destination.lat)
            
            path_result = await engine.route_async(
                start=start,
                end=end,
                vehicle_capability=None,
                disaster_areas=[],
            )
            
            # 转换结果
            polyline = [Point(lon=p.lon, lat=p.lat) for p in path_result.points]
            
            return RouteResult(
                source="internal",
                success=True,
                origin=origin,
                destination=destination,
                total_distance_m=path_result.distance_m,
                total_duration_s=path_result.duration_s,
                polyline=polyline,
            )
            
        except Exception as e:
            logger.error(f"内部路径规划失败: {e}")
            return RouteResult(
                source="fallback",
                success=False,
                origin=origin,
                destination=destination,
                total_distance_m=0,
                total_duration_s=0,
                error_message=str(e),
            )
    
    async def _internal_route_with_avoidance(
        self,
        origin: Point,
        destination: Point,
        avoid_areas: List[AvoidArea],
    ) -> RouteResult:
        """内部避障路径规划"""
        logger.info(f"使用内部避障路径规划, 避让区域数={len(avoid_areas)}")
        
        if self._db is None:
            return RouteResult(
                source="fallback",
                success=False,
                origin=origin,
                destination=destination,
                total_distance_m=0,
                total_duration_s=0,
                error_message="数据库连接不可用",
            )
        
        try:
            from src.planning.algorithms.routing import DatabaseRouteEngine, DisasterArea
            from src.planning.algorithms.routing.types import Point as RoutingPoint
            
            engine = DatabaseRouteEngine(self._db)
            
            start = RoutingPoint(lon=origin.lon, lat=origin.lat)
            end = RoutingPoint(lon=destination.lon, lat=destination.lat)
            
            # 转换避让区域为DisasterArea
            disaster_areas = []
            for area in avoid_areas:
                coords = [(p.lon, p.lat) for p in area.polygon]
                disaster_areas.append(DisasterArea(
                    boundary={"type": "Polygon", "coordinates": [coords]},
                    hardness="hard" if area.severity == "hard" else "soft",
                ))
            
            path_result = await engine.route_async(
                start=start,
                end=end,
                vehicle_capability=None,
                disaster_areas=disaster_areas,
            )
            
            polyline = [Point(lon=p.lon, lat=p.lat) for p in path_result.points]
            
            return RouteResult(
                source="internal",
                success=True,
                origin=origin,
                destination=destination,
                total_distance_m=path_result.distance_m,
                total_duration_s=path_result.duration_s,
                polyline=polyline,
            )
            
        except Exception as e:
            logger.error(f"内部避障路径规划失败: {e}")
            return RouteResult(
                source="fallback",
                success=False,
                origin=origin,
                destination=destination,
                total_distance_m=0,
                total_duration_s=0,
                error_message=str(e),
            )
    
    def _parse_amap_result(
        self,
        origin: Point,
        destination: Point,
        result: dict,
        source: str,
    ) -> RouteResult:
        """解析高德API返回结果"""
        paths = result.get("paths", [])
        if not paths:
            return RouteResult(
                source=source,
                success=False,
                origin=origin,
                destination=destination,
                total_distance_m=0,
                total_duration_s=0,
                error_message="高德API无返回路径",
            )
        
        path = paths[0]
        distance = int(path.get("distance", 0))
        duration = int(path.get("duration", 0))
        
        segments = []
        polyline_points: List[Point] = []
        
        for step in path.get("steps", []):
            segments.append(RouteSegment(
                from_point=origin,
                to_point=destination,
                distance_m=int(step.get("step_distance", 0)),
                duration_s=0,
                instruction=step.get("instruction", ""),
                road_name=step.get("road_name", ""),
            ))
            # 解析 step.polyline: "lng,lat;lng,lat;..."
            step_polyline = step.get("polyline", "")
            if step_polyline:
                for coord_str in step_polyline.split(";"):
                    parts = coord_str.split(",")
                    if len(parts) >= 2:
                        try:
                            lng, lat = float(parts[0]), float(parts[1])
                            polyline_points.append(Point(lon=lng, lat=lat))
                        except ValueError:
                            continue
        
        logger.debug(f"高德路径解析: distance={distance}m, points={len(polyline_points)}")
        
        return RouteResult(
            source=source,
            success=True,
            origin=origin,
            destination=destination,
            total_distance_m=distance,
            total_duration_s=duration,
            segments=segments,
            polyline=polyline_points,
        )


_routing_service: Optional[RoutePlanningService] = None


def get_routing_service(db: Optional[AsyncSession] = None) -> RoutePlanningService:
    """获取路径规划服务实例"""
    global _routing_service
    if _routing_service is None or db is not None:
        _routing_service = RoutePlanningService(db)
    return _routing_service
