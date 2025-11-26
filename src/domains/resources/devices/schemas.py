"""
设备数据模型（Pydantic Schemas）

对应SQL表: operational_v2.devices_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DeviceType(str, Enum):
    """设备类型枚举"""
    drone = "drone"    # 无人机
    dog = "dog"        # 机器狗
    ship = "ship"      # 无人艇
    robot = "robot"    # 其他机器人


class EnvType(str, Enum):
    """作业环境类型"""
    air = "air"      # 空中
    land = "land"    # 地面
    sea = "sea"      # 水上


class ModuleType(str, Enum):
    """模块类型"""
    sensor = "sensor"              # 传感器模块
    communication = "communication" # 通信模块
    utility = "utility"            # 功能模块
    power = "power"                # 电源模块


class DeviceStatus(str, Enum):
    """设备状态"""
    available = "available"      # 可用
    deployed = "deployed"        # 已部署
    charging = "charging"        # 充电中
    maintenance = "maintenance"  # 维护中


class DeviceCreate(BaseModel):
    """创建设备请求"""
    code: str = Field(..., max_length=50, description="设备编号，如DV-DRONE-001")
    name: str = Field(..., max_length=200, description="设备名称")
    device_type: DeviceType = Field(..., description="设备类型")
    env_type: EnvType = Field(..., description="作业环境")
    
    # 物理属性（必填）
    weight_kg: Decimal = Field(..., ge=0, description="设备重量（公斤）")
    volume_m3: Decimal = Field(..., ge=0, description="设备体积（立方米）")
    
    # 模块系统
    module_slots: int = Field(0, ge=0, description="模块插槽数量")
    compatible_module_types: list[ModuleType] = Field(default_factory=list, description="可安装的模块类型")
    
    # 灾害适用性
    applicable_disasters: list[str] = Field(default_factory=list, description="适用灾害类型")
    forbidden_disasters: list[str] = Field(default_factory=list, description="禁用灾害类型")
    min_response_level: Optional[str] = Field(None, max_length=10, description="最低响应等级")
    
    # 设备能力
    base_capabilities: list[str] = Field(default_factory=list, description="设备自带能力")
    
    # 型号信息
    model: Optional[str] = Field(None, max_length=100, description="设备型号")
    manufacturer: Optional[str] = Field(None, max_length=100, description="生产厂商")
    
    # 关联
    in_vehicle_id: Optional[UUID] = Field(None, description="装载到的车辆ID")
    entity_id: Optional[UUID] = Field(None, description="关联地图实体ID")
    
    # 扩展
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class DeviceUpdate(BaseModel):
    """更新设备请求"""
    name: Optional[str] = Field(None, max_length=200, description="设备名称")
    
    # 模块系统
    module_slots: Optional[int] = Field(None, ge=0, description="模块插槽数量")
    compatible_module_types: Optional[list[ModuleType]] = Field(None, description="可安装的模块类型")
    
    # 灾害适用性
    applicable_disasters: Optional[list[str]] = Field(None, description="适用灾害类型")
    forbidden_disasters: Optional[list[str]] = Field(None, description="禁用灾害类型")
    min_response_level: Optional[str] = Field(None, max_length=10, description="最低响应等级")
    
    # 设备能力
    base_capabilities: Optional[list[str]] = Field(None, description="设备自带能力")
    
    # 型号信息
    model: Optional[str] = Field(None, max_length=100, description="设备型号")
    manufacturer: Optional[str] = Field(None, max_length=100, description="生产厂商")
    
    # 状态
    status: Optional[DeviceStatus] = Field(None, description="设备状态")
    
    # 关联
    entity_id: Optional[UUID] = Field(None, description="关联地图实体ID")
    
    # 扩展
    properties: Optional[dict[str, Any]] = Field(None, description="扩展属性")


class DeviceResponse(BaseModel):
    """设备响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    device_type: DeviceType
    env_type: EnvType
    
    # 物理属性
    weight_kg: Decimal
    volume_m3: Decimal
    
    # 模块系统
    module_slots: int
    current_module_count: int
    compatible_module_types: list[str]
    
    # 灾害适用性
    applicable_disasters: list[str]
    forbidden_disasters: list[str]
    min_response_level: Optional[str]
    
    # 设备能力
    base_capabilities: list[str]
    
    # 型号信息
    model: Optional[str]
    manufacturer: Optional[str]
    
    # 状态与关联
    status: DeviceStatus
    in_vehicle_id: Optional[UUID]
    entity_id: Optional[UUID]
    
    # 扩展
    properties: dict[str, Any]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime


class DeviceListResponse(BaseModel):
    """设备列表响应"""
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


class DeviceLoadRequest(BaseModel):
    """设备装载请求"""
    vehicle_id: UUID = Field(..., description="目标车辆ID")


class DeviceLoadResult(BaseModel):
    """设备装载结果"""
    device_id: UUID
    vehicle_id: UUID
    success: bool
    message: Optional[str] = None


class DeviceTelemetryData(BaseModel):
    """设备遥测数据"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    altitude_m: Optional[float] = Field(None, description="高度(米)")
    heading: Optional[float] = Field(None, ge=0, lt=360, description="航向角(度)")
    speed_ms: Optional[float] = Field(None, ge=0, description="速度(米/秒)")
    battery_percent: Optional[int] = Field(None, ge=0, le=100, description="电量(%)")
    signal_strength: Optional[int] = Field(None, ge=0, le=100, description="信号强度(%)")
    sensors: dict[str, Any] = Field(default_factory=dict, description="传感器数据")
    timestamp: Optional[datetime] = Field(None, description="数据时间戳(设备端)")


class DeviceTelemetryResponse(BaseModel):
    """设备遥测响应"""
    device_id: UUID
    received_at: datetime
    location_updated: bool
    message: str
