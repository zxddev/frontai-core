from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from src.core.database import get_db
from .service import EventService
from .schemas import (
    EventCreate, EventUpdate, EventResponse, EventStatusUpdate,
    EventConfirm, EventPreConfirmExtend, EventListResponse, EventStatistics,
    EventUpdateCreate, EventUpdateResponse, EventUpdateListResponse,
    BatchConfirmRequest, BatchConfirmResponse,
)


router = APIRouter(prefix="/events", tags=["events"])


def get_service(db: AsyncSession = Depends(get_db)) -> EventService:
    return EventService(db)


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    service: EventService = Depends(get_service),
):
    """创建/上报事件"""
    return await service.create(data)


@router.get("", response_model=EventListResponse)
async def list_events(
    scenario_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    event_type: Optional[str] = None,
    service: EventService = Depends(get_service),
):
    """获取事件列表"""
    return await service.list(scenario_id, page, page_size, status, priority, event_type)


@router.get("/pending-review", response_model=list[EventResponse])
async def get_pending_review_events(
    scenario_id: UUID,
    service: EventService = Depends(get_service),
):
    """获取待复核事件列表（pending + pre_confirmed）"""
    return await service.get_pending_review(scenario_id)


@router.get("/statistics", response_model=EventStatistics)
async def get_event_statistics(
    scenario_id: UUID,
    service: EventService = Depends(get_service),
):
    """获取事件统计数据"""
    return await service.get_statistics(scenario_id)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    service: EventService = Depends(get_service),
):
    """获取事件详情"""
    return await service.get_by_id(event_id)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    service: EventService = Depends(get_service),
):
    """更新事件信息"""
    return await service.update(event_id, data)


@router.post("/{event_id}/confirm", response_model=EventResponse)
async def confirm_event(
    event_id: UUID,
    data: EventConfirm,
    service: EventService = Depends(get_service),
):
    """人工确认事件"""
    return await service.confirm(event_id, data)


@router.post("/{event_id}/extend-pre-confirm", response_model=EventResponse)
async def extend_pre_confirm(
    event_id: UUID,
    data: EventPreConfirmExtend,
    service: EventService = Depends(get_service),
):
    """延长预确认倒计时"""
    return await service.extend_pre_confirm(event_id, data)


@router.post("/{event_id}/cancel", response_model=EventResponse)
async def cancel_event(
    event_id: UUID,
    reason: str = Query(..., description="取消原因"),
    service: EventService = Depends(get_service),
):
    """取消事件（误报等）"""
    return await service.cancel(event_id, reason)


@router.post("/{event_id}/escalate", response_model=EventResponse)
async def escalate_event(
    event_id: UUID,
    reason: str = Query(..., description="升级原因"),
    service: EventService = Depends(get_service),
):
    """升级事件"""
    return await service.escalate(event_id, reason)


@router.post("/{event_id}/status", response_model=EventResponse)
async def update_event_status(
    event_id: UUID,
    data: EventStatusUpdate,
    service: EventService = Depends(get_service),
):
    """更新事件状态"""
    return await service.update_status(event_id, data)


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: UUID,
    service: EventService = Depends(get_service),
):
    """删除事件（仅pending/cancelled状态可删除）"""
    await service.delete(event_id)


@router.get("/{event_id}/updates", response_model=EventUpdateListResponse)
async def get_event_updates(
    event_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: EventService = Depends(get_service),
):
    """获取事件更新记录列表"""
    return await service.get_updates(event_id, page, page_size)


@router.post("/{event_id}/updates", response_model=EventUpdateResponse, status_code=201)
async def add_event_update(
    event_id: UUID,
    data: EventUpdateCreate,
    service: EventService = Depends(get_service),
):
    """添加事件更新记录（现场反馈、情况变化等）"""
    return await service.add_update(event_id, data)


@router.post("/batch-confirm", response_model=BatchConfirmResponse)
async def batch_confirm_events(
    data: BatchConfirmRequest,
    service: EventService = Depends(get_service),
):
    """批量确认事件"""
    return await service.batch_confirm(data)
