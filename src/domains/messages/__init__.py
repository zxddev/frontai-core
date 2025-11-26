"""
指挥消息管理模块

对应SQL表: public.command_messages_v2, public.message_receipts_v2
"""

from .router import router
from .service import MessageService
from .schemas import (
    MessageCreate, MessageResponse, MessageListResponse,
    MessageType, MessagePriority, RecipientType, MessageStatus,
    ReceiptResponse, UnreadCountResponse,
    MarkAsReadRequest, AcknowledgeRequest
)

__all__ = [
    "router",
    "MessageService",
    "MessageCreate",
    "MessageResponse",
    "MessageListResponse",
    "MessageType",
    "MessagePriority",
    "RecipientType",
    "MessageStatus",
    "ReceiptResponse",
    "UnreadCountResponse",
    "MarkAsReadRequest",
    "AcknowledgeRequest",
]
