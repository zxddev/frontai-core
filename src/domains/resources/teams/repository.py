"""
救援队伍数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Team
from .schemas import TeamCreate, TeamUpdate, Location

logger = logging.getLogger(__name__)


class TeamRepository:
    """队伍数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: TeamCreate) -> Team:
        """创建队伍"""
        base_location_wkt = None
        if data.base_location:
            base_location_wkt = f"POINT({data.base_location.longitude} {data.base_location.latitude})"
        
        team = Team(
            code=data.code,
            name=data.name,
            team_type=data.team_type.value,
            parent_org=data.parent_org,
            contact_person=data.contact_person,
            contact_phone=data.contact_phone,
            base_location=base_location_wkt,
            base_address=data.base_address,
            total_personnel=data.total_personnel,
            available_personnel=data.available_personnel,
            capability_level=data.capability_level,
            certification_level=data.certification_level,
            response_time_minutes=data.response_time_minutes,
            max_deployment_hours=data.max_deployment_hours,
            properties=data.properties,
            status='standby',
        )
        self._db.add(team)
        await self._db.flush()
        await self._db.refresh(team)
        
        logger.info(f"创建队伍: code={team.code}, id={team.id}")
        return team
    
    async def get_by_id(self, team_id: UUID) -> Optional[Team]:
        """根据ID查询队伍"""
        result = await self._db.execute(
            select(Team).where(Team.id == team_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Team]:
        """根据编号查询队伍"""
        result = await self._db.execute(
            select(Team).where(Team.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        team_type: Optional[str] = None,
        min_capability_level: Optional[int] = None,
    ) -> tuple[Sequence[Team], int]:
        """
        分页查询队伍列表
        
        Returns:
            (队伍列表, 总数)
        """
        query = select(Team)
        count_query = select(func.count(Team.id))
        
        if status:
            query = query.where(Team.status == status)
            count_query = count_query.where(Team.status == status)
        
        if team_type:
            query = query.where(Team.team_type == team_type)
            count_query = count_query.where(Team.team_type == team_type)
        
        if min_capability_level:
            query = query.where(Team.capability_level >= min_capability_level)
            count_query = count_query.where(Team.capability_level >= min_capability_level)
        
        query = query.order_by(Team.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_available(
        self,
        team_type: Optional[str] = None,
        min_personnel: Optional[int] = None,
        min_capability_level: Optional[int] = None,
    ) -> Sequence[Team]:
        """
        查询可用队伍（待命状态）
        
        Args:
            team_type: 队伍类型筛选
            min_personnel: 最小可用人数要求
            min_capability_level: 最小能力等级
        """
        query = select(Team).where(Team.status == 'standby')
        
        if team_type:
            query = query.where(Team.team_type == team_type)
        
        if min_personnel is not None:
            query = query.where(Team.available_personnel >= min_personnel)
        
        if min_capability_level is not None:
            query = query.where(Team.capability_level >= min_capability_level)
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def update(self, team: Team, data: TeamUpdate) -> Team:
        """更新队伍"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 处理位置数据
        if 'base_location' in update_dict:
            loc = update_dict.pop('base_location')
            if loc:
                team.base_location = f"POINT({loc['longitude']} {loc['latitude']})"
            else:
                team.base_location = None
        
        # 枚举转字符串
        if 'status' in update_dict and update_dict['status']:
            update_dict['status'] = (
                update_dict['status'].value 
                if hasattr(update_dict['status'], 'value') 
                else update_dict['status']
            )
        
        for key, value in update_dict.items():
            setattr(team, key, value)
        
        await self._db.flush()
        await self._db.refresh(team)
        
        logger.info(f"更新队伍: id={team.id}, fields={list(update_dict.keys())}")
        return team
    
    async def update_status(
        self, 
        team: Team, 
        status: str, 
        task_id: Optional[UUID] = None
    ) -> Team:
        """更新队伍状态"""
        old_status = team.status
        team.status = status
        
        if status == 'deployed' and task_id:
            team.current_task_id = task_id
        elif status in ('standby', 'resting'):
            team.current_task_id = None
        
        await self._db.flush()
        await self._db.refresh(team)
        
        logger.info(f"队伍状态变更: id={team.id}, {old_status} -> {status}")
        return team
    
    async def update_personnel(
        self, 
        team: Team, 
        total: Optional[int] = None, 
        available: Optional[int] = None
    ) -> Team:
        """更新人员数量"""
        if total is not None:
            team.total_personnel = total
        if available is not None:
            team.available_personnel = available
        
        await self._db.flush()
        await self._db.refresh(team)
        
        logger.info(f"队伍人员更新: id={team.id}, total={team.total_personnel}, available={team.available_personnel}")
        return team
    
    async def delete(self, team: Team) -> None:
        """删除队伍"""
        team_id = team.id
        await self._db.delete(team)
        await self._db.flush()
        
        logger.info(f"删除队伍: id={team_id}")
    
    async def check_code_exists(self, code: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查编号是否已存在"""
        query = select(func.count(Team.id)).where(Team.code == code)
        if exclude_id:
            query = query.where(Team.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
