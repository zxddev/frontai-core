"""
路径规划服务

封装高德API + 内部路径规划的fallback机制。
遵循架构规范：Agent Node → Service → Algorithm/External API
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point, RouteResult, RouteSegment, AvoidArea
from src.infra.clients.amap.route_planning import (
    amap_route_planning_async,
    amap_route_planning_with_avoidance_async,
)

logger = logging.getLogger(__name__)

# 是否优先使用内部路径规划（已废弃，改为高德优先 + 直线fallback）
# 可通过环境变量 PREFER_INTERNAL_ROUTING=true 恢复内部路径规划
PREFER_INTERNAL_ROUTING = os.environ.get("PREFER_INTERNAL_ROUTING", "false").lower() == "true"


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
        
        if PREFER_INTERNAL_ROUTING:
            # 内部路径规划模式（需设置环境变量 PREFER_INTERNAL_ROUTING=true）
            internal_result = await self._internal_route(origin, destination)
            if internal_result.success:
                return internal_result
            logger.warning("内部路径规划失败，fallback到直线估算")
            return self._fallback_straight_line(origin, destination)
        
        # 默认模式：优先高德API → 直线fallback
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
        
        # Fallback: 直线距离 + 系数估算
        logger.info("高德API无结果，使用直线距离估算")
        return self._fallback_straight_line(origin, destination)
    
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
        
        # 无避让区域，使用普通规划
        if not avoid_areas:
            return await self.plan_route(origin, destination, strategy)
        
        # 转换避让区域为高德格式
        avoid_polygons = [
            [(p.lon, p.lat) for p in area.polygon]
            for area in avoid_areas
            if area.severity == "hard"
        ]
        
        if PREFER_INTERNAL_ROUTING:
            # 内部路径规划模式（需设置环境变量 PREFER_INTERNAL_ROUTING=true）
            internal_result = await self._internal_route_with_avoidance(origin, destination, avoid_areas)
            if internal_result.success:
                return internal_result
            logger.warning("内部避障路径规划失败，fallback到直线估算")
            return self._fallback_straight_line(origin, destination)
        
        # 默认模式：优先高德API → 直线fallback
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
        
        # Fallback: 直线距离 + 系数估算
        logger.info("高德避障API无结果，使用直线距离估算")
        return self._fallback_straight_line(origin, destination)
    
    async def _internal_route(
        self,
        origin: Point,
        destination: Point,
    ) -> RouteResult:
        """内部路径规划（DatabaseRouteEngine）"""
        import time
        start_time = time.perf_counter()
        
        logger.info(
            f"[内部路径规划] 开始 ({origin.lon:.4f},{origin.lat:.4f}) → ({destination.lon:.4f},{destination.lat:.4f})"
        )
        
        if self._db is None:
            logger.warning("[内部路径规划] 数据库连接不可用")
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
            from uuid import uuid4
            from src.planning.algorithms.routing.db_route_engine import (
                DatabaseRouteEngine,
                VehicleCapability,
                Point as RoutingPoint,
            )
            
            engine = DatabaseRouteEngine(self._db)
            
            start = RoutingPoint(lon=origin.lon, lat=origin.lat)
            end = RoutingPoint(lon=destination.lon, lat=destination.lat)
            
            # 创建默认车辆能力（普通救援车辆）
            default_vehicle = VehicleCapability(
                vehicle_id=uuid4(),
                vehicle_code="DEFAULT_RESCUE",
                max_speed_kmh=60,
                is_all_terrain=False,
                terrain_capabilities=["paved", "gravel"],
                terrain_speed_factors={"paved": 1.0, "gravel": 0.7, "dirt": 0.5},
                max_gradient_percent=15,
                max_wading_depth_m=0.3,
                width_m=2.5,
                height_m=3.0,
                total_weight_kg=10000,
            )
            
            path_result = await engine.plan_route(
                start=start,
                end=end,
                vehicle=default_vehicle,
            )
            
            # 转换结果
            polyline = [Point(lon=p.lon, lat=p.lat) for p in path_result.path_points]
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"[内部路径规划] 成功 距离={path_result.distance_m/1000:.2f}km "
                f"时间={path_result.duration_seconds/60:.1f}分钟 耗时={elapsed_ms:.0f}ms"
            )
            
            return RouteResult(
                source="internal",
                success=True,
                origin=origin,
                destination=destination,
                total_distance_m=path_result.distance_m,
                total_duration_s=int(path_result.duration_seconds),
                polyline=polyline,
            )
            
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"[内部路径规划] 失败(耗时{elapsed_ms:.0f}ms): {e}")
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
        import time
        start_time = time.perf_counter()
        
        logger.info(
            f"[内部避障路径规划] 开始 ({origin.lon:.4f},{origin.lat:.4f}) → ({destination.lon:.4f},{destination.lat:.4f}) "
            f"避让区域数={len(avoid_areas)}"
        )
        
        if self._db is None:
            logger.warning("[内部避障路径规划] 数据库连接不可用")
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
            from uuid import uuid4
            from src.planning.algorithms.routing.db_route_engine import (
                DatabaseRouteEngine,
                VehicleCapability,
                Point as RoutingPoint,
            )
            
            engine = DatabaseRouteEngine(self._db)
            
            start = RoutingPoint(lon=origin.lon, lat=origin.lat)
            end = RoutingPoint(lon=destination.lon, lat=destination.lat)
            
            # 创建默认车辆能力（普通救援车辆）
            default_vehicle = VehicleCapability(
                vehicle_id=uuid4(),
                vehicle_code="DEFAULT_RESCUE",
                max_speed_kmh=60,
                is_all_terrain=False,
                terrain_capabilities=["paved", "gravel"],
                terrain_speed_factors={"paved": 1.0, "gravel": 0.7, "dirt": 0.5},
                max_gradient_percent=15,
                max_wading_depth_m=0.3,
                width_m=2.5,
                height_m=3.0,
                total_weight_kg=10000,
            )
            
            # TODO: 当前 plan_route 不支持直接传入避让区域
            # 避障功能需要从数据库加载 disaster_affected_areas_v2
            # 暂时使用普通路径规划
            path_result = await engine.plan_route(
                start=start,
                end=end,
                vehicle=default_vehicle,
            )
            
            polyline = [Point(lon=p.lon, lat=p.lat) for p in path_result.path_points]
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"[内部避障路径规划] 成功 距离={path_result.distance_m/1000:.2f}km "
                f"时间={path_result.duration_seconds/60:.1f}分钟 耗时={elapsed_ms:.0f}ms"
            )
            
            return RouteResult(
                source="internal",
                success=True,
                origin=origin,
                destination=destination,
                total_distance_m=path_result.distance_m,
                total_duration_s=int(path_result.duration_seconds),
                polyline=polyline,
            )
            
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"[内部避障路径规划] 失败(耗时{elapsed_ms:.0f}ms): {e}")
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
    
    def _fallback_straight_line(
        self,
        origin: Point,
        destination: Point,
        road_factor: float = 1.4,
        avg_speed_kmh: float = 40,
    ) -> RouteResult:
        """
        直线距离 + 系数估算（高德失败时的fallback）
        
        Args:
            origin: 起点
            destination: 终点
            road_factor: 道路迂回系数（直线距离 × 1.4 = 估算道路距离）
            avg_speed_kmh: 平均行驶速度（考虑城镇和山区道路）
            
        Returns:
            估算的路径规划结果
        """
        straight_distance_m = self._haversine_distance(origin, destination)
        estimated_distance_m = straight_distance_m * road_factor
        estimated_duration_s = int(estimated_distance_m / (avg_speed_kmh * 1000 / 3600))
        
        logger.info(
            f"[直线估算] 直线距离={straight_distance_m/1000:.2f}km, "
            f"估算道路距离={estimated_distance_m/1000:.2f}km, "
            f"估算时间={estimated_duration_s/60:.1f}分钟"
        )
        
        return RouteResult(
            source="fallback_straight_line",
            success=True,
            origin=origin,
            destination=destination,
            total_distance_m=estimated_distance_m,
            total_duration_s=estimated_duration_s,
            polyline=[origin, destination],
        )
    
    def _haversine_distance(self, p1: Point, p2: Point) -> float:
        """Haversine公式计算两点间直线距离（米）"""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371000  # 地球半径（米）
        
        lat1, lon1 = radians(p1.lat), radians(p1.lon)
        lat2, lon2 = radians(p2.lat), radians(p2.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c


_routing_service: Optional[RoutePlanningService] = None


def get_routing_service(db: Optional[AsyncSession] = None) -> RoutePlanningService:
    """获取路径规划服务实例"""
    global _routing_service
    if _routing_service is None or db is not None:
        _routing_service = RoutePlanningService(db)
    return _routing_service
