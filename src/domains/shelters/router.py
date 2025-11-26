"""
疏散安置点API路由

接口前缀: /shelters
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import ShelterService
from .schemas import (
    ShelterCreate, ShelterUpdate, ShelterCapacityUpdate, ShelterStatusUpdate,
    ShelterResponse, ShelterListResponse,
    ShelterNearbyQuery, ShelterNearbyResult, Location
)


router = APIRouter(prefix="/shelters", tags=["shelters"])


def get_service(db: AsyncSession = Depends(get_db)) -> ShelterService:
    return ShelterService(db)


@router.post("", response_model=ShelterResponse, status_code=201)
async def create_shelter(
    data: ShelterCreate,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """
    创建安置点
    
    安置点用于人员疏散和临时安置。
    scenario_id为空表示常备安置点，可在多个想定中使用。
    """
    return await service.create(data)


@router.get("", response_model=ShelterListResponse)
async def list_shelters(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID（包含常备安置点）"),
    shelter_type: Optional[str] = Query(None, description="类型筛选: temporary/permanent/medical/supply_depot/command_post/helipad/staging_area"),
    status: Optional[str] = Query(None, description="状态筛选: preparing/open/full/limited/closed/damaged"),
    service: ShelterService = Depends(get_service),
) -> ShelterListResponse:
    """分页查询安置点列表"""
    return await service.list(page, page_size, scenario_id, shelter_type, status)


@router.get("/available", response_model=list[ShelterResponse])
async def list_available_shelters(
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    shelter_type: Optional[str] = Query(None, description="安置点类型筛选"),
    min_capacity: int = Query(1, ge=1, description="最小剩余容量要求"),
    service: ShelterService = Depends(get_service),
) -> list[ShelterResponse]:
    """
    查询可用安置点（用于人员疏散分配）
    
    仅返回状态为open且有剩余容量的安置点
    """
    return await service.list_available(scenario_id, shelter_type, min_capacity)


@router.get("/nearby", response_model=list[ShelterNearbyResult])
async def find_nearby_shelters(
    longitude: float = Query(..., ge=-180, le=180, description="查询中心点经度"),
    latitude: float = Query(..., ge=-90, le=90, description="查询中心点纬度"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    required_capacity: int = Query(1, ge=1, description="需要的容量"),
    limit: int = Query(5, ge=1, le=20, description="返回数量上限"),
    service: ShelterService = Depends(get_service),
) -> list[ShelterNearbyResult]:
    """
    查找最近的可用安置点
    
    调用数据库空间查询函数，返回按距离排序的安置点列表。
    仅返回开放且有足够剩余容量的安置点。
    """
    query = ShelterNearbyQuery(
        location=Location(longitude=longitude, latitude=latitude),
        scenario_id=scenario_id,
        required_capacity=required_capacity,
        limit=limit,
    )
    return await service.find_nearest(query)


@router.get("/code/{code}", response_model=ShelterResponse)
async def get_shelter_by_code(
    code: str,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """根据编号获取安置点"""
    return await service.get_by_code(code)


@router.get("/{shelter_id}", response_model=ShelterResponse)
async def get_shelter(
    shelter_id: UUID,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """根据ID获取安置点详情"""
    return await service.get_by_id(shelter_id)


@router.put("/{shelter_id}", response_model=ShelterResponse)
async def update_shelter(
    shelter_id: UUID,
    data: ShelterUpdate,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """更新安置点基本信息"""
    return await service.update(shelter_id, data)


@router.patch("/{shelter_id}/capacity", response_model=ShelterResponse)
async def update_shelter_capacity(
    shelter_id: UUID,
    data: ShelterCapacityUpdate,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """
    更新安置点容量
    
    更新总容量或当前入住人数。
    当入住人数达到总容量时，状态自动变为full。
    当有空位时，状态自动从full恢复为open。
    """
    return await service.update_capacity(shelter_id, data)


@router.patch("/{shelter_id}/status", response_model=ShelterResponse)
async def update_shelter_status(
    shelter_id: UUID,
    data: ShelterStatusUpdate,
    service: ShelterService = Depends(get_service),
) -> ShelterResponse:
    """
    更新安置点状态
    
    状态转换规则:
    - preparing -> open, closed
    - open -> full, limited, closed, damaged
    - full -> open, limited, closed
    - limited -> open, closed
    - closed -> open, preparing
    - damaged -> closed, preparing
    """
    return await service.update_status(shelter_id, data)


@router.delete("/{shelter_id}", status_code=204)
async def delete_shelter(
    shelter_id: UUID,
    service: ShelterService = Depends(get_service),
) -> None:
    """
    删除安置点
    
    限制:
    - 有人员入住的安置点不能删除
    - 开放中的安置点不能删除
    """
    await service.delete(shelter_id)
