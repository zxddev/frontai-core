"""Schemas for ReconSchedulerAgent API endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WeatherInput(BaseModel):
    """天气输入参数"""
    wind_speed_ms: float = Field(default=5.0, description="风速 m/s")
    wind_direction_deg: float = Field(default=0.0, description="风向角度")
    rain_level: str = Field(default="none", description="降雨等级: none/light/moderate/heavy/storm")
    visibility_m: float = Field(default=10000.0, description="能见度 m")
    temperature_c: float = Field(default=20.0, description="温度 ℃")


class ReconScheduleRequest(BaseModel):
    """侦察调度请求"""
    scenarioId: Optional[str] = Field(default=None, description="想定ID，可选")
    eventId: Optional[str] = Field(default=None, description="事件ID，可选")
    disasterType: str = Field(..., description="灾情类型: earthquake_collapse/flood/fire/hazmat/landslide")
    targetArea: Dict[str, Any] = Field(..., description="目标区域 GeoJSON Polygon")
    weather: Optional[WeatherInput] = Field(default=None, description="天气条件，可选")
    reconRequest: Optional[str] = Field(default=None, description="自然语言侦察需求描述")


class WaypointItem(BaseModel):
    """航点"""
    seq: int = Field(..., description="序号")
    lat: float = Field(..., description="纬度")
    lng: float = Field(..., description="经度")
    alt_m: float = Field(..., description="高度 m")
    action: str = Field(..., description="动作: takeoff/waypoint/hover/land")
    speed_ms: Optional[float] = Field(default=None, description="速度 m/s")


class FlightStatistics(BaseModel):
    """航线统计"""
    total_distance_m: float = Field(..., description="总距离 m")
    total_duration_min: float = Field(..., description="总时长 min")
    waypoint_count: int = Field(..., description="航点数")


class FlightPlanItem(BaseModel):
    """航线计划"""
    taskId: str = Field(..., description="任务ID")
    taskName: str = Field(..., description="任务名称")
    deviceId: str = Field(..., description="设备ID")
    deviceName: str = Field(..., description="设备名称")
    scanPattern: str = Field(..., description="扫描模式: zigzag/spiral_inward/spiral_outward/circular")
    altitude_m: float = Field(..., description="飞行高度 m")
    waypoints: List[WaypointItem] = Field(default_factory=list, description="航点列表")
    statistics: FlightStatistics = Field(..., description="航线统计")
    kmlContent: Optional[str] = Field(default=None, description="KML文件内容")


class TimelineItem(BaseModel):
    """时间线条目"""
    taskName: str
    deviceName: str
    startMin: float
    endMin: float
    phase: int


class ExecutiveSummaryItem(BaseModel):
    """执行摘要"""
    missionName: str = Field(..., description="任务名称")
    disasterType: str = Field(..., description="灾情类型")
    totalDevices: int = Field(..., description="设备总数")
    totalPhases: int = Field(..., description="阶段总数")
    totalTasks: int = Field(..., description="任务总数")
    estimatedDurationMin: float = Field(..., description="预计时长 min")
    overallRiskLevel: str = Field(..., description="总体风险等级")


class ReconScheduleResponse(BaseModel):
    """侦察调度响应"""
    planId: str = Field(..., description="计划ID")
    success: bool = Field(..., description="是否成功")
    
    executiveSummary: Optional[ExecutiveSummaryItem] = Field(default=None, description="执行摘要")
    
    flightPlans: List[FlightPlanItem] = Field(default_factory=list, description="航线计划列表")
    
    timeline: List[TimelineItem] = Field(default_factory=list, description="时间线")
    totalDurationMin: float = Field(default=0, description="总时长 min")
    
    flightCondition: str = Field(default="green", description="飞行条件: green/yellow/red/black")
    riskLevel: str = Field(default="medium", description="风险等级: low/medium/high/critical")
    validationPassed: bool = Field(default=False, description="校验是否通过")
    
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")


__all__ = [
    "WeatherInput",
    "ReconScheduleRequest",
    "WaypointItem",
    "FlightStatistics",
    "FlightPlanItem",
    "TimelineItem",
    "ExecutiveSummaryItem",
    "ReconScheduleResponse",
]
