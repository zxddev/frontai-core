"""
车辆ORM模型

对应SQL表: operational_v2.vehicles_v2
参考: sql/v2_vehicle_device_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Numeric, Text,
    ARRAY, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geography

from src.core.database import Base


# 车辆类型枚举 - 对应 operational_v2.vehicle_type_v2
VehicleTypeEnum = ENUM(
    'reconnaissance',    # 侦察控制车
    'drone_transport',   # 无人机输送车
    'ship_transport',    # 无人艇输送车
    'medical',           # 医疗救援车
    'logistics',         # 综合保障车
    'command',           # 指挥车
    name='vehicle_type_v2',
    schema='operational_v2',
    create_type=False,   # 类型已在SQL中创建
)

# 设备类型枚举 - 用于compatible_device_types数组
DeviceTypeEnum = ENUM(
    'drone',   # 无人机
    'dog',     # 机器狗
    'ship',    # 无人艇
    'robot',   # 其他机器人
    name='device_type_v2',
    schema='operational_v2',
    create_type=False,
)


class Vehicle(Base):
    """
    车辆表 ORM 模型
    
    业务说明:
    - 车辆是静态资源池，不属于特定场景
    - 通过 scheme_resource_allocations_v2 分配到具体方案
    - current_weight_kg/current_volume_m3/current_device_count 由数据库触发器维护
    """
    __tablename__ = "vehicles_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 基本信息 ====================
    code: str = Column(
        String(50), 
        unique=True, 
        nullable=False,
        comment="车辆编号，如VH-001"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="车辆名称"
    )
    vehicle_type: str = Column(
        VehicleTypeEnum, 
        nullable=False,
        comment="车辆类型: reconnaissance/drone_transport/ship_transport/medical/logistics/command"
    )
    
    # ==================== 载物能力约束 ====================
    max_weight_kg: Decimal = Column(
        Numeric(10, 2), 
        nullable=False,
        comment="最大载重（公斤），不含车辆自重"
    )
    max_volume_m3: Decimal = Column(
        Numeric(10, 4), 
        nullable=False,
        comment="最大载物容积（立方米）"
    )
    max_device_slots: int = Column(
        Integer, 
        nullable=False,
        comment="最大设备位数量"
    )
    
    # ==================== 设备兼容性 ====================
    compatible_device_types: list[str] = Column(
        ARRAY(String),  # 存储枚举值的字符串数组
        nullable=False,
        comment="可装载的设备类型数组: drone/dog/ship/robot"
    )
    
    # ==================== 当前装载状态（触发器维护） ====================
    current_weight_kg: Decimal = Column(
        Numeric(10, 2), 
        default=0,
        comment="当前已装载重量（触发器维护）"
    )
    current_volume_m3: Decimal = Column(
        Numeric(10, 4), 
        default=0,
        comment="当前已占用体积（触发器维护）"
    )
    current_device_count: int = Column(
        Integer, 
        default=0,
        comment="当前已装载设备数（触发器维护）"
    )
    
    # ==================== 车辆本身属性 ====================
    self_weight_kg: Optional[Decimal] = Column(
        Numeric(10, 2),
        comment="车辆自重（公斤）"
    )
    crew_capacity: int = Column(
        Integer, 
        default=4,
        comment="乘员容量"
    )
    
    # ==================== 地形通过能力 ====================
    terrain_capabilities: list[str] = Column(
        ARRAY(String), 
        default=[],
        comment="地形通过能力: all_terrain/mountain/flood/urban/forest/desert/snow"
    )
    is_all_terrain: bool = Column(
        Boolean, 
        default=False,
        comment="是否全地形越野车辆"
    )
    max_gradient_percent: Optional[int] = Column(
        Integer,
        comment="最大爬坡度百分比，如60表示60%坡度"
    )
    max_wading_depth_m: Optional[Decimal] = Column(
        Numeric(4, 2),
        comment="最大涉水深度（米）"
    )
    min_turning_radius_m: Optional[Decimal] = Column(
        Numeric(4, 2),
        comment="最小转弯半径（米）"
    )
    
    # ==================== 通过性参数 ====================
    ground_clearance_mm: Optional[int] = Column(
        Integer,
        comment="最小离地间隙（毫米）"
    )
    approach_angle_deg: Optional[int] = Column(
        Integer,
        comment="接近角（度）"
    )
    departure_angle_deg: Optional[int] = Column(
        Integer,
        comment="离去角（度）"
    )
    breakover_angle_deg: Optional[int] = Column(
        Integer,
        comment="纵向通过角（度）"
    )
    
    # ==================== 速度/续航参数 ====================
    max_speed_kmh: Optional[int] = Column(
        Integer,
        comment="最大速度（公里/小时）"
    )
    terrain_speed_factors: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="地形速度系数，如{mountain:0.6,forest:0.5}"
    )
    fuel_capacity_l: Optional[Decimal] = Column(
        Numeric(6, 2),
        comment="油箱容量（升）"
    )
    fuel_consumption_per_100km: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="百公里油耗（升）"
    )
    range_km: Optional[int] = Column(
        Integer,
        comment="满油续航里程（公里）"
    )
    
    # ==================== 尺寸限制 ====================
    length_m: Optional[Decimal] = Column(
        Numeric(4, 2),
        comment="车长（米）"
    )
    width_m: Optional[Decimal] = Column(
        Numeric(4, 2),
        comment="车宽（米）"
    )
    height_m: Optional[Decimal] = Column(
        Numeric(4, 2),
        comment="车高（米）"
    )
    
    # ==================== 状态与关联 ====================
    status: str = Column(
        String(20), 
        default='available',
        comment="状态: available/deployed/maintenance"
    )
    entity_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联地图实体ID"
    )
    
    # ==================== 扩展属性 ====================
    properties: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="扩展属性JSON"
    )
    
    # ==================== 实时位置（GPS遥测更新） ====================
    # current_location = Column(
    #     Geography('POINT', srid=4326),
    #     comment="车辆当前位置（由GPS遥测数据写入）"
    # )
    # last_location_update: Optional[datetime] = Column(
    #     DateTime(timezone=True),
    #     comment="位置最后更新时间"
    # )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
