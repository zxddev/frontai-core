"""
仿真推演ORM模型

对应SQL表:
- simulation_scenarios_v2 - 仿真场景元数据
- drill_assessments_v2 - 演练评估

架构说明:
- 仿真使用真实数据表 + 事务快照还原
- 仿真开始时创建 SAVEPOINT，结束后 ROLLBACK
- 事件注入直接调用真实的 EventService
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Numeric, Text,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM

from src.core.database import Base


# 仿真状态枚举
SimulationStatusEnum = ENUM(
    'ready',
    'running',
    'paused',
    'completed',
    'stopped',
    name='simulation_status_v2',
    schema='public',
    create_type=False,
)

# 仿真来源类型枚举
SimulationSourceEnum = ENUM(
    'new',
    'from_history',
    name='simulation_source_type_v2',
    schema='public',
    create_type=False,
)


class SimulationScenario(Base):
    """
    仿真场景表 ORM 模型
    
    业务说明:
    - 仿真场景关联到一个想定(scenario)
    - 支持基于历史想定复制创建
    - 支持时间倍率调整
    """
    __tablename__ = "simulation_scenarios_v2"
    __table_args__ = {"schema": "public"}
    
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
        comment="场景名称"
    )
    description: Optional[str] = Column(
        Text,
        comment="描述"
    )
    
    # ==================== 关联想定 ====================
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.scenarios_v2.id"),
        nullable=False,
        comment="关联想定ID"
    )
    
    # ==================== 来源信息 ====================
    source_type: str = Column(
        SimulationSourceEnum,
        nullable=False,
        default='new',
        comment="来源类型: new/from_history"
    )
    source_scenario_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="历史想定ID（复制来源）"
    )
    
    # ==================== 时间控制 ====================
    time_scale: Decimal = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.0"),
        comment="时间倍率 0.5-10.0"
    )
    start_simulation_time: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="仿真起始时间（仿真世界中的时间）"
    )
    current_simulation_time: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="当前仿真时间"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        SimulationStatusEnum,
        nullable=False,
        default='ready',
        comment="状态: ready/running/paused/completed/stopped"
    )
    
    # ==================== 参与人员 ====================
    participants: dict[str, Any] = Column(
        JSONB,
        default=[],
        comment="参与人员JSON数组"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    started_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="实际开始时间（真实世界）"
    )
    paused_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="暂停时间"
    )
    completed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="完成时间"
    )
    
    # ==================== 累计暂停时长 ====================
    total_pause_duration_s: float = Column(
        Numeric(10, 2),
        default=0,
        comment="累计暂停时长（秒）"
    )
    
    # ==================== 事务快照名称 ====================
    # 用于仿真结束后还原数据库状态
    savepoint_name: Optional[str] = Column(
        String(100),
        comment="数据库SAVEPOINT名称，用于还原"
    )


class InjectedEvent(Base):
    """
    注入事件表 ORM 模型
    
    业务说明:
    - 仿真中的事件注入记录
    - 支持定时注入和立即注入
    """
    __tablename__ = "injected_events_v2"
    __table_args__ = {"schema": "public"}
    
    id: UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid_lib.uuid4
    )
    simulation_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.simulation_scenarios_v2.id", ondelete="CASCADE"),
        nullable=False
    )
    event_type: str = Column(String(50), nullable=False)
    event_data: dict[str, Any] = Column(JSONB, default={})
    inject_time: Optional[datetime] = Column(DateTime(timezone=True))
    status: str = Column(String(20), default='pending')
    injected_at: Optional[datetime] = Column(DateTime(timezone=True))
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)


class DrillAssessment(Base):
    """
    演练评估表 ORM 模型
    
    业务说明:
    - 仿真结束后生成的评估报告
    - 包含各维度得分和改进建议
    """
    __tablename__ = "drill_assessments_v2"
    __table_args__ = {"schema": "public"}
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联仿真场景 ====================
    simulation_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.simulation_scenarios_v2.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="仿真场景ID（一对一）"
    )
    
    # ==================== 总分 ====================
    overall_score: Decimal = Column(
        Numeric(5, 2),
        nullable=False,
        comment="总分 0-100"
    )
    
    # ==================== 各项得分 ====================
    response_time_score: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="响应时间得分"
    )
    decision_score: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="决策得分"
    )
    coordination_score: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="协调得分"
    )
    resource_utilization_score: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="资源利用得分"
    )
    
    # ==================== 详细评估 ====================
    details: dict[str, Any] = Column(
        JSONB,
        default={},
        comment="详细评估JSON，包含时间线分析和改进建议"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
