"""
设备API路由

接口前缀: /devices
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import DeviceService
from .schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, 
    DeviceListResponse, DeviceStatus, DeviceLoadRequest, DeviceLoadResult,
    DeviceTelemetryData, DeviceTelemetryResponse,
)


router = APIRouter(prefix="/devices", tags=["devices"])


def get_service(db: AsyncSession = Depends(get_db)) -> DeviceService:
    return DeviceService(db)


@router.post("", response_model=DeviceResponse, status_code=201)
async def create_device(
    data: DeviceCreate,
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """
    创建设备
    
    设备包括无人机、机器狗、无人艇等。
    可在创建时直接指定装载到的车辆。
    """
    return await service.create(data)


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: available/deployed/charging/maintenance"),
    device_type: Optional[str] = Query(None, description="设备类型筛选: drone/dog/ship/robot"),
    env_type: Optional[str] = Query(None, description="作业环境筛选: air/land/sea"),
    in_vehicle_id: Optional[UUID] = Query(None, description="筛选指定车辆上的设备"),
    service: DeviceService = Depends(get_service),
) -> DeviceListResponse:
    """分页查询设备列表"""
    return await service.list(page, page_size, status, device_type, env_type, in_vehicle_id)


@router.get("/available", response_model=list[DeviceResponse])
async def list_available_devices(
    device_type: Optional[str] = Query(None, description="设备类型筛选"),
    env_type: Optional[str] = Query(None, description="作业环境筛选"),
    not_in_vehicle: bool = Query(False, description="仅查询未装载的设备"),
    service: DeviceService = Depends(get_service),
) -> list[DeviceResponse]:
    """
    查询可用设备（用于资源分配）
    
    仅返回状态为available的设备
    """
    return await service.list_available(device_type, env_type, not_in_vehicle)


@router.get("/vehicle/{vehicle_id}", response_model=list[DeviceResponse])
async def list_devices_by_vehicle(
    vehicle_id: UUID,
    service: DeviceService = Depends(get_service),
) -> list[DeviceResponse]:
    """查询车辆上装载的所有设备"""
    return await service.list_by_vehicle(vehicle_id)


@router.get("/code/{code}", response_model=DeviceResponse)
async def get_device_by_code(
    code: str,
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """根据编号获取设备"""
    return await service.get_by_code(code)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """根据ID获取设备详情"""
    return await service.get_by_id(device_id)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """更新设备信息"""
    return await service.update(device_id, data)


@router.post("/{device_id}/status", response_model=DeviceResponse)
async def update_device_status(
    device_id: UUID,
    status: DeviceStatus = Query(..., description="目标状态"),
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """
    更新设备状态
    
    状态转换规则:
    - available -> deployed, charging, maintenance
    - deployed/charging/maintenance -> available
    """
    return await service.update_status(device_id, status)


@router.post("/{device_id}/load", response_model=DeviceLoadResult)
async def load_device_to_vehicle(
    device_id: UUID,
    data: DeviceLoadRequest,
    service: DeviceService = Depends(get_service),
) -> DeviceLoadResult:
    """
    装载设备到车辆
    
    业务规则:
    - 设备必须是available状态
    - 车辆必须有足够容量（重量、体积、设备位）
    - 设备类型必须在车辆兼容列表中
    """
    return await service.load_to_vehicle(device_id, data)


@router.post("/{device_id}/unload", response_model=DeviceResponse)
async def unload_device_from_vehicle(
    device_id: UUID,
    service: DeviceService = Depends(get_service),
) -> DeviceResponse:
    """从车辆卸载设备"""
    return await service.unload_from_vehicle(device_id)


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: UUID,
    service: DeviceService = Depends(get_service),
) -> None:
    """
    删除设备
    
    限制:
    - 已部署(deployed)状态的设备不能删除
    - 装载在车辆上的设备需要先卸载
    """
    await service.delete(device_id)


@router.post("/{device_id}/telemetry", response_model=DeviceTelemetryResponse)
async def receive_device_telemetry(
    device_id: UUID,
    data: DeviceTelemetryData,
    service: DeviceService = Depends(get_service),
) -> DeviceTelemetryResponse:
    """
    接收设备遥测数据
    
    由设备网关或仿真模块调用，上报设备位置、电量、传感器数据等。
    数据存储在properties.last_telemetry中。
    """
    return await service.receive_telemetry(device_id, data)
