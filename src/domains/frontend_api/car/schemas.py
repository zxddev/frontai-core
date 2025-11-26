"""
前端车辆装备模块数据结构
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class ItemData(BaseModel):
    """装备/物资数据"""
    id: str
    name: str
    model: str = ""
    type: Literal["device", "supply"] = "device"
    isSelected: int = 0


class CarItem(BaseModel):
    """车辆数据"""
    id: str
    name: str
    status: Literal["available", "preparing", "ready"] = "available"
    isSelected: bool = False
    isBelongsToThisCar: int = 0
    itemDataList: list[ItemData] = Field(default_factory=list)


class CarListData(BaseModel):
    """车辆列表响应"""
    carItemDataList: list[CarItem] = Field(default_factory=list)
    carQuestStatus: Literal["pending", "dispatched", "ready", "departed"] = "pending"


class ItemProperty(BaseModel):
    """装备属性"""
    key: str
    value: str


class ItemDetail(BaseModel):
    """装备详情"""
    image: str = ""
    properties: list[ItemProperty] = Field(default_factory=list)


class ItemDetailResponse(BaseModel):
    """装备详情响应"""
    itemDetail: str  # JSON字符串


class CarItemSelect(BaseModel):
    """车辆装备选择"""
    carId: str
    deviceIdList: list[str] = Field(default_factory=list)
    supplyIdList: list[str] = Field(default_factory=list)


class EventIdForm(BaseModel):
    """事件ID表单"""
    eventId: str
