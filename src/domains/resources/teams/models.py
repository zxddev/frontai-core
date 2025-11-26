"""
救援队伍ORM模型

对应SQL表: operational_v2.rescue_teams_v2
参考: sql/v2_rescue_resource_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, DateTime, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geography

from src.core.database import Base


# 队伍类型枚举 - 对应 operational_v2.team_type_v2
TeamTypeEnum = ENUM(
    'fire_rescue',       # 消防救援队
    'medical',           # 医疗救护队
    'search_rescue',     # 搜救队
    'hazmat',            # 危化品处置队
    'engineering',       # 工程抢险队
    'communication',     # 通信保障队
    'logistics',         # 后勤保障队
    'evacuation',        # 疏散转移队
    'water_rescue',      # 水上救援队
    'mountain_rescue',   # 山地救援队
    'mine_rescue',       # 矿山救护队
    'armed_police',      # 武警部队
    'militia',           # 民兵预备役
    'volunteer',         # 志愿者队伍
    name='team_type_v2',
    schema='operational_v2',
    create_type=False,
)


class Team(Base):
    """
    救援队伍表 ORM 模型
    
    业务说明:
    - 队伍是静态资源池，不属于特定场景
    - 通过 scheme_resource_allocations_v2 分配到具体方案
    - base_location 使用 GEOGRAPHY 类型（球面计算）
    """
    __tablename__ = "rescue_teams_v2"
    __table_args__ = (
        CheckConstraint('capability_level >= 1 AND capability_level <= 5', name='chk_capability_level'),
        {"schema": "operational_v2"},
    )
    
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
        comment="队伍编号，如RT-FR-001"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="队伍名称"
    )
    team_type: str = Column(
        TeamTypeEnum, 
        nullable=False,
        comment="队伍类型枚举"
    )
    
    # ==================== 组织信息 ====================
    parent_org: Optional[str] = Column(
        String(200),
        comment="上级单位名称"
    )
    contact_person: Optional[str] = Column(
        String(100),
        comment="联系人姓名"
    )
    contact_phone: Optional[str] = Column(
        String(20),
        comment="联系电话"
    )
    
    # ==================== 位置信息 ====================
    base_location = Column(
        Geography('POINT', srid=4326),
        comment="驻地地理坐标"
    )
    base_address: Optional[str] = Column(
        String(300),
        comment="驻地详细地址"
    )
    jurisdiction_area = Column(
        Geography('POLYGON', srid=4326),
        comment="管辖区域多边形"
    )
    
    # ==================== 人员配置 ====================
    total_personnel: int = Column(
        Integer, 
        default=0,
        comment="队伍总人数"
    )
    available_personnel: int = Column(
        Integer, 
        default=0,
        comment="当前可用人数"
    )
    
    # ==================== 能力等级 ====================
    capability_level: int = Column(
        Integer, 
        default=3,
        comment="能力等级1-5，5为最高（国家级）"
    )
    certification_level: Optional[str] = Column(
        String(50),
        comment="资质等级，如一级消防站"
    )
    
    # ==================== 响应能力 ====================
    response_time_minutes: Optional[int] = Column(
        Integer,
        comment="平均响应时间（分钟）"
    )
    max_deployment_hours: int = Column(
        Integer, 
        default=72,
        comment="最大连续部署时长（小时）"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        String(20), 
        default='standby',
        comment="状态: standby/deployed/resting/unavailable"
    )
    current_task_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="当前执行的任务ID"
    )
    
    # ==================== 扩展属性 ====================
    properties: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="扩展属性JSON"
    )
    
    # ==================== 实时位置（GPS遥测更新） ====================
    current_location = Column(
        Geography('POINT', srid=4326),
        comment="队伍当前位置（由GPS遥测数据写入）"
    )
    last_location_update: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="位置最后更新时间"
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
