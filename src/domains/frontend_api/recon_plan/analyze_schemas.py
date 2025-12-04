"""
侦察目标分析接口数据模型

用于 POST /api/v1/recon-plan/analyze-targets 接口
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    """侦察目标类型"""
    EVENT = "event"                # 灾情事件
    RISK_AREA = "risk_area"        # 危险区域
    POI = "poi"                    # 重点目标
    RESCUE_POINT = "rescue_point"  # 救援点


class PriorityLevel(str, Enum):
    """优先级等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScanPattern(str, Enum):
    """扫描模式"""
    ZIGZAG = "zigzag"              # Z字形覆盖
    SPIRAL = "spiral"             # 螺旋详查
    CIRCULAR = "circular"         # 环形监控
    LINEAR = "linear"             # 线性巡查


class DeviceType(str, Enum):
    """设备类型"""
    DRONE = "drone"
    DOG = "dog"
    SHIP = "ship"


class LocationPoint(BaseModel):
    """位置点"""
    lat: float = Field(..., description="纬度")
    lng: float = Field(..., description="经度")


class DeviceRecommendationDetail(BaseModel):
    """设备推荐详情"""
    device_type: DeviceType = Field(..., alias="deviceType", description="设备类型")
    reason: str = Field(..., description="推荐理由")
    capabilities_needed: list[str] = Field(default_factory=list, alias="capabilitiesNeeded", description="需要的设备能力")
    
    class Config:
        populate_by_name = True


class ReconMethodDetail(BaseModel):
    """侦察方法详情"""
    method_name: str = Field(..., alias="methodName", description="方法名称")
    description: str = Field(..., description="方法描述")
    route_description: str = Field(..., alias="routeDescription", description="路线描述")
    altitude_or_distance: str = Field(..., alias="altitudeOrDistance", description="飞行高度或作业距离")
    coverage_pattern: ScanPattern = Field(..., alias="coveragePattern", description="覆盖模式")
    
    class Config:
        populate_by_name = True


class RiskMitigationDetail(BaseModel):
    """风险规避措施"""
    risk_type: str = Field(..., alias="riskType", description="风险类型")
    mitigation_measure: str = Field(..., alias="mitigationMeasure", description="规避措施")
    
    class Config:
        populate_by_name = True


class PrioritizedTarget(BaseModel):
    """优先级排序后的侦察目标"""
    target_id: str = Field(..., description="目标ID")
    target_type: TargetType = Field(..., description="目标类型")
    name: str = Field(..., description="目标名称")
    location: LocationPoint | None = Field(None, description="位置坐标")
    geometry_wkt: str | None = Field(None, description="几何WKT（面状区域）")
    
    priority: PriorityLevel = Field(..., description="优先级等级")
    priority_score: int = Field(..., ge=0, le=100, description="优先级分数0-100")
    priority_reason: str = Field(..., description="优先级理由")
    
    # 设备推荐（新增详细信息）
    recommended_devices: list[DeviceRecommendationDetail] = Field(
        default_factory=list, alias="recommendedDevices", description="推荐设备详情列表"
    )
    recommended_device_types: list[DeviceType] = Field(
        default_factory=list, alias="recommendedDeviceTypes", description="推荐设备类型（简化）"
    )
    
    # 侦察方法（新增）
    recon_method: ReconMethodDetail | None = Field(None, alias="reconMethod", description="侦察方法详情")
    recon_focus: list[str] = Field(default_factory=list, alias="reconFocus", description="侦察重点")
    recon_content: list[str] = Field(default_factory=list, alias="reconContent", description="具体侦察内容")
    
    # 风险与安全（新增）
    risk_mitigations: list[RiskMitigationDetail] = Field(
        default_factory=list, alias="riskMitigations", description="风险规避措施"
    )
    safety_notes: list[str] = Field(default_factory=list, alias="safetyNotes", description="安全注意事项")
    abort_conditions: list[str] = Field(default_factory=list, alias="abortConditions", description="中止条件")
    coordination_notes: str = Field("", alias="coordinationNotes", description="协同说明")
    
    estimated_duration_min: float | None = Field(None, alias="estimatedDurationMin", description="预计侦察时长（分钟）")
    
    source_table: str = Field(..., alias="sourceTable", description="来源表名")
    source_id: str = Field(..., alias="sourceId", description="来源记录ID")
    
    # 额外信息
    estimated_victims: int | None = Field(None, alias="estimatedVictims", description="估计受害人数")
    is_time_critical: bool = Field(False, alias="isTimeCritical", description="是否时间紧迫")
    golden_hour_remaining_min: float | None = Field(None, alias="goldenHourRemainingMin", description="黄金救援时间剩余（分钟）")
    risk_level: int | None = Field(None, alias="riskLevel", description="风险等级1-10")
    population: int | None = Field(None, description="影响人口")
    
    class Config:
        populate_by_name = True


class ResourceEstimate(BaseModel):
    """资源估算"""
    total_devices_needed: int = Field(..., description="需要设备总数")
    total_duration_min: float = Field(..., description="预计总时长（分钟）")
    device_breakdown: dict[str, int] = Field(default_factory=dict, description="设备类型分布")


class AnalysisReport(BaseModel):
    """分析报告"""
    summary: str = Field(..., description="分析摘要")
    resource_estimate: ResourceEstimate = Field(..., description="资源估算")
    recommendations: list[str] = Field(default_factory=list, description="建议列表")
    warnings: list[str] = Field(default_factory=list, description="警告列表")


class ReconTargetAnalysisRequest(BaseModel):
    """侦察目标分析请求"""
    scenario_id: str | None = Field(None, alias="scenarioId", description="想定ID，不传使用当前生效想定")
    use_crewai: bool = Field(True, alias="useCrewAI", description="是否使用LLM分析")
    include_events: bool = Field(True, alias="includeEvents", description="是否包含事件")
    include_risk_areas: bool = Field(True, alias="includeRiskAreas", description="是否包含危险区域")
    include_pois: bool = Field(True, alias="includePOIs", description="是否包含重点目标")
    include_rescue_points: bool = Field(True, alias="includeRescuePoints", description="是否包含救援点")
    
    class Config:
        populate_by_name = True


class ReconTargetAnalysisResponse(BaseModel):
    """侦察目标分析响应"""
    analysis_id: str = Field(..., alias="analysisId", description="分析ID")
    latest_plan_id: str | None = Field(None, alias="latestPlanId", description="最新已有方案ID")
    total_targets: int = Field(..., alias="totalTargets", description="目标总数")
    prioritized_targets: list[PrioritizedTarget] = Field(..., alias="prioritizedTargets", description="优先级排序后的目标列表")
    analysis_report: AnalysisReport = Field(..., alias="analysisReport", description="分析报告")
    created_at: datetime = Field(default_factory=datetime.now, alias="createdAt", description="创建时间")
    
    class Config:
        populate_by_name = True
