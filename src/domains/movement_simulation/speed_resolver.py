"""
速度获取模块

根据实体类型和资源ID从数据库获取移动速度
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .schemas import EntityType

logger = logging.getLogger(__name__)


# 默认速度配置 (km/h)
DEFAULT_SPEEDS_KMH = {
    EntityType.VEHICLE: 60,       # 车辆默认 60 km/h
    EntityType.TEAM: 5,           # 队伍徒步 5 km/h
    EntityType.UAV: 50,           # 无人机 50 km/h
    EntityType.ROBOTIC_DOG: 10,   # 机器狗 10 km/h
    EntityType.USV: 30,           # 无人艇 30 km/h
}

# 设备类型到速度的映射
DEVICE_TYPE_SPEEDS_KMH = {
    "drone": 50,
    "dog": 10,
    "ship": 30,
    "robot": 15,
}


class SpeedResolver:
    """
    速度解析器
    
    从数据库获取车辆/队伍/设备的速度配置，
    如果数据库无配置则返回默认值
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def resolve_speed_mps(
        self,
        entity_type: EntityType,
        resource_id: Optional[UUID] = None,
    ) -> float:
        """
        获取实体移动速度（米/秒）
        
        Args:
            entity_type: 实体类型
            resource_id: 资源ID（车辆ID/队伍ID/设备ID）
            
        Returns:
            速度（米/秒）
        """
        speed_kmh = await self._resolve_speed_kmh(entity_type, resource_id)
        speed_mps = speed_kmh / 3.6
        
        logger.debug(
            f"速度解析: entity_type={entity_type.value}, "
            f"resource_id={resource_id}, speed={speed_kmh}km/h ({speed_mps:.2f}m/s)"
        )
        
        return speed_mps
    
    async def _resolve_speed_kmh(
        self,
        entity_type: EntityType,
        resource_id: Optional[UUID],
    ) -> float:
        """获取速度（km/h）"""
        
        # 无资源ID时使用默认值
        if resource_id is None:
            return DEFAULT_SPEEDS_KMH.get(entity_type, 10)
        
        try:
            if entity_type == EntityType.VEHICLE:
                return await self._get_vehicle_speed(resource_id)
            
            elif entity_type == EntityType.TEAM:
                return await self._get_team_speed(resource_id)
            
            elif entity_type in (EntityType.UAV, EntityType.ROBOTIC_DOG, EntityType.USV):
                return await self._get_device_speed(resource_id, entity_type)
            
        except Exception as e:
            logger.warning(f"获取速度失败，使用默认值: {e}")
        
        return DEFAULT_SPEEDS_KMH.get(entity_type, 10)
    
    async def _get_vehicle_speed(self, vehicle_id: UUID) -> float:
        """从车辆表获取速度"""
        from src.domains.resources.vehicles.models import Vehicle
        
        result = await self._db.execute(
            select(Vehicle.max_speed_kmh, Vehicle.properties)
            .where(Vehicle.id == vehicle_id)
        )
        row = result.first()
        
        if row:
            # 优先使用 max_speed_kmh 字段
            if row.max_speed_kmh:
                return float(row.max_speed_kmh)
            # 备选：从 properties 中读取
            if row.properties and "speed_kmh" in row.properties:
                return float(row.properties["speed_kmh"])
        
        return DEFAULT_SPEEDS_KMH[EntityType.VEHICLE]
    
    async def _get_team_speed(self, team_id: UUID) -> float:
        """从队伍表获取速度"""
        from src.domains.resources.teams.models import Team
        
        result = await self._db.execute(
            select(Team.properties)
            .where(Team.id == team_id)
        )
        row = result.first()
        
        if row and row.properties:
            # 队伍速度存储在 properties 中
            if "speed_kmh" in row.properties:
                return float(row.properties["speed_kmh"])
            # 或者有车辆时使用车辆速度
            if "vehicle_speed_kmh" in row.properties:
                return float(row.properties["vehicle_speed_kmh"])
        
        return DEFAULT_SPEEDS_KMH[EntityType.TEAM]
    
    async def _get_device_speed(self, device_id: UUID, entity_type: EntityType) -> float:
        """从设备表获取速度"""
        from src.domains.resources.devices.models import Device
        
        result = await self._db.execute(
            select(Device.device_type, Device.properties)
            .where(Device.id == device_id)
        )
        row = result.first()
        
        if row:
            # 优先从 properties 读取
            if row.properties and "max_speed_kmh" in row.properties:
                return float(row.properties["max_speed_kmh"])
            
            # 根据设备类型使用默认速度
            if row.device_type:
                return DEVICE_TYPE_SPEEDS_KMH.get(row.device_type, 20)
        
        return DEFAULT_SPEEDS_KMH.get(entity_type, 20)


async def get_speed_resolver(db: AsyncSession) -> SpeedResolver:
    """获取速度解析器实例"""
    return SpeedResolver(db)
