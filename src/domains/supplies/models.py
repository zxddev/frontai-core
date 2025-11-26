"""
物资ORM模型

对应SQL表: operational_v2.supplies_v2
参考: sql/v2_vehicle_device_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Numeric, ARRAY, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from src.core.database import Base


class Supply(Base):
    """
    物资表 ORM 模型
    
    业务说明:
    - 物资是救援行动中使用的消耗品或装备
    - 通过vehicle_supply_loads_v2关联到车辆
    - category字段标识物资类别（医疗/防护/救援等）
    """
    __tablename__ = "supplies_v2"
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
        comment="物资编号，如SP-MED-001"
    )
    name: str = Column(
        String(200), 
        nullable=False,
        comment="物资名称"
    )
    category: str = Column(
        String(50), 
        nullable=False,
        comment="物资类别: medical/protection/rescue/communication/life/tool"
    )
    
    # ==================== 物理属性 ====================
    weight_kg: Decimal = Column(
        Numeric(10, 2), 
        nullable=False,
        comment="单件重量（公斤）"
    )
    volume_m3: Optional[Decimal] = Column(
        Numeric(10, 4),
        comment="单件体积（立方米）"
    )
    unit: str = Column(
        String(20), 
        default='piece',
        comment="计量单位: piece件/box箱/kg公斤/set套"
    )
    
    # ==================== 灾害适用性 ====================
    applicable_disasters: Optional[list[str]] = Column(
        ARRAY(Text),
        comment="适用灾害类型数组"
    )
    required_for_disasters: Optional[list[str]] = Column(
        ARRAY(Text),
        comment="某些灾害必须携带此物资"
    )
    
    # ==================== 消耗属性 ====================
    is_consumable: bool = Column(
        Boolean, 
        default=True,
        comment="是否消耗品"
    )
    shelf_life_days: Optional[int] = Column(
        Integer,
        comment="保质期（天）"
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
