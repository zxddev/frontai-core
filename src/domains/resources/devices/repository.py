"""
设备数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Device
from .schemas import DeviceCreate, DeviceUpdate

logger = logging.getLogger(__name__)


class DeviceRepository:
    """设备数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: DeviceCreate) -> Device:
        """创建设备"""
        device = Device(
            code=data.code,
            name=data.name,
            device_type=data.device_type.value,
            env_type=data.env_type.value,
            weight_kg=data.weight_kg,
            volume_m3=data.volume_m3,
            module_slots=data.module_slots,
            compatible_module_types=[mt.value for mt in data.compatible_module_types],
            applicable_disasters=data.applicable_disasters,
            forbidden_disasters=data.forbidden_disasters,
            min_response_level=data.min_response_level,
            base_capabilities=data.base_capabilities,
            model=data.model,
            manufacturer=data.manufacturer,
            in_vehicle_id=data.in_vehicle_id,
            entity_id=data.entity_id,
            properties=data.properties,
            status='available',
        )
        self._db.add(device)
        await self._db.flush()
        await self._db.refresh(device)
        
        logger.info(f"创建设备: code={device.code}, id={device.id}")
        return device
    
    async def get_by_id(self, device_id: UUID) -> Optional[Device]:
        """根据ID查询设备"""
        result = await self._db.execute(
            select(Device).where(Device.id == device_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Device]:
        """根据编号查询设备"""
        result = await self._db.execute(
            select(Device).where(Device.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
        env_type: Optional[str] = None,
        in_vehicle_id: Optional[UUID] = None,
    ) -> tuple[Sequence[Device], int]:
        """
        分页查询设备列表
        
        Returns:
            (设备列表, 总数)
        """
        query = select(Device)
        count_query = select(func.count(Device.id))
        
        if status:
            query = query.where(Device.status == status)
            count_query = count_query.where(Device.status == status)
        
        if device_type:
            query = query.where(Device.device_type == device_type)
            count_query = count_query.where(Device.device_type == device_type)
        
        if env_type:
            query = query.where(Device.env_type == env_type)
            count_query = count_query.where(Device.env_type == env_type)
        
        if in_vehicle_id is not None:
            query = query.where(Device.in_vehicle_id == in_vehicle_id)
            count_query = count_query.where(Device.in_vehicle_id == in_vehicle_id)
        
        query = query.order_by(Device.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_available(
        self,
        device_type: Optional[str] = None,
        env_type: Optional[str] = None,
        not_in_vehicle: bool = False,
    ) -> Sequence[Device]:
        """
        查询可用设备
        
        Args:
            device_type: 设备类型筛选
            env_type: 作业环境筛选
            not_in_vehicle: 是否仅查询未装载的设备
        """
        query = select(Device).where(Device.status == 'available')
        
        if device_type:
            query = query.where(Device.device_type == device_type)
        
        if env_type:
            query = query.where(Device.env_type == env_type)
        
        if not_in_vehicle:
            query = query.where(Device.in_vehicle_id.is_(None))
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def list_by_vehicle(self, vehicle_id: UUID) -> Sequence[Device]:
        """查询车辆上装载的设备"""
        result = await self._db.execute(
            select(Device).where(Device.in_vehicle_id == vehicle_id)
        )
        return result.scalars().all()
    
    async def update(self, device: Device, data: DeviceUpdate) -> Device:
        """更新设备"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 枚举转字符串
        if 'compatible_module_types' in update_dict and update_dict['compatible_module_types']:
            update_dict['compatible_module_types'] = [
                mt.value if hasattr(mt, 'value') else mt 
                for mt in update_dict['compatible_module_types']
            ]
        if 'status' in update_dict and update_dict['status']:
            update_dict['status'] = (
                update_dict['status'].value 
                if hasattr(update_dict['status'], 'value') 
                else update_dict['status']
            )
        
        for key, value in update_dict.items():
            setattr(device, key, value)
        
        await self._db.flush()
        await self._db.refresh(device)
        
        logger.info(f"更新设备: id={device.id}, fields={list(update_dict.keys())}")
        return device
    
    async def update_status(self, device: Device, status: str) -> Device:
        """更新设备状态"""
        old_status = device.status
        device.status = status
        await self._db.flush()
        await self._db.refresh(device)
        
        logger.info(f"设备状态变更: id={device.id}, {old_status} -> {status}")
        return device
    
    async def load_to_vehicle(self, device: Device, vehicle_id: UUID) -> Device:
        """装载设备到车辆"""
        device.in_vehicle_id = vehicle_id
        await self._db.flush()
        await self._db.refresh(device)
        
        logger.info(f"设备装载到车辆: device_id={device.id}, vehicle_id={vehicle_id}")
        return device
    
    async def unload_from_vehicle(self, device: Device) -> Device:
        """从车辆卸载设备"""
        old_vehicle_id = device.in_vehicle_id
        device.in_vehicle_id = None
        await self._db.flush()
        await self._db.refresh(device)
        
        logger.info(f"设备从车辆卸载: device_id={device.id}, old_vehicle_id={old_vehicle_id}")
        return device
    
    async def delete(self, device: Device) -> None:
        """删除设备"""
        device_id = device.id
        await self._db.delete(device)
        await self._db.flush()
        
        logger.info(f"删除设备: id={device_id}")
    
    async def check_code_exists(self, code: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查编号是否已存在"""
        query = select(func.count(Device.id)).where(Device.code == code)
        if exclude_id:
            query = query.where(Device.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
