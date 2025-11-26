"""
地图实体API路由

接口前缀: /entities, /layers
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import EntityService, LayerService
from .schemas import (
    EntityCreate, EntityUpdate, EntityResponse, EntityListResponse,
    EntityLocationUpdate, BatchLocationUpdate, EntityWithDistance,
    PlotCreate, PlotResponse,
    LayerResponse, LayerUpdate, LayerListResponse,
    TrackResponse,
)


# 实体路由
entity_router = APIRouter(prefix="/entities", tags=["entities"])

# 图层路由
layer_router = APIRouter(prefix="/layers", tags=["layers"])


def get_entity_service(db: AsyncSession = Depends(get_db)) -> EntityService:
    return EntityService(db)


def get_layer_service(db: AsyncSession = Depends(get_db)) -> LayerService:
    return LayerService(db)


# ============================================================================
# 实体管理接口
# ============================================================================

@entity_router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(
    data: EntityCreate,
    service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    """
    创建实体
    
    实体是地图上显示的各类对象，包括灾情点、救援队伍、设备等。
    """
    return await service.create(data)


@entity_router.get("", response_model=EntityListResponse)
async def list_entities(
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    entity_types: Optional[str] = Query(None, description="类型过滤，逗号分隔"),
    layer_code: Optional[str] = Query(None, description="图层过滤"),
    is_visible: Optional[bool] = Query(None, description="是否可见"),
    bbox: Optional[str] = Query(None, description="边界框 minLng,minLat,maxLng,maxLat"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量"),
    service: EntityService = Depends(get_entity_service),
) -> EntityListResponse:
    """获取实体列表"""
    return await service.list(
        scenario_id, entity_types, layer_code, is_visible, bbox, page, page_size
    )


@entity_router.get("/in-bounds", response_model=EntityListResponse)
async def list_entities_in_bounds(
    scenario_id: UUID = Query(..., description="想定ID"),
    bounds: str = Query(..., description="边界框 minLng,minLat,maxLng,maxLat"),
    entity_types: Optional[str] = Query(None, description="类型过滤，逗号分隔"),
    service: EntityService = Depends(get_entity_service),
) -> EntityListResponse:
    """获取边界框内的实体"""
    return await service.list_in_bounds(scenario_id, bounds, entity_types)


@entity_router.get("/nearby", response_model=list[EntityWithDistance])
async def list_entities_nearby(
    scenario_id: UUID = Query(..., description="想定ID"),
    center: str = Query(..., description="中心点 lng,lat"),
    radius_km: float = Query(..., gt=0, le=100, description="半径(公里)"),
    entity_types: Optional[str] = Query(None, description="类型过滤，逗号分隔"),
    service: EntityService = Depends(get_entity_service),
) -> list[EntityWithDistance]:
    """获取附近实体"""
    return await service.list_nearby(scenario_id, center, radius_km, entity_types)


@entity_router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    """根据ID获取实体详情"""
    return await service.get_by_id(entity_id)


@entity_router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    data: EntityUpdate,
    service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    """更新实体"""
    return await service.update(entity_id, data)


@entity_router.delete("/{entity_id}", status_code=204)
async def delete_entity(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service),
) -> None:
    """删除实体"""
    await service.delete(entity_id)


@entity_router.patch("/{entity_id}/location", response_model=EntityResponse)
async def update_entity_location(
    entity_id: UUID,
    data: EntityLocationUpdate,
    service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    """更新单个实体位置"""
    return await service.update_location(entity_id, data)


@entity_router.patch("/batch-location")
async def batch_update_location(
    data: BatchLocationUpdate,
    service: EntityService = Depends(get_entity_service),
) -> dict:
    """
    批量更新实体位置
    
    用于实时位置上报，自动记录轨迹并触发WebSocket推送
    """
    return await service.batch_update_location(data)


@entity_router.patch("/{entity_id}/visibility", response_model=EntityResponse)
async def update_entity_visibility(
    entity_id: UUID,
    visible: bool = Query(..., description="是否可见"),
    service: EntityService = Depends(get_entity_service),
) -> EntityResponse:
    """切换实体可见性"""
    return await service.update_visibility(entity_id, visible)


@entity_router.get("/{entity_id}/tracks", response_model=TrackResponse)
async def get_entity_tracks(
    entity_id: UUID,
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    sample_interval: Optional[int] = Query(None, ge=1, description="采样间隔(秒)"),
    service: EntityService = Depends(get_entity_service),
) -> TrackResponse:
    """获取实体历史轨迹"""
    return await service.get_tracks(entity_id, start_time, end_time, sample_interval)


@entity_router.post("/plot", response_model=PlotResponse, status_code=201)
async def create_plot(
    data: PlotCreate,
    service: EntityService = Depends(get_entity_service),
) -> PlotResponse:
    """
    态势标绘
    
    创建标绘图形（点/线/面/圆/箭头/文字）
    """
    return await service.create_plot(data)


# ============================================================================
# 图层管理接口
# ============================================================================

@layer_router.get("", response_model=LayerListResponse)
async def list_layers(
    service: LayerService = Depends(get_layer_service),
) -> LayerListResponse:
    """获取所有图层及其支持的类型"""
    return await service.list_all()


@layer_router.get("/{layer_id}", response_model=LayerResponse)
async def get_layer(
    layer_id: UUID,
    service: LayerService = Depends(get_layer_service),
) -> LayerResponse:
    """根据ID获取图层详情"""
    return await service.get_by_id(layer_id)


@layer_router.put("/{layer_id}", response_model=LayerResponse)
async def update_layer(
    layer_id: UUID,
    data: LayerUpdate,
    service: LayerService = Depends(get_layer_service),
) -> LayerResponse:
    """更新图层配置"""
    return await service.update(layer_id, data)
