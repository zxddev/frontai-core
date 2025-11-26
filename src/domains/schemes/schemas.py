from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class SchemeType(str, Enum):
    search_rescue = "search_rescue"
    evacuation = "evacuation"
    supply_delivery = "supply_delivery"
    medical = "medical"
    communication = "communication"
    traffic_control = "traffic_control"
    comprehensive = "comprehensive"


class SchemeSource(str, Enum):
    ai_generated = "ai_generated"
    human_created = "human_created"
    template_based = "template_based"
    hybrid = "hybrid"


class SchemeStatus(str, Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    executing = "executing"
    completed = "completed"
    cancelled = "cancelled"
    superseded = "superseded"


class AllocationStatus(str, Enum):
    proposed = "proposed"
    confirmed = "confirmed"
    modified = "modified"
    rejected = "rejected"
    executing = "executing"
    completed = "completed"


class SchemeCreate(BaseModel):
    event_id: UUID
    scenario_id: UUID
    scheme_type: SchemeType
    source: SchemeSource = SchemeSource.human_created
    title: str = Field(..., max_length=500)
    objective: str
    description: Optional[str] = None
    constraints: Optional[dict[str, Any]] = None
    risk_assessment: Optional[dict[str, Any]] = None
    planned_start_at: Optional[datetime] = None
    planned_end_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None


class SchemeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    objective: Optional[str] = None
    description: Optional[str] = None
    constraints: Optional[dict[str, Any]] = None
    risk_assessment: Optional[dict[str, Any]] = None
    planned_start_at: Optional[datetime] = None
    planned_end_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None


class SchemeSubmitReview(BaseModel):
    """提交审批"""
    comment: Optional[str] = None


class SchemeApprove(BaseModel):
    """审批通过"""
    comment: Optional[str] = None


class SchemeReject(BaseModel):
    """审批驳回"""
    comment: str


class ResourceAllocationCreate(BaseModel):
    """资源分配"""
    resource_type: str
    resource_id: UUID
    resource_name: str
    assigned_role: Optional[str] = None
    match_score: Optional[float] = None
    full_recommendation_reason: Optional[str] = None
    alternative_resources: Optional[list[dict[str, Any]]] = None


class ResourceAllocationModify(BaseModel):
    """人工修改资源分配"""
    new_resource_id: UUID
    new_resource_name: str
    modification_reason: str


class ResourceAllocationResponse(BaseModel):
    id: UUID
    scheme_id: UUID
    resource_type: str
    resource_id: UUID
    resource_name: Optional[str]
    status: AllocationStatus
    assigned_role: Optional[str]
    match_score: Optional[float]
    full_recommendation_reason: Optional[str]
    is_human_modified: bool
    human_modification_reason: Optional[str]
    original_resource_id: Optional[UUID]
    alternative_resources: Optional[list[dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SchemeResponse(BaseModel):
    id: UUID
    event_id: UUID
    scenario_id: UUID
    scheme_code: str
    scheme_type: SchemeType
    source: SchemeSource
    title: str
    objective: str
    description: Optional[str]
    status: SchemeStatus
    constraints: Optional[dict[str, Any]]
    risk_assessment: Optional[dict[str, Any]]
    planned_start_at: Optional[datetime]
    planned_end_at: Optional[datetime]
    actual_start_at: Optional[datetime]
    actual_end_at: Optional[datetime]
    estimated_duration_minutes: Optional[int]
    version: int
    ai_confidence_score: Optional[float]
    ai_reasoning: Optional[str]
    review_comment: Optional[str]
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    allocations: list[ResourceAllocationResponse] = []

    class Config:
        from_attributes = True


class SchemeListResponse(BaseModel):
    items: list[SchemeResponse]
    total: int
    page: int
    page_size: int
