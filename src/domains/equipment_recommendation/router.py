"""
装备推荐 Router
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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


async def _trigger_analysis_for_scenario(
    db: AsyncSession,
    *,
    scenario_id: UUID,
    entry_event_id: Optional[UUID] = None,
):
    """基于想定聚合其下所有事件后触发装备分析。

    - scenario_id: 想定ID
    - entry_event_id: 作为推荐记录挂载点的事件ID（不传则使用主事件）
    """

    # 查询该想定下的所有相关事件（主灾 + 次生灾害）
    events_result = await db.execute(
        text(
            """
            SELECT id, title, description, event_type, status
            FROM operational_v2.events_v2
            WHERE scenario_id = :scenario_id
              AND status <> 'cancelled'
            ORDER BY created_at ASC
            """
        ),
        {"scenario_id": str(scenario_id)},
    )
    events = events_result.fetchall()

    if not events:
        raise HTTPException(status_code=400, detail="该想定下没有可用事件")

    primary_event = events[0]

    # 确定用于挂载推荐记录的事件ID
    record_event_id: UUID
    if entry_event_id is not None:
        # 如果入口事件属于该想定，则优先用入口事件
        belongs = any(str(ev.id) == str(entry_event_id) for ev in events)
        record_event_id = entry_event_id if belongs else primary_event.id
    else:
        record_event_id = primary_event.id

    # 聚合灾情描述：第一个视为主灾，其余为次生灾害
    lines = []
    for idx, ev in enumerate(events, start=1):
        label = "主灾" if idx == 1 else "次生灾害"
        lines.append(f"[{label}] {ev.title} ({ev.event_type}, status={ev.status})")
        if ev.description:
            lines.append(ev.description)

    disaster_description = "\n".join(lines)

    primary_type = primary_event.event_type
    structured_input = {
        "disaster_type": primary_type,
        "primary_event_type": primary_type,
        "events": [
            {
                "id": str(ev.id),
                "type": ev.event_type,
                "status": ev.status,
            }
            for ev in events
        ],
    }

    service = EquipmentRecommendationService(db)
    await service.trigger_analysis(
        event_id=record_event_id,
        disaster_description=disaster_description,
        structured_input=structured_input,
        scenario_id=scenario_id,
    )

    return {
        "message": "分析已触发",
        "event_id": str(record_event_id),
        "scenario_id": str(scenario_id),
    }


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
    """按事件入口触发装备分析。

    仅用于兼容旧调用方式：仍然通过事件ID调用，但内部会基于该事件所在的
    想定(scenario)聚合其下所有相关事件（主灾 + 次生灾害）后再触发分析。

    - **event_id**: 入口事件ID
    """
    try:
        result = await db.execute(
            text(
                """
                SELECT scenario_id
                FROM operational_v2.events_v2
                WHERE id = :event_id
                """
            ),
            {"event_id": str(event_id)},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="事件不存在")
        scenario_id = row.scenario_id

        return await _trigger_analysis_for_scenario(
            db,
            scenario_id=scenario_id,
            entry_event_id=event_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"触发装备分析失败: event_id={event_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/equipment-recommendation/trigger",
    status_code=202,
    summary="按想定触发装备分析",
    description="基于指定想定下的所有事件（主灾+次生灾害）触发一次整体装备分析",
)
async def trigger_equipment_analysis_by_scenario(
    db: AsyncSession = Depends(get_db),
):
    """按想定触发装备分析。

    自动获取当前生效的想定（status='active'），以其为入口聚合该想定下所有
    相关事件（主灾 + 次生灾害）后触发装备推荐，不需要调用方传入任何ID。
    """
    try:
        # 与 overall_plan / recon_plan 保持一致：自动选择当前 active 想定
        result = await db.execute(
            text(
                "SELECT id FROM operational_v2.scenarios_v2 WHERE status = 'active' LIMIT 1"
            )
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有找到生效的想定，请先创建或激活一个想定",
            )

        scenario_id: UUID = row[0]
        return await _trigger_analysis_for_scenario(db, scenario_id=scenario_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("按想定触发装备分析失败: scenario_id=%s", scenario_id)
        raise HTTPException(status_code=500, detail=str(e))
