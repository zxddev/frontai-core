"""
车辆数据模型（Pydantic Schemas）

对应SQL表: operational_v2.vehicles_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class VehicleType(str, Enum):
    """车辆类型枚举"""
    reconnaissance = "reconnaissance"      # 侦察控制车
    drone_transport = "drone_transport"    # 无人机输送车
    ship_transport = "ship_transport"      # 无人艇输送车
    medical = "medical"                    # 医疗救援车
    logistics = "logistics"                # 综合保障车
    command = "command"                    # 指挥车


class DeviceType(str, Enum):
    """设备类型枚举（用于兼容性配置）"""
    drone = "drone"    # 无人机
    dog = "dog"        # 机器狗
    ship = "ship"      # 无人艇
    robot = "robot"    # 其他机器人


class VehicleStatus(str, Enum):
    """车辆状态"""
    available = "available"      # 可用
    deployed = "deployed"        # 已出动
    maintenance = "maintenance"  # 维护中


class VehicleCreate(BaseModel):
    """创建车辆请求"""
    code: str = Field(..., max_length=50, description="车辆编号，如VH-001")
    name: str = Field(..., max_length=200, description="车辆名称")
    vehicle_type: VehicleType = Field(..., description="车辆类型")
    
    # 载物能力（必填）
    max_weight_kg: Decimal = Field(..., ge=0, description="最大载重（公斤）")
    max_volume_m3: Decimal = Field(..., ge=0, description="最大载物容积（立方米）")
    max_device_slots: int = Field(..., ge=0, description="最大设备位数量")
    compatible_device_types: list[DeviceType] = Field(..., description="可装载的设备类型")
    
    # 车辆属性（可选）
    self_weight_kg: Optional[Decimal] = Field(None, ge=0, description="车辆自重（公斤）")
    crew_capacity: int = Field(4, ge=1, description="乘员容量")
    
    # 地形能力（可选）
    terrain_capabilities: list[str] = Field(default_factory=list, description="地形通过能力")
    is_all_terrain: bool = Field(False, description="是否全地形越野")
    max_gradient_percent: Optional[int] = Field(None, ge=0, le=100, description="最大爬坡度%")
    max_wading_depth_m: Optional[Decimal] = Field(None, ge=0, description="最大涉水深度（米）")
    min_turning_radius_m: Optional[Decimal] = Field(None, ge=0, description="最小转弯半径（米）")
    
    # 通过性参数（可选）
    ground_clearance_mm: Optional[int] = Field(None, ge=0, description="最小离地间隙（毫米）")
    approach_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="接近角（度）")
    departure_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="离去角（度）")
    breakover_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="纵向通过角（度）")
    
    # 速度/续航（可选）
    max_speed_kmh: Optional[int] = Field(None, ge=0, description="最大速度（公里/小时）")
    terrain_speed_factors: dict[str, float] = Field(default_factory=dict, description="地形速度系数")
    fuel_capacity_l: Optional[Decimal] = Field(None, ge=0, description="油箱容量（升）")
    fuel_consumption_per_100km: Optional[Decimal] = Field(None, ge=0, description="百公里油耗（升）")
    range_km: Optional[int] = Field(None, ge=0, description="续航里程（公里）")
    
    # 尺寸（可选）
    length_m: Optional[Decimal] = Field(None, ge=0, description="车长（米）")
    width_m: Optional[Decimal] = Field(None, ge=0, description="车宽（米）")
    height_m: Optional[Decimal] = Field(None, ge=0, description="车高（米）")
    
    # 扩展
    entity_id: Optional[UUID] = Field(None, description="关联地图实体ID")
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class VehicleUpdate(BaseModel):
    """更新车辆请求"""
    name: Optional[str] = Field(None, max_length=200, description="车辆名称")
    
    # 载物能力
    max_weight_kg: Optional[Decimal] = Field(None, ge=0, description="最大载重（公斤）")
    max_volume_m3: Optional[Decimal] = Field(None, ge=0, description="最大载物容积（立方米）")
    max_device_slots: Optional[int] = Field(None, ge=0, description="最大设备位数量")
    compatible_device_types: Optional[list[DeviceType]] = Field(None, description="可装载的设备类型")
    
    # 车辆属性
    self_weight_kg: Optional[Decimal] = Field(None, ge=0, description="车辆自重（公斤）")
    crew_capacity: Optional[int] = Field(None, ge=1, description="乘员容量")
    
    # 地形能力
    terrain_capabilities: Optional[list[str]] = Field(None, description="地形通过能力")
    is_all_terrain: Optional[bool] = Field(None, description="是否全地形越野")
    max_gradient_percent: Optional[int] = Field(None, ge=0, le=100, description="最大爬坡度%")
    max_wading_depth_m: Optional[Decimal] = Field(None, ge=0, description="最大涉水深度（米）")
    min_turning_radius_m: Optional[Decimal] = Field(None, ge=0, description="最小转弯半径（米）")
    
    # 通过性参数
    ground_clearance_mm: Optional[int] = Field(None, ge=0, description="最小离地间隙（毫米）")
    approach_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="接近角（度）")
    departure_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="离去角（度）")
    breakover_angle_deg: Optional[int] = Field(None, ge=0, le=90, description="纵向通过角（度）")
    
    # 速度/续航
    max_speed_kmh: Optional[int] = Field(None, ge=0, description="最大速度（公里/小时）")
    terrain_speed_factors: Optional[dict[str, float]] = Field(None, description="地形速度系数")
    fuel_capacity_l: Optional[Decimal] = Field(None, ge=0, description="油箱容量（升）")
    fuel_consumption_per_100km: Optional[Decimal] = Field(None, ge=0, description="百公里油耗（升）")
    range_km: Optional[int] = Field(None, ge=0, description="续航里程（公里）")
    
    # 尺寸
    length_m: Optional[Decimal] = Field(None, ge=0, description="车长（米）")
    width_m: Optional[Decimal] = Field(None, ge=0, description="车宽（米）")
    height_m: Optional[Decimal] = Field(None, ge=0, description="车高（米）")
    
    # 状态
    status: Optional[VehicleStatus] = Field(None, description="车辆状态")
    
    # 扩展
    entity_id: Optional[UUID] = Field(None, description="关联地图实体ID")
    properties: Optional[dict[str, Any]] = Field(None, description="扩展属性")


class VehicleResponse(BaseModel):
    """车辆响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    vehicle_type: VehicleType
    
    # 载物能力
    max_weight_kg: Decimal
    max_volume_m3: Decimal
    max_device_slots: int
    compatible_device_types: list[str]
    
    # 当前装载状态
    current_weight_kg: Decimal
    current_volume_m3: Decimal
    current_device_count: int
    
    # 车辆属性
    self_weight_kg: Optional[Decimal]
    crew_capacity: int
    
    # 地形能力
    terrain_capabilities: list[str]
    is_all_terrain: bool
    max_gradient_percent: Optional[int]
    max_wading_depth_m: Optional[Decimal]
    min_turning_radius_m: Optional[Decimal]
    
    # 通过性参数
    ground_clearance_mm: Optional[int]
    approach_angle_deg: Optional[int]
    departure_angle_deg: Optional[int]
    breakover_angle_deg: Optional[int]
    
    # 速度/续航
    max_speed_kmh: Optional[int]
    terrain_speed_factors: dict[str, Any]
    fuel_capacity_l: Optional[Decimal]
    fuel_consumption_per_100km: Optional[Decimal]
    range_km: Optional[int]
    
    # 尺寸
    length_m: Optional[Decimal]
    width_m: Optional[Decimal]
    height_m: Optional[Decimal]
    
    # 状态
    status: VehicleStatus
    entity_id: Optional[UUID]
    
    # 扩展
    properties: dict[str, Any]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    """车辆列表响应"""
    items: list[VehicleResponse]
    total: int
    page: int
    page_size: int


class VehicleCapacityCheck(BaseModel):
    """车辆容量检查结果"""
    vehicle_id: UUID
    can_load: bool
    remaining_weight_kg: Decimal
    remaining_volume_m3: Decimal
    remaining_device_slots: int
    message: Optional[str] = None


class VehicleLocationUpdate(BaseModel):
    """车辆位置更新请求"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    heading: Optional[float] = Field(None, ge=0, lt=360, description="航向角(度)")
    speed_kmh: Optional[float] = Field(None, ge=0, description="当前速度(km/h)")
    source: str = Field("gps", description="位置来源: gps/manual/simulation")


class VehicleLocationResponse(BaseModel):
    """车辆位置响应"""
    vehicle_id: UUID
    longitude: float
    latitude: float
    last_update: datetime
    message: str
