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
    description: str
    location: Location
    supplieList: list[str] = Field(default_factory=list, description="可协调资源列表")


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
    """多救援点任务详情"""
    level: int
    title: str
    rescueTask: list[RescueTask] = Field(default_factory=list)
