"""
疏散安置点业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import ShelterRepository
from .schemas import (
    ShelterCreate, ShelterUpdate, ShelterCapacityUpdate, ShelterStatusUpdate,
    ShelterResponse, ShelterListResponse, ShelterStatus, ShelterType,
    ShelterNearbyQuery, ShelterNearbyResult, Location
)

logger = logging.getLogger(__name__)


class ShelterService:
    """安置点业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ShelterRepository(db)
    
    async def create(self, data: ShelterCreate) -> ShelterResponse:
        """
        创建安置点
        
        业务规则:
        - shelter_code必须唯一
        - total_capacity必须大于0
        """
        if await self._repo.check_code_exists(data.shelter_code):
            raise ConflictError(
                error_code="SHELTER_CODE_EXISTS",
                message=f"安置点编号已存在: {data.shelter_code}"
            )
        
        shelter = await self._repo.create(data)
        
        # 获取数据库计算的available_capacity
        available = await self._repo.get_available_capacity(shelter.id)
        
        return self._to_response(shelter, available)
    
    async def get_by_id(self, shelter_id: UUID) -> ShelterResponse:
        """根据ID获取安置点"""
        shelter = await self._repo.get_by_id(shelter_id)
        if not shelter:
            raise NotFoundError("Shelter", str(shelter_id))
        
        available = await self._repo.get_available_capacity(shelter_id)
        return self._to_response(shelter, available)
    
    async def get_by_code(self, code: str) -> ShelterResponse:
        """根据编号获取安置点"""
        shelter = await self._repo.get_by_code(code)
        if not shelter:
            raise NotFoundError("Shelter", code)
        
        available = await self._repo.get_available_capacity(shelter.id)
        return self._to_response(shelter, available)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        scenario_id: Optional[UUID] = None,
        shelter_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ShelterListResponse:
        """分页查询安置点列表"""
        items, total = await self._repo.list(page, page_size, scenario_id, shelter_type, status)
        
        # 批量获取available_capacity
        responses = []
        for shelter in items:
            available = await self._repo.get_available_capacity(shelter.id)
            responses.append(self._to_response(shelter, available))
        
        return ShelterListResponse(
            items=responses,
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_available(
        self,
        scenario_id: Optional[UUID] = None,
        shelter_type: Optional[str] = None,
        min_capacity: int = 1,
    ) -> list[ShelterResponse]:
        """查询可用安置点"""
        shelters = await self._repo.list_available(scenario_id, shelter_type, min_capacity)
        
        responses = []
        for shelter in shelters:
            available = await self._repo.get_available_capacity(shelter.id)
            responses.append(self._to_response(shelter, available))
        
        return responses
    
    async def update(self, shelter_id: UUID, data: ShelterUpdate) -> ShelterResponse:
        """更新安置点基本信息"""
        shelter = await self._repo.get_by_id(shelter_id)
        if not shelter:
            raise NotFoundError("Shelter", str(shelter_id))
        
        shelter = await self._repo.update(shelter, data)
        available = await self._repo.get_available_capacity(shelter_id)
        return self._to_response(shelter, available)
    
    async def update_capacity(
        self, 
        shelter_id: UUID, 
        data: ShelterCapacityUpdate
    ) -> ShelterResponse:
        """
        更新安置点容量
        
        业务规则:
        - current_occupancy不能超过total_capacity
        - 容量变化后自动更新状态（满员时变为full）
        """
        shelter = await self._repo.get_by_id(shelter_id)
        if not shelter:
            raise NotFoundError("Shelter", str(shelter_id))
        
        new_total = data.total_capacity if data.total_capacity is not None else shelter.total_capacity
        new_current = data.current_occupancy if data.current_occupancy is not None else shelter.current_occupancy
        
        if new_current > new_total:
            raise ValidationError(
                message="当前入住人数不能超过总容量",
                details={"current_occupancy": new_current, "total_capacity": new_total}
            )
        
        shelter = await self._repo.update_capacity(shelter, data)
        
        # 自动状态转换：满员时变为full，有空位时从full恢复为open
        if new_current >= new_total and shelter.status == 'open':
            logger.info(f"安置点已满，自动更新状态: id={shelter_id}")
            shelter = await self._repo.update_status(shelter, 'full')
        elif new_current < new_total and shelter.status == 'full':
            logger.info(f"安置点有空位，自动恢复开放: id={shelter_id}")
            shelter = await self._repo.update_status(shelter, 'open')
        
        available = await self._repo.get_available_capacity(shelter_id)
        return self._to_response(shelter, available)
    
    async def update_status(
        self, 
        shelter_id: UUID, 
        data: ShelterStatusUpdate
    ) -> ShelterResponse:
        """
        更新安置点状态
        
        状态转换规则:
        - preparing -> open, closed
        - open -> full, limited, closed, damaged
        - full -> open, limited, closed
        - limited -> open, closed
        - closed -> open, preparing
        - damaged -> closed, preparing
        """
        shelter = await self._repo.get_by_id(shelter_id)
        if not shelter:
            raise NotFoundError("Shelter", str(shelter_id))
        
        current = shelter.status
        target = data.status.value
        
        valid_transitions = {
            'preparing': ['open', 'closed'],
            'open': ['full', 'limited', 'closed', 'damaged'],
            'full': ['open', 'limited', 'closed'],
            'limited': ['open', 'closed'],
            'closed': ['open', 'preparing'],
            'damaged': ['closed', 'preparing'],
        }
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError(
                error_code="SHELTER_INVALID_STATUS_TRANSITION",
                message=f"无效的状态转换: {current} -> {target}"
            )
        
        shelter = await self._repo.update_status(shelter, target)
        available = await self._repo.get_available_capacity(shelter_id)
        return self._to_response(shelter, available)
    
    async def delete(self, shelter_id: UUID) -> None:
        """
        删除安置点
        
        业务规则:
        - 有人员入住(current_occupancy > 0)的安置点不能删除
        - 开放状态(open)的安置点不能删除
        """
        shelter = await self._repo.get_by_id(shelter_id)
        if not shelter:
            raise NotFoundError("Shelter", str(shelter_id))
        
        if shelter.current_occupancy > 0:
            raise ConflictError(
                error_code="SHELTER_HAS_OCCUPANTS",
                message=f"安置点有{shelter.current_occupancy}人入住，不能删除"
            )
        
        if shelter.status == 'open':
            raise ConflictError(
                error_code="SHELTER_IS_OPEN",
                message="开放中的安置点不能删除，请先关闭"
            )
        
        await self._repo.delete(shelter)
    
    async def find_nearest(self, query: ShelterNearbyQuery) -> list[ShelterNearbyResult]:
        """查找最近的可用安置点"""
        results = await self._repo.find_nearest(
            location=query.location,
            scenario_id=query.scenario_id,
            required_capacity=query.required_capacity,
            limit=query.limit,
        )
        
        return [
            ShelterNearbyResult(
                shelter_id=r["shelter_id"],
                name=r["name"],
                shelter_type=r["shelter_type"],
                distance_meters=r["distance_meters"],
                available_capacity=r["available_capacity"],
                facilities=r["facilities"],
            )
            for r in results
        ]
    
    def _to_response(self, shelter, available_capacity: int) -> ShelterResponse:
        """ORM模型转响应模型"""
        location = None
        if shelter.location:
            from shapely import wkb
            try:
                # Geometry类型的WKB解析
                point = wkb.loads(bytes(shelter.location.data))
                location = Location(longitude=point.x, latitude=point.y)
            except Exception as e:
                logger.warning(f"解析安置点位置失败: shelter_id={shelter.id}, error={e}")
        
        # 计算入住率
        occupancy_rate = 0.0
        if shelter.total_capacity > 0:
            occupancy_rate = round(shelter.current_occupancy / shelter.total_capacity * 100, 1)
        
        return ShelterResponse(
            id=shelter.id,
            scenario_id=shelter.scenario_id,
            shelter_code=shelter.shelter_code,
            name=shelter.name,
            shelter_type=shelter.shelter_type,
            location=location,
            address=shelter.address,
            status=shelter.status,
            total_capacity=shelter.total_capacity,
            current_occupancy=shelter.current_occupancy,
            available_capacity=available_capacity,
            occupancy_rate=occupancy_rate,
            facilities=shelter.facilities or {},
            accessibility=shelter.accessibility or {},
            special_accommodations=shelter.special_accommodations or {},
            supply_inventory=shelter.supply_inventory or {},
            contact_person=shelter.contact_person,
            contact_phone=shelter.contact_phone,
            contact_backup=shelter.contact_backup,
            managing_organization=shelter.managing_organization,
            opened_at=shelter.opened_at,
            closed_at=shelter.closed_at,
            entity_id=shelter.entity_id,
            notes=shelter.notes,
            created_at=shelter.created_at,
            updated_at=shelter.updated_at,
        )
