"""
Task Coordinator 数据模型定义

定义任务协调过程中使用的所有 Pydantic 模型。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# 枚举类型
# ============================================================================

class CooperationMode(str, Enum):
    """协作模式"""
    SEQUENTIAL = "sequential"  # 顺序：A完成后B开始
    PARALLEL = "parallel"      # 并行：A和B同时进行
    SUPPORT = "support"        # 支援：B辅助A
    STANDBY = "standby"        # 待命：B在A需要时介入


class TeamRoleType(str, Enum):
    """队伍角色类型"""
    PRIMARY = "主攻"      # 主要执行者
    SUPPORT = "配合"      # 配合执行
    LOGISTICS = "保障"    # 后勤保障
    STANDBY = "待命"      # 待命支援


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


# ============================================================================
# SOP 相关模型（来自 Neo4j）
# ============================================================================

class SOPTemplate(BaseModel):
    """SOP 模板（从 Neo4j 加载）"""
    id: str
    name: str
    disaster_type: str
    scene_code: str
    description: Optional[str] = None
    version: str = "1.0"
    total_steps: int = 0
    estimated_duration_minutes: int = 0


class SOPStep(BaseModel):
    """SOP 步骤（从 Neo4j 加载）"""
    id: str
    name: str
    sequence: int
    duration_minutes: int = 30
    roles: List[str] = Field(default_factory=list)  # ["主攻", "配合"]
    required_capabilities: List[str] = Field(default_factory=list)
    required_equipment: List[str] = Field(default_factory=list)
    parallel_allowed: bool = False
    completion_criteria: Optional[str] = None
    safety_notes: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)  # 依赖的步骤ID


# ============================================================================
# 队伍和分配相关模型
# ============================================================================

class TeamInfo(BaseModel):
    """队伍基本信息"""
    team_id: str
    team_name: str
    capabilities: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    personnel_count: int = 0
    current_location: Optional[Dict[str, float]] = None  # {lat, lng}


class TeamRole(BaseModel):
    """队伍角色分配"""
    team_id: str
    team_name: str
    role: TeamRoleType
    responsibilities: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)


class StepAssignment(BaseModel):
    """步骤分配（一个步骤可能有多个队伍）"""
    step_id: str
    step_name: str
    sequence: int
    teams: List[TeamRole] = Field(default_factory=list)
    cooperation_mode: CooperationMode = CooperationMode.SEQUENTIAL
    depends_on: List[str] = Field(default_factory=list)
    estimated_duration: int = 30  # 分钟
    completion_criteria: Optional[str] = None
    safety_notes: Optional[str] = None


# ============================================================================
# 输入输出模型
# ============================================================================

class TaskAllocation(BaseModel):
    """来自 emergency_ai 的任务分配"""
    task_id: str
    task_name: str
    disaster_type: str
    scene_code: Optional[str] = None
    allocated_teams: List[TeamInfo] = Field(default_factory=list)
    location: Optional[Dict[str, float]] = None
    priority: int = 1
    estimated_victims: int = 0


class TaskCoordinatorInput(BaseModel):
    """Task Coordinator 输入"""
    event_id: str
    allocations: List[TaskAllocation]
    disaster_info: Optional[Dict[str, Any]] = None


class StepInstruction(BaseModel):
    """步骤级指令（输出给队伍）"""
    step_id: str
    step_name: str
    sequence: int
    teams: List[TeamRole]
    cooperation_mode: str
    depends_on: List[str]
    estimated_duration: int
    completion_criteria: Optional[str] = None
    safety_notes: Optional[str] = None


class TaskCoordinatorOutput(BaseModel):
    """Task Coordinator 输出"""
    task_id: str
    task_name: str
    sop_template: str
    total_steps: int
    estimated_duration_minutes: int
    step_instructions: List[StepInstruction]
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# 错误和警告
# ============================================================================

class CoordinatorWarning(BaseModel):
    """协调警告"""
    code: str
    message: str
    severity: str = "warning"  # warning/error/info
    related_step: Optional[str] = None
    related_team: Optional[str] = None
