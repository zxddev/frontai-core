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


class EntityDto(BaseModel):
    """实体数据"""
    id: str
    layerCode: str
    type: str
    geometry: EntityGeometry
    properties: dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = None
    timestamp: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    visibleOnMap: bool = True
    dynamic: bool = False
    source: str = "system"
    lastPositionAt: Optional[str] = None
    styleOverrides: Optional[dict[str, Any]] = None
    createdAt: str = ""
    updatedAt: str = ""


class EntityPage(BaseModel):
    """分页实体结果"""
    items: list[EntityDto] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    pageSize: int = 20
    totalPages: int = 0
