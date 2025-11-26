"""
地图实体数据模型（Pydantic Schemas）

对应SQL表: entities_v2, layers_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class EntityType(str, Enum):
    """实体类型枚举"""
    # 装备设备类
    command_vehicle = "command_vehicle"
    uav = "uav"
    drone = "drone"
    robotic_dog = "robotic_dog"
    usv = "usv"
    ship = "ship"
    realTime_uav = "realTime_uav"
    realTime_robotic_dog = "realTime_robotic_dog"
    realTime_usv = "realTime_usv"
    realTime_command_vhicle = "realTime_command_vhicle"
    
    # 路径类
    start_point = "start_point"
    end_point = "end_point"
    planned_route = "planned_route"
    
    # 救援目标类
    rescue_target = "rescue_target"
    resettle_point = "resettle_point"
    rescue_team = "rescue_team"
    resource_point = "resource_point"
    
    # 区域类
    danger_area = "danger_area"
    danger_zone = "danger_zone"
    safety_area = "safety_area"
    investigation_area = "investigation_area"
    weather_area = "weather_area"
    
    # 事件态势类
    event_point = "event_point"
    event_range = "event_range"
    situation_point = "situation_point"
    command_post_candidate = "command_post_candidate"
    
    # 灾害信息类
    earthquake_epicenter = "earthquake_epicenter"


class EntitySource(str, Enum):
    """实体来源"""
    system = "system"
    manual = "manual"


class LayerCategory(str, Enum):
    """图层分类"""
    system = "system"
    manual = "manual"
    hybrid = "hybrid"


class GeometryKind(str, Enum):
    """几何类型"""
    point = "point"
    line = "line"
    polygon = "polygon"
    circle = "circle"


class PlotType(str, Enum):
    """标绘类型"""
    point = "point"
    polyline = "polyline"
    polygon = "polygon"
    circle = "circle"
    arrow = "arrow"
    text = "text"


class Location(BaseModel):
    """地理坐标"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class GeoJsonGeometry(BaseModel):
    """GeoJSON几何对象"""
    type: str = Field(..., description="几何类型: Point/LineString/Polygon")
    coordinates: Any = Field(..., description="坐标数组")


# ============================================================================
# 实体相关
# ============================================================================

class EntityCreate(BaseModel):
    """创建实体请求"""
    type: EntityType = Field(..., description="实体类型")
    layer_code: str = Field(..., max_length=100, description="所属图层编码")
    geometry: GeoJsonGeometry = Field(..., description="几何形状")
    properties: dict[str, Any] = Field(default_factory=dict, description="动态属性")
    device_id: Optional[str] = Field(None, max_length=100, description="关联设备ID")
    source: EntitySource = Field(EntitySource.manual, description="实体来源")
    visible_on_map: bool = Field(True, description="是否在地图显示")
    is_dynamic: bool = Field(False, description="是否为动态实体")
    style_overrides: dict[str, Any] = Field(default_factory=dict, description="样式覆盖")
    scenario_id: Optional[UUID] = Field(None, description="所属场景ID")
    event_id: Optional[UUID] = Field(None, description="关联事件ID")


class EntityUpdate(BaseModel):
    """更新实体请求"""
    geometry: Optional[GeoJsonGeometry] = Field(None, description="几何形状")
    properties: Optional[dict[str, Any]] = Field(None, description="动态属性")
    visible_on_map: Optional[bool] = Field(None, description="是否在地图显示")
    style_overrides: Optional[dict[str, Any]] = Field(None, description="样式覆盖")


class EntityLocationUpdate(BaseModel):
    """更新实体位置请求"""
    location: Location = Field(..., description="新位置")
    speed_kmh: Optional[Decimal] = Field(None, ge=0, description="速度(km/h)")
    heading: Optional[int] = Field(None, ge=0, le=360, description="朝向(0-360)")


class BatchLocationUpdate(BaseModel):
    """批量更新位置请求"""
    updates: list["EntityLocationItem"] = Field(..., description="位置更新列表")


class EntityLocationItem(BaseModel):
    """单个实体位置更新"""
    entity_id: UUID = Field(..., description="实体ID")
    location: Location = Field(..., description="新位置")
    speed_kmh: Optional[Decimal] = Field(None, ge=0, description="速度(km/h)")
    heading: Optional[int] = Field(None, ge=0, le=360, description="朝向(0-360)")


class EntityResponse(BaseModel):
    """实体响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    type: EntityType
    layer_code: str
    device_id: Optional[str]
    geometry: GeoJsonGeometry
    properties: dict[str, Any]
    source: EntitySource
    visible_on_map: bool
    is_dynamic: bool
    last_position_at: Optional[datetime]
    style_overrides: dict[str, Any]
    scenario_id: Optional[UUID]
    event_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class EntityListResponse(BaseModel):
    """实体列表响应"""
    items: list[EntityResponse]
    total: int


class EntityWithDistance(BaseModel):
    """带距离的实体（附近查询用）"""
    id: UUID
    type: EntityType
    name: Optional[str]
    location: Location
    distance_km: float


# ============================================================================
# 态势标绘
# ============================================================================

class PlotCreate(BaseModel):
    """创建标绘请求"""
    scenario_id: UUID = Field(..., description="所属场景ID")
    plot_type: PlotType = Field(..., description="标绘类型")
    name: str = Field(..., max_length=200, description="名称")
    geometry: GeoJsonGeometry = Field(..., description="几何形状")
    style: dict[str, Any] = Field(default_factory=dict, description="样式配置")
    properties: dict[str, Any] = Field(default_factory=dict, description="属性")
    layer_code: Optional[str] = Field("layer.manual", description="目标图层")


class PlotResponse(BaseModel):
    """标绘响应"""
    id: UUID
    plot_type: PlotType
    name: str
    created_at: datetime


# ============================================================================
# 图层相关
# ============================================================================

class LayerResponse(BaseModel):
    """图层响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    category: LayerCategory
    visible_by_default: bool
    style_config: dict[str, Any]
    update_interval_seconds: Optional[int]
    description: Optional[str]
    sort_order: int


class LayerUpdate(BaseModel):
    """更新图层请求"""
    is_visible: Optional[bool] = Field(None, description="是否可见")
    z_index: Optional[int] = Field(None, description="层级")
    style: Optional[dict[str, Any]] = Field(None, description="样式配置")


class LayerWithTypes(BaseModel):
    """带类型定义的图层"""
    code: str
    name: str
    category: LayerCategory
    visible_by_default: bool
    style_config: dict[str, Any]
    update_interval_seconds: Optional[int]
    supported_types: list[dict[str, Any]]


class LayerListResponse(BaseModel):
    """图层列表响应"""
    layers: list[LayerWithTypes]


# ============================================================================
# 历史轨迹
# ============================================================================

class TrackPoint(BaseModel):
    """轨迹点"""
    location: Location
    speed_kmh: Optional[Decimal]
    heading: Optional[int]
    recorded_at: datetime


class TrackResponse(BaseModel):
    """轨迹响应"""
    entity_id: UUID
    tracks: list[TrackPoint]
    total_distance_km: Optional[float]
    duration_min: Optional[int]
