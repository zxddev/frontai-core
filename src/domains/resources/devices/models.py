"""
设备ORM模型

对应SQL表: operational_v2.devices_v2
参考: sql/v2_vehicle_device_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, DateTime, Numeric, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM

from src.core.database import Base


# 设备类型枚举 - 对应 operational_v2.device_type_v2
DeviceTypeEnum = ENUM(
    'drone',   # 无人机
    'dog',     # 机器狗
    'ship',    # 无人艇
    'robot',   # 其他机器人
    name='device_type_v2',
    schema='operational_v2',
    create_type=False,
)

# 模块类型枚举 - 对应 operational_v2.module_type_v2
ModuleTypeEnum = ENUM(
    'sensor',        # 传感器模块
    'communication', # 通信模块
    'utility',       # 功能模块
    'power',         # 电源模块
    name='module_type_v2',
    schema='operational_v2',
    create_type=False,
)


class Device(Base):
    """
    设备表 ORM 模型
    
    业务说明:
    - 设备包括无人机、机器狗、无人艇等
    - 通过 in_vehicle_id 关联到车辆（装载关系）
    - 通过模块系统扩展设备能力
    """
    __tablename__ = "devices_v2"
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
        comment="设备编号，如DV-DRONE-001"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="设备名称"
    )
    device_type: str = Column(
        DeviceTypeEnum, 
        nullable=False,
        comment="设备类型: drone/dog/ship/robot"
    )
    env_type: str = Column(
        String(20), 
        nullable=False,
        comment="作业环境: air/land/sea"
    )
    
    # ==================== 物理属性 ====================
    weight_kg: Decimal = Column(
        Numeric(10, 2), 
        nullable=False,
        comment="设备重量（公斤）"
    )
    volume_m3: Decimal = Column(
        Numeric(10, 4), 
        nullable=False,
        comment="设备体积（立方米）"
    )
    
    # ==================== 模块系统 ====================
    module_slots: int = Column(
        Integer, 
        default=0,
        comment="模块插槽数量"
    )
    current_module_count: int = Column(
        Integer, 
        default=0,
        comment="当前已安装模块数（触发器维护）"
    )
    compatible_module_types: list[str] = Column(
        ARRAY(String),
        comment="可安装的模块类型数组"
    )
    
    # ==================== 灾害适用性 ====================
    applicable_disasters: list[str] = Column(
        ARRAY(String),
        comment="适用灾害类型数组"
    )
    forbidden_disasters: list[str] = Column(
        ARRAY(String),
        comment="禁用灾害类型数组"
    )
    min_response_level: Optional[str] = Column(
        String(10),
        comment="最低响应等级要求"
    )
    
    # ==================== 设备能力 ====================
    base_capabilities: list[str] = Column(
        ARRAY(String),
        comment="设备自带能力（不依赖模块）"
    )
    
    # ==================== 型号信息 ====================
    model: Optional[str] = Column(
        String(100),
        comment="设备型号"
    )
    manufacturer: Optional[str] = Column(
        String(100),
        comment="生产厂商"
    )
    
    # ==================== 状态与关联 ====================
    status: str = Column(
        String(20), 
        default='available',
        comment="状态: available/deployed/charging/maintenance"
    )
    in_vehicle_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("operational_v2.vehicles_v2.id"),
        comment="当前所在车辆ID"
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
