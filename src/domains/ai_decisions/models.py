"""
AI决策日志ORM模型

对应SQL表: operational_v2.ai_decision_logs_v2
参考: sql/v2_event_scheme_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from src.core.database import Base


class AIDecisionLog(Base):
    """
    AI决策日志表 ORM 模型
    
    记录所有AI决策过程，支持可追溯可解释。
    决策类型包括：event_analysis(事件分析)、resource_matching(资源匹配)、
    route_planning(路径规划)、scheme_generation(方案生成)等。
    """
    __tablename__ = "ai_decision_logs_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid_lib.uuid4,
        comment="主键"
    )
    
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="所属想定ID"
    )
    
    event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="关联事件ID"
    )
    
    scheme_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="关联方案ID"
    )
    
    decision_type: str = Column(
        String(100),
        nullable=False,
        comment="决策类型: event_analysis/resource_matching/route_planning/scheme_generation"
    )
    
    algorithm_used: Optional[str] = Column(
        String(200),
        nullable=True,
        comment="使用的算法，多个用逗号分隔"
    )
    
    input_snapshot: dict[str, Any] = Column(
        JSONB,
        nullable=False,
        comment="输入数据快照"
    )
    
    output_result: dict[str, Any] = Column(
        JSONB,
        nullable=False,
        comment="输出结果"
    )
    
    confidence_score: Optional[Decimal] = Column(
        Numeric(5, 4),
        nullable=True,
        comment="置信度评分 [0,1]"
    )
    
    reasoning_chain: Optional[dict[str, Any]] = Column(
        JSONB,
        nullable=True,
        comment="推理链条，用于可解释性"
    )
    
    processing_time_ms: Optional[int] = Column(
        Integer,
        nullable=True,
        comment="处理耗时（毫秒）"
    )
    
    is_accepted: Optional[bool] = Column(
        Boolean,
        nullable=True,
        comment="决策是否被采纳"
    )
    
    human_feedback: Optional[str] = Column(
        Text,
        nullable=True,
        comment="人工反馈内容"
    )
    
    feedback_rating: Optional[int] = Column(
        Integer,
        nullable=True,
        comment="反馈评分: -1=差, 0=中, 1=好"
    )
    
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )
