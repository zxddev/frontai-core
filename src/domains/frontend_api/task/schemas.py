"""
前端任务模块数据结构

对应前端期望的任务请求/响应格式
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class Location(BaseModel):
    """位置信息"""
    longitude: float
    latitude: float


class TaskLogData(BaseModel):
    """任务日志"""
    timestamp: str = Field(..., description="时间戳")
    origin: str = Field(..., description="来源/操作人")
    description: str = Field(..., description="描述")


class FrontendTask(BaseModel):
    """前端任务格式"""
    id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    description: str = Field("", description="任务描述")
    status: str = Field("PENDING", description="任务状态")
    createdAt: str = Field("", description="创建时间")
    deadline: Optional[str] = Field(None, description="截止时间")
    taskLogDataList: list[TaskLogData] = Field(default_factory=list, description="任务日志")


class TaskLogCommitRequest(BaseModel):
    """任务日志提交请求"""
    taskId: str = Field(..., description="任务ID")
    description: str = Field(..., description="操作描述")
    recorderName: str = Field(..., description="记录人名称")
    recorderId: str = Field(..., description="记录人ID")
    origin: str = Field(..., description="来源")
    status: str = Field(..., description="目标状态")


class UnitTask(BaseModel):
    """单位任务"""
    id: str
    name: str
    description: str = Field("", description="救援目标（事件发生地）")
    team_location: str = Field("", description="队伍当前位置")
    location: Location
    equipments: list[str] = Field(default_factory=list, description="携带装备")
    task_description: str = Field("", description="具体任务描述")
    rescue_point_name: str = Field("", description="所属救援点（用于协作分组）")
    target_situation: str = Field("", description="目标情况（被困人数、现场环境等）")
    risk_warnings: list[str] = Field(default_factory=list, description="风险预警列表")
    commander_order: str = Field("", description="指挥员命令/批示")
    eta_minutes: float = Field(0, description="预计到达时间（分钟）")
    collaborating_teams: list[str] = Field(default_factory=list, description="同组协作队伍名单")
    contact_name: str = Field("", description="队长/联系人姓名")
    contact_phone: str = Field("", description="队长/联系人电话")


class EquipmentTask(BaseModel):
    """设备任务"""
    deviceName: str
    deviceType: str
    carryingModule: str
    timeConsuming: str
    searchRoute: str


class TaskType(BaseModel):
    """任务类型分组"""
    type: str
    taskList: list[EquipmentTask]


class TaskSendRequest(BaseModel):
    """任务下发请求"""
    id: str
    eventId: str
    task: list[TaskType]


class RescueTask(BaseModel):
    """救援任务"""
    units: list[UnitTask] = Field(default_factory=list)
    equipmentList: list[EquipmentTask] = Field(default_factory=list)


class RescueDetailResponse(BaseModel):
    """救援方案详情响应"""
    time: str = Field(..., description="识别时间")
    textContent: str = Field(..., description="事件描述")
    locationName: str = Field(..., description="位置名称")
    location: Location
    origin: str = Field(..., description="来源")
    image: str = Field("", description="救援点图片URL")
    rescueTask: list[RescueTask] = Field(default_factory=list)


class RescuePoint(BaseModel):
    """救援点信息"""
    id: str = Field(..., description="事件ID")
    level: int = Field(1, description="紧急级别")
    title: str
    origin: str
    time: str
    locationName: str
    location: Location
    image: str = ""
    schema_: str = Field("", alias="schema", serialization_alias="schema", description="救援方案文本")
    description: str = ""
    
    model_config = {"populate_by_name": True}


class MultiRescueTaskDetail(BaseModel):
    """多救援点任务详情（草案）"""
    event_id: str = Field(..., description="关联事件ID，用于后续创建任务")
    source: str = Field("quick_recommended", description="方案来源: ai_recommended/quick_recommended")
    level: int = Field(..., description="紧急级别 1-4")
    title: str = Field(..., description="事件标题")
    rescueTask: list[RescueTask] = Field(default_factory=list)


class MissionDetail(BaseModel):
    """一线队员任务详情（AI生成）"""
    task_description: str = Field("", description="具体任务描述")
    rescue_point_name: str = Field("", description="所属救援点")
    target_situation: str = Field("", description="目标情况（被困人数、现场环境等）")
    collaborating_teams: list[str] = Field(default_factory=list, description="协作队伍名单")
    risk_warnings: list[str] = Field(default_factory=list, description="风险预警")
    equipments: list[str] = Field(default_factory=list, description="携带装备")
    eta_minutes: float = Field(0, description="预计到达时间（分钟）")
    commander_order: str = Field("", description="指挥员命令/批示")


class UnitTaskItem(BaseModel):
    """批量执行时的队伍分配项"""
    id: str = Field(..., description="队伍ID")
    name: str = Field(..., description="队伍名称")
    description: str = Field("", description="任务描述")
    commander_order: str = Field("", description="指挥员命令/批示")
    mission_detail: Optional[MissionDetail] = Field(None, description="一线队员任务详情（AI生成）")


class RescueTaskItem(BaseModel):
    """批量执行时的单个任务项"""
    event_id: str = Field(..., description="事件ID")
    title: str = Field("", description="任务标题")
    units: list[UnitTaskItem] = Field(default_factory=list, description="分配的队伍列表")


class BatchRescueTaskRequest(BaseModel):
    """批量执行救援任务请求"""
    scenario_id: str = Field(..., description="想定ID")
    tasks: list[RescueTaskItem] = Field(..., description="任务列表")


class TaskCreateResult(BaseModel):
    """单个任务创建结果"""
    event_id: str
    task_id: str = Field("", description="创建的任务ID，失败时为空")
    success: bool
    skipped: bool = False
    reason: str = Field("", description="跳过或失败原因")


class BatchRescueTaskResponse(BaseModel):
    """批量执行救援任务响应"""
    total: int = Field(..., description="总任务数")
    created: int = Field(..., description="成功创建数")
    skipped: int = Field(0, description="跳过数（已有任务）")
    results: list[TaskCreateResult] = Field(default_factory=list)
