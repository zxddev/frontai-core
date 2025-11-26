"""
方案ORM模型

对应SQL表: operational_v2.schemes_v2, operational_v2.scheme_resource_allocations_v2
参考: sql/v2_event_scheme_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, TYPE_CHECKING
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped

from src.core.database import Base


class Scheme(Base):
    """
    方案表 ORM 模型
    
    业务说明:
    - 方案是针对事件的响应计划
    - 支持AI生成、人工编制、模板等多种来源
    - 通过ResourceAllocation关联具体资源
    """
    __tablename__ = "schemes_v2"
    __table_args__ = {"schema": "operational_v2"}
    
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
        comment="关联事件ID"
    )
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        comment="所属想定ID（冗余，便于查询）"
    )
    
    # ==================== 方案基本信息 ====================
    scheme_code: str = Column(
        String(50), 
        nullable=False,
        comment="方案编号，场景内唯一"
    )
    scheme_type: str = Column(
        String(50), 
        nullable=False,
        comment="方案类型: search_rescue/evacuation/supply_delivery/medical/etc"
    )
    source: str = Column(
        String(50), 
        nullable=False, 
        default='human_created',
        comment="来源: ai_generated/human_created/template_based/hybrid"
    )
    
    # ==================== 内容 ====================
    title: str = Column(
        String(500), 
        nullable=False,
        comment="方案名称"
    )
    objective: str = Column(
        Text, 
        nullable=False,
        comment="方案目标"
    )
    description: Optional[str] = Column(
        Text,
        comment="方案详细描述"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        String(50), 
        nullable=False, 
        default='draft',
        comment="状态: draft/pending_review/approved/executing/completed/cancelled/superseded"
    )
    
    # ==================== 约束与评估 ====================
    constraints: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="约束条件: {time_limit, resource_limit, terrain_constraints, weather_constraints}"
    )
    risk_assessment: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="风险评估: {risk_level, risk_factors[], mitigation_measures[]}"
    )
    
    # ==================== 时间计划 ====================
    planned_start_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="预计开始时间"
    )
    planned_end_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="预计结束时间"
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
        comment="预估持续时间（分钟）"
    )
    
    # ==================== 版本控制 ====================
    version: int = Column(
        Integer, 
        nullable=False, 
        default=1,
        comment="版本号"
    )
    previous_version_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.schemes_v2.id"),
        comment="上一版本ID"
    )
    supersedes_scheme_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.schemes_v2.id"),
        comment="被替代的方案ID"
    )
    
    # ==================== AI相关 ====================
    ai_input_snapshot: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="AI生成时的输入快照"
    )
    ai_confidence_score: Optional[Decimal] = Column(
        Numeric(5, 4),
        comment="AI生成时的置信度"
    )
    ai_reasoning: Optional[str] = Column(
        Text,
        comment="AI推理说明"
    )
    
    # ==================== 审批流程 ====================
    created_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="创建人ID"
    )
    reviewed_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="审核人ID"
    )
    approved_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="批准人ID"
    )
    review_comment: Optional[str] = Column(
        Text,
        comment="审批意见"
    )
    
    # ==================== 时间戳 ====================
    submitted_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="提交时间"
    )
    reviewed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="审核时间"
    )
    approved_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="批准时间"
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
    allocations: Mapped[List["ResourceAllocation"]] = relationship(
        "ResourceAllocation", 
        back_populates="scheme", 
        lazy="selectin"
    )


class ResourceAllocation(Base):
    """
    方案资源分配表 ORM 模型
    
    业务说明:
    - 记录方案分配的具体资源
    - 核心功能：记录AI推荐理由和人工修改
    - 支持推荐排名和备选资源
    """
    __tablename__ = "scheme_resource_allocations_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联 ====================
    scheme_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.schemes_v2.id", ondelete="CASCADE"), 
        nullable=False,
        comment="关联方案ID"
    )
    
    # ==================== 资源信息 ====================
    resource_type: str = Column(
        String(50), 
        nullable=False,
        comment="资源类型: team/vehicle/device/equipment/supply"
    )
    resource_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        comment="资源ID"
    )
    resource_name: Optional[str] = Column(
        String(200),
        comment="资源名称（冗余，便于展示）"
    )
    
    # ==================== 分配状态 ====================
    status: str = Column(
        String(50), 
        nullable=False, 
        default='proposed',
        comment="状态: proposed/confirmed/modified/rejected/executing/completed"
    )
    assigned_role: Optional[str] = Column(
        String(200),
        comment="在方案中承担的角色"
    )
    
    # ==================== AI推荐理由（核心字段） ====================
    match_score: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="综合匹配得分 (0-100)"
    )
    capability_match_reason: Optional[str] = Column(
        Text,
        comment="能力匹配说明"
    )
    distance_reason: Optional[str] = Column(
        Text,
        comment="距离因素说明"
    )
    availability_reason: Optional[str] = Column(
        Text,
        comment="可用性说明"
    )
    equipment_reason: Optional[str] = Column(
        Text,
        comment="装备适配说明"
    )
    experience_reason: Optional[str] = Column(
        Text,
        comment="历史表现说明"
    )
    full_recommendation_reason: Optional[str] = Column(
        Text,
        comment="完整推荐理由（综合）"
    )
    recommendation_rank: Optional[int] = Column(
        Integer,
        comment="推荐排名"
    )
    
    # ==================== 人工修改 ====================
    is_human_modified: bool = Column(
        Boolean, 
        default=False,
        comment="是否经过人工修改"
    )
    human_modification_reason: Optional[str] = Column(
        Text,
        comment="人工修改理由"
    )
    modified_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="修改人ID"
    )
    modified_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="修改时间"
    )
    
    # ==================== 替换与备选 ====================
    original_resource_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="原始资源ID（人工替换时记录）"
    )
    alternative_resources: list[dict[str, Any]] = Column(
        JSONB, 
        default=[],
        comment="备选资源列表: [{resource_id, match_score, reason}]"
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
    scheme: Mapped["Scheme"] = relationship(
        "Scheme", 
        back_populates="allocations"
    )
