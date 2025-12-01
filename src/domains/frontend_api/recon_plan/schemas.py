"""Schemas for frontend reconnaissance planning APIs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReconPlanRequest(BaseModel):
    """Initial recon planning request from frontend.

    If ``scenarioId`` is omitted, the backend will automatically use the
    currently active scenario (status = 'active').
    """

    scenarioId: Optional[str] = Field(default=None, description="想定ID，可选；为空时使用当前生效想定")
    eventId: Optional[str] = Field(default=None, description="事件ID，可选")


class ReconTargetItem(BaseModel):
    """A single recon target with priority score."""

    id: str = Field(..., description="目标ID，对应风险区域ID")
    riskAreaId: Optional[str] = Field(default=None, description="关联的风险区域ID")
    name: str = Field(..., description="目标名称")
    priority: str = Field(..., description="优先级 critical/high/medium/low")
    score: float = Field(..., description="综合打分[0,1]")
    geometry: Dict[str, Any] = Field(default_factory=dict, description="GeoJSON几何信息")
    features: Dict[str, Any] = Field(default_factory=dict, description="用于打分的特征字段快照")
    reasons: List[str] = Field(default_factory=list, description="打分理由/硬规则触发说明")


class DeviceAssignmentItem(BaseModel):
    """Device-to-target assignment for initial recon."""

    deviceId: str = Field(..., description="设备ID")
    deviceName: str = Field(..., description="设备名称")
    deviceType: str = Field(..., description="设备类型 drone/dog/ship/robot")
    targetId: str = Field(..., description="目标ID")
    targetName: str = Field(..., description="目标名称")
    priority: str = Field(..., description="该目标的优先级")
    reason: str = Field(default="", description="分配该设备的理由")


class MissionStepItem(BaseModel):
    """侦察任务执行步骤"""
    
    stepName: str = Field(..., description="步骤名称")
    description: str = Field(..., description="步骤描述")
    durationMinutes: int = Field(..., description="预计耗时（分钟）")
    keyActions: List[str] = Field(default_factory=list, description="关键动作")


class ReconMissionItem(BaseModel):
    """单个设备的侦察任务方案"""
    
    missionId: str = Field(..., description="任务ID")
    deviceId: str = Field(..., description="设备ID")
    deviceName: str = Field(..., description="设备名称")
    deviceType: str = Field(..., description="设备类型")
    targetId: str = Field(..., description="目标ID")
    targetName: str = Field(..., description="目标名称")
    priority: str = Field(..., description="任务优先级")
    
    missionObjective: str = Field(..., description="任务目标")
    reconFocus: List[str] = Field(default_factory=list, description="侦察重点")
    reconMethod: str = Field(..., description="侦察方法")
    routeDescription: str = Field(..., description="路线描述")
    altitudeOrDepth: str = Field(default="", description="作业高度/距离")
    estimatedDurationMinutes: int = Field(..., description="预计耗时（分钟）")
    steps: List[MissionStepItem] = Field(default_factory=list, description="执行步骤")
    
    coordinationNotes: str = Field(default="", description="协同说明")
    safetyNotes: List[str] = Field(default_factory=list, description="安全注意事项")
    abortConditions: List[str] = Field(default_factory=list, description="中止条件")


class ReconExecutionPlan(BaseModel):
    """完整的侦察执行方案"""
    
    planId: str = Field(..., description="方案ID")
    summary: str = Field(..., description="方案概述")
    totalDurationMinutes: int = Field(..., description="总预计耗时（分钟）")
    
    missions: List[ReconMissionItem] = Field(default_factory=list, description="各设备任务方案")
    
    coordinationStrategy: str = Field(default="", description="整体协同策略")
    communicationPlan: str = Field(default="", description="通讯方案")
    contingencyPlan: str = Field(default="", description="应急预案")


class ReconPlanResponse(BaseModel):
    """Initial recon plan returned to frontend."""

    scenarioId: str = Field(..., description="想定ID")
    eventId: Optional[str] = Field(default=None, description="事件ID")
    targets: List[ReconTargetItem] = Field(default_factory=list, description="按优先级排序的侦察目标列表")
    assignments: List[DeviceAssignmentItem] = Field(default_factory=list, description="无人设备初始分配方案")
    explanation: str = Field(..., description="中文解释文本，便于直接展示")
    riskAreas: List[Dict[str, Any]] = Field(default_factory=list, description="原始风险区域数据快照")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="参与本次侦察的设备列表")
    reconPlan: Optional[ReconExecutionPlan] = Field(default=None, description="侦察执行方案（含每个设备的具体任务）")


__all__ = [
    "ReconPlanRequest",
    "ReconTargetItem",
    "DeviceAssignmentItem",
    "MissionStepItem",
    "ReconMissionItem",
    "ReconExecutionPlan",
    "ReconPlanResponse",
]
