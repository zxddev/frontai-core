from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.rules.db_models import SafetyOverride

logger = logging.getLogger(__name__)


class AuditRepository:
    """审计日志仓储，仅允许追加与结果更新。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, record: SafetyOverride) -> SafetyOverride:
        self._db.add(record)
        await self._db.flush()
        logger.info("审计记录创建", extra={"rule_id": record.rule_id, "operator": record.operator_id})
        return record

    async def update_outcome(self, override_id: UUID, outcome: dict[str, Any]) -> None:
        stmt = (
            update(SafetyOverride)
            .where(SafetyOverride.id == override_id)
            .values(outcome=outcome, outcome_recorded_at=datetime.utcnow())
        )
        await self._db.execute(stmt)
        await self._db.flush()
        logger.info("审计记录结果已更新", extra={"override_id": str(override_id)})

    async def query(
        self,
        *,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operator_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[SafetyOverride]:
        stmt = select(SafetyOverride).order_by(SafetyOverride.timestamp.desc()).limit(limit)

        if start_time:
            stmt = stmt.where(SafetyOverride.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(SafetyOverride.timestamp <= end_time)
        if operator_id:
            stmt = stmt.where(SafetyOverride.operator_id == operator_id)
        if rule_id:
            stmt = stmt.where(SafetyOverride.rule_id == rule_id)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())
