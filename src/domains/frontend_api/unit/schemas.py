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
