"""
指挥消息API路由

接口前缀: /messages
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import MessageService
from .schemas import (
    MessageCreate, MessageResponse, MessageListResponse,
    ReceiptResponse, UnreadCountResponse,
    MarkAsReadRequest, AcknowledgeRequest
)


router = APIRouter(prefix="/messages", tags=["messages"])


def get_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(db)


@router.post("", response_model=MessageResponse, status_code=201)
async def send_message(
    data: MessageCreate,
    service: MessageService = Depends(get_service),
) -> MessageResponse:
    """
    发送指挥消息
    
    支持向指定用户、角色、队伍或广播发送消息。
    可设置消息优先级和确认要求。
    """
    return await service.send(data)


@router.get("", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    sender_id: Optional[UUID] = Query(None, description="发送者ID"),
    message_type: Optional[str] = Query(None, description="消息类型: order/report/request/notification/alert/acknowledgment/inquiry/response"),
    priority: Optional[str] = Query(None, description="优先级: urgent/high/normal/low"),
    service: MessageService = Depends(get_service),
) -> MessageListResponse:
    """分页查询消息列表"""
    return await service.list(page, page_size, scenario_id, sender_id, message_type, priority)


@router.get("/received", response_model=MessageListResponse)
async def list_received_messages(
    user_id: UUID = Query(..., description="用户ID"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    unread_only: bool = Query(False, description="是否只返回未读消息"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: MessageService = Depends(get_service),
) -> MessageListResponse:
    """
    查询用户收到的消息
    
    支持按想定筛选，支持只返回未读消息。
    """
    return await service.list_received(user_id, scenario_id, unread_only, page, page_size)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user_id: UUID = Query(..., description="用户ID"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    service: MessageService = Depends(get_service),
) -> UnreadCountResponse:
    """
    获取用户未读消息统计
    
    返回未读总数、紧急消息数、待确认消息数。
    """
    return await service.get_unread_count(user_id, scenario_id)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    service: MessageService = Depends(get_service),
) -> MessageResponse:
    """根据ID获取消息详情（含接收记录）"""
    return await service.get_by_id(message_id)


@router.post("/{message_id}/read", response_model=ReceiptResponse)
async def mark_message_as_read(
    message_id: UUID,
    data: MarkAsReadRequest,
    service: MessageService = Depends(get_service),
) -> ReceiptResponse:
    """
    标记消息为已读
    
    用户阅读消息时调用，更新接收记录的read_at时间。
    """
    return await service.mark_as_read(message_id, data)


@router.post("/{message_id}/acknowledge", response_model=ReceiptResponse)
async def acknowledge_message(
    message_id: UUID,
    data: AcknowledgeRequest,
    service: MessageService = Depends(get_service),
) -> ReceiptResponse:
    """
    确认消息
    
    对于requires_acknowledgment=true的消息，接收者需要确认。
    可附带确认内容/回复。
    当所有接收者都确认后，消息状态变为acknowledged。
    """
    return await service.acknowledge(message_id, data)


@router.delete("/{message_id}", status_code=204)
async def delete_message(
    message_id: UUID,
    service: MessageService = Depends(get_service),
) -> None:
    """删除消息"""
    await service.delete(message_id)
