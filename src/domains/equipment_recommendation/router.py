"""
装备推荐 Router
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import NotFoundError, ConflictError
from .service import EquipmentRecommendationService
from .schemas import (
    EquipmentRecommendationResponse,
    EquipmentRecommendationConfirm,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["equipment-recommendation"])


@router.get(
    "/{event_id}/equipment-recommendation",
    response_model=EquipmentRecommendationResponse,
    summary="获取事件的装备推荐",
    description="获取指定事件的AI装备推荐结果",
)
async def get_equipment_recommendation(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取事件的装备推荐
    
    - **event_id**: 事件ID
    
    Returns:
        装备推荐详情，包含推荐设备、物资、缺口告警、装载方案等
    """
    try:
        service = EquipmentRecommendationService(db)
        return await service.get_by_event_id(event_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{event_id}/equipment-recommendation/confirm",
    response_model=EquipmentRecommendationResponse,
    summary="确认装备推荐",
    description="指挥员确认装备推荐，选择最终携带的设备和物资",
)
async def confirm_equipment_recommendation(
    event_id: UUID,
    data: EquipmentRecommendationConfirm,
    db: AsyncSession = Depends(get_db),
    # TODO: 从认证获取用户ID
    # current_user: User = Depends(get_current_user),
):
    """
    确认装备推荐
    
    - **event_id**: 事件ID
    - **device_ids**: 确认的设备ID列表
    - **supplies**: 确认的物资列表 [{supply_id, quantity}]
    - **note**: 确认备注（可选）
    
    Returns:
        更新后的装备推荐
    """
    try:
        service = EquipmentRecommendationService(db)
        return await service.confirm(
            event_id=event_id,
            data=data,
            confirmed_by=None,  # TODO: current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/{event_id}/equipment-recommendation/trigger",
    status_code=202,
    summary="手动触发装备分析",
    description="手动触发装备分析（通常由事件创建自动触发）",
)
async def trigger_equipment_analysis(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发装备分析
    
    注意：通常装备分析在事件创建时自动触发，此接口用于重新分析。
    
    - **event_id**: 事件ID
    
    Returns:
        202 Accepted，分析将异步执行
    """
    try:
        # 获取事件信息
        from sqlalchemy import text
        result = await db.execute(
            text("""
                SELECT title, description, scenario_id, event_type
                FROM operational_v2.events_v2
                WHERE id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="事件不存在")
        
        service = EquipmentRecommendationService(db)
        await service.trigger_analysis(
            event_id=event_id,
            disaster_description=f"{row.title}\n{row.description or ''}",
            structured_input={"disaster_type": row.event_type},
            scenario_id=row.scenario_id,
        )
        
        return {"message": "分析已触发", "event_id": str(event_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"触发装备分析失败: event_id={event_id}")
        raise HTTPException(status_code=500, detail=str(e))
