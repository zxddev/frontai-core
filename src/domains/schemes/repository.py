from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from datetime import datetime

from .models import Scheme, ResourceAllocation
from .schemas import SchemeCreate, SchemeUpdate, ResourceAllocationCreate


class SchemeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: SchemeCreate, scheme_code: str, created_by: Optional[UUID] = None) -> Scheme:
        scheme = Scheme(
            event_id=data.event_id,
            scenario_id=data.scenario_id,
            scheme_code=scheme_code,
            scheme_type=data.scheme_type.value,
            source=data.source.value,
            title=data.title,
            objective=data.objective,
            description=data.description,
            constraints=data.constraints or {},
            risk_assessment=data.risk_assessment or {},
            planned_start_at=data.planned_start_at,
            planned_end_at=data.planned_end_at,
            estimated_duration_minutes=data.estimated_duration_minutes,
            created_by=created_by,
            status="draft",
        )
        self.db.add(scheme)
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def get_by_id(self, scheme_id: UUID) -> Optional[Scheme]:
        result = await self.db.execute(
            select(Scheme)
            .options(selectinload(Scheme.allocations))
            .where(Scheme.id == scheme_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[Scheme], int]:
        query = select(Scheme).options(selectinload(Scheme.allocations))
        count_query = select(func.count(Scheme.id))
        
        if scenario_id:
            query = query.where(Scheme.scenario_id == scenario_id)
            count_query = count_query.where(Scheme.scenario_id == scenario_id)
        
        if event_id:
            query = query.where(Scheme.event_id == event_id)
            count_query = count_query.where(Scheme.event_id == event_id)
        
        if status:
            query = query.where(Scheme.status == status)
            count_query = count_query.where(Scheme.status == status)
        
        query = query.order_by(Scheme.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        return items, total
    
    async def update(self, scheme: Scheme, data: SchemeUpdate) -> Scheme:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(scheme, key, value)
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def update_status(self, scheme: Scheme, status: str) -> Scheme:
        scheme.status = status
        if status == "approved":
            scheme.approved_at = datetime.utcnow()
        elif status == "executing":
            scheme.actual_start_at = datetime.utcnow()
        elif status == "completed":
            scheme.actual_end_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def submit_for_review(self, scheme: Scheme) -> Scheme:
        scheme.status = "pending_review"
        scheme.submitted_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def approve(self, scheme: Scheme, approved_by: Optional[UUID], comment: Optional[str]) -> Scheme:
        scheme.status = "approved"
        scheme.approved_by = approved_by
        scheme.approved_at = datetime.utcnow()
        scheme.review_comment = comment
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def reject(self, scheme: Scheme, reviewed_by: Optional[UUID], comment: str) -> Scheme:
        scheme.status = "draft"
        scheme.reviewed_by = reviewed_by
        scheme.reviewed_at = datetime.utcnow()
        scheme.review_comment = comment
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme
    
    async def delete(self, scheme: Scheme) -> None:
        await self.db.delete(scheme)
        await self.db.flush()
    
    async def get_next_scheme_code(self, scenario_id: UUID) -> str:
        result = await self.db.execute(
            select(func.count(Scheme.id)).where(Scheme.scenario_id == scenario_id)
        )
        count = result.scalar() or 0
        return f"SCH-{count + 1:04d}"
    
    async def add_allocation(self, scheme_id: UUID, data: ResourceAllocationCreate) -> ResourceAllocation:
        allocation = ResourceAllocation(
            scheme_id=scheme_id,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            resource_name=data.resource_name,
            assigned_role=data.assigned_role,
            match_score=data.match_score,
            full_recommendation_reason=data.full_recommendation_reason,
            alternative_resources=data.alternative_resources or [],
            status="proposed",
        )
        self.db.add(allocation)
        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation
    
    async def get_allocation(self, allocation_id: UUID) -> Optional[ResourceAllocation]:
        result = await self.db.execute(
            select(ResourceAllocation).where(ResourceAllocation.id == allocation_id)
        )
        return result.scalar_one_or_none()
    
    async def modify_allocation(
        self,
        allocation: ResourceAllocation,
        new_resource_id: UUID,
        new_resource_name: str,
        reason: str,
        modified_by: Optional[UUID] = None,
    ) -> ResourceAllocation:
        allocation.original_resource_id = allocation.resource_id
        allocation.resource_id = new_resource_id
        allocation.resource_name = new_resource_name
        allocation.is_human_modified = True
        allocation.human_modification_reason = reason
        allocation.modified_by = modified_by
        allocation.modified_at = datetime.utcnow()
        allocation.status = "modified"
        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation
    
    async def confirm_allocation(self, allocation: ResourceAllocation) -> ResourceAllocation:
        allocation.status = "confirmed"
        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation
    
    async def delete_allocation(self, allocation: ResourceAllocation) -> None:
        await self.db.delete(allocation)
        await self.db.flush()
