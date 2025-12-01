"""
指挥消息数据模型（Pydantic Schemas）

对应SQL表: operational_v2.command_messages_v2, operational_v2.message_receipts_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MessageType(str, Enum):
    """消息类型枚举"""
    order = "order"                    # 命令
    report = "report"                  # 报告
    request = "request"                # 请求
    notification = "notification"      # 通知
    alert = "alert"                    # 警报
    acknowledgment = "acknowledgment"  # 确认
    inquiry = "inquiry"                # 询问
    response = "response"              # 回复


class MessagePriority(str, Enum):
    """消息优先级枚举"""
    urgent = "urgent"    # 紧急
    high = "high"        # 高
    normal = "normal"    # 普通
    low = "low"          # 低


class RecipientType(str, Enum):
    """接收者类型枚举"""
    broadcast = "broadcast"  # 广播(所有人)
    role = "role"            # 按角色
    user = "user"            # 指定用户
    team = "team"            # 指定队伍
    group = "group"          # 指定群组


class MessageStatus(str, Enum):
    """消息状态枚举"""
    draft = "draft"              # 草稿
    sent = "sent"                # 已发送
    delivered = "delivered"      # 已送达
    read = "read"                # 已读
    acknowledged = "acknowledged"  # 已确认
    expired = "expired"          # 已过期


class AttachmentInfo(BaseModel):
    """附件信息"""
    type: str = Field(..., description="附件类型: image/file/audio/video")
    url: str = Field(..., description="附件URL")
    name: str = Field(..., description="文件名")
    size: Optional[int] = Field(None, description="文件大小(字节)")


class MessageCreate(BaseModel):
    """创建消息请求"""
    scenario_id: UUID = Field(..., description="所属想定ID")
    
    # 发送者（通常从当前用户获取）
    sender_id: UUID = Field(..., description="发送者用户ID")
    sender_name: Optional[str] = Field(None, max_length=200, description="发送者姓名")
    sender_role: Optional[str] = Field(None, max_length=100, description="发送者角色")
    
    # 接收者
    recipient_type: RecipientType = Field(..., description="接收者类型")
    recipient_id: Optional[UUID] = Field(None, description="接收者ID")
    recipient_role: Optional[str] = Field(None, max_length=100, description="接收者角色")
    
    # 消息内容
    message_type: MessageType = Field(..., description="消息类型")
    priority: MessagePriority = Field(MessagePriority.normal, description="优先级")
    subject: Optional[str] = Field(None, max_length=500, description="主题")
    content: str = Field(..., description="消息内容")
    attachments: list[AttachmentInfo] = Field(default_factory=list, description="附件")
    
    # 关联业务对象
    related_event_id: Optional[UUID] = Field(None, description="关联事件ID")
    related_scheme_id: Optional[UUID] = Field(None, description="关联方案ID")
    related_task_id: Optional[UUID] = Field(None, description="关联任务ID")
    
    # 确认要求
    requires_acknowledgment: bool = Field(False, description="是否需要确认")
    acknowledgment_deadline: Optional[datetime] = Field(None, description="确认截止时间")
    
    # 回复
    reply_to_message_id: Optional[UUID] = Field(None, description="回复的消息ID")


class MessageResponse(BaseModel):
    """消息响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    scenario_id: UUID
    
    # 发送者
    sender_id: UUID
    sender_name: Optional[str]
    sender_role: Optional[str]
    
    # 接收者
    recipient_type: RecipientType
    recipient_id: Optional[UUID]
    recipient_role: Optional[str]
    
    # 消息内容
    message_type: MessageType
    priority: MessagePriority
    subject: Optional[str]
    content: str
    attachments: list[dict[str, Any]]
    
    # 关联
    related_event_id: Optional[UUID]
    related_scheme_id: Optional[UUID]
    related_task_id: Optional[UUID]
    
    # 确认
    requires_acknowledgment: bool
    acknowledgment_deadline: Optional[datetime]
    
    # 回复和状态
    reply_to_message_id: Optional[UUID]
    status: MessageStatus
    
    # 时间戳
    created_at: datetime
    
    # 接收记录（可选）
    receipts: Optional[list["ReceiptResponse"]] = None


class MessageListResponse(BaseModel):
    """消息列表响应"""
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class ReceiptResponse(BaseModel):
    """消息接收记录响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    message_id: UUID
    recipient_id: UUID
    recipient_name: Optional[str]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledgment_content: Optional[str]
    created_at: datetime


class MarkAsReadRequest(BaseModel):
    """标记已读请求"""
    user_id: UUID = Field(..., description="用户ID")


class AcknowledgeRequest(BaseModel):
    """确认消息请求"""
    user_id: UUID = Field(..., description="用户ID")
    content: Optional[str] = Field(None, description="确认内容/回复")


class UnreadCountResponse(BaseModel):
    """未读消息统计响应"""
    user_id: UUID
    unread_count: int
    urgent_count: int
    pending_ack_count: int
    latest_message_at: Optional[datetime]


# 用于relationship的前向引用
MessageResponse.model_rebuild()
