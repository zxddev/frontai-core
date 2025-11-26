"""
救援流程ORM模型

对应SQL表: 
- rescue_points_v2, rescue_point_team_assignments_v2, rescue_point_progress_v2
- evaluation_reports_v2
参考: sql/v2_rescue_points.sql, sql/v2_evaluation_reports.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from typing import List

from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Text, Numeric, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from geoalchemy2 import Geometry

from src.core.database import Base


class RescuePoint(Base):
    """
    救援点表 ORM 模型
    
    记录灾情现场需要救援的目标点位，包括被困人员位置、倒塌建筑等
    """
    __tablename__ = "rescue_points_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联 ====================
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        index=True,
        comment="所属想定ID"
    )
    event_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        index=True,
        comment="所属事件ID"
    )
    
    # ==================== 基本信息 ====================
    name: str = Column(
        String(200), 
        nullable=False,
        comment="救援点名称"
    )
    point_type: str = Column(
        String(50), 
        nullable=False,
        comment="类型: trapped_person/collapsed_building/fire/flood_area/hazmat_leak/landslide/vehicle_accident/medical_emergency/other"
    )
    priority: str = Column(
        String(20), 
        nullable=False, 
        default='medium',
        index=True,
        comment="优先级: low/medium/high/critical"
    )
    description: Optional[str] = Column(
        Text,
        comment="描述"
    )
    
    # ==================== 位置信息 ====================
    location = Column(
        Geometry('POINT', srid=4326), 
        nullable=False,
        comment="救援点位置"
    )
    address: Optional[str] = Column(
        String(500),
        comment="地址描述"
    )
    
    # ==================== 人员统计 ====================
    estimated_victims: int = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="预估被困人数"
    )
    rescued_count: int = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="已救出人数"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        String(20), 
        nullable=False, 
        default='pending',
        index=True,
        comment="状态: pending/in_progress/completed/cancelled"
    )
    
    # ==================== AI检测相关 ====================
    detection_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="AI检测ID（如果由AI检测创建）"
    )
    detection_confidence: Optional[Decimal] = Column(
        Numeric(3, 2),
        comment="检测置信度 [0,1]"
    )
    detection_source: str = Column(
        String(20), 
        nullable=False, 
        default='manual',
        comment="检测来源: manual/uav_image/sensor/ai_analysis"
    )
    source_image_url: Optional[str] = Column(
        Text,
        comment="来源图像URL"
    )
    
    # ==================== 上报者 ====================
    reported_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="上报人ID"
    )
    
    # ==================== 备注 ====================
    notes: Optional[str] = Column(
        Text,
        comment="备注"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # ==================== 关系 ====================
    team_assignments: Mapped[List["RescuePointTeamAssignment"]] = relationship(
        "RescuePointTeamAssignment",
        back_populates="rescue_point",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    progress_records: Mapped[List["RescuePointProgress"]] = relationship(
        "RescuePointProgress",
        back_populates="rescue_point",
        lazy="noload",
        cascade="all, delete-orphan"
    )


class RescuePointTeamAssignment(Base):
    """
    救援点队伍指派表
    
    记录哪些队伍被指派到哪些救援点（多对多关系）
    """
    __tablename__ = "rescue_point_team_assignments_v2"
    
    # ==================== 复合主键 ====================
    rescue_point_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rescue_points_v2.id", ondelete="CASCADE"),
        primary_key=True
    )
    team_id: UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        index=True
    )
    
    # ==================== 指派信息 ====================
    assigned_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    assigned_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="指派人ID"
    )
    notes: Optional[str] = Column(
        Text,
        comment="备注"
    )
    
    # ==================== 关系 ====================
    rescue_point: Mapped["RescuePoint"] = relationship(
        "RescuePoint",
        back_populates="team_assignments"
    )


class RescuePointProgress(Base):
    """
    救援点进度记录表
    
    追踪救援点状态和进度变更历史
    """
    __tablename__ = "rescue_point_progress_v2"
    
    # ==================== 主键 ====================
    id: int = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True
    )
    
    # ==================== 关联 ====================
    rescue_point_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("rescue_points_v2.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # ==================== 进度记录 ====================
    progress_type: str = Column(
        String(50), 
        nullable=False,
        comment="进度类型: status_change/victim_rescued/team_arrived/resource_request"
    )
    previous_value: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="变更前的值"
    )
    new_value: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="变更后的值"
    )
    
    # ==================== 操作者 ====================
    recorded_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="记录人ID"
    )
    
    # ==================== 时间戳 ====================
    recorded_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        index=True
    )
    
    # ==================== 关系 ====================
    rescue_point: Mapped["RescuePoint"] = relationship(
        "RescuePoint",
        back_populates="progress_records"
    )


class EvaluationReport(Base):
    """
    评估报告表 ORM 模型
    
    存储救援行动评估报告（AI生成或人工编写）
    一个事件只有一份最终报告
    """
    __tablename__ = "evaluation_reports_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联 ====================
    event_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        unique=True,
        index=True,
        comment="所属事件ID（唯一）"
    )
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        index=True,
        comment="所属想定ID"
    )
    
    # ==================== 报告内容 ====================
    report_data: dict[str, Any] = Column(
        JSONB, 
        nullable=False,
        comment="完整报告内容（JSON）"
    )
    
    # ==================== 元信息 ====================
    generated_by: str = Column(
        String(50), 
        nullable=False, 
        default='ai_generated',
        comment="生成来源: ai_generated/manual"
    )
    generated_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True,
        comment="报告生成时间"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
