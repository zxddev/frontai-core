"""
AI决策日志Pydantic模型

用于API请求/响应和数据验证
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAIDecisionLogRequest(BaseModel):
    """创建AI决策日志的请求模型"""
    
    scenario_id: UUID = Field(..., description="所属想定ID")
    event_id: Optional[UUID] = Field(None, description="关联事件ID")
    scheme_id: Optional[UUID] = Field(None, description="关联方案ID")
    decision_type: str = Field(..., description="决策类型")
    algorithm_used: Optional[str] = Field(None, description="使用的算法")
    input_snapshot: dict[str, Any] = Field(..., description="输入数据快照")
    output_result: dict[str, Any] = Field(..., description="输出结果")
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1, description="置信度")
    reasoning_chain: Optional[dict[str, Any]] = Field(None, description="推理链条")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="处理耗时(ms)")


class AIDecisionLogResponse(BaseModel):
    """AI决策日志响应模型"""
    
    id: UUID
    scenario_id: UUID
    event_id: Optional[UUID]
    scheme_id: Optional[UUID]
    decision_type: str
    algorithm_used: Optional[str]
    input_snapshot: dict[str, Any]
    output_result: dict[str, Any]
    confidence_score: Optional[Decimal]
    reasoning_chain: Optional[dict[str, Any]]
    processing_time_ms: Optional[int]
    is_accepted: Optional[bool]
    human_feedback: Optional[str]
    feedback_rating: Optional[int]
    created_at: datetime
    
    model_config = {"from_attributes": True}
