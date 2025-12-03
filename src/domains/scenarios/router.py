"""
想定API路由

接口前缀: /scenarios
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import ScenarioService
from .schemas import (
    ScenarioCreate, ScenarioUpdate, ScenarioResponse, 
    ScenarioListResponse, ScenarioStatusUpdate,
    ScenarioResourcesConfig, ScenarioResourcesResponse,
    ScenarioEnvironmentConfig, ScenarioEnvironmentResponse,
    ScenarioResetRequest, ScenarioResetResponse,
)


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def get_service(db: AsyncSession = Depends(get_db)) -> ScenarioService:
    return ScenarioService(db)


@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    data: ScenarioCreate,
    service: ScenarioService = Depends(get_service),
) -> ScenarioResponse:
    """
    创建想定
    
    想定是应急事件的顶层容器，所有事件、方案、任务都关联到具体想定。
    """
    return await service.create(data)


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: draft/active/resolved/archived"),
    scenario_type: Optional[str] = Query(None, description="类型筛选: earthquake/flood/fire/hazmat/landslide"),
    service: ScenarioService = Depends(get_service),
) -> ScenarioListResponse:
    """分页查询想定列表"""
    return await service.list(page, page_size, status, scenario_type)


@router.get("/active", response_model=ScenarioResponse)
async def get_active_scenario(
    service: ScenarioService = Depends(get_service),
) -> Optional[ScenarioResponse]:
    """
    获取当前活动的想定
    
    同一时间只有一个活动想定
    """
    return await service.get_active()


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID,
    service: ScenarioService = Depends(get_service),
) -> ScenarioResponse:
    """根据ID获取想定详情"""
    return await service.get_by_id(scenario_id)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    data: ScenarioUpdate,
    service: ScenarioService = Depends(get_service),
) -> ScenarioResponse:
    """更新想定信息"""
    return await service.update(scenario_id, data)


@router.post("/{scenario_id}/status", response_model=ScenarioResponse)
async def update_scenario_status(
    scenario_id: UUID,
    data: ScenarioStatusUpdate,
    service: ScenarioService = Depends(get_service),
) -> ScenarioResponse:
    """
    更新想定状态
    
    状态转换规则:
    - draft -> active
    - active -> resolved
    - resolved -> archived
    
    激活新想定时，其他活动想定自动结束。
    """
    return await service.update_status(scenario_id, data)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: UUID,
    service: ScenarioService = Depends(get_service),
) -> None:
    """
    删除想定
    
    限制: 活动中(active)的想定不能删除
    """
    await service.delete(scenario_id)


@router.post("/{scenario_id}/resources", response_model=ScenarioResourcesResponse)
async def configure_resources(
    scenario_id: UUID,
    data: ScenarioResourcesConfig,
    service: ScenarioService = Depends(get_service),
) -> ScenarioResourcesResponse:
    """
    配置想定初始资源
    
    指定参与本想定的队伍、车辆、设备等资源。
    只有draft/active状态可配置资源。
    """
    return await service.configure_resources(scenario_id, data)


@router.post("/{scenario_id}/environment", response_model=ScenarioEnvironmentResponse)
async def configure_environment(
    scenario_id: UUID,
    data: ScenarioEnvironmentConfig,
    service: ScenarioService = Depends(get_service),
) -> ScenarioEnvironmentResponse:
    """
    配置想定环境参数
    
    设置天气、道路、通信等环境条件。
    用于仿真模块评估资源可达性和任务难度。
    """
    return await service.configure_environment(scenario_id, data)


@router.post("/reset", response_model=ScenarioResetResponse)
async def reset_active_scenario(
    service: ScenarioService = Depends(get_service),
) -> ScenarioResetResponse:
    """
    重置当前活动想定数据
    
    自动获取当前 active 状态的想定，删除其所有关联数据。
    不需要传参，默认删除所有事件、实体、风险区域、方案、任务等。
    """
    return await service.reset_active()


@router.post("/{scenario_id}/reset", response_model=ScenarioResetResponse)
async def reset_scenario(
    scenario_id: UUID,
    data: ScenarioResetRequest = ScenarioResetRequest(),
    service: ScenarioService = Depends(get_service),
) -> ScenarioResetResponse:
    """
    重置指定想定数据
    
    删除想定下的所有事件、实体、风险区域、方案、任务等数据，
    保留想定本身，方便重新开始仿真推演。
    
    可选择性地保留某些数据类型（通过设置对应字段为false）。
    
    示例：
    - 全部重置：POST /scenarios/{id}/reset （使用默认值，删除所有关联数据）
    - 只删除事件和实体：POST /scenarios/{id}/reset {"delete_schemes": false, "delete_tasks": false}
    """
    return await service.reset(scenario_id, data)
