"""
设备业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import DeviceRepository
from .schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, 
    DeviceListResponse, DeviceStatus, DeviceLoadRequest, DeviceLoadResult,
    DeviceTelemetryData, DeviceTelemetryResponse,
)
from datetime import datetime

logger = logging.getLogger(__name__)


class DeviceService:
    """设备业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = DeviceRepository(db)
        self._db = db
    
    async def create(self, data: DeviceCreate) -> DeviceResponse:
        """
        创建设备
        
        业务规则:
        - code必须唯一
        - 如果指定了in_vehicle_id，需要验证车辆容量
        """
        if await self._repo.check_code_exists(data.code):
            raise ConflictError(
                error_code="DV_CODE_EXISTS",
                message=f"设备编号已存在: {data.code}"
            )
        
        # 如果指定了车辆，验证容量
        if data.in_vehicle_id:
            await self._validate_vehicle_capacity(
                data.in_vehicle_id, 
                data.weight_kg, 
                data.volume_m3,
                data.device_type.value,
            )
        
        device = await self._repo.create(data)
        return self._to_response(device)
    
    async def get_by_id(self, device_id: UUID) -> DeviceResponse:
        """根据ID获取设备"""
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        return self._to_response(device)
    
    async def get_by_code(self, code: str) -> DeviceResponse:
        """根据编号获取设备"""
        device = await self._repo.get_by_code(code)
        if not device:
            raise NotFoundError("Device", code)
        return self._to_response(device)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
        env_type: Optional[str] = None,
        in_vehicle_id: Optional[UUID] = None,
    ) -> DeviceListResponse:
        """分页查询设备列表"""
        items, total = await self._repo.list(
            page, page_size, status, device_type, env_type, in_vehicle_id
        )
        return DeviceListResponse(
            items=[self._to_response(d) for d in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_available(
        self,
        device_type: Optional[str] = None,
        env_type: Optional[str] = None,
        not_in_vehicle: bool = False,
    ) -> list[DeviceResponse]:
        """
        查询可用设备（用于资源分配）
        """
        devices = await self._repo.list_available(device_type, env_type, not_in_vehicle)
        return [self._to_response(d) for d in devices]
    
    async def list_by_vehicle(self, vehicle_id: UUID) -> list[DeviceResponse]:
        """查询车辆上装载的设备"""
        devices = await self._repo.list_by_vehicle(vehicle_id)
        return [self._to_response(d) for d in devices]
    
    async def update(self, device_id: UUID, data: DeviceUpdate) -> DeviceResponse:
        """更新设备"""
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        device = await self._repo.update(device, data)
        return self._to_response(device)
    
    async def update_status(
        self, 
        device_id: UUID, 
        status: DeviceStatus
    ) -> DeviceResponse:
        """
        更新设备状态
        
        状态转换规则:
        - available -> deployed, charging, maintenance
        - deployed -> available
        - charging -> available
        - maintenance -> available
        """
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        current = device.status
        target = status.value
        
        valid_transitions = {
            'available': ['deployed', 'charging', 'maintenance'],
            'deployed': ['available'],
            'charging': ['available'],
            'maintenance': ['available'],
        }
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError(
                error_code="DV_INVALID_STATUS_TRANSITION",
                message=f"无效的状态转换: {current} -> {target}"
            )
        
        device = await self._repo.update_status(device, target)
        return self._to_response(device)
    
    async def load_to_vehicle(
        self, 
        device_id: UUID, 
        data: DeviceLoadRequest
    ) -> DeviceLoadResult:
        """
        装载设备到车辆
        
        业务规则:
        - 设备必须是available状态
        - 设备不能已在其他车辆上
        - 车辆必须有足够容量
        - 设备类型必须在车辆兼容列表中
        """
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        # 检查设备状态
        if device.status != 'available':
            return DeviceLoadResult(
                device_id=device_id,
                vehicle_id=data.vehicle_id,
                success=False,
                message=f"设备状态为{device.status}，无法装载"
            )
        
        # 检查是否已在车辆上
        if device.in_vehicle_id:
            if device.in_vehicle_id == data.vehicle_id:
                return DeviceLoadResult(
                    device_id=device_id,
                    vehicle_id=data.vehicle_id,
                    success=True,
                    message="设备已在目标车辆上"
                )
            return DeviceLoadResult(
                device_id=device_id,
                vehicle_id=data.vehicle_id,
                success=False,
                message=f"设备已在车辆{device.in_vehicle_id}上，请先卸载"
            )
        
        # 验证车辆容量和兼容性
        try:
            await self._validate_vehicle_capacity(
                data.vehicle_id,
                device.weight_kg,
                device.volume_m3,
                device.device_type,
            )
        except (ConflictError, ValidationError) as e:
            return DeviceLoadResult(
                device_id=device_id,
                vehicle_id=data.vehicle_id,
                success=False,
                message=str(e.detail.get('message', str(e)))
            )
        
        await self._repo.load_to_vehicle(device, data.vehicle_id)
        
        return DeviceLoadResult(
            device_id=device_id,
            vehicle_id=data.vehicle_id,
            success=True,
            message="装载成功"
        )
    
    async def unload_from_vehicle(self, device_id: UUID) -> DeviceResponse:
        """从车辆卸载设备"""
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        if not device.in_vehicle_id:
            raise ConflictError(
                error_code="DV_NOT_IN_VEHICLE",
                message="设备未装载到任何车辆"
            )
        
        device = await self._repo.unload_from_vehicle(device)
        return self._to_response(device)
    
    async def delete(self, device_id: UUID) -> None:
        """
        删除设备
        
        业务规则:
        - 已部署(deployed)状态的设备不能删除
        - 装载在车辆上的设备需要先卸载
        """
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        if device.status == 'deployed':
            raise ConflictError(
                error_code="DV_DELETE_DEPLOYED",
                message="已部署设备不能删除"
            )
        
        if device.in_vehicle_id:
            raise ConflictError(
                error_code="DV_DELETE_IN_VEHICLE",
                message="设备在车辆上，请先卸载"
            )
        
        await self._repo.delete(device)
    
    async def receive_telemetry(
        self,
        device_id: UUID,
        data: DeviceTelemetryData,
    ) -> DeviceTelemetryResponse:
        """
        接收设备遥测数据
        
        更新设备位置和状态信息。
        """
        device = await self._repo.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        
        now = datetime.utcnow()
        
        # 更新设备属性中的遥测数据
        props = device.properties or {}
        props['last_telemetry'] = {
            'longitude': data.longitude,
            'latitude': data.latitude,
            'altitude_m': data.altitude_m,
            'heading': data.heading,
            'speed_ms': data.speed_ms,
            'battery_percent': data.battery_percent,
            'signal_strength': data.signal_strength,
            'sensors': data.sensors,
            'device_timestamp': data.timestamp.isoformat() if data.timestamp else None,
            'received_at': now.isoformat(),
        }
        device.properties = props
        
        await self._db.flush()
        
        logger.info(
            f"设备遥测数据: device_id={device_id}, "
            f"lon={data.longitude}, lat={data.latitude}, battery={data.battery_percent}"
        )
        
        return DeviceTelemetryResponse(
            device_id=device_id,
            received_at=now,
            location_updated=True,
            message="遥测数据已接收",
        )
    
    async def _validate_vehicle_capacity(
        self,
        vehicle_id: UUID,
        weight_kg: Decimal,
        volume_m3: Decimal,
        device_type: str,
    ) -> None:
        """验证车辆容量和兼容性"""
        from src.domains.resources.vehicles.repository import VehicleRepository
        vehicle_repo = VehicleRepository(self._db)
        
        capacity = await vehicle_repo.get_capacity_info(vehicle_id)
        if not capacity:
            raise NotFoundError("Vehicle", str(vehicle_id))
        
        # 检查容量
        remaining_weight = capacity['remaining_weight_kg']
        remaining_volume = capacity['remaining_volume_m3']
        remaining_slots = capacity['remaining_device_slots']
        
        if remaining_weight < weight_kg:
            raise ConflictError(
                error_code="VH_WEIGHT_EXCEEDED",
                message=f"车辆载重不足: 剩余{remaining_weight}kg, 需要{weight_kg}kg"
            )
        
        if remaining_volume < volume_m3:
            raise ConflictError(
                error_code="VH_VOLUME_EXCEEDED",
                message=f"车辆容积不足: 剩余{remaining_volume}m³, 需要{volume_m3}m³"
            )
        
        if remaining_slots < 1:
            raise ConflictError(
                error_code="VH_SLOTS_EXCEEDED",
                message="车辆设备位已满"
            )
    
    def _to_response(self, device) -> DeviceResponse:
        """ORM模型转响应模型"""
        return DeviceResponse(
            id=device.id,
            code=device.code,
            name=device.name,
            device_type=device.device_type,
            env_type=device.env_type,
            weight_kg=device.weight_kg,
            volume_m3=device.volume_m3,
            module_slots=device.module_slots or 0,
            current_module_count=device.current_module_count or 0,
            compatible_module_types=device.compatible_module_types or [],
            applicable_disasters=device.applicable_disasters or [],
            forbidden_disasters=device.forbidden_disasters or [],
            min_response_level=device.min_response_level,
            base_capabilities=device.base_capabilities or [],
            model=device.model,
            manufacturer=device.manufacturer,
            status=device.status,
            in_vehicle_id=device.in_vehicle_id,
            entity_id=device.entity_id,
            properties=device.properties or {},
            created_at=device.created_at,
            updated_at=device.updated_at,
        )
