"""
物资业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import SupplyRepository
from .schemas import (
    SupplyCreate, SupplyUpdate, SupplyResponse, 
    SupplyListResponse, SupplyCategory, SupplyUnit
)

logger = logging.getLogger(__name__)


class SupplyService:
    """物资业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = SupplyRepository(db)
    
    async def create(self, data: SupplyCreate) -> SupplyResponse:
        """
        创建物资
        
        业务规则:
        - code必须唯一
        - weight_kg必须大于0
        """
        if await self._repo.check_code_exists(data.code):
            raise ConflictError(
                error_code="SUPPLY_CODE_EXISTS",
                message=f"物资编号已存在: {data.code}"
            )
        
        supply = await self._repo.create(data)
        return self._to_response(supply)
    
    async def get_by_id(self, supply_id: UUID) -> SupplyResponse:
        """根据ID获取物资"""
        supply = await self._repo.get_by_id(supply_id)
        if not supply:
            raise NotFoundError("Supply", str(supply_id))
        return self._to_response(supply)
    
    async def get_by_code(self, code: str) -> SupplyResponse:
        """根据编号获取物资"""
        supply = await self._repo.get_by_code(code)
        if not supply:
            raise NotFoundError("Supply", code)
        return self._to_response(supply)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        is_consumable: Optional[bool] = None,
        disaster_type: Optional[str] = None,
    ) -> SupplyListResponse:
        """分页查询物资列表"""
        items, total = await self._repo.list(
            page, page_size, category, is_consumable, disaster_type
        )
        return SupplyListResponse(
            items=[self._to_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_by_category(self, category: str) -> list[SupplyResponse]:
        """按类别查询物资"""
        supplies = await self._repo.list_by_category(category)
        return [self._to_response(s) for s in supplies]
    
    async def list_required_for_disaster(self, disaster_type: str) -> list[SupplyResponse]:
        """
        查询指定灾害必须携带的物资
        
        Args:
            disaster_type: 灾害类型 (earthquake/flood/fire/hazmat/landslide)
        """
        supplies = await self._repo.list_required_for_disaster(disaster_type)
        return [self._to_response(s) for s in supplies]
    
    async def update(self, supply_id: UUID, data: SupplyUpdate) -> SupplyResponse:
        """更新物资"""
        supply = await self._repo.get_by_id(supply_id)
        if not supply:
            raise NotFoundError("Supply", str(supply_id))
        
        supply = await self._repo.update(supply, data)
        return self._to_response(supply)
    
    async def delete(self, supply_id: UUID) -> None:
        """
        删除物资
        
        业务规则:
        - 暂无额外限制，直接删除
        - 未来可能需要检查是否被车辆装载
        """
        supply = await self._repo.get_by_id(supply_id)
        if not supply:
            raise NotFoundError("Supply", str(supply_id))
        
        await self._repo.delete(supply)
    
    def _to_response(self, supply) -> SupplyResponse:
        """ORM模型转响应模型"""
        return SupplyResponse(
            id=supply.id,
            code=supply.code,
            name=supply.name,
            category=supply.category,
            weight_kg=supply.weight_kg,
            volume_m3=supply.volume_m3,
            unit=supply.unit or 'piece',
            applicable_disasters=supply.applicable_disasters or [],
            required_for_disasters=supply.required_for_disasters or [],
            is_consumable=supply.is_consumable if supply.is_consumable is not None else True,
            shelf_life_days=supply.shelf_life_days,
            properties=supply.properties or {},
            created_at=supply.created_at,
        )
