"""
救援队伍业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import TeamRepository
from .schemas import (
    TeamCreate, TeamUpdate, TeamResponse, 
    TeamListResponse, TeamStatus, TeamAvailabilityCheck, Location,
    TeamLocationUpdate, TeamLocationResponse,
)
from datetime import datetime

logger = logging.getLogger(__name__)


class TeamService:
    """队伍业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = TeamRepository(db)
    
    async def create(self, data: TeamCreate) -> TeamResponse:
        """
        创建队伍
        
        业务规则:
        - code必须唯一
        - available_personnel 不能超过 total_personnel
        """
        if await self._repo.check_code_exists(data.code):
            raise ConflictError(
                error_code="TM_CODE_EXISTS",
                message=f"队伍编号已存在: {data.code}"
            )
        
        if data.available_personnel > data.total_personnel:
            raise ValidationError(
                message="可用人数不能超过总人数",
                details={"available_personnel": data.available_personnel, "total_personnel": data.total_personnel}
            )
        
        team = await self._repo.create(data)
        return self._to_response(team)
    
    async def get_by_id(self, team_id: UUID) -> TeamResponse:
        """根据ID获取队伍"""
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        return self._to_response(team)
    
    async def get_by_code(self, code: str) -> TeamResponse:
        """根据编号获取队伍"""
        team = await self._repo.get_by_code(code)
        if not team:
            raise NotFoundError("Team", code)
        return self._to_response(team)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        team_type: Optional[str] = None,
        min_capability_level: Optional[int] = None,
    ) -> TeamListResponse:
        """分页查询队伍列表"""
        items, total = await self._repo.list(page, page_size, status, team_type, min_capability_level)
        return TeamListResponse(
            items=[self._to_response(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def list_available(
        self,
        team_type: Optional[str] = None,
        min_personnel: Optional[int] = None,
        min_capability_level: Optional[int] = None,
    ) -> list[TeamResponse]:
        """
        查询可用队伍（用于资源分配）
        """
        teams = await self._repo.list_available(team_type, min_personnel, min_capability_level)
        return [self._to_response(t) for t in teams]
    
    async def update(self, team_id: UUID, data: TeamUpdate) -> TeamResponse:
        """更新队伍"""
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        # 验证人员数量
        update_dict = data.model_dump(exclude_unset=True)
        new_total = update_dict.get('total_personnel', team.total_personnel)
        new_available = update_dict.get('available_personnel', team.available_personnel)
        
        if new_available > new_total:
            raise ValidationError(
                message="可用人数不能超过总人数",
                details={"available_personnel": new_available, "total_personnel": new_total}
            )
        
        team = await self._repo.update(team, data)
        return self._to_response(team)
    
    async def update_status(
        self, 
        team_id: UUID, 
        status: TeamStatus,
        task_id: Optional[UUID] = None,
    ) -> TeamResponse:
        """
        更新队伍状态
        
        状态转换规则:
        - standby -> deployed
        - deployed -> standby, resting
        - resting -> standby
        - unavailable <-> standby
        """
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        current = team.status
        target = status.value
        
        valid_transitions = {
            'standby': ['deployed', 'unavailable'],
            'deployed': ['standby', 'resting'],
            'resting': ['standby'],
            'unavailable': ['standby'],
        }
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError(
                error_code="TM_INVALID_STATUS_TRANSITION",
                message=f"无效的状态转换: {current} -> {target}"
            )
        
        # 部署时必须指定任务
        if target == 'deployed' and not task_id:
            raise ValidationError(
                message="部署队伍时必须指定任务ID",
                details={"task_id": "required"}
            )
        
        team = await self._repo.update_status(team, target, task_id)
        return self._to_response(team)
    
    async def update_personnel(
        self,
        team_id: UUID,
        total: Optional[int] = None,
        available: Optional[int] = None,
    ) -> TeamResponse:
        """更新人员数量"""
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        new_total = total if total is not None else team.total_personnel
        new_available = available if available is not None else team.available_personnel
        
        if new_available > new_total:
            raise ValidationError(
                message="可用人数不能超过总人数",
                details={"available_personnel": new_available, "total_personnel": new_total}
            )
        
        team = await self._repo.update_personnel(team, total, available)
        return self._to_response(team)
    
    async def delete(self, team_id: UUID) -> None:
        """
        删除队伍
        
        业务规则:
        - 已部署(deployed)状态的队伍不能删除
        """
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        if team.status == 'deployed':
            raise ConflictError(
                error_code="TM_DELETE_DEPLOYED",
                message="已部署队伍不能删除"
            )
        
        await self._repo.delete(team)
    
    async def check_availability(self, team_id: UUID) -> TeamAvailabilityCheck:
        """检查队伍可用性"""
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        is_available = team.status == 'standby' and team.available_personnel > 0
        
        message = None
        if not is_available:
            if team.status != 'standby':
                message = f"队伍状态为{team.status}，不可分配"
            elif team.available_personnel == 0:
                message = "无可用人员"
        
        return TeamAvailabilityCheck(
            team_id=team_id,
            is_available=is_available,
            available_personnel=team.available_personnel,
            status=team.status,
            current_task_id=team.current_task_id,
            message=message,
        )
    
    async def update_location(
        self,
        team_id: UUID,
        data: TeamLocationUpdate,
    ) -> TeamLocationResponse:
        """
        更新队伍当前位置
        
        由GPS遥测数据或手动输入调用。
        """
        team = await self._repo.get_by_id(team_id)
        if not team:
            raise NotFoundError("Team", str(team_id))
        
        wkt = f"SRID=4326;POINT({data.longitude} {data.latitude})"
        team.current_location = wkt
        team.last_location_update = datetime.utcnow()
        
        # 扩展属性存储航向信息
        props = team.properties or {}
        if data.heading is not None:
            props['heading'] = data.heading
        props['location_source'] = data.source
        team.properties = props
        
        await self._repo._db.flush()
        
        logger.info(
            f"队伍位置更新: team_id={team_id}, "
            f"lon={data.longitude}, lat={data.latitude}"
        )
        
        return TeamLocationResponse(
            team_id=team_id,
            longitude=data.longitude,
            latitude=data.latitude,
            last_update=team.last_location_update,
            message="位置更新成功",
        )
    
    def _to_response(self, team) -> TeamResponse:
        """ORM模型转响应模型"""
        base_location = None
        if team.base_location:
            from shapely import wkb
            try:
                point = wkb.loads(bytes(team.base_location.data))
                base_location = Location(longitude=point.x, latitude=point.y)
            except Exception as e:
                logger.warning(f"解析队伍位置失败: team_id={team.id}, error={e}")
        
        return TeamResponse(
            id=team.id,
            code=team.code,
            name=team.name,
            team_type=team.team_type,
            parent_org=team.parent_org,
            contact_person=team.contact_person,
            contact_phone=team.contact_phone,
            base_location=base_location,
            base_address=team.base_address,
            total_personnel=team.total_personnel or 0,
            available_personnel=team.available_personnel or 0,
            capability_level=team.capability_level or 3,
            certification_level=team.certification_level,
            response_time_minutes=team.response_time_minutes,
            max_deployment_hours=team.max_deployment_hours or 72,
            status=team.status,
            current_task_id=team.current_task_id,
            properties=team.properties or {},
            created_at=team.created_at,
            updated_at=team.updated_at,
        )
