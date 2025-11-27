"""
预警监测智能体数据模型（Pydantic Schemas）
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class DisasterType(str, Enum):
    """灾害类型"""
    fire = "fire"
    flood = "flood"
    chemical = "chemical"
    landslide = "landslide"
    earthquake = "earthquake"


class WarningLevel(str, Enum):
    """预警级别"""
    blue = "blue"      # >5km
    yellow = "yellow"  # 3-5km
    orange = "orange"  # 1-3km
    red = "red"        # <1km


class WarningStatus(str, Enum):
    """预警状态"""
    pending = "pending"
    acknowledged = "acknowledged"
    responded = "responded"
    resolved = "resolved"
    cancelled = "cancelled"


class ResponseAction(str, Enum):
    """响应行动"""
    continue_ = "continue"
    detour = "detour"
    standby = "standby"


class GeoPoint(BaseModel):
    """地理坐标点"""
    lon: float = Field(..., ge=-180, le=180, description="经度")
    lat: float = Field(..., ge=-90, le=90, description="纬度")


class GeoPolygon(BaseModel):
    """GeoJSON多边形"""
    type: str = "Polygon"
    coordinates: List[List[List[float]]] = Field(..., description="多边形坐标")


# ============ 灾害态势相关 ============

class DisasterUpdateRequest(BaseModel):
    """灾害更新请求（第三方接口）"""
    scenario_id: Optional[UUID] = Field(None, description="想定ID，不指定则自动查找")
    disaster_type: DisasterType = Field(..., description="灾害类型")
    disaster_name: Optional[str] = Field(None, max_length=200, description="灾害名称")
    boundary: GeoPolygon = Field(..., description="灾害范围多边形")
    center_point: Optional[GeoPoint] = Field(None, description="中心点")
    buffer_distance_m: int = Field(3000, ge=100, le=50000, description="预警缓冲距离(米)")
    spread_direction: Optional[str] = Field(None, description="扩散方向 N/NE/E/SE/S/SW/W/NW")
    spread_speed_mps: Optional[float] = Field(None, ge=0, description="扩散速度 m/s")
    severity_level: int = Field(3, ge=1, le=5, description="严重程度 1-5")
    source: Optional[str] = Field(None, max_length=100, description="数据来源")
    source_update_time: Optional[datetime] = Field(None, description="数据源更新时间")
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")
    needs_response: bool = Field(True, description="是否需要救援响应（false=仅预警如天气预报）")


class DisasterSituationResponse(BaseModel):
    """灾害态势响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    scenario_id: Optional[UUID]
    disaster_type: str
    disaster_name: Optional[str]
    boundary: dict
    center_point: Optional[dict]
    buffer_distance_m: int
    spread_direction: Optional[str]
    spread_speed_mps: Optional[float]
    severity_level: int
    status: str
    source: Optional[str]
    needs_response: bool
    linked_event_id: Optional[UUID]
    map_entity_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


# ============ 预警记录相关 ============

class WarningRecordResponse(BaseModel):
    """预警记录响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    disaster_id: UUID
    scenario_id: Optional[UUID]
    
    affected_type: str
    affected_id: UUID
    affected_name: Optional[str]
    
    notify_target_type: str
    notify_target_id: Optional[UUID]
    notify_target_name: Optional[str]
    
    warning_level: str
    distance_m: Optional[float]
    estimated_contact_minutes: Optional[int]
    route_affected: bool
    
    warning_title: Optional[str]
    warning_message: Optional[str]
    
    status: str
    response_action: Optional[str]
    response_reason: Optional[str]
    
    created_at: datetime
    acknowledged_at: Optional[datetime]
    responded_at: Optional[datetime]
    resolved_at: Optional[datetime]


class WarningListResponse(BaseModel):
    """预警列表响应"""
    items: List[WarningRecordResponse]
    total: int
    page: int
    page_size: int


class WarningAcknowledgeRequest(BaseModel):
    """确认收到预警请求"""
    pass  # 只需要warning_id在路径中


class WarningRespondRequest(BaseModel):
    """预警响应请求"""
    action: ResponseAction = Field(..., description="响应行动: continue/detour/standby")
    reason: Optional[str] = Field(None, max_length=500, description="响应理由")


class DetourOption(BaseModel):
    """绕行选项"""
    route_id: str
    path_points: List[GeoPoint]
    total_distance_m: float
    total_duration_seconds: float
    additional_distance_m: float
    additional_time_seconds: float
    risk_level: str
    description: str


class DetourOptionsResponse(BaseModel):
    """绕行选项响应"""
    warning_id: UUID
    original_route_distance_m: float
    original_route_duration_seconds: float
    avoid_area: GeoPolygon
    options: List[DetourOption]


class ConfirmDetourRequest(BaseModel):
    """确认绕行请求"""
    route_id: str = Field(..., description="选择的路线ID")


# ============ 预警处理结果 ============

class DisasterUpdateResponse(BaseModel):
    """灾害更新响应"""
    disaster_id: UUID
    scenario_id: Optional[UUID] = None
    linked_event_id: Optional[UUID] = None
    map_entity_id: Optional[UUID] = None
    warnings_generated: int
    affected_vehicles: int
    affected_teams: int
    notifications_sent: int
    message: str
    scenario_warning: Optional[str] = None


# ============ WebSocket预警消息 ============

class WarningNotification(BaseModel):
    """WebSocket预警通知消息"""
    warning_id: str
    warning_level: str
    warning_title: str
    warning_message: str
    
    disaster_type: str
    disaster_name: Optional[str]
    
    affected_type: str
    affected_id: str
    affected_name: str
    
    distance_m: float
    estimated_contact_minutes: Optional[int]
    route_affected: bool
    
    actions: List[str] = Field(default=["detour", "continue", "standby"])
    
    created_at: str
