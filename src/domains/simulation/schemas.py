"""
仿真推演数据模型

架构说明:
- 仿真使用真实数据表 + 事务快照还原
- 事件注入直接调用真实的 EventService
- 仿真结束后 ROLLBACK 到 SAVEPOINT 还原数据
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class SimulationStatus(str, Enum):
    """仿真状态"""
    READY = "ready"           # 准备就绪
    RUNNING = "running"       # 运行中
    PAUSED = "paused"         # 暂停
    COMPLETED = "completed"   # 已完成
    STOPPED = "stopped"       # 已停止


class SimulationSourceType(str, Enum):
    """仿真来源类型"""
    NEW = "new"                    # 新建场景
    FROM_HISTORY = "from_history"  # 基于历史想定


# ============================================================================
# 仿真场景
# ============================================================================

class SimulationParticipant(BaseModel):
    """参与人员"""
    user_id: str = Field(..., description="用户ID")
    role: str = Field(..., description="角色")
    joined_at: Optional[datetime] = Field(None, description="加入时间")


class SimulationScenarioCreate(BaseModel):
    """创建仿真场景请求"""
    name: str = Field(..., max_length=200, description="场景名称")
    description: Optional[str] = Field(None, description="描述")
    scenario_id: UUID = Field(..., description="关联想定ID")
    source_type: SimulationSourceType = Field(SimulationSourceType.NEW, description="来源类型")
    source_scenario_id: Optional[UUID] = Field(None, description="历史想定ID（复制来源）")
    time_scale: Decimal = Field(Decimal("1.0"), ge=Decimal("0.5"), le=Decimal("10.0"), description="时间倍率")
    start_simulation_time: Optional[datetime] = Field(None, description="仿真起始时间")
    participants: list[SimulationParticipant] = Field(default_factory=list, description="参与人员")
    inject_events: list["InjectionEventCreate"] = Field(default_factory=list, description="预设注入事件")


class SimulationScenarioResponse(BaseModel):
    """仿真场景响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str]
    scenario_id: UUID
    source_type: SimulationSourceType
    source_scenario_id: Optional[UUID]
    time_scale: Decimal
    start_simulation_time: Optional[datetime]
    current_simulation_time: Optional[datetime]
    status: SimulationStatus
    participants: list[SimulationParticipant]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class SimulationListResponse(BaseModel):
    """仿真场景列表响应"""
    items: list[SimulationScenarioResponse]
    total: int


# ============================================================================
# 事件注入（直接调用真实 EventService）
# ============================================================================

class EventTemplate(BaseModel):
    """
    事件模板
    
    用于预设注入和即时注入，最终会转换为真实的 EventCreate 调用 EventService
    """
    title: str = Field(..., description="事件标题")
    event_type: str = Field(..., description="事件类型: trapped_person/fire/flood/landslide等")
    location: Optional[dict] = Field(None, description="位置 {longitude, latitude}")
    priority: str = Field("medium", description="优先级: low/medium/high/critical")
    description: Optional[str] = Field(None, description="事件描述")
    estimated_victims: int = Field(0, description="预估伤亡人数")
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class ScheduledInjection(BaseModel):
    """
    预设注入事件（内存管理，仿真结束后随数据库回滚一起清除）
    """
    id: str = Field(..., description="注入ID")
    relative_time_min: int = Field(..., ge=0, description="相对仿真开始的时间（分钟）")
    event_template: EventTemplate = Field(..., description="事件模板")
    injected: bool = Field(False, description="是否已注入")
    injected_event_id: Optional[UUID] = Field(None, description="注入后的真实事件ID")
    injected_at: Optional[datetime] = Field(None, description="实际注入时间")


class InjectionEventCreate(BaseModel):
    """创建预设注入事件请求"""
    relative_time_min: int = Field(..., ge=0, description="相对仿真开始的时间（分钟）")
    event_template: EventTemplate = Field(..., description="事件模板")


class ImmediateInjectionRequest(BaseModel):
    """立即注入请求"""
    event: EventTemplate = Field(..., description="事件内容")


class InjectionQueueResponse(BaseModel):
    """注入队列响应"""
    pending: list[ScheduledInjection] = Field(default_factory=list, description="待注入")
    injected: list[ScheduledInjection] = Field(default_factory=list, description="已注入")


# ============================================================================
# 时间控制
# ============================================================================

class TimeScaleUpdateRequest(BaseModel):
    """时间倍率更新请求"""
    time_scale: Decimal = Field(..., ge=Decimal("0.5"), le=Decimal("10.0"), description="时间倍率")


class SimulationTimeResponse(BaseModel):
    """仿真时间响应"""
    real_time: datetime = Field(..., description="真实时间")
    simulation_time: datetime = Field(..., description="仿真时间")
    time_scale: Decimal = Field(..., description="当前倍率")
    elapsed_real_seconds: float = Field(..., description="真实已过秒数")
    elapsed_simulation_seconds: float = Field(..., description="仿真已过秒数")


# ============================================================================
# 演练评估
# ============================================================================

class AssessmentGrade(BaseModel):
    """评估项得分"""
    score: Decimal = Field(..., ge=0, le=100, description="得分")
    detail: str = Field(..., description="详细说明")


class TimelineEvent(BaseModel):
    """时间线事件"""
    time: str = Field(..., description="时间点，如 T+5min")
    event: str = Field(..., description="事件描述")
    evaluation: str = Field(..., description="评价")
    benchmark: Optional[str] = Field(None, description="标准参考")


class AssessmentResult(BaseModel):
    """评估结果"""
    overall_score: Decimal = Field(..., ge=0, le=100, description="总分")
    grades: dict[str, AssessmentGrade] = Field(..., description="各项得分")
    timeline_analysis: list[TimelineEvent] = Field(default_factory=list, description="时间线分析")
    recommendations: list[str] = Field(default_factory=list, description="改进建议")


class AssessmentResponse(BaseModel):
    """评估响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    simulation_id: UUID
    assessment: AssessmentResult
    created_at: datetime


class AssessmentCreateRequest(BaseModel):
    """创建评估请求"""
    include_timeline: bool = Field(True, description="是否包含时间线分析")
    include_recommendations: bool = Field(True, description="是否包含改进建议")


# ============================================================================
# 历史回放
# ============================================================================

class ReplayRequest(BaseModel):
    """历史回放请求"""
    source_scenario_id: UUID = Field(..., description="历史想定ID")
    start_from: Optional[datetime] = Field(None, description="起始时间")
    end_at: Optional[datetime] = Field(None, description="结束时间")
    include_events: bool = Field(True, description="包含事件")
    include_tasks: bool = Field(True, description="包含任务")
    include_entity_tracks: bool = Field(True, description="包含实体轨迹")
    time_scale: Decimal = Field(Decimal("1.0"), description="回放倍率")


class ReplayResponse(BaseModel):
    """历史回放响应"""
    simulation_id: UUID
    source_scenario_id: UUID
    replay_duration_min: float
    events_count: int
    tasks_count: int
    entities_count: int
