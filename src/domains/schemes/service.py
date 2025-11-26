from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from .repository import SchemeRepository
from .schemas import (
    SchemeCreate, SchemeUpdate, SchemeResponse, SchemeListResponse,
    SchemeSubmitReview, SchemeApprove, SchemeReject,
    ResourceAllocationCreate, ResourceAllocationModify, ResourceAllocationResponse
)
from src.core.exceptions import NotFoundError, ConflictError


class SchemeService:
    def __init__(self, db: AsyncSession):
        self.repo = SchemeRepository(db)
    
    async def create(self, data: SchemeCreate, created_by: Optional[UUID] = None) -> SchemeResponse:
        scheme_code = await self.repo.get_next_scheme_code(data.scenario_id)
        scheme = await self.repo.create(data, scheme_code, created_by)
        return self._to_response(scheme)
    
    async def get_by_id(self, scheme_id: UUID) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        return self._to_response(scheme)
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> SchemeListResponse:
        items, total = await self.repo.list(scenario_id, event_id, page, page_size, status)
        return SchemeListResponse(
            items=[self._to_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def update(self, scheme_id: UUID, data: SchemeUpdate) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status not in ("draft", "pending_review"):
            raise ConflictError("SC4005", f"Cannot update scheme in status: {scheme.status}")
        
        scheme = await self.repo.update(scheme, data)
        return self._to_response(scheme)
    
    async def submit_for_review(self, scheme_id: UUID, data: SchemeSubmitReview) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status != "draft":
            raise ConflictError("SC4006", "Can only submit draft schemes for review")
        
        scheme = await self.repo.submit_for_review(scheme)
        return self._to_response(scheme)
    
    async def approve(self, scheme_id: UUID, data: SchemeApprove, approved_by: Optional[UUID] = None) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status != "pending_review":
            raise ConflictError("SC4007", "Can only approve pending_review schemes")
        
        scheme = await self.repo.approve(scheme, approved_by, data.comment)
        return self._to_response(scheme)
    
    async def reject(self, scheme_id: UUID, data: SchemeReject, reviewed_by: Optional[UUID] = None) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status != "pending_review":
            raise ConflictError("SC4008", "Can only reject pending_review schemes")
        
        scheme = await self.repo.reject(scheme, reviewed_by, data.comment)
        return self._to_response(scheme)
    
    async def start_execution(self, scheme_id: UUID) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status != "approved":
            raise ConflictError("SC4009", "Can only start execution of approved schemes")
        
        scheme = await self.repo.update_status(scheme, "executing")
        return self._to_response(scheme)
    
    async def complete(self, scheme_id: UUID) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status != "executing":
            raise ConflictError("SC4010", "Can only complete executing schemes")
        
        scheme = await self.repo.update_status(scheme, "completed")
        return self._to_response(scheme)
    
    async def cancel(self, scheme_id: UUID) -> SchemeResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status in ("completed", "cancelled"):
            raise ConflictError("SC4011", f"Cannot cancel scheme in status: {scheme.status}")
        
        scheme = await self.repo.update_status(scheme, "cancelled")
        return self._to_response(scheme)
    
    async def delete(self, scheme_id: UUID) -> None:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status not in ("draft", "cancelled"):
            raise ConflictError("SC4012", "Can only delete draft or cancelled schemes")
        
        await self.repo.delete(scheme)
    
    async def add_allocation(self, scheme_id: UUID, data: ResourceAllocationCreate) -> ResourceAllocationResponse:
        scheme = await self.repo.get_by_id(scheme_id)
        if not scheme:
            raise NotFoundError("Scheme", str(scheme_id))
        
        if scheme.status not in ("draft", "pending_review"):
            raise ConflictError("SC4013", "Cannot add allocation to scheme in this status")
        
        allocation = await self.repo.add_allocation(scheme_id, data)
        return self._allocation_to_response(allocation)
    
    async def modify_allocation(
        self,
        allocation_id: UUID,
        data: ResourceAllocationModify,
        modified_by: Optional[UUID] = None,
    ) -> ResourceAllocationResponse:
        allocation = await self.repo.get_allocation(allocation_id)
        if not allocation:
            raise NotFoundError("ResourceAllocation", str(allocation_id))
        
        allocation = await self.repo.modify_allocation(
            allocation, data.new_resource_id, data.new_resource_name, data.modification_reason, modified_by
        )
        return self._allocation_to_response(allocation)
    
    async def confirm_allocation(self, allocation_id: UUID) -> ResourceAllocationResponse:
        allocation = await self.repo.get_allocation(allocation_id)
        if not allocation:
            raise NotFoundError("ResourceAllocation", str(allocation_id))
        
        allocation = await self.repo.confirm_allocation(allocation)
        return self._allocation_to_response(allocation)
    
    async def delete_allocation(self, allocation_id: UUID) -> None:
        allocation = await self.repo.get_allocation(allocation_id)
        if not allocation:
            raise NotFoundError("ResourceAllocation", str(allocation_id))
        await self.repo.delete_allocation(allocation)
    
    def _to_response(self, scheme) -> SchemeResponse:
        return SchemeResponse(
            id=scheme.id,
            event_id=scheme.event_id,
            scenario_id=scheme.scenario_id,
            scheme_code=scheme.scheme_code,
            scheme_type=scheme.scheme_type,
            source=scheme.source,
            title=scheme.title,
            objective=scheme.objective,
            description=scheme.description,
            status=scheme.status,
            constraints=scheme.constraints,
            risk_assessment=scheme.risk_assessment,
            planned_start_at=scheme.planned_start_at,
            planned_end_at=scheme.planned_end_at,
            actual_start_at=scheme.actual_start_at,
            actual_end_at=scheme.actual_end_at,
            estimated_duration_minutes=scheme.estimated_duration_minutes,
            version=scheme.version,
            ai_confidence_score=float(scheme.ai_confidence_score) if scheme.ai_confidence_score else None,
            ai_reasoning=scheme.ai_reasoning,
            review_comment=scheme.review_comment,
            submitted_at=scheme.submitted_at,
            approved_at=scheme.approved_at,
            created_at=scheme.created_at,
            updated_at=scheme.updated_at,
            allocations=[self._allocation_to_response(a) for a in (scheme.allocations or [])],
        )
    
    def _allocation_to_response(self, allocation) -> ResourceAllocationResponse:
        return ResourceAllocationResponse(
            id=allocation.id,
            scheme_id=allocation.scheme_id,
            resource_type=allocation.resource_type,
            resource_id=allocation.resource_id,
            resource_name=allocation.resource_name,
            status=allocation.status,
            assigned_role=allocation.assigned_role,
            match_score=float(allocation.match_score) if allocation.match_score else None,
            full_recommendation_reason=allocation.full_recommendation_reason,
            is_human_modified=allocation.is_human_modified or False,
            human_modification_reason=allocation.human_modification_reason,
            original_resource_id=allocation.original_resource_id,
            alternative_resources=allocation.alternative_resources,
            created_at=allocation.created_at,
            updated_at=allocation.updated_at,
        )
