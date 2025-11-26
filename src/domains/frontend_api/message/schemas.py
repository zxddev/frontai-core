"""
前端消息模块数据结构

对应前端期望的消息格式，与v2 CommandMessage做映射转换
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessagePayload(BaseModel):
    """消息内容体"""
    title: str = Field(..., description="消息标题")
    content: str = Field(..., description="消息内容")
    promptLevel: int = Field(
        default=3,
        ge=1,
        le=4,
        description="提示级别: 1-红色(紧急) 2-橙色(重要) 3-蓝色(一般) 4-黑色(普通)"
    )
    messageId: str = Field(..., description="消息ID")
    extra: dict[str, Any] = Field(default_factory=dict, description="扩展信息")


class FrontendMessage(BaseModel):
    """前端消息结构"""
    payload: MessagePayload = Field(..., description="消息内容体")
    timestamp: str = Field(..., description="消息时间戳(ISO8601)")
    acked: bool = Field(default=False, description="是否已确认")


class MessageListRequest(BaseModel):
    """消息列表请求"""
    userId: str = Field(..., description="用户ID")


class MessageAckRequest(BaseModel):
    """消息确认请求"""
    messageId: str = Field(..., description="消息ID")
    userId: Optional[str] = Field(None, description="用户ID")


def priority_to_prompt_level(priority: str) -> int:
    """
    将v2优先级转换为前端promptLevel
    
    v2: urgent/high/normal/low
    前端: 1(紧急)/2(重要)/3(一般)/4(普通)
    """
    mapping = {
        "urgent": 1,
        "high": 2,
        "normal": 3,
        "low": 4,
    }
    return mapping.get(priority, 3)


def message_type_to_module(message_type: str, related_event_id: Optional[UUID] = None) -> str:
    """
    将v2消息类型转换为前端module标识
    
    用于前端根据module执行不同业务逻辑
    """
    if message_type == "alert" and related_event_id:
        return "event"
    if message_type == "notification":
        return "1-2"
    return message_type
