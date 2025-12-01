"""
想定数据模型（Pydantic Schemas）

对应SQL表: operational_v2.scenarios_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ScenarioType(str, Enum):
    """想定类型枚举"""
    earthquake = "earthquake"  # 地震
    flood = "flood"            # 洪涝
    fire = "fire"              # 火灾
    hazmat = "hazmat"          # 危化品
    landslide = "landslide"    # 滑坡


class ResponseLevel(str, Enum):
    """响应等级"""
    I = "I"    # 特别重大
    II = "II"  # 重大
    III = "III"  # 较大
    IV = "IV"  # 一般


class ScenarioStatus(str, Enum):
    """想定状态"""
    draft = "draft"        # 草稿
    active = "active"      # 进行中
    resolved = "resolved"  # 已解决
    archived = "archived"  # 已归档


class Location(BaseModel):
    """地理坐标"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class ScenarioCreate(BaseModel):
    """创建想定请求"""
    name: str = Field(..., max_length=200, description="想定名称")
    scenario_type: ScenarioType = Field(..., description="想定类型")
    response_level: Optional[ResponseLevel] = Field(None, description="响应等级")
    location: Optional[Location] = Field(None, description="事发中心点")
    started_at: Optional[datetime] = Field(None, description="事件发生时间")
    parameters: dict[str, Any] = Field(default_factory=dict, description="想定参数")
    affected_population: Optional[int] = Field(None, ge=0, description="预估影响人口")
    affected_area_km2: Optional[Decimal] = Field(None, ge=0, description="影响面积(km²)")


class ScenarioUpdate(BaseModel):
    """更新想定请求"""
    name: Optional[str] = Field(None, max_length=200, description="想定名称")
    response_level: Optional[ResponseLevel] = Field(None, description="响应等级")
    location: Optional[Location] = Field(None, description="事发中心点")
    started_at: Optional[datetime] = Field(None, description="事件发生时间")
    ended_at: Optional[datetime] = Field(None, description="事件结束时间")
    parameters: Optional[dict[str, Any]] = Field(None, description="想定参数")
    affected_population: Optional[int] = Field(None, ge=0, description="预估影响人口")
    affected_area_km2: Optional[Decimal] = Field(None, ge=0, description="影响面积(km²)")


class ScenarioStatusUpdate(BaseModel):
    """更新想定状态请求"""
    status: ScenarioStatus = Field(..., description="目标状态")
    reason: Optional[str] = Field(None, description="状态变更原因")


class ScenarioResponse(BaseModel):
    """想定响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    scenario_type: ScenarioType
    response_level: Optional[ResponseLevel]
    status: ScenarioStatus
    location: Optional[Location]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    parameters: dict[str, Any]
    affected_population: Optional[int]
    affected_area_km2: Optional[Decimal]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class ScenarioListResponse(BaseModel):
    """想定列表响应"""
    items: list[ScenarioResponse]
    total: int
    page: int
    page_size: int


# ==================== 资源配置 ====================

class ResourceAssignment(BaseModel):
    """单个资源分配"""
    resource_id: UUID = Field(..., description="资源ID")
    role: Optional[str] = Field(None, max_length=200, description="在想定中的角色")


class ScenarioResourcesConfig(BaseModel):
    """想定资源配置请求"""
    teams: list[ResourceAssignment] = Field(default_factory=list, description="队伍列表")
    vehicles: list[ResourceAssignment] = Field(default_factory=list, description="车辆列表")
    devices: list[ResourceAssignment] = Field(default_factory=list, description="设备列表")


class ScenarioResourcesResponse(BaseModel):
    """想定资源配置响应"""
    scenario_id: UUID
    configured_teams: int
    configured_vehicles: int
    configured_devices: int
    message: str


# ==================== 环境配置 ====================

class WeatherConfig(BaseModel):
    """天气配置"""
    condition: str = Field(..., description="天气状况: sunny/cloudy/rainy/etc")
    temperature_celsius: Optional[float] = Field(None, description="温度(摄氏度)")
    visibility_km: Optional[float] = Field(None, ge=0, description="能见度(公里)")
    wind_speed_ms: Optional[float] = Field(None, ge=0, description="风速(米/秒)")
    humidity_percent: Optional[int] = Field(None, ge=0, le=100, description="湿度(%)")


class RoadConditionConfig(BaseModel):
    """道路状况配置"""
    damaged_roads: list[str] = Field(default_factory=list, description="受损道路ID列表")
    blocked_areas: list[dict[str, Any]] = Field(default_factory=list, description="封锁区域GeoJSON")


class CommunicationConfig(BaseModel):
    """通信状况配置"""
    coverage_percentage: int = Field(100, ge=0, le=100, description="信号覆盖率(%)")
    satellite_available: bool = Field(True, description="卫星通信是否可用")
    affected_areas: list[dict[str, Any]] = Field(default_factory=list, description="通信中断区域GeoJSON")


class ScenarioEnvironmentConfig(BaseModel):
    """想定环境参数配置"""
    weather: Optional[WeatherConfig] = Field(None, description="天气配置")
    road_conditions: Optional[RoadConditionConfig] = Field(None, description="道路状况")
    communication: Optional[CommunicationConfig] = Field(None, description="通信状况")


class ScenarioEnvironmentResponse(BaseModel):
    """想定环境配置响应"""
    scenario_id: UUID
    weather_configured: bool
    road_conditions_configured: bool
    communication_configured: bool
    message: str


# ==================== 重置想定 ====================

class ScenarioResetRequest(BaseModel):
    """重置想定请求"""
    delete_events: bool = Field(True, description="删除事件")
    delete_entities: bool = Field(True, description="删除地图实体")
    delete_risk_areas: bool = Field(True, description="删除风险区域")
    delete_schemes: bool = Field(True, description="删除方案")
    delete_tasks: bool = Field(True, description="删除任务")
    delete_messages: bool = Field(True, description="删除消息")
    delete_ai_decisions: bool = Field(True, description="删除AI决策记录")


class ScenarioResetResponse(BaseModel):
    """重置想定响应"""
    scenario_id: UUID
    deleted_events: int
    deleted_entities: int
    deleted_risk_areas: int
    deleted_schemes: int
    deleted_tasks: int
    deleted_messages: int
    deleted_ai_decisions: int
    message: str
