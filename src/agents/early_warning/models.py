"""
预警监测数据模型（SQLAlchemy Models）

对应SQL表:
- operational_v2.disaster_situations
- operational_v2.warning_records
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, 
    ForeignKey, Numeric, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from geoalchemy2 import Geometry

from src.core.database import Base


class DisasterSituation(Base):
    """灾害态势表"""
    __tablename__ = "disaster_situations"
    __table_args__ = {"schema": "operational_v2"}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id = Column(PGUUID(as_uuid=True), nullable=True, comment="关联想定ID")
    disaster_type = Column(String(50), nullable=False)
    disaster_name = Column(String(200), nullable=True)
    boundary = Column(Geometry("POLYGON", srid=4326), nullable=True)
    center_point = Column(Geometry("POINT", srid=4326), nullable=True)
    buffer_distance_m = Column(Integer, default=3000)
    spread_direction = Column(String(20), nullable=True)
    spread_speed_mps = Column(Numeric(10, 2), nullable=True)
    severity_level = Column(Integer, default=3)
    status = Column(String(20), default="active")
    source = Column(String(100), nullable=True)
    source_update_time = Column(DateTime, nullable=True)
    properties = Column(JSON, default=dict)
    
    # 新增：关联字段
    needs_response = Column(Boolean, default=True, comment="是否需要救援响应（false=仅预警）")
    linked_event_id = Column(PGUUID(as_uuid=True), nullable=True, comment="关联事件ID")
    map_entity_id = Column(PGUUID(as_uuid=True), nullable=True, comment="关联地图实体ID")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarningRecord(Base):
    """预警记录表"""
    __tablename__ = "warning_records"
    __table_args__ = {"schema": "operational_v2"}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    disaster_id = Column(PGUUID(as_uuid=True), ForeignKey("operational_v2.disaster_situations.id"), nullable=True)
    scenario_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # 受影响对象
    affected_type = Column(String(20), nullable=False)  # vehicle/team
    affected_id = Column(PGUUID(as_uuid=True), nullable=False)
    affected_name = Column(String(200), nullable=True)
    affected_location = Column(Geometry("POINT", srid=4326), nullable=True)
    
    # 通知目标
    notify_target_type = Column(String(20), nullable=False)  # commander/team_leader
    notify_target_id = Column(PGUUID(as_uuid=True), nullable=True)
    notify_target_name = Column(String(100), nullable=True)
    
    # 预警信息
    warning_level = Column(String(10), nullable=False, default="yellow")
    distance_m = Column(Numeric(10, 2), nullable=True)
    estimated_contact_minutes = Column(Integer, nullable=True)
    route_affected = Column(Boolean, default=False)
    route_intersection_point = Column(Geometry("POINT", srid=4326), nullable=True)
    
    # 预警内容
    warning_title = Column(String(200), nullable=True)
    warning_message = Column(Text, nullable=True)
    
    # 状态跟踪
    status = Column(String(20), default="pending")
    response_action = Column(String(20), nullable=True)
    response_reason = Column(Text, nullable=True)
    selected_route_id = Column(String(100), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # 扩展
    properties = Column(JSON, default=dict)
