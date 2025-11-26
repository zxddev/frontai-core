"""
前端事件API路由

接口路径: /events/*
对接前端事件确认等操作
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.events.service import EventService
from src.domains.events.schemas import EventConfirm
from src.domains.frontend_api.common import ApiResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["前端-事件"])


def get_event_service(db: AsyncSession = Depends(get_db)) -> EventService:
    """获取事件服务实例"""
    return EventService(db)


@router.get("/event-confirm", response_model=ApiResponse)
async def confirm_event(
    eventId: Optional[str] = Query(None, description="事件ID，不传则确认最新待确认事件"),
    scenarioId: Optional[str] = Query(None, description="想定ID"),
    service: EventService = Depends(get_event_service),
) -> ApiResponse:
    """
    灾害事件确认
    
    前端调用时机：指挥员收到事件消息后点击确认
    业务逻辑：
    1. 如果传了eventId，确认指定事件
    2. 如果没传eventId但传了scenarioId，确认该想定下最新的待确认事件
    3. 都没传则返回错误
    """
    logger.info(f"事件确认请求, eventId={eventId}, scenarioId={scenarioId}")
    
    try:
        if eventId:
            event_uuid = UUID(eventId)
            confirm_data = EventConfirm(confirmation_note="前端确认")
            result = await service.confirm(event_uuid, confirm_data)
            logger.info(f"事件确认成功, eventId={eventId}")
            return ApiResponse.success({"eventId": str(result.id), "status": result.status})
        
        elif scenarioId:
            scenario_uuid = UUID(scenarioId)
            pending_events = await service.get_pending_review(scenario_uuid)
            
            if not pending_events:
                logger.info(f"没有待确认事件, scenarioId={scenarioId}")
                return ApiResponse.success(None, "没有待确认的事件")
            
            latest_event = pending_events[0]
            confirm_data = EventConfirm(confirmation_note="前端确认")
            result = await service.confirm(latest_event.id, confirm_data)
            logger.info(f"确认最新事件成功, eventId={latest_event.id}")
            return ApiResponse.success({"eventId": str(result.id), "status": result.status})
        
        else:
            return ApiResponse.error(400, "需要提供eventId或scenarioId")
            
    except ValueError as e:
        logger.warning(f"无效的ID格式: {e}")
        return ApiResponse.error(400, f"无效的ID格式: {str(e)}")
    except Exception as e:
        logger.exception(f"事件确认失败: {e}")
        return ApiResponse.error(500, f"事件确认失败: {str(e)}")


@router.get("/pending", response_model=ApiResponse)
async def get_pending_events(
    scenarioId: str = Query(..., description="想定ID"),
    service: EventService = Depends(get_event_service),
) -> ApiResponse:
    """
    获取待确认事件列表
    
    返回pending和pre_confirmed状态的事件
    """
    logger.info(f"获取待确认事件列表, scenarioId={scenarioId}")
    
    try:
        scenario_uuid = UUID(scenarioId)
        events = await service.get_pending_review(scenario_uuid)
        
        result = []
        for event in events:
            result.append({
                "eventId": str(event.id),
                "title": event.title,
                "description": event.description,
                "status": event.status,
                "priority": event.priority,
                "eventType": event.event_type,
                "location": {
                    "longitude": event.location.longitude,
                    "latitude": event.location.latitude,
                },
                "address": event.address,
                "reportedAt": event.reported_at.isoformat() if event.reported_at else None,
            })
        
        logger.info(f"返回待确认事件数量: {len(result)}")
        return ApiResponse.success(result)
        
    except ValueError as e:
        logger.warning(f"无效的ID格式: {e}")
        return ApiResponse.error(400, f"无效的ID格式: {str(e)}")
    except Exception as e:
        logger.exception(f"获取待确认事件失败: {e}")
        return ApiResponse.error(500, f"获取待确认事件失败: {str(e)}")
