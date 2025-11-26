"""
车辆业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import VehicleRepository
from .schemas import (
    VehicleCreate, VehicleUpdate, VehicleResponse, 
    VehicleListResponse, VehicleCapacityCheck, VehicleStatus,
    VehicleLocationUpdate, VehicleLocationResponse,
)
from datetime import datetime

logger = logging.getLogger(__name__)


class VehicleService:
    """车辆业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = VehicleRepository(db)
    
    async def create(self, data: VehicleCreate) -> VehicleResponse:
        """
        创建车辆
        
        业务规则:
        - code必须唯一
        - compatible_device_types不能为空
        """
        # 检查编号唯一性
        if await self._repo.check_code_exists(data.code):
            raise ConflictError(
                error_code="VH_CODE_EXISTS",
                message=f"车辆编号已存在: {data.code}"
            )
        
        # 验证设备兼容性配置
        if not data.compatible_device_types:
            raise ValidationError(
                message="compatible_device_types不能为空",
                details={"field": "compatible_device_types"}
            )
        
        vehicle = await self._repo.create(data)
        return self._to_response(vehicle)
    
    async def get_by_id(self, vehicle_id: UUID) -> VehicleResponse:
        """根据ID获取车辆"""
        vehicle = await self._repo.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle", str(vehicle_id))
        return self._to_response(vehicle)
    
    async def get_by_code(self, code: str) -> VehicleResponse:
        """根据编号获取车辆"""
        vehicle = await self._repo.get_by_code(code)
        if not vehicle:
            raise NotFoundError("Vehicle", code)
        return self._to_response(vehicle)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
    ) -> VehicleListResponse:
        """
        分页查询车辆列表
        
        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            status: 状态筛选
            vehicle_type: 类型筛选
        """
        items, total = await self._repo.list(page, page_size, status, vehicle_type)
        return VehicleListResponse(
            items=[self._to_response(v) for v in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_available(
        self,
        vehicle_type: Optional[str] = None,
        min_weight_capacity: Optional[Decimal] = None,
        required_terrain: Optional[str] = None,
    ) -> list[VehicleResponse]:
        """
        查询可用车辆（用于资源分配）
        
        Args:
            vehicle_type: 车辆类型筛选
            min_weight_capacity: 最小剩余载重要求（公斤）
            required_terrain: 必须具备的地形能力
        """
        vehicles = await self._repo.list_available(
            vehicle_type, min_weight_capacity, required_terrain
        )
        return [self._to_response(v) for v in vehicles]
    
    async def update(self, vehicle_id: UUID, data: VehicleUpdate) -> VehicleResponse:
        """
        更新车辆
        
        业务规则:
        - 已出动(deployed)状态的车辆不能修改载物能力参数
        """
        vehicle = await self._repo.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        # 检查状态限制
        if vehicle.status == 'deployed':
            restricted_fields = {
                'max_weight_kg', 'max_volume_m3', 'max_device_slots', 
                'compatible_device_types'
            }
            update_fields = set(data.model_dump(exclude_unset=True).keys())
            if restricted_fields & update_fields:
                raise ConflictError(
                    error_code="VH_DEPLOYED_RESTRICT",
                    message="已出动车辆不能修改载物能力参数"
                )
        
        vehicle = await self._repo.update(vehicle, data)
        return self._to_response(vehicle)
    
    async def update_status(
        self, 
        vehicle_id: UUID, 
        status: VehicleStatus
    ) -> VehicleResponse:
        """
        更新车辆状态
        
        状态转换规则:
        - available -> deployed, maintenance
        - deployed -> available
        - maintenance -> available
        """
        vehicle = await self._repo.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        current = vehicle.status
        target = status.value
        
        valid_transitions = {
            'available': ['deployed', 'maintenance'],
            'deployed': ['available'],
            'maintenance': ['available'],
        }
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError(
                error_code="VH_INVALID_STATUS_TRANSITION",
                message=f"无效的状态转换: {current} -> {target}"
            )
        
        vehicle = await self._repo.update_status(vehicle, target)
        return self._to_response(vehicle)
    
    async def delete(self, vehicle_id: UUID) -> None:
        """
        删除车辆
        
        业务规则:
        - 已出动(deployed)状态的车辆不能删除
        - 有装载设备的车辆不能删除
        """
        vehicle = await self._repo.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        if vehicle.status == 'deployed':
            raise ConflictError(
                error_code="VH_DELETE_DEPLOYED",
                message="已出动车辆不能删除"
            )
        
        if vehicle.current_device_count > 0:
            raise ConflictError(
                error_code="VH_DELETE_HAS_DEVICES",
                message=f"车辆上有{vehicle.current_device_count}个设备，请先卸载"
            )
        
        await self._repo.delete(vehicle)
    
    async def check_capacity(
        self,
        vehicle_id: UUID,
        required_weight_kg: Decimal,
        required_volume_m3: Decimal,
        required_slots: int = 1,
    ) -> VehicleCapacityCheck:
        """
        检查车辆容量是否满足需求
        
        Args:
            vehicle_id: 车辆ID
            required_weight_kg: 需要的重量（公斤）
            required_volume_m3: 需要的体积（立方米）
            required_slots: 需要的设备位数量
        """
        capacity = await self._repo.get_capacity_info(vehicle_id)
        if not capacity:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        remaining_weight = capacity['remaining_weight_kg']
        remaining_volume = capacity['remaining_volume_m3']
        remaining_slots = capacity['remaining_device_slots']
        
        can_load = (
            remaining_weight >= required_weight_kg and
            remaining_volume >= required_volume_m3 and
            remaining_slots >= required_slots
        )
        
        message = None
        if not can_load:
            issues = []
            if remaining_weight < required_weight_kg:
                issues.append(f"重量不足(剩余{remaining_weight}kg,需要{required_weight_kg}kg)")
            if remaining_volume < required_volume_m3:
                issues.append(f"体积不足(剩余{remaining_volume}m³,需要{required_volume_m3}m³)")
            if remaining_slots < required_slots:
                issues.append(f"设备位不足(剩余{remaining_slots},需要{required_slots})")
            message = "; ".join(issues)
        
        return VehicleCapacityCheck(
            vehicle_id=vehicle_id,
            can_load=can_load,
            remaining_weight_kg=remaining_weight,
            remaining_volume_m3=remaining_volume,
            remaining_device_slots=remaining_slots,
            message=message,
        )
    
    async def update_location(
        self,
        vehicle_id: UUID,
        data: VehicleLocationUpdate,
    ) -> VehicleLocationResponse:
        """
        更新车辆位置
        
        由GPS遥测数据或仿真模块调用。
        """
        vehicle = await self._repo.get_by_id(vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        # 使用WKT格式设置位置
        from geoalchemy2.functions import ST_GeogFromText
        wkt = f"SRID=4326;POINT({data.longitude} {data.latitude})"
        vehicle.current_location = wkt
        vehicle.last_location_update = datetime.utcnow()
        
        # 扩展属性可存储航向和速度
        props = vehicle.properties or {}
        if data.heading is not None:
            props['heading'] = data.heading
        if data.speed_kmh is not None:
            props['speed_kmh'] = data.speed_kmh
        props['location_source'] = data.source
        vehicle.properties = props
        
        await self._repo._db.flush()
        
        logger.info(
            f"车辆位置更新: vehicle_id={vehicle_id}, "
            f"lon={data.longitude}, lat={data.latitude}"
        )
        
        return VehicleLocationResponse(
            vehicle_id=vehicle_id,
            longitude=data.longitude,
            latitude=data.latitude,
            last_update=vehicle.last_location_update,
            message="位置更新成功",
        )
    
    def _to_response(self, vehicle) -> VehicleResponse:
        """ORM模型转响应模型"""
        return VehicleResponse(
            id=vehicle.id,
            code=vehicle.code,
            name=vehicle.name,
            vehicle_type=vehicle.vehicle_type,
            max_weight_kg=vehicle.max_weight_kg,
            max_volume_m3=vehicle.max_volume_m3,
            max_device_slots=vehicle.max_device_slots,
            compatible_device_types=vehicle.compatible_device_types or [],
            current_weight_kg=vehicle.current_weight_kg or Decimal(0),
            current_volume_m3=vehicle.current_volume_m3 or Decimal(0),
            current_device_count=vehicle.current_device_count or 0,
            self_weight_kg=vehicle.self_weight_kg,
            crew_capacity=vehicle.crew_capacity or 4,
            terrain_capabilities=vehicle.terrain_capabilities or [],
            is_all_terrain=vehicle.is_all_terrain or False,
            max_gradient_percent=vehicle.max_gradient_percent,
            max_wading_depth_m=vehicle.max_wading_depth_m,
            min_turning_radius_m=vehicle.min_turning_radius_m,
            ground_clearance_mm=vehicle.ground_clearance_mm,
            approach_angle_deg=vehicle.approach_angle_deg,
            departure_angle_deg=vehicle.departure_angle_deg,
            breakover_angle_deg=vehicle.breakover_angle_deg,
            max_speed_kmh=vehicle.max_speed_kmh,
            terrain_speed_factors=vehicle.terrain_speed_factors or {},
            fuel_capacity_l=vehicle.fuel_capacity_l,
            fuel_consumption_per_100km=vehicle.fuel_consumption_per_100km,
            range_km=vehicle.range_km,
            length_m=vehicle.length_m,
            width_m=vehicle.width_m,
            height_m=vehicle.height_m,
            status=vehicle.status,
            entity_id=vehicle.entity_id,
            properties=vehicle.properties or {},
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
        )
