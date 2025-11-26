"""
车辆API路由

接口前缀: /vehicles
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import VehicleService
from .schemas import (
    VehicleCreate, VehicleUpdate, VehicleResponse, 
    VehicleListResponse, VehicleStatus, VehicleCapacityCheck,
    VehicleLocationUpdate, VehicleLocationResponse,
)


router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def get_service(db: AsyncSession = Depends(get_db)) -> VehicleService:
    return VehicleService(db)


@router.post("", response_model=VehicleResponse, status_code=201)
async def create_vehicle(
    data: VehicleCreate,
    service: VehicleService = Depends(get_service),
) -> VehicleResponse:
    """
    创建车辆
    
    车辆是静态资源，不属于特定场景。通过方案资源分配关联到具体任务。
    """
    return await service.create(data)


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: available/deployed/maintenance"),
    vehicle_type: Optional[str] = Query(None, description="类型筛选"),
    service: VehicleService = Depends(get_service),
) -> VehicleListResponse:
    """分页查询车辆列表"""
    return await service.list(page, page_size, status, vehicle_type)


@router.get("/available", response_model=list[VehicleResponse])
async def list_available_vehicles(
    vehicle_type: Optional[str] = Query(None, description="车辆类型筛选"),
    min_weight_capacity: Optional[Decimal] = Query(None, ge=0, description="最小剩余载重(kg)"),
    required_terrain: Optional[str] = Query(None, description="必须具备的地形能力"),
    service: VehicleService = Depends(get_service),
) -> list[VehicleResponse]:
    """
    查询可用车辆（用于资源分配）
    
    - vehicle_type: 车辆类型筛选
    - min_weight_capacity: 最小剩余载重要求（公斤）
    - required_terrain: 必须具备的地形能力（如mountain/flood）
    """
    return await service.list_available(vehicle_type, min_weight_capacity, required_terrain)


@router.get("/code/{code}", response_model=VehicleResponse)
async def get_vehicle_by_code(
    code: str,
    service: VehicleService = Depends(get_service),
) -> VehicleResponse:
    """根据编号获取车辆"""
    return await service.get_by_code(code)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    service: VehicleService = Depends(get_service),
) -> VehicleResponse:
    """根据ID获取车辆详情"""
    return await service.get_by_id(vehicle_id)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    service: VehicleService = Depends(get_service),
) -> VehicleResponse:
    """
    更新车辆
    
    限制: 已出动(deployed)车辆不能修改载物能力参数
    """
    return await service.update(vehicle_id, data)


@router.post("/{vehicle_id}/status", response_model=VehicleResponse)
async def update_vehicle_status(
    vehicle_id: UUID,
    status: VehicleStatus = Query(..., description="目标状态"),
    service: VehicleService = Depends(get_service),
) -> VehicleResponse:
    """
    更新车辆状态
    
    状态转换规则:
    - available -> deployed, maintenance
    - deployed -> available
    - maintenance -> available
    """
    return await service.update_status(vehicle_id, status)


@router.get("/{vehicle_id}/capacity", response_model=VehicleCapacityCheck)
async def check_vehicle_capacity(
    vehicle_id: UUID,
    required_weight_kg: Decimal = Query(..., ge=0, description="需要的重量(kg)"),
    required_volume_m3: Decimal = Query(..., ge=0, description="需要的体积(m³)"),
    required_slots: int = Query(1, ge=1, description="需要的设备位数"),
    service: VehicleService = Depends(get_service),
) -> VehicleCapacityCheck:
    """
    检查车辆容量是否满足需求
    
    用于设备装载前的容量校验
    """
    return await service.check_capacity(
        vehicle_id, required_weight_kg, required_volume_m3, required_slots
    )


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: UUID,
    service: VehicleService = Depends(get_service),
) -> None:
    """
    删除车辆
    
    限制:
    - 已出动(deployed)车辆不能删除
    - 有装载设备的车辆不能删除
    """
    await service.delete(vehicle_id)


@router.patch("/{vehicle_id}/location", response_model=VehicleLocationResponse)
async def update_vehicle_location(
    vehicle_id: UUID,
    data: VehicleLocationUpdate,
    service: VehicleService = Depends(get_service),
) -> VehicleLocationResponse:
    """
    更新车辆位置
    
    由GPS遥测数据、手动输入或仿真模块调用。
    更新current_location和last_location_update字段。
    """
    return await service.update_location(vehicle_id, data)
