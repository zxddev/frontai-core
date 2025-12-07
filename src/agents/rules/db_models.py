"""
安全规则 ORM 模型

对应SQL表: config.safety_rules
参考: sql/migrations/v20251207_add_safety_rules_table.sql
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from src.core.database import Base


class SafetyRule(Base):
    """
    安全规则 ORM 模型
    
    对应数据库表: config.safety_rules
    
    规则类型:
    - reject: 硬性阻断，按钮置灰不可Override
    - break_glass: Break Glass，长按5秒确认，必须审计
    - warn: 软性提示，点击确认即可
    """
    __tablename__ = "safety_rules"
    __table_args__ = {"schema": "config"}
    
    # 主键
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # 规则标识
    rule_id: str = Column(String(32), unique=True, nullable=False, comment="规则ID，如HB_001, BG_003")
    rule_name: str = Column(String(128), nullable=False, comment="规则名称")
    rule_type: str = Column(String(16), nullable=False, comment="规则类型: reject/break_glass/warn")
    
    # 触发条件（可选前置条件）
    condition_field: Optional[str] = Column(String(64), nullable=True, comment="前置条件字段")
    condition_operator: Optional[str] = Column(String(16), nullable=True, comment="前置条件操作符")
    condition_value: Optional[Any] = Column(JSONB, nullable=True, comment="前置条件值")
    
    # 检查条件
    check_field: str = Column(String(64), nullable=False, comment="检查字段")
    check_operator: str = Column(String(16), nullable=False, comment="检查操作符")
    check_threshold: Optional[Any] = Column(JSONB, nullable=True, comment="固定阈值")
    check_threshold_field: Optional[str] = Column(String(64), nullable=True, comment="动态阈值字段名")
    
    # 提示信息
    message_template: str = Column(Text, nullable=False, comment="消息模板")
    risk_description: Optional[str] = Column(Text, nullable=True, comment="风险说明（Break Glass专用）")
    severity: str = Column(String(16), nullable=False, comment="严重程度: critical/high/medium/low")
    
    # 元数据
    is_active: bool = Column(Boolean, default=True, nullable=False, comment="是否启用")
    sort_order: int = Column(Integer, default=0, nullable=False, comment="排序顺序")
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<SafetyRule {self.rule_id}: {self.rule_name} ({self.rule_type})>"


class SafetyOverride(Base):
    """
    安全规则覆盖记录 ORM 模型（审计日志）
    对应数据库表: audit.safety_overrides
    """

    __tablename__ = "safety_overrides"
    __table_args__ = {"schema": "audit"}

    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    timestamp: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # 操作者信息
    operator_id: str = Column(String(64), nullable=False, comment="操作员ID")
    operator_name: str = Column(String(128), nullable=False, comment="操作员名称")
    operator_role: str = Column(String(32), nullable=False, comment="角色: commander/deputy/operator")
    auth_method: str = Column(String(32), nullable=False, comment="确认方式: long_press_5s/password/dual_confirm")

    # 规则信息
    rule_id: str = Column(String(32), nullable=False, comment="规则ID")
    rule_name: str = Column(String(128), nullable=False, comment="规则名称")
    risk_overridden: str = Column(Text, nullable=False, comment="被覆盖的风险描述")

    # 操作详情
    action_type: str = Column(String(64), nullable=False, comment="动作类型，如 deploy_team/start_mission")
    target_resource: Any = Column(JSONB, nullable=False, comment="被操作的资源")
    target_event: Any = Column(JSONB, nullable=True, comment="关联事件/任务")

    # AI 建议
    ai_recommendation: Any = Column(JSONB, nullable=True, comment="AI替代方案")
    was_adopted: bool = Column(Boolean, default=False, nullable=False, comment="是否采纳AI建议")

    # 环境快照与结果
    context: Any = Column(JSONB, nullable=False, comment="决策上下文")
    outcome: Any = Column(JSONB, nullable=True, comment="事后结果")
    outcome_recorded_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<SafetyOverride {self.rule_id} by {self.operator_name} at {self.timestamp}>"


class SensorCalibration(Base):
    """
    传感器校准记录 ORM 模型
    对应数据库表: audit.sensor_calibrations
    """

    __tablename__ = "sensor_calibrations"
    __table_args__ = {"schema": "audit"}

    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    timestamp: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # 操作员信息
    operator_id: str = Column(String(64), nullable=False, comment="操作员ID")
    operator_name: str = Column(String(128), nullable=False, comment="操作员名称")

    # 传感器信息
    device_id: str = Column(String(64), nullable=False, comment="设备ID")
    sensor_type: str = Column(String(32), nullable=False, comment="传感器类型: battery/weight/gps/signal等")

    # 校准值
    original_value: float = Column(String(32), nullable=False, comment="原始读数")
    calibrated_value: float = Column(String(32), nullable=False, comment="校准后读数")
    calibration_reason: str = Column(Text, nullable=False, comment="校准原因")
    requires_password: bool = Column(Boolean, default=True, nullable=False, comment="是否需要主指挥员密码")

    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<SensorCalibration {self.sensor_type} on {self.device_id} at {self.timestamp}>"
