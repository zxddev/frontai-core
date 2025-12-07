from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.rules.db_models import SafetyOverride
from .repository import AuditRepository
from .schemas import (
    ActionInfo,
    BreakGlassOverride,
    BreakGlassOverrideCreate,
    BreakGlassOverrideResponse,
    OperatorInfo,
    OutcomeInfo,
)

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AuditRepository(db)

    async def record_break_glass(
        self,
        *,
        operator: OperatorInfo,
        rule_id: str,
        rule_name: str,
        risk_overridden: str,
        action: ActionInfo,
        ai_recommendation: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        was_adopted: bool = False,
    ) -> BreakGlassOverride:
        record = SafetyOverride(
            operator_id=operator.operator_id,
            operator_name=operator.operator_name,
            operator_role=operator.operator_role,
            auth_method=operator.auth_method,
            rule_id=rule_id,
            rule_name=rule_name,
            risk_overridden=risk_overridden,
            action_type=action.action_type,
            target_resource=action.target_resource,
            target_event=action.target_event,
            ai_recommendation=ai_recommendation,
            was_adopted=was_adopted,
            context=context,
        )

        record = await self._repo.create(record)
        await self._db.commit()

        return BreakGlassOverride(
            id=record.id,
            timestamp=record.timestamp,
            operator_id=record.operator_id,
            operator_name=record.operator_name,
            operator_role=record.operator_role,
            auth_method=record.auth_method,
            rule_id=record.rule_id,
            rule_name=record.rule_name,
            risk_overridden=record.risk_overridden,
            action_type=record.action_type,
            target_resource=record.target_resource,
            target_event=record.target_event,
            ai_recommendation=record.ai_recommendation,
            was_adopted=record.was_adopted,
            context=record.context,
            outcome=record.outcome,
            outcome_recorded_at=record.outcome_recorded_at,
            created_at=record.created_at,
        )

    async def update_outcome(self, override_id: UUID, outcome: OutcomeInfo) -> None:
        await self._repo.update_outcome(override_id, outcome.model_dump())
        await self._db.commit()

    async def query_break_glass_logs(
        self,
        *,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operator_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[BreakGlassOverrideResponse]:
        rows = await self._repo.query(
            start_time=start_time,
            end_time=end_time,
            operator_id=operator_id,
            rule_id=rule_id,
            limit=limit,
        )

        return [
            BreakGlassOverrideResponse(
                id=row.id,
                timestamp=row.timestamp,
                operator_id=row.operator_id,
                operator_name=row.operator_name,
                operator_role=row.operator_role,
                rule_id=row.rule_id,
                rule_name=row.rule_name,
                risk_overridden=row.risk_overridden,
                action_type=row.action_type,
                target_resource=row.target_resource,
                target_event=row.target_event,
                ai_recommendation=row.ai_recommendation,
                was_adopted=row.was_adopted,
                context=row.context,
                outcome=row.outcome,
                outcome_recorded_at=row.outcome_recorded_at,
                created_at=row.created_at,
            )
            for row in rows
        ]
