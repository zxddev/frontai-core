"""
前端方案模块数据结构

对应前端期望的方案请求/响应格式
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class SchemeHistoryRequest(BaseModel):
    """历史方案查询请求"""
    eventId: str = Field(..., description="事件ID")
    hazardType: int = Field(1, description="灾害类型: 1-地震 2-洪涝 3-滑坡等")
    keyWords: str = Field("", description="搜索关键词")


class SchemeHistoryItem(BaseModel):
    """历史方案项"""
    generatedAt: str = Field(..., description="生成时间 ISO8601")
    planData: str = Field(..., description="方案文本内容")


class SchemeCreateRequest(BaseModel):
    """生成侦察任务请求"""
    planData: str = Field(..., description="侦察方案文本描述")
    eventId: str = Field(..., description="事件ID")


class TaskItem(BaseModel):
    """任务项"""
    deviceName: str = Field("", description="设备名称")
    deviceType: str = Field("", description="设备类型")
    carryingModule: str = Field("", description="携带模组")
    timeConsuming: str = Field("", description="预计侦察时间")
    searchRoute: str = Field("", description="侦察路线")


class TaskType(BaseModel):
    """任务类型分组"""
    type: str = Field(..., description="任务类型名称")
    taskList: list[TaskItem] = Field(default_factory=list, description="该类型下的任务列表")


class PlanTaskList(BaseModel):
    """方案任务列表"""
    id: str = Field(..., description="方案ID")
    eventId: str = Field(..., description="事件ID")
    task: list[TaskType] = Field(default_factory=list, description="任务分类数组")


class TaskSendRequest(BaseModel):
    """任务下发请求"""
    id: str = Field(..., description="方案ID")
    eventId: str = Field(..., description="事件ID")
    task: list[TaskType] = Field(default_factory=list, description="任务数组")
