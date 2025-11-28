"""
前端事件API数据模型

地震事件触发等请求/响应定义
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EarthquakeLocation(BaseModel):
    """地震位置"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class EarthquakeTriggerRequest(BaseModel):
    """
    地震事件触发请求
    
    前端调用此接口触发地震模拟仿真：
    1. 先推送动画效果到WebSocket
    2. 然后创建真实事件记录
    """
    scenario_id: UUID = Field(..., alias="scenarioId", description="想定ID")
    
    # 地震基本参数
    magnitude: Decimal = Field(
        ..., 
        ge=Decimal("1.0"), 
        le=Decimal("10.0"), 
        description="震级（里氏震级，1.0-10.0）"
    )
    location: EarthquakeLocation = Field(..., description="震中位置")
    depth_km: Optional[Decimal] = Field(
        None, 
        alias="depthKm",
        ge=Decimal("0"), 
        le=Decimal("700"),
        description="震源深度（公里），默认10km"
    )
    
    # 展示信息
    epicenter_name: str = Field(
        ..., 
        alias="epicenterName",
        max_length=200, 
        description="震中地名，如'北川县'"
    )
    message: Optional[str] = Field(
        None,
        max_length=500,
        description="自定义推送消息，如'北川县发生6.5级地震'。不传则自动生成"
    )
    
    # 可选：影响评估
    estimated_victims: int = Field(
        default=0, 
        alias="estimatedVictims",
        ge=0,
        description="预估受灾人数"
    )
    affected_area_km2: Optional[Decimal] = Field(
        None,
        alias="affectedAreaKm2",
        ge=Decimal("0"),
        description="影响范围（平方公里）"
    )
    
    # 动画控制
    animation_duration_ms: int = Field(
        default=3000,
        alias="animationDurationMs",
        ge=1000,
        le=10000,
        description="动画持续时间（毫秒），默认3秒"
    )
    
    class Config:
        populate_by_name = True


class EarthquakeAnimationPayload(BaseModel):
    """
    地震动画WebSocket推送负载
    
    发送到 /topic/scenario.disaster.triggered
    前端根据此数据播放地震动画效果
    
    必须包含前端灾害事件所需的字段：eventId, eventLevel, eventType, title, time, origin, data
    """
    # 前端灾害事件必填字段
    event_id: str = Field(..., alias="eventId", description="事件ID")
    message_id: str = Field(..., alias="messageId", description="消息ID（用于确认接口）")
    title: str = Field(..., description="事件标题")
    event_level: int = Field(..., alias="eventLevel", description="灾害等级 1-4")
    event_type: int = Field(..., alias="eventType", description="灾害类型编码 1=地震")
    time: str = Field(..., description="发生时间 ISO8601")
    origin: str = Field(..., description="事件来源")
    data: str = Field(..., description="描述内容（弹窗显示）")
    
    # 地震专属字段
    animation_type: str = Field(default="earthquake", alias="animationType")
    magnitude: Decimal = Field(..., description="震级")
    location: list[float] = Field(..., description="震中坐标 [lng, lat]")
    epicenter_name: str = Field(..., alias="epicenterName", description="震中地名")
    depth_km: Decimal = Field(..., alias="depthKm", description="震源深度")
    message: str = Field(..., description="推送消息文本")
    animation_duration_ms: int = Field(..., alias="animationDurationMs", description="动画时长")
    timestamp: str = Field(..., description="事件时间 ISO8601")
    scenario_id: str = Field(..., alias="scenarioId", description="想定ID")
    
    # 影响评估（可选）
    estimated_victims: Optional[int] = Field(None, alias="estimatedVictims")
    affected_area_km2: Optional[Decimal] = Field(None, alias="affectedAreaKm2")
    
    # 关联实体（用于地图渲染）
    entity_ids: Optional[list[str]] = Field(None, alias="entityIds", description="关联的地图实体ID列表")
    
    class Config:
        populate_by_name = True


class EarthquakeTriggerResponse(BaseModel):
    """地震事件触发响应"""
    event_id: str = Field(..., alias="eventId", description="创建的事件ID")
    event_code: str = Field(..., alias="eventCode", description="事件编码")
    message: str = Field(..., description="推送的消息内容")
    animation_sent: bool = Field(..., alias="animationSent", description="动画是否已推送")
    duplicate: bool = Field(default=False, description="是否为重复事件（幂等返回）")
    
    class Config:
        populate_by_name = True
