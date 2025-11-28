"""
风险区域业务逻辑层
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import RiskAreaRepository
from .schemas import (
    RiskAreaCreateRequest,
    RiskAreaUpdateRequest,
    PassageStatusUpdateRequest,
    RiskAreaResponse,
    RiskAreaListResponse,
)


logger = logging.getLogger(__name__)


class RiskAreaService:
    """风险区域服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = RiskAreaRepository(db)

    async def create(self, request: RiskAreaCreateRequest) -> RiskAreaResponse:
        """创建风险区域"""
        data = await self.repo.create(request)
        return RiskAreaResponse(**data)

    async def get_by_id(self, area_id: UUID) -> Optional[RiskAreaResponse]:
        """根据ID获取风险区域"""
        data = await self.repo.get_by_id(area_id)
        if not data:
            return None
        return RiskAreaResponse(**data)

    async def list_by_scenario(
        self,
        scenario_id: UUID,
        area_type: Optional[str] = None,
        min_risk_level: Optional[int] = None,
        passage_status: Optional[str] = None,
    ) -> RiskAreaListResponse:
        """获取想定下的风险区域列表"""
        items = await self.repo.list_by_scenario(
            scenario_id=scenario_id,
            area_type=area_type,
            min_risk_level=min_risk_level,
            passage_status=passage_status,
        )
        return RiskAreaListResponse(
            items=[RiskAreaResponse(**item) for item in items],
            total=len(items),
        )

    async def update(
        self,
        area_id: UUID,
        request: RiskAreaUpdateRequest,
    ) -> Optional[RiskAreaResponse]:
        """更新风险区域"""
        data = await self.repo.update(area_id, request)
        if not data:
            return None
        return RiskAreaResponse(**data)

    async def update_passage_status(
        self,
        area_id: UUID,
        request: PassageStatusUpdateRequest,
    ) -> Optional[RiskAreaResponse]:
        """更新通行状态"""
        data = await self.repo.update_passage_status(area_id, request)
        if not data:
            return None
        return RiskAreaResponse(**data)

    async def delete(self, area_id: UUID) -> bool:
        """删除风险区域"""
        return await self.repo.delete(area_id)
