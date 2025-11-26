"""
AI决策日志数据库操作

提供AI决策日志的CRUD操作
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AIDecisionLog
from .schemas import CreateAIDecisionLogRequest

logger = logging.getLogger(__name__)


class AIDecisionLogRepository:
    """AI决策日志仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    
    async def create(self, data: CreateAIDecisionLogRequest) -> AIDecisionLog:
        """
        创建AI决策日志
        
        Args:
            data: 日志数据
            
        Returns:
            创建的日志记录
        """
        log_entry = AIDecisionLog(
            scenario_id=data.scenario_id,
            event_id=data.event_id,
            scheme_id=data.scheme_id,
            decision_type=data.decision_type,
            algorithm_used=data.algorithm_used,
            input_snapshot=data.input_snapshot,
            output_result=data.output_result,
            confidence_score=data.confidence_score,
            reasoning_chain=data.reasoning_chain,
            processing_time_ms=data.processing_time_ms,
        )
        
        self.db.add(log_entry)
        await self.db.flush()
        await self.db.refresh(log_entry)
        
        logger.info(
            "AI决策日志已创建",
            extra={
                "log_id": str(log_entry.id),
                "scenario_id": str(data.scenario_id),
                "event_id": str(data.event_id) if data.event_id else None,
                "decision_type": data.decision_type,
            }
        )
        
        return log_entry
    
    async def get_by_id(self, log_id: UUID) -> Optional[AIDecisionLog]:
        """
        根据ID获取日志
        
        Args:
            log_id: 日志ID
            
        Returns:
            日志记录或None
        """
        result = await self.db.execute(
            select(AIDecisionLog).where(AIDecisionLog.id == log_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_event_id(self, event_id: UUID) -> list[AIDecisionLog]:
        """
        获取事件关联的所有决策日志
        
        Args:
            event_id: 事件ID
            
        Returns:
            日志列表
        """
        result = await self.db.execute(
            select(AIDecisionLog)
            .where(AIDecisionLog.event_id == event_id)
            .order_by(AIDecisionLog.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update_feedback(
        self,
        log_id: UUID,
        is_accepted: Optional[bool] = None,
        human_feedback: Optional[str] = None,
        feedback_rating: Optional[int] = None,
    ) -> Optional[AIDecisionLog]:
        """
        更新人工反馈
        
        Args:
            log_id: 日志ID
            is_accepted: 是否采纳
            human_feedback: 反馈内容
            feedback_rating: 评分
            
        Returns:
            更新后的日志或None
        """
        log_entry = await self.get_by_id(log_id)
        if not log_entry:
            return None
        
        if is_accepted is not None:
            log_entry.is_accepted = is_accepted
        if human_feedback is not None:
            log_entry.human_feedback = human_feedback
        if feedback_rating is not None:
            log_entry.feedback_rating = feedback_rating
        
        await self.db.flush()
        await self.db.refresh(log_entry)
        
        logger.info(
            "AI决策日志反馈已更新",
            extra={
                "log_id": str(log_id),
                "is_accepted": is_accepted,
                "feedback_rating": feedback_rating,
            }
        )
        
        return log_entry
