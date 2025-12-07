"""
救援队伍位置查询数据模型

强类型定义，完整字段匹配
"""
from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field


class TeamLocationItem(BaseModel):
    """队伍位置信息"""
    teamId: str = Field(..., description="队伍ID")
    name: str = Field(..., description="队伍名称")
    teamType: str = Field(..., description="队伍类型")
    status: str = Field(..., description="队伍状态")
    longitude: Optional[float] = Field(None, description="经度，空表示无位置")
    latitude: Optional[float] = Field(None, description="纬度，空表示无位置")
    lastLocationUpdate: Optional[str] = Field(None, description="位置最后更新时间(ISO格式)")
    hasLocation: bool = Field(..., description="是否有位置数据")
    locationStale: bool = Field(False, description="位置是否过期(超过30分钟)")
    currentTaskId: Optional[str] = Field(None, description="当前执行的任务ID")


class TeamLocationListRequest(BaseModel):
    """队伍位置列表查询请求(Query参数，此处仅用于文档)"""
    scenarioId: Optional[str] = Field(None, description="场景ID，默认查活动场景")
    status: Optional[str] = Field(None, description="队伍状态筛选")
    teamType: Optional[str] = Field(None, description="队伍类型筛选")
    convertToGcj02: bool = Field(True, description="是否转换为高德坐标系(GCJ02)")


class TeamLocationListResponse(BaseModel):
    """队伍位置列表响应"""
    items: List[TeamLocationItem] = Field(default_factory=list, description="队伍位置列表")
    total: int = Field(..., description="总数")
    scenarioId: Optional[str] = Field(None, description="查询的场景ID")


class TeamLocationBatchRequest(BaseModel):
    """批量查询队伍位置请求"""
    teamIds: List[str] = Field(..., min_length=1, max_length=100, description="队伍ID列表，最多100个")
    convertToGcj02: bool = Field(True, description="是否转换为高德坐标系(GCJ02)")


class TeamLocationBatchResponse(BaseModel):
    """批量查询队伍位置响应"""
    items: List[TeamLocationItem] = Field(default_factory=list, description="队伍位置列表")
    total: int = Field(..., description="返回数量")
    requestedCount: int = Field(..., description="请求的队伍数量")
