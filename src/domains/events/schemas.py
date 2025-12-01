from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class EventType(str, Enum):
    earthquake = "earthquake"  # 地震（主震）
    trapped_person = "trapped_person"
    fire = "fire"
    flood = "flood"
    landslide = "landslide"
    building_collapse = "building_collapse"
    road_damage = "road_damage"
    power_outage = "power_outage"
    communication_lost = "communication_lost"
    hazmat_leak = "hazmat_leak"
    epidemic = "epidemic"
    earthquake_secondary = "earthquake_secondary"
    other = "other"


class EventSourceType(str, Enum):
    manual_report = "manual_report"
    ai_detection = "ai_detection"
    sensor_alert = "sensor_alert"
    system_inference = "system_inference"
    external_system = "external_system"


class EventStatus(str, Enum):
    pending = "pending"
    pre_confirmed = "pre_confirmed"
    confirmed = "confirmed"
    planning = "planning"
    executing = "executing"
    resolved = "resolved"
    escalated = "escalated"
    cancelled = "cancelled"


class EventPriority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Location(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class EventCreate(BaseModel):
    scenario_id: UUID
    event_type: EventType
    source_type: EventSourceType = EventSourceType.manual_report
    source_detail: Optional[dict[str, Any]] = None
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    location: Location
    address: Optional[str] = None
    priority: EventPriority = EventPriority.medium
    estimated_victims: int = 0
    is_time_critical: bool = False
    golden_hour_deadline: Optional[datetime] = None
    media_attachments: Optional[list[dict[str, Any]]] = None
    confirmation_score: Optional[float] = Field(None, ge=0, le=1)
    is_main_event: bool = Field(False, description="是否为想定主事件")


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    address: Optional[str] = None
    priority: Optional[EventPriority] = None
    estimated_victims: Optional[int] = None
    rescued_count: Optional[int] = None
    casualty_count: Optional[int] = None
    is_time_critical: Optional[bool] = None
    golden_hour_deadline: Optional[datetime] = None
    media_attachments: Optional[list[dict[str, Any]]] = None


class EventStatusUpdate(BaseModel):
    status: EventStatus
    reason: Optional[str] = None


class EventConfirm(BaseModel):
    """人工确认事件"""
    confirmation_note: Optional[str] = None
    priority_override: Optional[EventPriority] = None


class EventPreConfirmExtend(BaseModel):
    """延长预确认倒计时"""
    extend_minutes: int = Field(30, ge=10, le=120)
    reason: str


class EventResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    event_code: str
    event_type: EventType
    source_type: EventSourceType
    source_detail: Optional[dict[str, Any]]
    title: str
    description: Optional[str]
    location: Location
    address: Optional[str]
    status: EventStatus
    priority: EventPriority
    estimated_victims: int
    rescued_count: int
    casualty_count: int
    is_time_critical: bool
    golden_hour_deadline: Optional[datetime]
    auto_confirmed: bool
    confirmation_score: Optional[float]
    pre_confirm_expires_at: Optional[datetime]
    pre_allocated_resources: Optional[list[dict[str, Any]]]
    media_attachments: Optional[list[dict[str, Any]]]
    is_main_event: bool = False
    reported_at: datetime
    confirmed_at: Optional[datetime]
    pre_confirmed_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int


class EventStatistics(BaseModel):
    """事件统计"""
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_type: dict[str, int]
    pending_count: int
    pre_confirmed_count: int
    time_critical_count: int


# ==================== 事件更新记录 ====================

class EventUpdateType(str, Enum):
    """更新类型"""
    status_change = "status_change"
    info_update = "info_update"
    victim_update = "victim_update"
    location_update = "location_update"
    media_update = "media_update"
    pre_confirm_extend = "pre_confirm_extend"
    ai_analysis = "ai_analysis"
    field_report = "field_report"


class EventUpdateCreate(BaseModel):
    """添加事件更新"""
    update_type: EventUpdateType = EventUpdateType.info_update
    description: str = Field(..., min_length=1, max_length=1000)
    new_value: Optional[dict[str, Any]] = None
    source_type: EventSourceType = EventSourceType.manual_report


class EventUpdateResponse(BaseModel):
    """事件更新记录响应"""
    id: UUID
    event_id: UUID
    update_type: str
    previous_value: Optional[dict[str, Any]]
    new_value: Optional[dict[str, Any]]
    description: Optional[str]
    source_type: str
    updated_by: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class EventUpdateListResponse(BaseModel):
    """事件更新列表响应"""
    items: list[EventUpdateResponse]
    total: int
    page: int
    page_size: int


# ==================== 批量确认 ====================

class BatchConfirmRequest(BaseModel):
    """批量确认请求"""
    event_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = None


class BatchConfirmResult(BaseModel):
    """单个事件确认结果"""
    id: UUID
    success: bool
    error: Optional[str] = None


class BatchConfirmResponse(BaseModel):
    """批量确认响应"""
    confirmed: list[UUID]
    failed: list[BatchConfirmResult]
    total_requested: int
    total_confirmed: int
