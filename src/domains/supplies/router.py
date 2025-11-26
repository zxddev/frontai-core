"""
物资管理API路由

接口前缀: /supplies
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import SupplyService
from .schemas import (
    SupplyCreate, SupplyUpdate, SupplyResponse, SupplyListResponse
)


router = APIRouter(prefix="/supplies", tags=["supplies"])


def get_service(db: AsyncSession = Depends(get_db)) -> SupplyService:
    return SupplyService(db)


@router.post("", response_model=SupplyResponse, status_code=201)
async def create_supply(
    data: SupplyCreate,
    service: SupplyService = Depends(get_service),
) -> SupplyResponse:
    """
    创建物资
    
    物资是救援行动中使用的消耗品或装备，如急救背囊、便携式AED等。
    创建后可通过车辆装载接口将物资分配到车辆。
    """
    return await service.create(data)


@router.get("", response_model=SupplyListResponse)
async def list_supplies(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="类别筛选: medical/protection/rescue/communication/life/tool"),
    is_consumable: Optional[bool] = Query(None, description="是否消耗品"),
    disaster_type: Optional[str] = Query(None, description="适用灾害类型筛选: earthquake/flood/fire/hazmat/landslide"),
    service: SupplyService = Depends(get_service),
) -> SupplyListResponse:
    """分页查询物资列表"""
    return await service.list(page, page_size, category, is_consumable, disaster_type)


@router.get("/category/{category}", response_model=list[SupplyResponse])
async def list_supplies_by_category(
    category: str,
    service: SupplyService = Depends(get_service),
) -> list[SupplyResponse]:
    """
    按类别查询物资
    
    category: medical/protection/rescue/communication/life/tool
    """
    return await service.list_by_category(category)


@router.get("/required/{disaster_type}", response_model=list[SupplyResponse])
async def list_required_supplies(
    disaster_type: str,
    service: SupplyService = Depends(get_service),
) -> list[SupplyResponse]:
    """
    查询指定灾害必须携带的物资
    
    返回required_for_disasters包含指定灾害类型的物资。
    用于AI装备建议和任务准备阶段。
    """
    return await service.list_required_for_disaster(disaster_type)


@router.get("/code/{code}", response_model=SupplyResponse)
async def get_supply_by_code(
    code: str,
    service: SupplyService = Depends(get_service),
) -> SupplyResponse:
    """根据编号获取物资"""
    return await service.get_by_code(code)


@router.get("/{supply_id}", response_model=SupplyResponse)
async def get_supply(
    supply_id: UUID,
    service: SupplyService = Depends(get_service),
) -> SupplyResponse:
    """根据ID获取物资详情"""
    return await service.get_by_id(supply_id)


@router.put("/{supply_id}", response_model=SupplyResponse)
async def update_supply(
    supply_id: UUID,
    data: SupplyUpdate,
    service: SupplyService = Depends(get_service),
) -> SupplyResponse:
    """更新物资信息"""
    return await service.update(supply_id, data)


@router.delete("/{supply_id}", status_code=204)
async def delete_supply(
    supply_id: UUID,
    service: SupplyService = Depends(get_service),
) -> None:
    """删除物资"""
    await service.delete(supply_id)
