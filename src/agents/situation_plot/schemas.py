"""
态势标绘Agent API Schema

定义对话式标绘接口的请求/响应模型。
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SituationPlotRequest(BaseModel):
    """对话式标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    message: str = Field(..., min_length=1, max_length=1000, description="用户指令")
    conversation_id: Optional[str] = Field(None, description="会话ID(用于多轮对话)")


class SituationPlotResponse(BaseModel):
    """对话式标绘响应"""
    success: bool = Field(..., description="是否成功")
    response: str = Field(..., description="AI回复内容")
    entity_id: Optional[str] = Field(None, description="创建的实体ID(如有)")
