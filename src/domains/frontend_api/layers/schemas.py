"""
前端图层模块数据结构
"""

from typing import Optional, Any, Literal
from pydantic import BaseModel, Field


class LayerTypeDefinition(BaseModel):
    """图层类型定义"""
    type: str
    geometryKind: str  # Point/Line/Polygon/Circle
    icon: Optional[str] = None
    propertyKeys: list[str] = Field(default_factory=list)


class LayerDto(BaseModel):
    """图层数据"""
    code: str
    name: str
    category: Literal["system", "manual", "hybrid"] = "system"
    visibleByDefault: bool = True
    styleConfig: dict[str, Any] = Field(default_factory=dict)
    updateIntervalSeconds: Optional[int] = None
    description: Optional[str] = None
    supportedTypes: list[LayerTypeDefinition] = Field(default_factory=list)


class EntityGeometry(BaseModel):
    """实体几何数据"""
    type: str  # Point/Line/Polygon/Circle
    coordinates: Any = None
    # 圆形区域补充字段（前端 handleEntity.js 需要）
    center: Optional[list[float]] = None
    radius: Optional[float] = None
    # 天气区域边界框
    bbox: Optional[list[float]] = None


class EntityDto(BaseModel):
    """
    实体数据 - 对接前端地图图层规范
    
    参考: docs/地图图层与后端对接规范.md 第2章
    """
    id: str
    type: str
    layerCode: str
    geometry: Optional[EntityGeometry] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    visibleOnMap: bool = True
    styleOverrides: dict[str, Any] = Field(default_factory=dict)
    createdAt: str = ""
    updatedAt: str = ""


class EntityPage(BaseModel):
    """分页实体结果"""
    items: list[EntityDto] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    pageSize: int = 20
    totalPages: int = 0
