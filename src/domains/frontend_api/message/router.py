"""
前端消息API路由

接口路径: /message/*
对接前端消息通知模块
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.messages.service import MessageService
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    FrontendMessage,
    MessagePayload,
    MessageListRequest,
    MessageAckRequest,
    priority_to_prompt_level,
    message_type_to_module,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/message", tags=["前端-消息通知"])


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    """获取消息服务实例"""
    return MessageService(db)


@router.post("/message-list", response_model=ApiResponse[list[FrontendMessage]])
async def get_message_list(
    request: MessageListRequest,
    service: MessageService = Depends(get_message_service),
) -> ApiResponse[list[FrontendMessage]]:
    """
    获取消息通知列表
    
    将v2 CommandMessage转换为前端期望的消息格式
    """
    logger.info(f"获取用户消息列表, userId={request.userId}")
    
    try:
        user_id = UUID(request.userId)
    except ValueError:
        logger.warning(f"无效的用户ID格式: {request.userId}")
        return ApiResponse.error(400, f"无效的用户ID格式: {request.userId}")
    
    try:
        result = await service.list_received(
            user_id=user_id,
            scenario_id=None,
            unread_only=False,
            page=1,
            page_size=100,
        )
        
        frontend_messages: list[FrontendMessage] = []
        for msg in result.items:
            extra = {
                "module": message_type_to_module(msg.message_type, msg.related_event_id),
            }
            if msg.related_event_id:
                extra["eventId"] = str(msg.related_event_id)
            if msg.related_task_id:
                extra["taskId"] = str(msg.related_task_id)
            if msg.related_scheme_id:
                extra["schemeId"] = str(msg.related_scheme_id)
            
            payload = MessagePayload(
                title=msg.subject or "系统通知",
                content=msg.content,
                promptLevel=priority_to_prompt_level(msg.priority),
                messageId=str(msg.id),
                extra=extra,
            )
            
            is_acked = False
            if msg.receipts:
                for receipt in msg.receipts:
                    if receipt.recipient_id == user_id and receipt.acknowledged_at:
                        is_acked = True
                        break
            
            frontend_msg = FrontendMessage(
                payload=payload,
                timestamp=msg.created_at.isoformat(),
                acked=is_acked,
            )
            frontend_messages.append(frontend_msg)
        
        logger.info(f"返回消息列表, 数量={len(frontend_messages)}")
        return ApiResponse.success(frontend_messages)
        
    except Exception as e:
        logger.exception(f"获取消息列表失败: {e}")
        return ApiResponse.error(500, f"获取消息列表失败: {str(e)}")


@router.post("/message-ack", response_model=ApiResponse)
async def ack_message(
    request: MessageAckRequest,
    service: MessageService = Depends(get_message_service),
) -> ApiResponse:
    """
    消息确认
    
    标记消息为已确认状态
    """
    logger.info(f"消息确认, messageId={request.messageId}, userId={request.userId}")
    
    try:
        message_id = UUID(request.messageId)
    except ValueError:
        logger.warning(f"无效的消息ID格式: {request.messageId}")
        return ApiResponse.error(400, f"无效的消息ID格式: {request.messageId}")
    
    user_id: Optional[UUID] = None
    if request.userId:
        try:
            user_id = UUID(request.userId)
        except ValueError:
            logger.warning(f"无效的用户ID格式: {request.userId}")
            return ApiResponse.error(400, f"无效的用户ID格式: {request.userId}")
    
    try:
        if user_id:
            from src.domains.messages.schemas import AcknowledgeRequest
            ack_data = AcknowledgeRequest(user_id=user_id, content="已确认")
            await service.acknowledge(message_id, ack_data)
        
        logger.info(f"消息确认成功, messageId={request.messageId}")
        return ApiResponse.success(None, "消息确认成功")
        
    except Exception as e:
        logger.exception(f"消息确认失败: {e}")
        return ApiResponse.error(500, f"消息确认失败: {str(e)}")
