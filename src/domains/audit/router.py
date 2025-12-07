from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import AuditService
from .schemas import BreakGlassOverrideResponse


router = APIRouter(prefix="/api/audit", tags=["审计"])


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(db)


@router.get("/break-glass", response_model=List[BreakGlassOverrideResponse])
async def query_break_glass_logs(
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    operator_id: Optional[str] = Query(default=None),
    rule_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: AuditService = Depends(get_audit_service),
):
    """查询 Break Glass 审计日志。"""

    return await service.query_break_glass_logs(
        start_time=start_time,
        end_time=end_time,
        operator_id=operator_id,
        rule_id=rule_id,
        limit=limit,
    )
