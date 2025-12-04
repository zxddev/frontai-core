"""
空中路径规划服务

无人机直线飞行路径规划，使用 Haversine 公式计算球面距离
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from .schemas import Point, RouteResult

logger = logging.getLogger(__name__)

# 地球半径（米）
EARTH_RADIUS_M: float = 6371000.0

# 默认无人机巡航速度（km/h）
DEFAULT_CRUISE_SPEED_KMH: float = 50.0


class AirRoutePlanningService:
    """
    空中路径规划服务
    
    无人机采用直线飞行，起点到终点直接连线
    """
    
    def __init__(self, cruise_speed_kmh: Optional[float] = None) -> None:
        """
        初始化空中路径规划服务
        
        Args:
            cruise_speed_kmh: 巡航速度（km/h），默认 50 km/h
        """
        self._cruise_speed_kmh = cruise_speed_kmh or DEFAULT_CRUISE_SPEED_KMH
    
    async def plan_route(
        self,
        origin: Point,
        destination: Point,
        cruise_speed_kmh: Optional[float] = None,
    ) -> RouteResult:
        """
        空中直线路径规划
        
        Args:
            origin: 起点坐标
            destination: 终点坐标
            cruise_speed_kmh: 巡航速度（km/h），覆盖实例默认值
            
        Returns:
            RouteResult: 路径规划结果
        """
        speed = cruise_speed_kmh or self._cruise_speed_kmh
        
        logger.info(
            f"空中路径规划: ({origin.lon},{origin.lat}) → ({destination.lon},{destination.lat}), "
            f"巡航速度={speed} km/h"
        )
        
        # Haversine 公式计算直线距离（米）
        distance_m = self._haversine_distance(
            origin.lon, origin.lat,
            destination.lon, destination.lat
        )
        
        # 飞行时间（秒）= 距离（米）/ 速度（米/秒）
        speed_ms = speed * 1000 / 3600  # km/h → m/s
        duration_s = distance_m / speed_ms
        
        logger.info(f"空中路径规划完成: 距离={distance_m:.0f}m, 时间={duration_s:.0f}s")
        
        return RouteResult(
            source="air_direct",
            success=True,
            origin=origin,
            destination=destination,
            total_distance_m=distance_m,
            total_duration_s=duration_s,
            segments=[],
            polyline=[origin, destination],
        )
    
    @staticmethod
    def _haversine_distance(
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float,
    ) -> float:
        """
        Haversine 公式计算两点间球面距离（米）
        
        Args:
            lon1, lat1: 起点经纬度
            lon2, lat2: 终点经纬度
            
        Returns:
            距离（米）
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return EARTH_RADIUS_M * c


_air_service: Optional[AirRoutePlanningService] = None


def get_air_routing_service(cruise_speed_kmh: Optional[float] = None) -> AirRoutePlanningService:
    """获取空中路径规划服务实例"""
    global _air_service
    if _air_service is None:
        _air_service = AirRoutePlanningService(cruise_speed_kmh)
    return _air_service
