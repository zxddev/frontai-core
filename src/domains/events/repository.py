from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from .models import Event, EventUpdate as EventUpdateModel
from .schemas import EventCreate, EventUpdate, Location


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: EventCreate, event_code: str, reported_by: Optional[UUID] = None) -> Event:
        location_wkt = f"POINT({data.location.longitude} {data.location.latitude})"
        
        event = Event(
            scenario_id=data.scenario_id,
            event_code=event_code,
            event_type=data.event_type.value,
            source_type=data.source_type.value,
            source_detail=data.source_detail or {},
            title=data.title,
            description=data.description,
            location=location_wkt,
            address=data.address,
            priority=data.priority.value,
            estimated_victims=data.estimated_victims,
            is_time_critical=data.is_time_critical,
            golden_hour_deadline=data.golden_hour_deadline,
            media_attachments=data.media_attachments or [],
            confirmation_score=data.confirmation_score,
            reported_by=reported_by,
            status="pending",
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        scenario_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> tuple[list[Event], int]:
        query = select(Event).where(Event.scenario_id == scenario_id)
        count_query = select(func.count(Event.id)).where(Event.scenario_id == scenario_id)
        
        if status:
            query = query.where(Event.status == status)
            count_query = count_query.where(Event.status == status)
        
        if priority:
            query = query.where(Event.priority == priority)
            count_query = count_query.where(Event.priority == priority)
        
        if event_type:
            query = query.where(Event.event_type == event_type)
            count_query = count_query.where(Event.event_type == event_type)
        
        query = query.order_by(Event.reported_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        return items, total
    
    async def get_pending_review(self, scenario_id: UUID) -> list[Event]:
        """获取待复核事件 (pending + pre_confirmed)"""
        result = await self.db.execute(
            select(Event)
            .where(Event.scenario_id == scenario_id)
            .where(Event.status.in_(["pending", "pre_confirmed"]))
            .order_by(Event.priority.desc(), Event.reported_at.asc())
        )
        return list(result.scalars().all())
    
    async def update(self, event: Event, data: EventUpdate) -> Event:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(event, key, value)
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def update_status(self, event: Event, status: str) -> Event:
        event.status = status
        if status == "confirmed":
            event.confirmed_at = datetime.utcnow()
        elif status == "pre_confirmed":
            event.pre_confirmed_at = datetime.utcnow()
            event.pre_confirm_expires_at = datetime.utcnow() + timedelta(minutes=30)
        elif status == "resolved":
            event.resolved_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def confirm(self, event: Event, confirmed_by: Optional[UUID] = None, auto: bool = False) -> Event:
        event.status = "confirmed"
        event.confirmed_at = datetime.utcnow()
        event.confirmed_by = confirmed_by
        event.auto_confirmed = auto
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def pre_confirm(self, event: Event) -> Event:
        event.status = "pre_confirmed"
        event.pre_confirmed_at = datetime.utcnow()
        event.pre_confirm_expires_at = datetime.utcnow() + timedelta(minutes=30)
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def extend_pre_confirm(self, event: Event, minutes: int) -> Event:
        event.pre_confirm_expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def cancel(self, event: Event, reason: str) -> Event:
        event.status = "cancelled"
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def escalate(self, event: Event) -> Event:
        event.status = "escalated"
        await self.db.flush()
        await self.db.refresh(event)
        return event
    
    async def delete(self, event: Event) -> None:
        await self.db.delete(event)
        await self.db.flush()
    
    async def get_next_event_code(self, scenario_id: UUID) -> str:
        result = await self.db.execute(
            select(func.count(Event.id)).where(Event.scenario_id == scenario_id)
        )
        count = result.scalar() or 0
        return f"EVT-{count + 1:04d}"
    
    async def get_statistics(self, scenario_id: UUID) -> dict:
        base = select(Event).where(Event.scenario_id == scenario_id)
        
        total_result = await self.db.execute(select(func.count(Event.id)).where(Event.scenario_id == scenario_id))
        total = total_result.scalar() or 0
        
        by_status = {}
        for status in ["pending", "pre_confirmed", "confirmed", "planning", "executing", "resolved", "escalated", "cancelled"]:
            r = await self.db.execute(
                select(func.count(Event.id))
                .where(Event.scenario_id == scenario_id)
                .where(Event.status == status)
            )
            by_status[status] = r.scalar() or 0
        
        by_priority = {}
        for priority in ["critical", "high", "medium", "low"]:
            r = await self.db.execute(
                select(func.count(Event.id))
                .where(Event.scenario_id == scenario_id)
                .where(Event.priority == priority)
            )
            by_priority[priority] = r.scalar() or 0
        
        time_critical_result = await self.db.execute(
            select(func.count(Event.id))
            .where(Event.scenario_id == scenario_id)
            .where(Event.is_time_critical == True)
            .where(Event.status.notin_(["resolved", "cancelled"]))
        )
        time_critical_count = time_critical_result.scalar() or 0
        
        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_type": {},
            "pending_count": by_status.get("pending", 0),
            "pre_confirmed_count": by_status.get("pre_confirmed", 0),
            "time_critical_count": time_critical_count,
        }
    
    async def add_update_record(
        self,
        event_id: UUID,
        update_type: str,
        previous_value: Optional[dict],
        new_value: Optional[dict],
        description: Optional[str] = None,
        updated_by: Optional[UUID] = None,
        source_type: str = "manual_report",
    ) -> EventUpdateModel:
        """添加事件更新记录"""
        record = EventUpdateModel(
            event_id=event_id,
            update_type=update_type,
            previous_value=previous_value,
            new_value=new_value,
            description=description,
            updated_by=updated_by,
            source_type=source_type,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record
    
    async def get_updates(
        self,
        event_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[EventUpdateModel], int]:
        """获取事件更新记录列表"""
        query = (
            select(EventUpdateModel)
            .where(EventUpdateModel.event_id == event_id)
            .order_by(EventUpdateModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await self.db.execute(
            select(func.count(EventUpdateModel.id))
            .where(EventUpdateModel.event_id == event_id)
        )
        total = count_result.scalar() or 0
        
        return items, total
    
    async def get_by_ids(self, event_ids: list[UUID]) -> list[Event]:
        """批量获取事件"""
        if not event_ids:
            return []
        result = await self.db.execute(
            select(Event).where(Event.id.in_(event_ids))
        )
        return list(result.scalars().all())
