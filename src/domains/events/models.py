"""
事件ORM模型

对应SQL表: operational_v2.events_v2, operational_v2.event_updates_v2
参考: sql/v2_event_scheme_model.sql

ENUM类型说明:
- 使用 PostgreSQL 原生 ENUM 类型，强约束数据有效性
- create_type=False 表示类型已在数据库中存在（由迁移脚本创建）
- 所有ENUM类型定义在 operational_v2 schema 下
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geometry

from src.core.database import Base


# ============================================================================
# ENUM 类型定义 - 对应 operational_v2 schema 中的枚举类型
# ============================================================================

# 事件类型枚举
EventTypeEnum = ENUM(
    'earthquake',          # 地震（主震）
    'trapped_person',      # 被困人员
    'fire',                # 火灾
    'flood',               # 洪水
    'landslide',           # 滑坡
    'building_collapse',   # 建筑倒塌
    'road_damage',         # 道路损毁
    'power_outage',        # 电力中断
    'communication_lost',  # 通信中断
    'hazmat_leak',         # 危化品泄漏
    'epidemic',            # 疫情
    'earthquake_secondary',# 地震次生灾害
    'other',               # 其他
    name='event_type_v2',
    schema='operational_v2',
    create_type=False,     # 类型已存在，不重复创建
)

# 事件来源类型枚举
EventSourceTypeEnum = ENUM(
    'manual_report',       # 人工上报
    'ai_detection',        # AI识别(无人机图像等)
    'sensor_alert',        # 传感器告警
    'system_inference',    # 系统推演
    'external_system',     # 外部系统接入
    name='event_source_type_v2',
    schema='operational_v2',
    create_type=False,
)

# 事件状态枚举
EventStatusEnum = ENUM(
    'pending',             # 待确认 (AI评分<0.6)
    'pre_confirmed',       # 预确认 (0.6≤AI评分<0.85)
    'confirmed',           # 已确认 (AI评分≥0.85自动确认 或 人工确认)
    'planning',            # 方案制定中
    'executing',           # 执行中
    'resolved',            # 已解决
    'escalated',           # 已升级
    'cancelled',           # 已取消(误报等)
    name='event_status_v2',
    schema='operational_v2',
    create_type=False,
)

# 事件优先级枚举
EventPriorityEnum = ENUM(
    'critical',            # 紧急(人命关天)
    'high',                # 高
    'medium',              # 中
    'low',                 # 低
    name='event_priority_v2',
    schema='operational_v2',
    create_type=False,
)


class Event(Base):
    """
    事件表 ORM 模型
    
    业务说明:
    - 事件是救援行动的触发点
    - 支持多种来源：手动上报、传感器、AI检测、第三方系统
    - 使用pre_confirmed状态实现30分钟自动确认倒计时
    - 所有状态字段使用PostgreSQL ENUM类型强约束
    """
    __tablename__ = "events_v2"
    __table_args__ = {"schema": "operational_v2"}
    
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
        comment="所属想定ID"
    )
    event_code: str = Column(
        String(50), 
        nullable=False,
        comment="事件编号，场景内唯一"
    )
    
    # ==================== 事件分类（使用ENUM强约束）====================
    event_type: str = Column(
        EventTypeEnum, 
        nullable=False,
        comment="事件类型枚举"
    )
    source_type: str = Column(
        EventSourceTypeEnum, 
        nullable=False, 
        default='manual_report',
        comment="来源类型枚举"
    )
    source_detail: dict[str, Any] = Column(
        JSONB, 
        default={},
        comment="来源详情（报警人信息/传感器ID/AI模型等）"
    )
    
    # ==================== 事件内容 ====================
    title: str = Column(
        String(500), 
        nullable=False,
        comment="事件名称/标题"
    )
    description: Optional[str] = Column(
        Text,
        comment="事件描述"
    )
    
    # ==================== 位置信息 ====================
    location = Column(
        Geometry('POINT', srid=4326), 
        nullable=False,
        comment="事件位置（精确点位）"
    )
    affected_area = Column(
        Geometry('POLYGON', srid=4326),
        comment="影响范围（面状区域）"
    )
    address: Optional[str] = Column(
        Text,
        comment="地址描述"
    )
    
    # ==================== 状态与优先级（使用ENUM强约束）====================
    status: str = Column(
        EventStatusEnum, 
        nullable=False, 
        default='pending',
        comment="事件状态枚举"
    )
    priority: str = Column(
        EventPriorityEnum, 
        nullable=False, 
        default='medium',
        comment="优先级枚举"
    )
    
    # ==================== 人员统计 ====================
    estimated_victims: int = Column(
        Integer, 
        default=0,
        comment="预估受困人数"
    )
    rescued_count: int = Column(
        Integer, 
        default=0,
        comment="已救出人数"
    )
    casualty_count: int = Column(
        Integer, 
        default=0,
        comment="伤亡人数"
    )
    
    # ==================== 时效性 ====================
    is_time_critical: bool = Column(
        Boolean, 
        default=False,
        comment="是否有黄金救援时间限制"
    )
    golden_hour_deadline: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="黄金时间截止"
    )
    
    # ==================== 事件关联 ====================
    parent_event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.events_v2.id"),
        comment="父事件ID（次生灾害关联）"
    )
    merged_into_event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.events_v2.id"),
        comment="合并到的事件ID（重复上报合并）"
    )
    entity_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联的地图实体ID"
    )
    
    # ==================== 附件与媒体 ====================
    media_attachments: list[dict[str, Any]] = Column(
        JSONB, 
        default=[],
        comment="媒体附件: [{type, url, thumbnail_url, description}]"
    )
    
    # ==================== 人员操作 ====================
    reported_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="上报人ID"
    )
    confirmed_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="确认人ID"
    )
    resolved_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="解决人ID"
    )
    
    # ==================== 自动确认机制 ====================
    auto_confirmed: bool = Column(
        Boolean, 
        default=False,
        comment="是否自动确认（超时或高置信度）"
    )
    pre_confirm_expires_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="预确认过期时间（30分钟倒计时）"
    )
    pre_allocated_resources: list[dict[str, Any]] = Column(
        JSONB, 
        default=[],
        comment="预分配资源（pre_confirmed时）"
    )
    pre_generated_scheme_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="预生成方案ID（pre_confirmed时）"
    )
    
    # ==================== AI评分与规则 ====================
    confirmation_score: Optional[Decimal] = Column(
        Numeric(5, 4),
        comment="AI确认评分 [0,1]，≥0.85自动确认"
    )
    matched_auto_confirm_rules: list[str] = Column(
        ARRAY(String),
        comment="匹配的自动确认规则"
    )
    
    # ==================== 主事件标识 ====================
    is_main_event: bool = Column(
        Boolean,
        default=False,
        comment="是否为想定主事件（每个想定只有一个，想定激活时自动创建）"
    )
    
    # ==================== 时间戳 ====================
    reported_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        comment="上报时间"
    )
    confirmed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="确认时间"
    )
    pre_confirmed_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="预确认时间"
    )
    resolved_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="解决时间"
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


class EventUpdate(Base):
    """
    事件更新日志表 ORM 模型
    
    记录事件的每次状态变更和字段更新
    """
    __tablename__ = "event_updates_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    event_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.events_v2.id", ondelete="CASCADE"), 
        nullable=False
    )
    update_type: str = Column(
        String(50), 
        nullable=False,
        comment="更新类型: status_change/info_update/victim_update/etc"
    )
    previous_value: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="更新前的值"
    )
    new_value: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="更新后的值"
    )
    description: Optional[str] = Column(
        Text,
        comment="变更说明"
    )
    source_type: str = Column(
        String(50), 
        nullable=False, 
        default='manual_report',
        comment="来源类型"
    )
    updated_by: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="操作人ID"
    )
    created_at: datetime = Column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
