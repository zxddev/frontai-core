"""
指挥消息数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import CommandMessage, MessageReceipt
from .schemas import MessageCreate

logger = logging.getLogger(__name__)


class MessageRepository:
    """指挥消息数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: MessageCreate) -> CommandMessage:
        """创建消息"""
        message = CommandMessage(
            scenario_id=data.scenario_id,
            sender_id=data.sender_id,
            sender_name=data.sender_name,
            sender_role=data.sender_role,
            recipient_type=data.recipient_type.value,
            recipient_id=data.recipient_id,
            recipient_role=data.recipient_role,
            message_type=data.message_type.value,
            priority=data.priority.value,
            subject=data.subject,
            content=data.content,
            attachments=[a.model_dump() for a in data.attachments] if data.attachments else [],
            related_event_id=data.related_event_id,
            related_scheme_id=data.related_scheme_id,
            related_task_id=data.related_task_id,
            requires_acknowledgment=data.requires_acknowledgment,
            acknowledgment_deadline=data.acknowledgment_deadline,
            reply_to_message_id=data.reply_to_message_id,
            status='sent',
        )
        self._db.add(message)
        await self._db.flush()
        await self._db.refresh(message)
        
        logger.info(
            f"创建消息: id={message.id}, type={message.message_type}, "
            f"priority={message.priority}, recipient_type={message.recipient_type}"
        )
        return message
    
    async def create_receipt(
        self,
        message_id: UUID,
        recipient_id: UUID,
        recipient_name: Optional[str] = None,
    ) -> MessageReceipt:
        """创建消息接收记录"""
        receipt = MessageReceipt(
            message_id=message_id,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            delivered_at=datetime.now(timezone.utc),
        )
        self._db.add(receipt)
        await self._db.flush()
        await self._db.refresh(receipt)
        
        logger.info(f"创建消息接收记录: message_id={message_id}, recipient_id={recipient_id}")
        return receipt
    
    async def get_by_id(self, message_id: UUID) -> Optional[CommandMessage]:
        """根据ID查询消息（含接收记录）"""
        result = await self._db.execute(
            select(CommandMessage)
            .options(selectinload(CommandMessage.receipts))
            .where(CommandMessage.id == message_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        scenario_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        message_type: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> tuple[Sequence[CommandMessage], int]:
        """
        分页查询消息列表
        
        Returns:
            (消息列表, 总数)
        """
        query = select(CommandMessage)
        count_query = select(func.count(CommandMessage.id))
        
        if scenario_id:
            query = query.where(CommandMessage.scenario_id == scenario_id)
            count_query = count_query.where(CommandMessage.scenario_id == scenario_id)
        
        if sender_id:
            query = query.where(CommandMessage.sender_id == sender_id)
            count_query = count_query.where(CommandMessage.sender_id == sender_id)
        
        if message_type:
            query = query.where(CommandMessage.message_type == message_type)
            count_query = count_query.where(CommandMessage.message_type == message_type)
        
        if priority:
            query = query.where(CommandMessage.priority == priority)
            count_query = count_query.where(CommandMessage.priority == priority)
        
        query = query.order_by(CommandMessage.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_by_recipient(
        self,
        recipient_id: UUID,
        scenario_id: Optional[UUID] = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[CommandMessage], int]:
        """查询用户收到的消息"""
        base_query = (
            select(CommandMessage)
            .join(MessageReceipt, MessageReceipt.message_id == CommandMessage.id)
            .where(MessageReceipt.recipient_id == recipient_id)
        )
        count_base = (
            select(func.count(CommandMessage.id))
            .join(MessageReceipt, MessageReceipt.message_id == CommandMessage.id)
            .where(MessageReceipt.recipient_id == recipient_id)
        )
        
        if scenario_id:
            base_query = base_query.where(CommandMessage.scenario_id == scenario_id)
            count_base = count_base.where(CommandMessage.scenario_id == scenario_id)
        
        if unread_only:
            base_query = base_query.where(MessageReceipt.read_at.is_(None))
            count_base = count_base.where(MessageReceipt.read_at.is_(None))
        
        query = base_query.order_by(CommandMessage.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_base)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def get_receipt(
        self,
        message_id: UUID,
        recipient_id: UUID,
    ) -> Optional[MessageReceipt]:
        """获取消息接收记录"""
        result = await self._db.execute(
            select(MessageReceipt)
            .where(MessageReceipt.message_id == message_id)
            .where(MessageReceipt.recipient_id == recipient_id)
        )
        return result.scalar_one_or_none()
    
    async def mark_as_read(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> Optional[MessageReceipt]:
        """标记消息为已读"""
        receipt = await self.get_receipt(message_id, user_id)
        if receipt and not receipt.read_at:
            receipt.read_at = datetime.now(timezone.utc)
            await self._db.flush()
            await self._db.refresh(receipt)
            logger.info(f"消息标记为已读: message_id={message_id}, user_id={user_id}")
        return receipt
    
    async def acknowledge(
        self,
        message_id: UUID,
        user_id: UUID,
        content: Optional[str] = None,
    ) -> Optional[MessageReceipt]:
        """确认消息"""
        receipt = await self.get_receipt(message_id, user_id)
        if receipt and not receipt.acknowledged_at:
            now = datetime.now(timezone.utc)
            receipt.acknowledged_at = now
            receipt.acknowledgment_content = content
            if not receipt.read_at:
                receipt.read_at = now
            await self._db.flush()
            await self._db.refresh(receipt)
            logger.info(f"消息已确认: message_id={message_id}, user_id={user_id}")
        return receipt
    
    async def update_message_status(self, message: CommandMessage, status: str) -> CommandMessage:
        """更新消息状态"""
        old_status = message.status
        message.status = status
        await self._db.flush()
        await self._db.refresh(message)
        logger.info(f"消息状态变更: id={message.id}, {old_status} -> {status}")
        return message
    
    async def get_unread_count(self, user_id: UUID, scenario_id: Optional[UUID] = None) -> dict:
        """获取用户未读消息统计"""
        sql = text("""
            SELECT 
                COUNT(*) as unread_count,
                COUNT(*) FILTER (WHERE cm.priority = 'urgent') as urgent_count,
                COUNT(*) FILTER (WHERE cm.requires_acknowledgment AND mr.acknowledged_at IS NULL) as pending_ack_count,
                MAX(cm.created_at) as latest_message_at
            FROM message_receipts_v2 mr
            JOIN command_messages_v2 cm ON cm.id = mr.message_id
            WHERE mr.recipient_id = :user_id
              AND mr.read_at IS NULL
              AND (:scenario_id IS NULL OR cm.scenario_id = :scenario_id)
        """)
        
        result = await self._db.execute(
            sql,
            {"user_id": user_id, "scenario_id": scenario_id}
        )
        row = result.fetchone()
        
        return {
            "user_id": user_id,
            "unread_count": row.unread_count or 0,
            "urgent_count": row.urgent_count or 0,
            "pending_ack_count": row.pending_ack_count or 0,
            "latest_message_at": row.latest_message_at,
        }
    
    async def delete(self, message: CommandMessage) -> None:
        """删除消息"""
        message_id = message.id
        await self._db.delete(message)
        await self._db.flush()
        logger.info(f"删除消息: id={message_id}")
