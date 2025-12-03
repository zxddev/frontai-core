"""
前端资源单位模块数据结构
"""

from typing import Optional
from pydantic import BaseModel, Field


class UnitSearchRequest(BaseModel):
    """单位搜索请求"""
    lon: float = Field(..., description="中心点经度")
    lat: float = Field(..., description="中心点纬度")
    rangeInMeters: float = Field(10000, description="搜索半径(米)")
    type: str = Field("", description="单位类型筛选")
    nameLike: str = Field("", description="名称模糊搜索")


class UnitLocation(BaseModel):
    """单位位置"""
    longitude: float
    latitude: float


class Unit(BaseModel):
    """资源单位"""
    id: str
    name: str
    type: str = Field(..., description="单位类型")
    location: Optional[UnitLocation] = None
    address: str = ""
    contact: str = ""
    phone: str = ""
    description: str = ""


class UnitCategory(BaseModel):
    """单位分类"""
    type: str = Field(..., description="分类名称")
    units: list[Unit] = Field(default_factory=list)


class UnitSupportRequest(BaseModel):
    """单位支援资源请求"""
    unitId: str


class SupportResource(BaseModel):
    """支援资源"""
    id: str
    name: str
    type: str
    quantity: int = 0
    status: str = "available"
    description: str = ""


class MobilizeRequest(BaseModel):
    """车辆动员请求"""
    event_id: str = Field(..., description="关联事件ID")
    vehicle_ids: list[str] = Field(..., description="要动员的车辆ID列表")


class MobilizedTeamSummary(BaseModel):
    """已动员队伍摘要"""
    team_id: str
    name: str
    source_vehicle_id: str
    status: str


class MobilizeResponse(BaseModel):
    """车辆动员响应"""
    mobilized_count: int
    teams: list[MobilizedTeamSummary]


class BatchTaskStatusRequest(BaseModel):
    """批量查询队伍任务状态请求"""
    teamIds: list[str] = Field(..., description="队伍ID列表")


class CurrentTaskInfo(BaseModel):
    """当前执行任务信息"""
    taskId: str = Field(..., description="任务ID")
    taskName: str = Field(..., description="任务名称")
    taskStatus: str = Field(..., description="任务状态")
    progressPercent: int = Field(0, description="执行进度(0-100)")
    assignedAt: Optional[str] = Field(None, description="分配时间")


class TeamTaskStatus(BaseModel):
    """队伍任务状态"""
    teamId: str = Field(..., description="队伍ID")
    teamName: str = Field("", description="队伍名称")
    hasTask: bool = Field(False, description="是否有执行中的任务")
    currentTask: Optional[CurrentTaskInfo] = Field(None, description="当前任务信息")


class BatchTaskStatusResponse(BaseModel):
    """批量查询队伍任务状态响应"""
    items: list[TeamTaskStatus] = Field(default_factory=list)
