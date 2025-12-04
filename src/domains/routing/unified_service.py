"""
统一路径规划服务

根据设备环境类型（air/land/sea）分发到对应的路径规划器
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point, RouteResult, AvoidArea
from .service import RoutePlanningService
from .air_service import AirRoutePlanningService
from src.domains.resources.devices.repository import DeviceRepository

logger = logging.getLogger(__name__)


class UnifiedRoutePlanningService:
    """
    统一路径规划服务
    
    根据设备的 env_type 字段分发到对应的路径规划器：
    - air: 空中直线飞行（AirRoutePlanningService）
    - land: 陆地路径规划（RoutePlanningService，高德API + 内部引擎）
    - sea: 水上路径规划（暂未实现）
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        初始化统一路径规划服务
        
        Args:
            db: 数据库会话，用于查询设备信息和陆地路径规划
        """
        self._db = db
        self._device_repo = DeviceRepository(db)
        self._land_service = RoutePlanningService(db)
        self._air_service = AirRoutePlanningService()
    
    async def plan_route(
        self,
        device_id: UUID,
        origin: Point,
        destination: Point,
        avoid_areas: Optional[List[AvoidArea]] = None,
    ) -> RouteResult:
        """
        根据设备类型进行路径规划
        
        Args:
            device_id: 设备ID，用于获取 env_type
            origin: 起点坐标
            destination: 终点坐标
            avoid_areas: 避让区域列表（仅陆地规划有效）
            
        Returns:
            RouteResult: 路径规划结果
            
        Raises:
            ValueError: 设备不存在
            NotImplementedError: 水上路径规划暂未实现
        """
        # 查询设备信息
        device = await self._device_repo.get_by_id(device_id)
        if device is None:
            logger.error(f"设备不存在: device_id={device_id}")
            raise ValueError(f"设备不存在: {device_id}")
        
        env_type: str = device.env_type
        logger.info(
            f"统一路径规划: device_id={device_id}, env_type={env_type}, "
            f"origin=({origin.lon},{origin.lat}), dest=({destination.lon},{destination.lat})"
        )
        
        # 根据环境类型分发
        if env_type == "air":
            return await self._plan_air_route(device, origin, destination)
        elif env_type == "land":
            return await self._plan_land_route(origin, destination, avoid_areas)
        elif env_type == "sea":
            logger.error(f"水上路径规划暂未实现: device_id={device_id}")
            raise NotImplementedError("水上路径规划暂未实现")
        else:
            logger.error(f"未知的环境类型: env_type={env_type}, device_id={device_id}")
            raise ValueError(f"未知的环境类型: {env_type}")
    
    async def _plan_air_route(
        self,
        device: "Device",  # type: ignore
        origin: Point,
        destination: Point,
    ) -> RouteResult:
        """
        空中路径规划
        
        从设备 properties 读取巡航速度，否则使用默认值
        """
        # 尝试从 properties 读取巡航速度
        cruise_speed_kmh: Optional[float] = None
        if device.properties:
            cruise_speed_kmh = device.properties.get("cruise_speed_kmh")
        
        logger.info(f"空中路径规划: device={device.code}, cruise_speed={cruise_speed_kmh}")
        
        return await self._air_service.plan_route(
            origin=origin,
            destination=destination,
            cruise_speed_kmh=cruise_speed_kmh,
        )
    
    async def _plan_land_route(
        self,
        origin: Point,
        destination: Point,
        avoid_areas: Optional[List[AvoidArea]] = None,
    ) -> RouteResult:
        """
        陆地路径规划
        
        调用现有 RoutePlanningService（高德API + DatabaseRouteEngine）
        """
        if avoid_areas:
            logger.info(f"陆地避障路径规划: 避让区域数={len(avoid_areas)}")
            return await self._land_service.plan_route_with_avoidance(
                origin=origin,
                destination=destination,
                avoid_areas=avoid_areas,
            )
        else:
            logger.info("陆地普通路径规划")
            return await self._land_service.plan_route(
                origin=origin,
                destination=destination,
            )
