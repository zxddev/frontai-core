from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from decimal import Decimal

from .repository import EventRepository
from .schemas import (
    EventCreate, EventUpdate, EventResponse, EventStatusUpdate,
    EventConfirm, EventPreConfirmExtend, EventListResponse, EventStatistics, Location,
    EventUpdateCreate, EventUpdateResponse, EventUpdateListResponse,
    BatchConfirmRequest, BatchConfirmResponse, BatchConfirmResult,
)
from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from src.core.stomp.broker import stomp_broker
import logging

logger = logging.getLogger(__name__)


# 事件类型映射（内部类型 -> 前端数字类型）
EVENT_TYPE_MAP = {
    "earthquake": 1,  # 地震（主震）- 前端图标目录为 event/1/
    "trapped_person": 1,
    "fire": 2,
    "flood": 3,
    "landslide": 4,
    "building_collapse": 5,
    "road_damage": 6,
    "power_outage": 7,
    "communication_lost": 8,
    "hazmat_leak": 9,
    "epidemic": 10,
    "earthquake_secondary": 11,
    "other": 99,
}

# 优先级映射（内部优先级 -> 前端eventLevel）
PRIORITY_LEVEL_MAP = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


AUTO_CONFIRM_THRESHOLD = Decimal("0.85")
PRE_CONFIRM_THRESHOLD = Decimal("0.60")


class EventService:
    def __init__(self, db: AsyncSession):
        self.repo = EventRepository(db)
    
    async def create(self, data: EventCreate, reported_by: Optional[UUID] = None) -> EventResponse:
        event_code = await self.repo.get_next_event_code(data.scenario_id)
        event = await self.repo.create(data, event_code, reported_by)
        
        if data.confirmation_score is not None:
            score = Decimal(str(data.confirmation_score))
            if score >= AUTO_CONFIRM_THRESHOLD:
                event = await self.repo.confirm(event, auto=True)
            elif score >= PRE_CONFIRM_THRESHOLD:
                event = await self.repo.pre_confirm(event)
            elif data.priority == "critical" and data.is_time_critical:
                event = await self.repo.pre_confirm(event)
        
        response = self._to_response(event)
        
        # 广播事件到前端
        await self._broadcast_event_to_frontend(response)
        
        # 异步触发装备准备智能体分析
        await self._trigger_equipment_analysis(response, data)
        
        return response
    
    async def _trigger_equipment_analysis(
        self, 
        event: EventResponse, 
        data: EventCreate
    ) -> None:
        """异步触发装备准备智能体分析"""
        try:
            from src.domains.equipment_recommendation.service import EquipmentRecommendationService
            
            # 构建灾情描述
            disaster_description = f"{event.title}\n{event.description or ''}"
            if event.address:
                disaster_description += f"\n位置: {event.address}"
            
            # 构建结构化输入
            structured_input = {
                "disaster_type": event.event_type.value,
                "location": {
                    "longitude": event.location.longitude,
                    "latitude": event.location.latitude,
                },
                "severity": event.priority.value,
                "estimated_victims": event.estimated_victims,
                "is_time_critical": event.is_time_critical,
            }
            
            # 使用新的db session触发（因为原session可能已提交）
            from src.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                service = EquipmentRecommendationService(db)
                await service.trigger_analysis(
                    event_id=event.id,
                    disaster_description=disaster_description,
                    structured_input=structured_input,
                    scenario_id=event.scenario_id,
                )
            
            logger.info(f"已触发装备分析: event_id={event.id}")
        except Exception as e:
            # 装备分析失败不应影响事件创建
            logger.error(f"触发装备分析失败: {e}")
    
    async def get_by_id(self, event_id: UUID) -> EventResponse:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        return self._to_response(event)
    
    async def list(
        self,
        scenario_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> EventListResponse:
        items, total = await self.repo.list(scenario_id, page, page_size, status, priority, event_type)
        return EventListResponse(
            items=[self._to_response(e) for e in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def get_pending_review(self, scenario_id: UUID) -> list[EventResponse]:
        """获取待复核事件列表"""
        items = await self.repo.get_pending_review(scenario_id)
        return [self._to_response(e) for e in items]
    
    async def update(self, event_id: UUID, data: EventUpdate) -> EventResponse:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status in ("resolved", "cancelled"):
            raise ConflictError("EV4005", "Cannot update resolved or cancelled event")
        
        old_values = {"priority": event.priority, "estimated_victims": event.estimated_victims}
        event = await self.repo.update(event, data)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="info_update",
            previous_value=old_values,
            new_value=data.model_dump(exclude_unset=True),
        )
        
        return self._to_response(event)
    
    async def confirm(self, event_id: UUID, data: EventConfirm, confirmed_by: Optional[UUID] = None) -> EventResponse:
        """人工确认事件"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status not in ("pending", "pre_confirmed"):
            raise ConflictError("EV4006", f"Cannot confirm event in status: {event.status}")
        
        if data.priority_override:
            event.priority = data.priority_override.value
        
        event = await self.repo.confirm(event, confirmed_by, auto=False)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="status_change",
            previous_value={"status": "pending"},
            new_value={"status": "confirmed"},
            description=data.confirmation_note,
            updated_by=confirmed_by,
        )
        
        return self._to_response(event)
    
    async def extend_pre_confirm(self, event_id: UUID, data: EventPreConfirmExtend) -> EventResponse:
        """延长预确认倒计时"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status != "pre_confirmed":
            raise ConflictError("EV4007", "Can only extend pre_confirmed events")
        
        event = await self.repo.extend_pre_confirm(event, data.extend_minutes)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="pre_confirm_extend",
            previous_value=None,
            new_value={"extend_minutes": data.extend_minutes},
            description=data.reason,
        )
        
        return self._to_response(event)
    
    async def cancel(self, event_id: UUID, reason: str) -> EventResponse:
        """取消事件（误报等）"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status in ("resolved", "cancelled"):
            raise ConflictError("EV4008", f"Cannot cancel event in status: {event.status}")
        
        old_status = event.status
        event = await self.repo.cancel(event, reason)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="status_change",
            previous_value={"status": old_status},
            new_value={"status": "cancelled"},
            description=reason,
        )
        
        return self._to_response(event)
    
    async def escalate(self, event_id: UUID, reason: str) -> EventResponse:
        """升级事件"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status in ("resolved", "cancelled", "escalated"):
            raise ConflictError("EV4009", f"Cannot escalate event in status: {event.status}")
        
        old_status = event.status
        event = await self.repo.escalate(event)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="status_change",
            previous_value={"status": old_status},
            new_value={"status": "escalated"},
            description=reason,
        )
        
        return self._to_response(event)
    
    async def update_status(self, event_id: UUID, data: EventStatusUpdate) -> EventResponse:
        """更新事件状态"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        valid_transitions = {
            "pending": ["pre_confirmed", "confirmed", "cancelled"],
            "pre_confirmed": ["confirmed", "cancelled"],
            "confirmed": ["planning", "cancelled"],
            "planning": ["executing", "cancelled"],
            "executing": ["resolved", "escalated"],
            "resolved": [],
            "escalated": ["executing", "resolved"],
            "cancelled": [],
        }
        
        current = event.status
        target = data.status.value
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError("EV4010", f"Invalid status transition: {current} -> {target}")
        
        old_status = event.status
        event = await self.repo.update_status(event, target)
        
        await self.repo.add_update_record(
            event_id=event.id,
            update_type="status_change",
            previous_value={"status": old_status},
            new_value={"status": target},
            description=data.reason,
        )
        
        return self._to_response(event)
    
    async def get_statistics(self, scenario_id: UUID) -> EventStatistics:
        stats = await self.repo.get_statistics(scenario_id)
        return EventStatistics(**stats)
    
    async def delete(self, event_id: UUID) -> None:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status not in ("pending", "cancelled"):
            raise ConflictError("EV4011", "Can only delete pending or cancelled events")
        
        await self.repo.delete(event)
    
    async def get_updates(
        self,
        event_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> EventUpdateListResponse:
        """获取事件更新记录"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        items, total = await self.repo.get_updates(event_id, page, page_size)
        
        return EventUpdateListResponse(
            items=[EventUpdateResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def add_update(
        self,
        event_id: UUID,
        data: EventUpdateCreate,
        updated_by: Optional[UUID] = None,
    ) -> EventUpdateResponse:
        """添加事件更新记录"""
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", str(event_id))
        
        if event.status in ("resolved", "cancelled"):
            raise ConflictError("EV4012", "Cannot add updates to resolved or cancelled events")
        
        logger.info(f"添加事件更新: event_id={event_id}, type={data.update_type}")
        
        record = await self.repo.add_update_record(
            event_id=event_id,
            update_type=data.update_type.value,
            previous_value=None,
            new_value=data.new_value,
            description=data.description,
            updated_by=updated_by,
            source_type=data.source_type.value,
        )
        
        return EventUpdateResponse.model_validate(record)
    
    async def batch_confirm(
        self,
        data: BatchConfirmRequest,
        confirmed_by: Optional[UUID] = None,
    ) -> BatchConfirmResponse:
        """批量确认事件"""
        confirmed: list[UUID] = []
        failed: list[BatchConfirmResult] = []
        
        events = await self.repo.get_by_ids(data.event_ids)
        event_map = {e.id: e for e in events}
        
        for event_id in data.event_ids:
            event = event_map.get(event_id)
            
            if not event:
                failed.append(BatchConfirmResult(
                    id=event_id,
                    success=False,
                    error="事件不存在"
                ))
                continue
            
            if event.status not in ("pending", "pre_confirmed"):
                failed.append(BatchConfirmResult(
                    id=event_id,
                    success=False,
                    error=f"状态不允许确认: {event.status}"
                ))
                continue
            
            try:
                await self.repo.confirm(event, confirmed_by, auto=False)
                
                await self.repo.add_update_record(
                    event_id=event.id,
                    update_type="status_change",
                    previous_value={"status": event.status},
                    new_value={"status": "confirmed"},
                    description=data.reason or "批量确认",
                    updated_by=confirmed_by,
                )
                
                confirmed.append(event_id)
                logger.info(f"批量确认成功: event_id={event_id}")
                
            except Exception as e:
                logger.error(f"批量确认失败: event_id={event_id}, error={e}")
                failed.append(BatchConfirmResult(
                    id=event_id,
                    success=False,
                    error=str(e)
                ))
        
        return BatchConfirmResponse(
            confirmed=confirmed,
            failed=failed,
            total_requested=len(data.event_ids),
            total_confirmed=len(confirmed),
        )
    
    def _to_response(self, event) -> EventResponse:
        from shapely import wkb
        point = wkb.loads(bytes(event.location.data))
        location = Location(longitude=point.x, latitude=point.y)
        
        return EventResponse(
            id=event.id,
            scenario_id=event.scenario_id,
            event_code=event.event_code,
            event_type=event.event_type,
            source_type=event.source_type,
            source_detail=event.source_detail,
            title=event.title,
            description=event.description,
            location=location,
            address=event.address,
            status=event.status,
            priority=event.priority,
            estimated_victims=event.estimated_victims or 0,
            rescued_count=event.rescued_count or 0,
            casualty_count=event.casualty_count or 0,
            is_time_critical=event.is_time_critical or False,
            golden_hour_deadline=event.golden_hour_deadline,
            auto_confirmed=event.auto_confirmed or False,
            confirmation_score=float(event.confirmation_score) if event.confirmation_score else None,
            pre_confirm_expires_at=event.pre_confirm_expires_at,
            pre_allocated_resources=event.pre_allocated_resources,
            media_attachments=event.media_attachments,
            reported_at=event.reported_at,
            confirmed_at=event.confirmed_at,
            pre_confirmed_at=event.pre_confirmed_at,
            resolved_at=event.resolved_at,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )
    
    async def _broadcast_event_to_frontend(self, event: EventResponse) -> None:
        """广播事件到前端（符合前端期望的消息格式）"""
        try:
            # 转换为前端期望的格式
            frontend_payload = {
                "eventId": str(event.id),
                "title": event.title,
                "eventLevel": PRIORITY_LEVEL_MAP.get(event.priority.value, 2),
                "eventType": EVENT_TYPE_MAP.get(event.event_type.value, 99),
                "location": [event.location.longitude, event.location.latitude],
                "time": event.reported_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "origin": event.source_type.value,
                "data": event.description or "",
                # 附加字段（前端可选使用）
                "eventCode": event.event_code,
                "status": event.status.value,
                "address": event.address,
                "estimatedVictims": event.estimated_victims,
                "isTimeCritical": event.is_time_critical,
                "scenarioId": str(event.scenario_id),
            }
            
            await stomp_broker.broadcast_event("disaster", frontend_payload, event.scenario_id)
            logger.info(f"已广播事件到前端: {event.event_code} - {event.title}")
        except Exception as e:
            logger.error(f"广播事件失败: {e}")
