"""
待处理事件接口 schemas

用于查询未分配任务的事件及其AI方案
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class PendingActionRequest(BaseModel):
    """查询待处理事件请求"""
    scenario_id: UUID = Field(..., alias="scenarioId", description="想定ID")

    class Config:
        populate_by_name = True


class GenerateSchemeRequest(BaseModel):
    """生成AI方案请求"""
    scenario_id: UUID = Field(..., alias="scenarioId", description="想定ID")

    class Config:
        populate_by_name = True


class LocationResponse(BaseModel):
    """位置信息"""
    longitude: float
    latitude: float


class EventDetail(BaseModel):
    """事件详情"""
    id: UUID = Field(alias="eventId")
    event_code: str = Field(alias="eventCode")
    event_type: str = Field(alias="eventType")
    title: str
    description: Optional[str] = None
    location: LocationResponse
    address: Optional[str] = None
    status: str
    priority: str
    estimated_victims: int = Field(alias="estimatedVictims")
    is_time_critical: bool = Field(alias="isTimeCritical")
    golden_hour_deadline: Optional[datetime] = Field(None, alias="goldenHourDeadline")
    reported_at: datetime = Field(alias="reportedAt")
    created_at: datetime = Field(alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class SchemeDetail(BaseModel):
    """方案详情"""
    id: UUID = Field(alias="schemeId")
    scheme_code: str = Field(alias="schemeCode")
    scheme_type: str = Field(alias="schemeType")
    title: str
    objective: str
    description: Optional[str] = None
    status: str
    ai_confidence_score: Optional[float] = Field(None, alias="aiConfidenceScore")
    ai_reasoning: Optional[str] = Field(None, alias="aiReasoning")
    estimated_duration_minutes: Optional[int] = Field(None, alias="estimatedDurationMinutes")
    created_at: datetime = Field(alias="createdAt")
    allocations: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        populate_by_name = True
        from_attributes = True


class PendingActionEventItem(BaseModel):
    """待处理事件项（事件+方案）"""
    event: EventDetail
    scheme: Optional[SchemeDetail] = None
    has_scheme: bool = Field(alias="hasScheme")
    scheme_expired: bool = Field(False, alias="schemeExpired")

    class Config:
        populate_by_name = True


class GenerateSchemeResponse(BaseModel):
    """生成方案响应"""
    event_id: UUID = Field(alias="eventId")
    scheme_id: UUID = Field(alias="schemeId")
    scheme: SchemeDetail
    generated_at: datetime = Field(alias="generatedAt")

    class Config:
        populate_by_name = True
