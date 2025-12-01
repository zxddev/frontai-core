"""
疏散安置点ORM模型

对应SQL表: operational_v2.evacuation_shelters_v2
参考: sql/v2_environment_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, DateTime, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geometry

from src.core.database import Base


# 安置点类型枚举 - 对应 operational_v2.shelter_type_v2
ShelterTypeEnum = ENUM(
    'temporary',       # 临时安置点
    'permanent',       # 固定安置点
    'medical',         # 医疗救护点
    'supply_depot',    # 物资集散点
    'command_post',    # 指挥所
    'helipad',         # 直升机起降点
    'staging_area',    # 集结区
    name='shelter_type_v2',
    create_type=False,
)


# 安置点状态枚举 - 对应 operational_v2.shelter_status_v2
ShelterStatusEnum = ENUM(
    'preparing',       # 准备中
    'open',            # 开放
    'full',            # 已满
    'limited',         # 限流
    'closed',          # 关闭
    'damaged',         # 受损
    name='shelter_status_v2',
    create_type=False,
)


class EvacuationShelter(Base):
    """
    疏散安置点表 ORM 模型
    
    业务说明:
    - 安置点用于人员疏散和临时安置
    - scenario_id为NULL表示常备安置点
    - available_capacity是数据库GENERATED列，由total_capacity - current_occupancy自动计算
    """
    __tablename__ = "evacuation_shelters_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联想定 ====================
    scenario_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="所属想定ID，NULL表示常备安置点"
    )
    
    # ==================== 基本信息 ====================
    shelter_code: str = Column(
        String(50), 
        nullable=False,
        comment="安置点编号"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="安置点名称"
    )
    shelter_type: str = Column(
        ShelterTypeEnum, 
        nullable=False,
        comment="安置点类型"
    )
    
    # ==================== 位置信息 ====================
    location = Column(
        Geometry('POINT', srid=4326),
        nullable=False,
        comment="安置点位置坐标"
    )
    boundary = Column(
        Geometry('POLYGON', srid=4326),
        comment="占地范围多边形"
    )
    address: Optional[str] = Column(
        Text,
        comment="详细地址"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        ShelterStatusEnum, 
        nullable=False, 
        default='preparing',
        comment="状态: preparing/open/full/limited/closed/damaged"
    )
    
    # ==================== 容量信息 ====================
    total_capacity: int = Column(
        Integer, 
        nullable=False,
        comment="总容量（人数）"
    )
    current_occupancy: int = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="当前入住人数"
    )
    # available_capacity是GENERATED列，数据库自动计算，不在ORM中定义为可写字段
    
    # ==================== 设施配置（JSONB） ====================
    facilities: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="设施配置: {medical, sanitation, food, water, power, communication}"
    )
    accessibility: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="无障碍设施: {wheelchair_accessible, sign_language, medical_equipment}"
    )
    special_accommodations: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="特殊人群容纳: {elderly_capacity, children_capacity, disabled_capacity, medical_patients}"
    )
    supply_inventory: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="物资储备: {water_bottles, food_packages, blankets, medicine_kits}"
    )
    
    # ==================== 联系人 ====================
    contact_person: Optional[str] = Column(
        String(100),
        comment="联系人姓名"
    )
    contact_phone: Optional[str] = Column(
        String(50),
        comment="联系电话"
    )
    contact_backup: Optional[str] = Column(
        String(50),
        comment="备用联系电话"
    )
    managing_organization: Optional[str] = Column(
        String(200),
        comment="管理单位"
    )
    
    # ==================== 时间信息 ====================
    opened_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="开放时间"
    )
    closed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="关闭时间"
    )
    
    # ==================== 关联 ====================
    entity_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联的地图实体ID"
    )
    
    # ==================== 备注 ====================
    notes: Optional[str] = Column(
        Text,
        comment="备注"
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
