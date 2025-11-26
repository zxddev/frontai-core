"""
指挥消息ORM模型

对应SQL表: public.command_messages_v2, public.message_receipts_v2
参考: sql/v2_conversation_message_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.core.database import Base


# 消息类型枚举 - 对应 public.command_message_type_v2
CommandMessageTypeEnum = ENUM(
    'order',           # 命令
    'report',          # 报告
    'request',         # 请求
    'notification',    # 通知
    'alert',           # 警报
    'acknowledgment',  # 确认
    'inquiry',         # 询问
    'response',        # 回复
    name='command_message_type_v2',
    create_type=False,
)


# 消息优先级枚举 - 对应 public.message_priority_v2
MessagePriorityEnum = ENUM(
    'urgent',      # 紧急
    'high',        # 高
    'normal',      # 普通
    'low',         # 低
    name='message_priority_v2',
    create_type=False,
)


# 接收者类型枚举 - 对应 public.recipient_type_v2
RecipientTypeEnum = ENUM(
    'broadcast',   # 广播(所有人)
    'role',        # 按角色
    'user',        # 指定用户
    'team',        # 指定队伍
    'group',       # 指定群组
    name='recipient_type_v2',
    create_type=False,
)


class CommandMessage(Base):
    """
    指挥消息表 ORM 模型
    
    业务说明:
    - 用于指挥员与队伍/人员之间的通信
    - 支持命令、报告、通知、警报等消息类型
    - 可设置确认要求和截止时间
    """
    __tablename__ = "command_messages_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联想定 ====================
    scenario_id: UUID = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="所属想定ID"
    )
    
    # ==================== 发送者信息 ====================
    sender_id: UUID = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="发送者用户ID"
    )
    sender_name: Optional[str] = Column(
        String(200),
        comment="发送者姓名"
    )
    sender_role: Optional[str] = Column(
        String(100),
        comment="发送者席位角色"
    )
    
    # ==================== 接收者信息 ====================
    recipient_type: str = Column(
        RecipientTypeEnum,
        nullable=False,
        comment="接收者类型: broadcast/role/user/team/group"
    )
    recipient_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="接收者ID（根据类型不同含义不同）"
    )
    recipient_role: Optional[str] = Column(
        String(100),
        comment="接收者角色（按角色发送时使用）"
    )
    
    # ==================== 消息内容 ====================
    message_type: str = Column(
        CommandMessageTypeEnum,
        nullable=False,
        comment="消息类型: order/report/request/notification/alert/acknowledgment/inquiry/response"
    )
    priority: str = Column(
        MessagePriorityEnum,
        nullable=False,
        default='normal',
        comment="优先级: urgent/high/normal/low"
    )
    subject: Optional[str] = Column(
        String(500),
        comment="消息主题"
    )
    content: str = Column(
        Text,
        nullable=False,
        comment="消息内容"
    )
    attachments: list[dict[str, Any]] = Column(
        JSONB,
        default=[],
        comment="附件列表: [{type, url, name, size}]"
    )
    
    # ==================== 关联业务对象 ====================
    related_event_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联事件ID"
    )
    related_scheme_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联方案ID"
    )
    related_task_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        comment="关联任务ID"
    )
    
    # ==================== 确认要求 ====================
    requires_acknowledgment: bool = Column(
        Boolean,
        default=False,
        comment="是否需要确认"
    )
    acknowledgment_deadline: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="确认截止时间"
    )
    
    # ==================== 回复 ====================
    reply_to_message_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("command_messages_v2.id"),
        comment="回复的消息ID"
    )
    
    # ==================== 状态 ====================
    status: str = Column(
        String(50),
        nullable=False,
        default='sent',
        comment="状态: draft/sent/delivered/read/acknowledged/expired"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow,
        nullable=False
    )
    
    # ==================== 关系 ====================
    receipts: Mapped[list["MessageReceipt"]] = relationship(
        "MessageReceipt",
        back_populates="message",
        lazy="selectin"
    )


class MessageReceipt(Base):
    """
    消息接收记录表 ORM 模型
    
    业务说明:
    - 跟踪消息的送达、阅读、确认状态
    - 每个接收者对应一条记录
    """
    __tablename__ = "message_receipts_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid_lib.uuid4
    )
    
    # ==================== 关联消息 ====================
    message_id: UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("command_messages_v2.id", ondelete="CASCADE"),
        nullable=False,
        comment="消息ID"
    )
    
    # ==================== 接收者信息 ====================
    recipient_id: UUID = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="接收者用户ID"
    )
    recipient_name: Optional[str] = Column(
        String(200),
        comment="接收者姓名"
    )
    
    # ==================== 状态时间 ====================
    delivered_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="送达时间"
    )
    read_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="阅读时间"
    )
    acknowledged_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="确认时间"
    )
    acknowledgment_content: Optional[str] = Column(
        Text,
        comment="确认内容/回复"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow,
        nullable=False
    )
    
    # ==================== 关系 ====================
    message: Mapped["CommandMessage"] = relationship(
        "CommandMessage",
        back_populates="receipts"
    )
