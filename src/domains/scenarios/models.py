"""
想定ORM模型

对应SQL表: operational_v2.scenarios_v2
参考: sql/v2_rescue_resource_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import Column, String, Integer, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from geoalchemy2 import Geography

from src.core.database import Base


class Scenario(Base):
    """
    想定表 ORM 模型
    
    业务说明:
    - 想定是应急事件的顶层容器
    - 所有事件、方案、任务都关联到具体想定
    - 同一时间只能有一个active状态的想定
    """
    __tablename__ = "scenarios_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 基本信息 ====================
    name: str = Column(
        String(200), 
        nullable=False,
        comment="想定名称，如四川茂县6.8级地震想定"
    )
    scenario_type: str = Column(
        String(50), 
        nullable=False,
        comment="想定类型: earthquake/flood/fire/hazmat/landslide"
    )
    response_level: Optional[str] = Column(
        String(10),
        comment="响应等级: I/II/III/IV"
    )
    status: str = Column(
        String(20), 
        default='draft',
        comment="状态: draft/active/resolved/archived"
    )
    
    # ==================== 位置信息 ====================
    location = Column(
        Geography('POINT', srid=4326),
        comment="事发中心点地理坐标"
    )
    affected_area = Column(
        Geography('POLYGON', srid=4326),
        comment="影响范围多边形"
    )
    
    # ==================== 时间 ====================
    started_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="事件发生时间"
    )
    ended_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="事件结束时间"
    )
    
    # ==================== 想定参数 ====================
    parameters: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="想定参数: {magnitude震级, depth_km震源深度, rainfall_mm降雨量等}"
    )
    affected_population: Optional[int] = Column(
        Integer,
        comment="预估影响人口数量"
    )
    affected_area_km2: Optional[Decimal] = Column(
        Numeric(10, 2),
        comment="影响面积（平方公里）"
    )
    
    # ==================== 审计 ====================
    created_by: Optional[str] = Column(
        String(100),
        comment="创建人"
    )
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
