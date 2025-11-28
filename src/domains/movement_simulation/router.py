"""
移动仿真API路由

提供移动控制的REST API接口
路由前缀: /movement
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .schemas import (
    MovementStartRequest, MovementStartResponse,
    BatchMovementStartRequest, BatchMovementStartResponse,
    MovementStatusResponse, ActiveSessionsResponse,
)
from .service import get_movement_manager, MovementSimulationManager
from .batch_service import get_batch_service, BatchMovementService


router = APIRouter(prefix="/movement", tags=["movement-simulation"])


async def get_manager() -> MovementSimulationManager:
    """获取移动管理器依赖"""
    return await get_movement_manager()


async def get_batch_svc() -> BatchMovementService:
    """获取批量服务依赖"""
    return await get_batch_service()


# =============================================================================
# 单实体移动API
# =============================================================================

@router.post("/start", response_model=MovementStartResponse, status_code=status.HTTP_201_CREATED)
async def start_movement(
    request: MovementStartRequest,
    db: AsyncSession = Depends(get_db),
    manager: MovementSimulationManager = Depends(get_manager),
) -> MovementStartResponse:
    """
    启动移动
    
    根据提供的路径启动实体移动仿真，返回会话ID用于后续控制。
    
    - **entity_id**: 地图实体ID
    - **entity_type**: 实体类型 (vehicle/team/uav/robotic_dog/usv)
    - **resource_id**: 资源ID，用于获取速度（可选）
    - **route**: 路径点数组 [[lng, lat], ...]
    - **speed_mps**: 覆盖速度（可选）
    - **waypoints**: 任务停靠点（可选）
    """
    try:
        return await manager.start_movement(request, db)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)


@router.post("/{session_id}/pause", response_model=MovementStatusResponse)
async def pause_movement(
    session_id: str,
    manager: MovementSimulationManager = Depends(get_manager),
) -> MovementStatusResponse:
    """
    暂停移动
    
    暂停指定会话的移动，保留当前位置和进度。
    """
    try:
        return await manager.pause_movement(session_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/{session_id}/resume", response_model=MovementStatusResponse)
async def resume_movement(
    session_id: str,
    manager: MovementSimulationManager = Depends(get_manager),
) -> MovementStatusResponse:
    """
    恢复移动
    
    恢复之前暂停的移动会话。
    """
    try:
        return await manager.resume_movement(session_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/{session_id}/cancel", response_model=MovementStatusResponse)
async def cancel_movement(
    session_id: str,
    manager: MovementSimulationManager = Depends(get_manager),
) -> MovementStatusResponse:
    """
    取消移动
    
    取消移动会话，不可恢复。
    """
    try:
        return await manager.cancel_movement(session_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.get("/{session_id}/status", response_model=MovementStatusResponse)
async def get_movement_status(
    session_id: str,
    manager: MovementSimulationManager = Depends(get_manager),
) -> MovementStatusResponse:
    """
    获取移动状态
    
    返回当前位置、进度、预计剩余时间等信息。
    """
    try:
        return await manager.get_status(session_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


@router.get("/active", response_model=ActiveSessionsResponse)
async def list_active_sessions(
    manager: MovementSimulationManager = Depends(get_manager),
) -> ActiveSessionsResponse:
    """
    获取所有活跃会话
    
    返回所有正在进行中的移动会话列表。
    """
    sessions = await manager.get_active_sessions()
    return ActiveSessionsResponse(total=len(sessions), sessions=sessions)


# =============================================================================
# 批量移动API
# =============================================================================

@router.post("/batch/start", response_model=BatchMovementStartResponse, status_code=status.HTTP_201_CREATED)
async def start_batch_movement(
    request: BatchMovementStartRequest,
    db: AsyncSession = Depends(get_db),
    batch_svc: BatchMovementService = Depends(get_batch_svc),
) -> BatchMovementStartResponse:
    """
    启动批量移动
    
    支持多实体协同移动（编队）。
    
    编队模式：
    - **convoy**: 纵队，依次出发，间隔 interval_s 秒
    - **parallel**: 并行，同时出发
    - **staggered**: 交错，奇偶分组出发
    
    - **movements**: 各实体移动请求列表
    - **formation**: 编队模式
    - **interval_s**: 间隔时间（秒）
    - **shared_route**: 共享路径（覆盖各自路径）
    """
    try:
        return await batch_svc.start_batch(request, db)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/batch/{batch_id}/pause")
async def pause_batch_movement(
    batch_id: str,
    batch_svc: BatchMovementService = Depends(get_batch_svc),
):
    """
    暂停批量移动
    
    暂停批量会话中的所有移动。
    """
    try:
        results = await batch_svc.pause_batch(batch_id)
        return {"batch_id": batch_id, "paused_count": len(results)}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


@router.post("/batch/{batch_id}/resume")
async def resume_batch_movement(
    batch_id: str,
    batch_svc: BatchMovementService = Depends(get_batch_svc),
):
    """
    恢复批量移动
    
    恢复批量会话中所有暂停的移动。
    """
    try:
        results = await batch_svc.resume_batch(batch_id)
        return {"batch_id": batch_id, "resumed_count": len(results)}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


@router.post("/batch/{batch_id}/cancel")
async def cancel_batch_movement(
    batch_id: str,
    batch_svc: BatchMovementService = Depends(get_batch_svc),
):
    """
    取消批量移动
    
    取消批量会话中的所有移动。
    """
    try:
        results = await batch_svc.cancel_batch(batch_id)
        return {"batch_id": batch_id, "cancelled_count": len(results)}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    batch_svc: BatchMovementService = Depends(get_batch_svc),
):
    """
    获取批量移动状态
    
    返回批量会话的整体状态和各子会话状态。
    """
    try:
        return await batch_svc.get_batch_status(batch_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
