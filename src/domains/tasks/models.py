"""
任务ORM模型

对应SQL表: operational_v2.tasks_v2, operational_v2.task_assignments_v2
参考: sql/v2_add_tasks_table.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from typing import List

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from geoalchemy2 import Geometry

from src.core.database import Base


class Task(Base):
    """
    任务表 ORM 模型
    
    业务说明:
    - 任务是从方案(scheme)分解出的具体可执行单元
    - 关系: scenario → event → scheme → task → assignment
    - 通过 TaskAssignment 关联到执行者（队伍/车辆/设备）
    """
    __tablename__ = "tasks_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联关系 ====================
    scheme_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        nullable=True,
        comment="所属方案ID（可选，准备任务可能无关联方案）"
    )
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        comment="所属想定ID（冗余，便于查询）"
    )
    event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联事件ID（可选）"
    )
    parent_task_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("operational_v2.tasks_v2.id"),
        comment="父任务ID（支持子任务层级）"
    )
    
    # ==================== 任务标识 ====================
    task_code: str = Column(
        String(50), 
        nullable=False,
        comment="任务编号，格式：TSK-0001（场景内唯一）"
    )
    
    # ==================== 任务类型 ====================
    task_type: str = Column(
        String(50), 
        nullable=False,
        comment="任务类型: search/rescue/evacuation/transport/medical/supply/reconnaissance/communication/other"
    )
    
    # ==================== 基本信息 ====================
    title: str = Column(
        String(500), 
        nullable=False,
        comment="任务标题"
    )
    description: Optional[str] = Column(
        Text,
        comment="任务详细描述"
    )
    
    # ==================== 任务状态 ====================
    status: str = Column(
        String(50), 
        nullable=False, 
        default='created',
        comment="状态: created/assigned/accepted/in_progress/paused/completed/failed/cancelled"
    )
    
    # ==================== 优先级 ====================
    priority: str = Column(
        String(20), 
        nullable=False, 
        default='medium',
        comment="优先级: critical/high/medium/low"
    )
    
    # ==================== 目标位置 ====================
    target_location = Column(
        Geometry('POINT', srid=4326),
        comment="任务目标点位（WGS84坐标）"
    )
    target_address: Optional[str] = Column(
        Text,
        comment="目标地址描述"
    )
    
    # ==================== 时间计划 ====================
    planned_start_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="计划开始时间"
    )
    planned_end_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="计划结束时间"
    )
    actual_start_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="实际开始时间"
    )
    actual_end_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="实际结束时间"
    )
    estimated_duration_minutes: Optional[int] = Column(
        Integer,
        comment="预计执行时长（分钟）"
    )
    
    # ==================== 执行说明 ====================
    instructions: Optional[str] = Column(
        Text,
        comment="执行指令和注意事项"
    )
    
    # ==================== 任务需求 ====================
    requirements: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="任务需求: {min_personnel, required_capabilities[], required_equipment[], special_requirements}"
    )
    
    # ==================== 执行结果 ====================
    rescued_count: int = Column(
        Integer, 
        default=0,
        comment="救出人数（救援类任务统计）"
    )
    progress_percent: int = Column(
        Integer, 
        default=0,
        comment="执行进度（0-100%）"
    )
    
    # ==================== 审计字段 ====================
    created_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="创建人ID"
    )
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
    assignments: Mapped[List["TaskAssignment"]] = relationship(
        "TaskAssignment", 
        back_populates="task", 
        lazy="selectin"
    )


class TaskAssignment(Base):
    """
    任务分配表 ORM 模型
    
    业务说明:
    - 记录任务分配给具体执行者（队伍/车辆/设备/用户）
    - 支持AI分配和人工分配两种来源
    - 追踪分配状态：pending → accepted/rejected → in_progress → completed
    """
    __tablename__ = "task_assignments_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联 ====================
    task_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.tasks_v2.id", ondelete="CASCADE"), 
        nullable=False,
        comment="关联任务ID"
    )
    
    # ==================== 执行者信息 ====================
    assignee_type: str = Column(
        String(50), 
        nullable=False,
        comment="执行者类型: team/vehicle/device/user"
    )
    assignee_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        comment="执行者ID"
    )
    assignee_name: Optional[str] = Column(
        String(200),
        comment="执行者名称（冗余，便于显示）"
    )
    
    # ==================== 分配信息 ====================
    assignment_source: str = Column(
        String(50), 
        nullable=False, 
        default='human_assigned',
        comment="分配来源: ai_recommended/human_assigned"
    )
    assignment_reason: Optional[str] = Column(
        Text,
        comment="分配理由（AI推荐理由或人工说明）"
    )
    
    # ==================== 分配状态 ====================
    status: str = Column(
        String(50), 
        nullable=False, 
        default='pending',
        comment="状态: pending/accepted/rejected/in_progress/completed/cancelled"
    )
    rejection_reason: Optional[str] = Column(
        Text,
        comment="拒绝理由"
    )
    
    # ==================== 分配人 ====================
    assigned_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="分配人ID"
    )
    
    # ==================== 时间节点 ====================
    assigned_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        comment="分配时间"
    )
    notified_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="通知时间"
    )
    accepted_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="接受时间"
    )
    rejected_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="拒绝时间"
    )
    started_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="开始执行时间"
    )
    completed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="完成时间"
    )
    
    # ==================== 执行进度 ====================
    progress_percent: int = Column(
        Integer, 
        default=0,
        comment="执行进度（0-100%）"
    )
    execution_notes: Optional[str] = Column(
        Text,
        comment="执行备注"
    )
    completion_summary: Optional[str] = Column(
        Text,
        comment="完成总结"
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
    task: Mapped["Task"] = relationship(
        "Task", 
        back_populates="assignments"
    )
