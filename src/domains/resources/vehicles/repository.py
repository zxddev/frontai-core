"""
车辆数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Vehicle
from .schemas import VehicleCreate, VehicleUpdate

logger = logging.getLogger(__name__)


class VehicleRepository:
    """车辆数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: VehicleCreate) -> Vehicle:
        """创建车辆"""
        vehicle = Vehicle(
            code=data.code,
            name=data.name,
            vehicle_type=data.vehicle_type.value,
            max_weight_kg=data.max_weight_kg,
            max_volume_m3=data.max_volume_m3,
            max_device_slots=data.max_device_slots,
            compatible_device_types=[dt.value for dt in data.compatible_device_types],
            self_weight_kg=data.self_weight_kg,
            crew_capacity=data.crew_capacity,
            terrain_capabilities=data.terrain_capabilities,
            is_all_terrain=data.is_all_terrain,
            max_gradient_percent=data.max_gradient_percent,
            max_wading_depth_m=data.max_wading_depth_m,
            min_turning_radius_m=data.min_turning_radius_m,
            ground_clearance_mm=data.ground_clearance_mm,
            approach_angle_deg=data.approach_angle_deg,
            departure_angle_deg=data.departure_angle_deg,
            breakover_angle_deg=data.breakover_angle_deg,
            max_speed_kmh=data.max_speed_kmh,
            terrain_speed_factors=data.terrain_speed_factors,
            fuel_capacity_l=data.fuel_capacity_l,
            fuel_consumption_per_100km=data.fuel_consumption_per_100km,
            range_km=data.range_km,
            length_m=data.length_m,
            width_m=data.width_m,
            height_m=data.height_m,
            entity_id=data.entity_id,
            properties=data.properties,
            status='available',
        )
        self._db.add(vehicle)
        await self._db.flush()
        await self._db.refresh(vehicle)
        
        logger.info(f"创建车辆: code={vehicle.code}, id={vehicle.id}")
        return vehicle
    
    async def get_by_id(self, vehicle_id: UUID) -> Optional[Vehicle]:
        """根据ID查询车辆"""
        result = await self._db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Vehicle]:
        """根据编号查询车辆"""
        result = await self._db.execute(
            select(Vehicle).where(Vehicle.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
    ) -> tuple[Sequence[Vehicle], int]:
        """
        分页查询车辆列表
        
        Returns:
            (车辆列表, 总数)
        """
        query = select(Vehicle)
        count_query = select(func.count(Vehicle.id))
        
        if status:
            query = query.where(Vehicle.status == status)
            count_query = count_query.where(Vehicle.status == status)
        
        if vehicle_type:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
            count_query = count_query.where(Vehicle.vehicle_type == vehicle_type)
        
        # 按创建时间倒序
        query = query.order_by(Vehicle.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_available(
        self,
        vehicle_type: Optional[str] = None,
        min_weight_capacity: Optional[Decimal] = None,
        required_terrain: Optional[str] = None,
    ) -> Sequence[Vehicle]:
        """
        查询可用车辆
        
        Args:
            vehicle_type: 车辆类型筛选
            min_weight_capacity: 最小剩余载重要求
            required_terrain: 必须具备的地形能力
        """
        query = select(Vehicle).where(Vehicle.status == 'available')
        
        if vehicle_type:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
        
        if min_weight_capacity is not None:
            remaining_weight = Vehicle.max_weight_kg - Vehicle.current_weight_kg
            query = query.where(remaining_weight >= min_weight_capacity)
        
        if required_terrain:
            query = query.where(Vehicle.terrain_capabilities.contains([required_terrain]))
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def update(self, vehicle: Vehicle, data: VehicleUpdate) -> Vehicle:
        """更新车辆"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 枚举转字符串
        if 'compatible_device_types' in update_dict and update_dict['compatible_device_types']:
            update_dict['compatible_device_types'] = [
                dt.value if hasattr(dt, 'value') else dt 
                for dt in update_dict['compatible_device_types']
            ]
        if 'status' in update_dict and update_dict['status']:
            update_dict['status'] = (
                update_dict['status'].value 
                if hasattr(update_dict['status'], 'value') 
                else update_dict['status']
            )
        
        for key, value in update_dict.items():
            setattr(vehicle, key, value)
        
        await self._db.flush()
        await self._db.refresh(vehicle)
        
        logger.info(f"更新车辆: id={vehicle.id}, fields={list(update_dict.keys())}")
        return vehicle
    
    async def update_status(self, vehicle: Vehicle, status: str) -> Vehicle:
        """更新车辆状态"""
        old_status = vehicle.status
        vehicle.status = status
        await self._db.flush()
        await self._db.refresh(vehicle)
        
        logger.info(f"车辆状态变更: id={vehicle.id}, {old_status} -> {status}")
        return vehicle
    
    async def delete(self, vehicle: Vehicle) -> None:
        """删除车辆"""
        vehicle_id = vehicle.id
        await self._db.delete(vehicle)
        await self._db.flush()
        
        logger.info(f"删除车辆: id={vehicle_id}")
    
    async def check_code_exists(self, code: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查编号是否已存在"""
        query = select(func.count(Vehicle.id)).where(Vehicle.code == code)
        if exclude_id:
            query = query.where(Vehicle.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
    
    async def get_capacity_info(self, vehicle_id: UUID) -> Optional[dict]:
        """
        获取车辆容量信息
        
        Returns:
            {
                'max_weight_kg': Decimal,
                'max_volume_m3': Decimal,
                'max_device_slots': int,
                'current_weight_kg': Decimal,
                'current_volume_m3': Decimal,
                'current_device_count': int,
                'remaining_weight_kg': Decimal,
                'remaining_volume_m3': Decimal,
                'remaining_device_slots': int,
            }
        """
        vehicle = await self.get_by_id(vehicle_id)
        if not vehicle:
            return None
        
        return {
            'max_weight_kg': vehicle.max_weight_kg,
            'max_volume_m3': vehicle.max_volume_m3,
            'max_device_slots': vehicle.max_device_slots,
            'current_weight_kg': vehicle.current_weight_kg,
            'current_volume_m3': vehicle.current_volume_m3,
            'current_device_count': vehicle.current_device_count,
            'remaining_weight_kg': vehicle.max_weight_kg - vehicle.current_weight_kg,
            'remaining_volume_m3': vehicle.max_volume_m3 - vehicle.current_volume_m3,
            'remaining_device_slots': vehicle.max_device_slots - vehicle.current_device_count,
        }
