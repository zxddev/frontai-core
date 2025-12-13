from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class TaskType(str, Enum):
    search = "search"
    rescue = "rescue"
    evacuation = "evacuation"
    transport = "transport"
    medical = "medical"
    supply = "supply"
    reconnaissance = "reconnaissance"
    communication = "communication"
    other = "other"


class TaskPriority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TaskStatus(str, Enum):
    created = "created"
    assigned = "assigned"
    accepted = "accepted"
    in_progress = "in_progress"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AssigneeType(str, Enum):
    team = "team"
    vehicle = "vehicle"
    device = "device"
    user = "user"


class Location(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)


class TaskCreate(BaseModel):
    scheme_id: Optional[UUID] = None
    scenario_id: UUID
    event_id: Optional[UUID] = None
    task_type: TaskType
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    target_location: Optional[Location] = None
    target_address: Optional[str] = None
    planned_start_at: Optional[datetime] = None
    planned_end_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    requirements: Optional[dict[str, Any]] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    target_location: Optional[Location] = None
    target_address: Optional[str] = None
    planned_start_at: Optional[datetime] = None
    planned_end_at: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    requirements: Optional[dict[str, Any]] = None


class TaskAssign(BaseModel):
    """任务分配"""
    assignee_type: AssigneeType
    assignee_id: UUID
    assignee_name: str
    assignment_reason: Optional[str] = None


class TaskProgressUpdate(BaseModel):
    """更新任务进度"""
    progress_percent: int = Field(..., ge=0, le=100)
    notes: Optional[str] = None


class TaskComplete(BaseModel):
    """完成任务"""
    completion_summary: str
    rescued_count: Optional[int] = None
    notes: Optional[str] = None


class TaskReject(BaseModel):
    """拒绝任务"""
    reason: str


class TaskReassign(BaseModel):
    """重新分配任务"""
    new_assignee_type: AssigneeType
    new_assignee_id: UUID
    new_assignee_name: str
    reason: str


class TaskIssueReport(BaseModel):
    """上报问题"""
    issue_type: str
    description: str
    requires_assistance: bool = False


class AssignmentResponse(BaseModel):
    id: UUID
    task_id: UUID
    assignee_type: AssigneeType
    assignee_id: UUID
    assignee_name: Optional[str]
    assignment_source: str
    assignment_reason: Optional[str]
    status: str
    rejection_reason: Optional[str]
    progress_percent: int
    execution_notes: Optional[str]
    completion_summary: Optional[str]
    assigned_at: datetime
    accepted_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: UUID
    scheme_id: Optional[UUID] = None
    scenario_id: UUID
    event_id: Optional[UUID]
    task_code: str
    task_type: TaskType
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    target_location: Optional[Location]
    target_address: Optional[str]
    planned_start_at: Optional[datetime]
    planned_end_at: Optional[datetime]
    actual_start_at: Optional[datetime]
    actual_end_at: Optional[datetime]
    estimated_duration_minutes: Optional[int]
    instructions: Optional[str]
    requirements: Optional[dict[str, Any]]
    rescued_count: Optional[int]
    progress_percent: int
    created_at: datetime
    updated_at: datetime
    assignments: list[AssignmentResponse] = []

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class MyTasksResponse(BaseModel):
    """执行者的任务列表"""
    items: list[TaskResponse]
    total: int


class TeamRealtimeStatus(BaseModel):
    """队伍实时状态"""
    team_id: UUID
    team_name: str
    location: Optional[Location] = None
    eta_minutes: float = 0
    communication_status: str = "unknown"
    movement_status: str = "unknown"
    last_update: Optional[datetime] = None
    mission_detail: Optional[dict] = None  # 一线队员任务详情（AI生成）
    contact_person: Optional[str] = None   # 队长/联系人姓名
    contact_phone: Optional[str] = None    # 队长/联系人电话


class StepTeamRole(BaseModel):
    """步骤中的队伍角色"""
    team_id: str
    team_name: str
    role: str  # 主攻/配合/保障/待命
    responsibilities: list[str] = []
    equipment: list[str] = []


class StepInstruction(BaseModel):
    """步骤级指令"""
    step_id: str
    step_name: str
    sequence: int
    teams: list[StepTeamRole] = []
    cooperation_mode: str = "sequential"  # sequential/parallel/support
    depends_on: list[str] = []
    estimated_duration: int = 30  # 分钟
    completion_criteria: Optional[str] = None
    safety_notes: Optional[str] = None


class ActionPlan(BaseModel):
    """步骤级协作方案（task_coordinator 输出）"""
    sop_template: str = ""
    total_steps: int = 0
    estimated_duration_minutes: int = 0
    step_instructions: list[StepInstruction] = []
    warnings: list[str] = []


class TaskDetailResponse(TaskResponse):
    """任务详情响应（含队伍实时状态和步骤级协作方案）"""
    team_realtime: list[TeamRealtimeStatus] = []
    action_plan: Optional[ActionPlan] = None  # 步骤级协作方案


class EventBasedTaskResponse(BaseModel):
    """
    基于事件ID查询的响应

    当事件已有任务时返回任务详情，否则返回事件信息（包装成任务结构）
    """
    has_task: bool
    task: Optional[TaskDetailResponse] = None
    event_id: UUID
    event_title: str
    event_description: Optional[str] = None
    event_type: str
    event_status: str
    event_priority: str
    event_address: Optional[str] = None
    event_location: Optional[Location] = None
    estimated_victims: int = 0
    reported_at: Optional[datetime] = None
