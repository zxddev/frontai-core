"""
疏散安置点数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EvacuationShelter
from .schemas import ShelterCreate, ShelterUpdate, ShelterCapacityUpdate, Location

logger = logging.getLogger(__name__)


class ShelterRepository:
    """安置点数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: ShelterCreate) -> EvacuationShelter:
        """创建安置点"""
        # 位置转WKT格式
        location_wkt = f"SRID=4326;POINT({data.location.longitude} {data.location.latitude})"
        
        shelter = EvacuationShelter(
            scenario_id=data.scenario_id,
            shelter_code=data.shelter_code,
            name=data.name,
            shelter_type=data.shelter_type.value,
            location=location_wkt,
            address=data.address,
            status='preparing',
            total_capacity=data.total_capacity,
            current_occupancy=0,
            facilities=data.facilities or {},
            accessibility=data.accessibility or {},
            special_accommodations=data.special_accommodations or {},
            supply_inventory=data.supply_inventory or {},
            contact_person=data.contact_person,
            contact_phone=data.contact_phone,
            contact_backup=data.contact_backup,
            managing_organization=data.managing_organization,
            notes=data.notes,
        )
        self._db.add(shelter)
        await self._db.flush()
        await self._db.refresh(shelter)
        
        logger.info(f"创建安置点: code={shelter.shelter_code}, id={shelter.id}, capacity={shelter.total_capacity}")
        return shelter
    
    async def get_by_id(self, shelter_id: UUID) -> Optional[EvacuationShelter]:
        """根据ID查询安置点"""
        result = await self._db.execute(
            select(EvacuationShelter).where(EvacuationShelter.id == shelter_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[EvacuationShelter]:
        """根据编号查询安置点"""
        result = await self._db.execute(
            select(EvacuationShelter).where(EvacuationShelter.shelter_code == code)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        scenario_id: Optional[UUID] = None,
        shelter_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[Sequence[EvacuationShelter], int]:
        """
        分页查询安置点列表
        
        Returns:
            (安置点列表, 总数)
        """
        query = select(EvacuationShelter)
        count_query = select(func.count(EvacuationShelter.id))
        
        # 想定筛选：指定scenario_id或常备安置点(NULL)
        if scenario_id is not None:
            query = query.where(
                (EvacuationShelter.scenario_id == scenario_id) | 
                (EvacuationShelter.scenario_id.is_(None))
            )
            count_query = count_query.where(
                (EvacuationShelter.scenario_id == scenario_id) | 
                (EvacuationShelter.scenario_id.is_(None))
            )
        
        if shelter_type:
            query = query.where(EvacuationShelter.shelter_type == shelter_type)
            count_query = count_query.where(EvacuationShelter.shelter_type == shelter_type)
        
        if status:
            query = query.where(EvacuationShelter.status == status)
            count_query = count_query.where(EvacuationShelter.status == status)
        
        query = query.order_by(EvacuationShelter.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_available(
        self,
        scenario_id: Optional[UUID] = None,
        shelter_type: Optional[str] = None,
        min_capacity: int = 1,
    ) -> Sequence[EvacuationShelter]:
        """
        查询可用安置点（开放状态且有剩余容量）
        
        Args:
            scenario_id: 想定ID
            shelter_type: 安置点类型筛选
            min_capacity: 最小剩余容量要求
        """
        query = select(EvacuationShelter).where(EvacuationShelter.status == 'open')
        
        # 想定筛选：包含常备安置点
        if scenario_id is not None:
            query = query.where(
                (EvacuationShelter.scenario_id == scenario_id) | 
                (EvacuationShelter.scenario_id.is_(None))
            )
        
        if shelter_type:
            query = query.where(EvacuationShelter.shelter_type == shelter_type)
        
        # 剩余容量筛选：total_capacity - current_occupancy >= min_capacity
        query = query.where(
            (EvacuationShelter.total_capacity - EvacuationShelter.current_occupancy) >= min_capacity
        )
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def update(self, shelter: EvacuationShelter, data: ShelterUpdate) -> EvacuationShelter:
        """更新安置点基本信息"""
        update_dict = data.model_dump(exclude_unset=True)
        
        # 处理位置数据
        if 'location' in update_dict:
            loc = update_dict.pop('location')
            if loc:
                shelter.location = f"SRID=4326;POINT({loc['longitude']} {loc['latitude']})"
        
        for key, value in update_dict.items():
            setattr(shelter, key, value)
        
        await self._db.flush()
        await self._db.refresh(shelter)
        
        logger.info(f"更新安置点: id={shelter.id}, fields={list(update_dict.keys())}")
        return shelter
    
    async def update_capacity(
        self, 
        shelter: EvacuationShelter, 
        data: ShelterCapacityUpdate
    ) -> EvacuationShelter:
        """更新安置点容量"""
        if data.total_capacity is not None:
            shelter.total_capacity = data.total_capacity
        if data.current_occupancy is not None:
            shelter.current_occupancy = data.current_occupancy
        
        await self._db.flush()
        await self._db.refresh(shelter)
        
        logger.info(
            f"更新安置点容量: id={shelter.id}, "
            f"total={shelter.total_capacity}, current={shelter.current_occupancy}"
        )
        return shelter
    
    async def update_status(self, shelter: EvacuationShelter, status: str) -> EvacuationShelter:
        """更新安置点状态"""
        old_status = shelter.status
        shelter.status = status
        
        # 状态变更时更新相关时间
        from datetime import datetime, timezone
        if status == 'open' and old_status == 'preparing':
            shelter.opened_at = datetime.now(timezone.utc)
        elif status == 'closed' and old_status != 'closed':
            shelter.closed_at = datetime.now(timezone.utc)
        
        await self._db.flush()
        await self._db.refresh(shelter)
        
        logger.info(f"安置点状态变更: id={shelter.id}, {old_status} -> {status}")
        return shelter
    
    async def delete(self, shelter: EvacuationShelter) -> None:
        """删除安置点"""
        shelter_id = shelter.id
        await self._db.delete(shelter)
        await self._db.flush()
        
        logger.info(f"删除安置点: id={shelter_id}")
    
    async def check_code_exists(self, code: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查编号是否已存在"""
        query = select(func.count(EvacuationShelter.id)).where(EvacuationShelter.shelter_code == code)
        if exclude_id:
            query = query.where(EvacuationShelter.id != exclude_id)
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0
    
    async def find_nearest(
        self,
        location: Location,
        scenario_id: Optional[UUID] = None,
        required_capacity: int = 1,
        limit: int = 5,
    ) -> list[dict]:
        """
        查找最近的可用安置点
        
        调用数据库函数 find_nearest_shelters_v2
        """
        point_wkt = f"POINT({location.longitude} {location.latitude})"
        
        sql = text("""
            SELECT 
                shelter_id,
                name,
                shelter_type,
                distance_meters,
                available_capacity,
                facilities
            FROM find_nearest_shelters_v2(
                ST_GeomFromText(:point, 4326),
                :scenario_id,
                :required_capacity,
                :limit
            )
        """)
        
        result = await self._db.execute(
            sql,
            {
                "point": point_wkt,
                "scenario_id": scenario_id,
                "required_capacity": required_capacity,
                "limit": limit,
            }
        )
        
        rows = result.fetchall()
        return [
            {
                "shelter_id": row.shelter_id,
                "name": row.name,
                "shelter_type": row.shelter_type,
                "distance_meters": row.distance_meters,
                "available_capacity": row.available_capacity,
                "facilities": row.facilities or {},
            }
            for row in rows
        ]
    
    async def get_available_capacity(self, shelter_id: UUID) -> int:
        """获取安置点剩余容量（读取数据库GENERATED列）"""
        sql = text("""
            SELECT available_capacity 
            FROM evacuation_shelters_v2 
            WHERE id = :shelter_id
        """)
        result = await self._db.execute(sql, {"shelter_id": shelter_id})
        row = result.fetchone()
        return row.available_capacity if row else 0
