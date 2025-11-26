"""
想定数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from .models import Scenario
from .schemas import ScenarioCreate, ScenarioUpdate

logger = logging.getLogger(__name__)


class ScenarioRepository:
    """想定数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: ScenarioCreate) -> Scenario:
        """创建想定"""
        location = None
        if data.location:
            location = ST_SetSRID(
                ST_MakePoint(data.location.longitude, data.location.latitude),
                4326
            )
        
        scenario = Scenario(
            name=data.name,
            scenario_type=data.scenario_type.value,
            response_level=data.response_level.value if data.response_level else None,
            location=location,
            started_at=data.started_at,
            parameters=data.parameters,
            affected_population=data.affected_population,
            affected_area_km2=data.affected_area_km2,
            status='draft',
        )
        self._db.add(scenario)
        await self._db.flush()
        await self._db.refresh(scenario)
        
        logger.info(f"创建想定: name={scenario.name}, id={scenario.id}")
        return scenario
    
    async def get_by_id(self, scenario_id: UUID) -> Optional[Scenario]:
        """根据ID查询想定"""
        result = await self._db.execute(
            select(Scenario).where(Scenario.id == scenario_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active(self) -> Optional[Scenario]:
        """获取当前活动的想定（同一时间只有一个）"""
        result = await self._db.execute(
            select(Scenario).where(Scenario.status == 'active')
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        scenario_type: Optional[str] = None,
    ) -> tuple[Sequence[Scenario], int]:
        """
        分页查询想定列表
        
        Returns:
            (想定列表, 总数)
        """
        query = select(Scenario)
        count_query = select(func.count(Scenario.id))
        
        if status:
            query = query.where(Scenario.status == status)
            count_query = count_query.where(Scenario.status == status)
        
        if scenario_type:
            query = query.where(Scenario.scenario_type == scenario_type)
            count_query = count_query.where(Scenario.scenario_type == scenario_type)
        
        query = query.order_by(Scenario.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def update(self, scenario: Scenario, data: ScenarioUpdate) -> Scenario:
        """更新想定"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 处理location
        if 'location' in update_dict:
            loc = update_dict.pop('location')
            if loc:
                scenario.location = ST_SetSRID(
                    ST_MakePoint(loc['longitude'], loc['latitude']),
                    4326
                )
            else:
                scenario.location = None
        
        # 枚举转字符串
        if 'response_level' in update_dict and update_dict['response_level']:
            update_dict['response_level'] = (
                update_dict['response_level'].value 
                if hasattr(update_dict['response_level'], 'value') 
                else update_dict['response_level']
            )
        
        for key, value in update_dict.items():
            setattr(scenario, key, value)
        
        await self._db.flush()
        await self._db.refresh(scenario)
        
        logger.info(f"更新想定: id={scenario.id}, fields={list(update_dict.keys())}")
        return scenario
    
    async def update_status(self, scenario: Scenario, status: str) -> Scenario:
        """更新想定状态"""
        old_status = scenario.status
        scenario.status = status
        await self._db.flush()
        await self._db.refresh(scenario)
        
        logger.info(f"想定状态变更: id={scenario.id}, {old_status} -> {status}")
        return scenario
    
    async def delete(self, scenario: Scenario) -> None:
        """删除想定"""
        scenario_id = scenario.id
        await self._db.delete(scenario)
        await self._db.flush()
        
        logger.info(f"删除想定: id={scenario_id}")
    
    async def check_name_exists(
        self, 
        name: str, 
        exclude_id: Optional[UUID] = None
    ) -> bool:
        """检查名称是否已存在"""
        query = select(func.count(Scenario.id)).where(Scenario.name == name)
        if exclude_id:
            query = query.where(Scenario.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
