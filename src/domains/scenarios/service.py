"""
想定业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from src.core.exceptions import NotFoundError, ConflictError
from .repository import ScenarioRepository
from .schemas import (
    ScenarioCreate, ScenarioUpdate, ScenarioResponse, 
    ScenarioListResponse, ScenarioStatus, ScenarioStatusUpdate, Location,
    ScenarioResourcesConfig, ScenarioResourcesResponse,
    ScenarioEnvironmentConfig, ScenarioEnvironmentResponse,
)

logger = logging.getLogger(__name__)


class ScenarioService:
    """想定业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ScenarioRepository(db)
        self._db = db
    
    async def create(self, data: ScenarioCreate) -> ScenarioResponse:
        """
        创建想定
        
        业务规则:
        - 名称必须唯一
        """
        if await self._repo.check_name_exists(data.name):
            raise ConflictError(
                error_code="SC_NAME_EXISTS",
                message=f"想定名称已存在: {data.name}"
            )
        
        scenario = await self._repo.create(data)
        return self._to_response(scenario)
    
    async def get_by_id(self, scenario_id: UUID) -> ScenarioResponse:
        """根据ID获取想定"""
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        return self._to_response(scenario)
    
    async def get_active(self) -> Optional[ScenarioResponse]:
        """获取当前活动的想定"""
        scenario = await self._repo.get_active()
        if not scenario:
            return None
        return self._to_response(scenario)
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        scenario_type: Optional[str] = None,
    ) -> ScenarioListResponse:
        """分页查询想定列表"""
        items, total = await self._repo.list(page, page_size, status, scenario_type)
        return ScenarioListResponse(
            items=[self._to_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def update(self, scenario_id: UUID, data: ScenarioUpdate) -> ScenarioResponse:
        """更新想定"""
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        
        scenario = await self._repo.update(scenario, data)
        return self._to_response(scenario)
    
    async def update_status(
        self, 
        scenario_id: UUID, 
        data: ScenarioStatusUpdate
    ) -> ScenarioResponse:
        """
        更新想定状态
        
        状态转换规则:
        - draft -> active
        - active -> resolved
        - resolved -> archived
        - active时，其他想定如果也是active则自动归档
        """
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        
        current = scenario.status
        target = data.status.value
        
        valid_transitions = {
            'draft': ['active'],
            'active': ['resolved'],
            'resolved': ['archived'],
            'archived': [],
        }
        
        if target not in valid_transitions.get(current, []):
            raise ConflictError(
                error_code="SC_INVALID_STATUS_TRANSITION",
                message=f"无效的状态转换: {current} -> {target}"
            )
        
        # 激活新想定时，检查是否有其他活动想定
        if target == 'active':
            existing_active = await self._repo.get_active()
            if existing_active and existing_active.id != scenario_id:
                # 自动将旧的active想定改为resolved
                await self._repo.update_status(existing_active, 'resolved')
                logger.warning(
                    f"自动结束旧想定: id={existing_active.id}, "
                    f"因为激活了新想定: id={scenario_id}"
                )
        
        scenario = await self._repo.update_status(scenario, target)
        return self._to_response(scenario)
    
    async def delete(self, scenario_id: UUID) -> None:
        """
        删除想定
        
        业务规则:
        - active状态的想定不能删除
        """
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        
        if scenario.status == 'active':
            raise ConflictError(
                error_code="SC_DELETE_ACTIVE",
                message="活动中的想定不能删除"
            )
        
        await self._repo.delete(scenario)
    
    async def configure_resources(
        self,
        scenario_id: UUID,
        data: ScenarioResourcesConfig,
    ) -> ScenarioResourcesResponse:
        """
        配置想定初始资源
        
        业务规则:
        - 只有preparing状态可配置资源
        - 资源必须存在且可用
        """
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        
        # 当前简化：draft和active都允许配置（根据实际业务调整）
        if scenario.status not in ('draft', 'active'):
            raise ConflictError(
                error_code="SC_INVALID_STATUS",
                message=f"当前状态({scenario.status})不允许配置资源"
            )
        
        # 将资源配置保存到parameters中
        existing_params = scenario.parameters or {}
        existing_params['configured_resources'] = {
            'teams': [{'id': str(t.resource_id), 'role': t.role} for t in data.teams],
            'vehicles': [{'id': str(v.resource_id), 'role': v.role} for v in data.vehicles],
            'devices': [{'id': str(d.resource_id), 'role': d.role} for d in data.devices],
        }
        
        scenario.parameters = existing_params
        await self._db.flush()
        
        logger.info(
            f"想定资源配置: scenario_id={scenario_id}, "
            f"teams={len(data.teams)}, vehicles={len(data.vehicles)}, devices={len(data.devices)}"
        )
        
        return ScenarioResourcesResponse(
            scenario_id=scenario_id,
            configured_teams=len(data.teams),
            configured_vehicles=len(data.vehicles),
            configured_devices=len(data.devices),
            message="资源配置成功",
        )
    
    async def configure_environment(
        self,
        scenario_id: UUID,
        data: ScenarioEnvironmentConfig,
    ) -> ScenarioEnvironmentResponse:
        """
        配置想定环境参数
        
        业务规则:
        - draft/active状态可配置环境
        """
        scenario = await self._repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", str(scenario_id))
        
        if scenario.status not in ('draft', 'active'):
            raise ConflictError(
                error_code="SC_INVALID_STATUS",
                message=f"当前状态({scenario.status})不允许配置环境"
            )
        
        # 保存环境配置到parameters
        existing_params = scenario.parameters or {}
        
        weather_configured = False
        road_configured = False
        comm_configured = False
        
        if data.weather:
            existing_params['environment_weather'] = data.weather.model_dump()
            weather_configured = True
        
        if data.road_conditions:
            existing_params['environment_roads'] = data.road_conditions.model_dump()
            road_configured = True
        
        if data.communication:
            existing_params['environment_communication'] = data.communication.model_dump()
            comm_configured = True
        
        scenario.parameters = existing_params
        await self._db.flush()
        
        logger.info(
            f"想定环境配置: scenario_id={scenario_id}, "
            f"weather={weather_configured}, roads={road_configured}, comm={comm_configured}"
        )
        
        return ScenarioEnvironmentResponse(
            scenario_id=scenario_id,
            weather_configured=weather_configured,
            road_conditions_configured=road_configured,
            communication_configured=comm_configured,
            message="环境参数配置成功",
        )
    
    def _to_response(self, scenario) -> ScenarioResponse:
        """ORM模型转响应模型"""
        location = None
        if scenario.location:
            try:
                point = to_shape(scenario.location)
                location = Location(longitude=point.x, latitude=point.y)
            except Exception as e:
                logger.warning(f"解析想定位置失败: scenario_id={scenario.id}, error={e}")
        
        return ScenarioResponse(
            id=scenario.id,
            name=scenario.name,
            scenario_type=scenario.scenario_type,
            response_level=scenario.response_level,
            status=scenario.status,
            location=location,
            started_at=scenario.started_at,
            ended_at=scenario.ended_at,
            parameters=scenario.parameters or {},
            affected_population=scenario.affected_population,
            affected_area_km2=scenario.affected_area_km2,
            created_by=scenario.created_by,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
        )
