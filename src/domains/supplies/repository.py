"""
物资数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Supply
from .schemas import SupplyCreate, SupplyUpdate

logger = logging.getLogger(__name__)


class SupplyRepository:
    """物资数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: SupplyCreate) -> Supply:
        """创建物资"""
        supply = Supply(
            code=data.code,
            name=data.name,
            category=data.category.value,
            weight_kg=data.weight_kg,
            volume_m3=data.volume_m3,
            unit=data.unit.value,
            applicable_disasters=data.applicable_disasters,
            required_for_disasters=data.required_for_disasters,
            is_consumable=data.is_consumable,
            shelf_life_days=data.shelf_life_days,
            properties=data.properties,
        )
        self._db.add(supply)
        await self._db.flush()
        await self._db.refresh(supply)
        
        logger.info(f"创建物资: code={supply.code}, id={supply.id}, category={supply.category}")
        return supply
    
    async def get_by_id(self, supply_id: UUID) -> Optional[Supply]:
        """根据ID查询物资"""
        result = await self._db.execute(
            select(Supply).where(Supply.id == supply_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Supply]:
        """根据编号查询物资"""
        result = await self._db.execute(
            select(Supply).where(Supply.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        is_consumable: Optional[bool] = None,
        disaster_type: Optional[str] = None,
    ) -> tuple[Sequence[Supply], int]:
        """
        分页查询物资列表
        
        Args:
            page: 页码
            page_size: 每页数量
            category: 类别筛选
            is_consumable: 是否消耗品筛选
            disaster_type: 适用灾害类型筛选
            
        Returns:
            (物资列表, 总数)
        """
        query = select(Supply)
        count_query = select(func.count(Supply.id))
        
        if category:
            query = query.where(Supply.category == category)
            count_query = count_query.where(Supply.category == category)
        
        if is_consumable is not None:
            query = query.where(Supply.is_consumable == is_consumable)
            count_query = count_query.where(Supply.is_consumable == is_consumable)
        
        # 灾害类型筛选：检查数组是否包含指定灾害
        if disaster_type:
            query = query.where(Supply.applicable_disasters.any(disaster_type))
            count_query = count_query.where(Supply.applicable_disasters.any(disaster_type))
        
        query = query.order_by(Supply.category, Supply.code)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_by_category(self, category: str) -> Sequence[Supply]:
        """按类别查询物资"""
        result = await self._db.execute(
            select(Supply).where(Supply.category == category).order_by(Supply.code)
        )
        return result.scalars().all()
    
    async def list_required_for_disaster(self, disaster_type: str) -> Sequence[Supply]:
        """查询指定灾害必须携带的物资"""
        result = await self._db.execute(
            select(Supply)
            .where(Supply.required_for_disasters.any(disaster_type))
            .order_by(Supply.category, Supply.code)
        )
        return result.scalars().all()
    
    async def update(self, supply: Supply, data: SupplyUpdate) -> Supply:
        """更新物资"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 枚举转字符串
        if 'category' in update_dict and update_dict['category']:
            update_dict['category'] = update_dict['category'].value
        if 'unit' in update_dict and update_dict['unit']:
            update_dict['unit'] = update_dict['unit'].value
        
        for key, value in update_dict.items():
            setattr(supply, key, value)
        
        await self._db.flush()
        await self._db.refresh(supply)
        
        logger.info(f"更新物资: id={supply.id}, fields={list(update_dict.keys())}")
        return supply
    
    async def delete(self, supply: Supply) -> None:
        """删除物资"""
        supply_id = supply.id
        await self._db.delete(supply)
        await self._db.flush()
        
        logger.info(f"删除物资: id={supply_id}")
    
    async def check_code_exists(self, code: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查编号是否已存在"""
        query = select(func.count(Supply.id)).where(Supply.code == code)
        if exclude_id:
            query = query.where(Supply.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
