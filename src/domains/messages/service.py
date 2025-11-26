"""
指挥消息业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import MessageRepository
from .schemas import (
    MessageCreate, MessageResponse, MessageListResponse,
    ReceiptResponse, UnreadCountResponse,
    MarkAsReadRequest, AcknowledgeRequest
)

logger = logging.getLogger(__name__)


class MessageService:
    """指挥消息业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = MessageRepository(db)
    
    async def send(self, data: MessageCreate) -> MessageResponse:
        """
        发送消息
        
        业务规则:
        - 创建消息记录
        - 根据接收者类型创建接收记录
        - 当前简化实现：仅支持发送给单个用户
        """
        message = await self._repo.create(data)
        
        # 根据接收者类型创建接收记录
        if data.recipient_type.value == 'user' and data.recipient_id:
            await self._repo.create_receipt(
                message_id=message.id,
                recipient_id=data.recipient_id,
                recipient_name=None,
            )
        elif data.recipient_type.value == 'broadcast':
            # 广播消息：需要查询想定下所有用户并创建接收记录
            # 当前简化实现：仅记录消息，不自动创建接收记录
            logger.info(f"广播消息创建: id={message.id}, 需要手动处理接收者列表")
        
        # 重新加载以获取receipts
        message = await self._repo.get_by_id(message.id)
        return self._to_response(message)
    
    async def get_by_id(self, message_id: UUID) -> MessageResponse:
        """根据ID获取消息"""
        message = await self._repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("Message", str(message_id))
        return self._to_response(message)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        scenario_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        message_type: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> MessageListResponse:
        """分页查询消息列表"""
        items, total = await self._repo.list(
            page, page_size, scenario_id, sender_id, message_type, priority
        )
        return MessageListResponse(
            items=[self._to_response(m) for m in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_received(
        self,
        user_id: UUID,
        scenario_id: Optional[UUID] = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> MessageListResponse:
        """
        查询用户收到的消息
        
        Args:
            user_id: 用户ID
            scenario_id: 想定ID（可选）
            unread_only: 是否只返回未读消息
        """
        items, total = await self._repo.list_by_recipient(
            user_id, scenario_id, unread_only, page, page_size
        )
        return MessageListResponse(
            items=[self._to_response(m) for m in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def mark_as_read(
        self,
        message_id: UUID,
        data: MarkAsReadRequest,
    ) -> ReceiptResponse:
        """
        标记消息为已读
        
        业务规则:
        - 消息必须存在
        - 用户必须是消息接收者
        """
        message = await self._repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("Message", str(message_id))
        
        receipt = await self._repo.mark_as_read(message_id, data.user_id)
        if not receipt:
            raise NotFoundError("MessageReceipt", f"{message_id}/{data.user_id}")
        
        return self._receipt_to_response(receipt)
    
    async def acknowledge(
        self,
        message_id: UUID,
        data: AcknowledgeRequest,
    ) -> ReceiptResponse:
        """
        确认消息
        
        业务规则:
        - 消息必须存在
        - 消息必须设置了requires_acknowledgment
        - 用户必须是消息接收者
        """
        message = await self._repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("Message", str(message_id))
        
        if not message.requires_acknowledgment:
            raise ValidationError(
                message="此消息不需要确认",
                details={"message_id": str(message_id)}
            )
        
        receipt = await self._repo.acknowledge(message_id, data.user_id, data.content)
        if not receipt:
            raise NotFoundError("MessageReceipt", f"{message_id}/{data.user_id}")
        
        # 检查是否所有接收者都已确认，更新消息状态
        all_acknowledged = all(r.acknowledged_at for r in message.receipts)
        if all_acknowledged:
            await self._repo.update_message_status(message, 'acknowledged')
        
        return self._receipt_to_response(receipt)
    
    async def get_unread_count(
        self,
        user_id: UUID,
        scenario_id: Optional[UUID] = None,
    ) -> UnreadCountResponse:
        """获取用户未读消息统计"""
        stats = await self._repo.get_unread_count(user_id, scenario_id)
        return UnreadCountResponse(**stats)
    
    async def delete(self, message_id: UUID) -> None:
        """
        删除消息
        
        业务规则:
        - 仅发送者可删除自己的消息（当前简化：直接删除）
        """
        message = await self._repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("Message", str(message_id))
        
        await self._repo.delete(message)
    
    def _to_response(self, message) -> MessageResponse:
        """ORM模型转响应模型"""
        receipts = None
        if message.receipts:
            receipts = [self._receipt_to_response(r) for r in message.receipts]
        
        return MessageResponse(
            id=message.id,
            scenario_id=message.scenario_id,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            sender_role=message.sender_role,
            recipient_type=message.recipient_type,
            recipient_id=message.recipient_id,
            recipient_role=message.recipient_role,
            message_type=message.message_type,
            priority=message.priority,
            subject=message.subject,
            content=message.content,
            attachments=message.attachments or [],
            related_event_id=message.related_event_id,
            related_scheme_id=message.related_scheme_id,
            related_task_id=message.related_task_id,
            requires_acknowledgment=message.requires_acknowledgment or False,
            acknowledgment_deadline=message.acknowledgment_deadline,
            reply_to_message_id=message.reply_to_message_id,
            status=message.status,
            created_at=message.created_at,
            receipts=receipts,
        )
    
    def _receipt_to_response(self, receipt) -> ReceiptResponse:
        """接收记录ORM转响应模型"""
        return ReceiptResponse(
            id=receipt.id,
            message_id=receipt.message_id,
            recipient_id=receipt.recipient_id,
            recipient_name=receipt.recipient_name,
            delivered_at=receipt.delivered_at,
            read_at=receipt.read_at,
            acknowledged_at=receipt.acknowledged_at,
            acknowledgment_content=receipt.acknowledgment_content,
            created_at=receipt.created_at,
        )
