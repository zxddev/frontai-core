"""
仿真推演API路由

路由前缀: /simulations
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .schemas import (
    SimulationScenarioCreate, SimulationScenarioResponse, SimulationListResponse,
    ImmediateInjectionRequest, InjectionQueueResponse,
    TimeScaleUpdateRequest, SimulationTimeResponse,
    AssessmentCreateRequest, AssessmentResponse,
)
from .service import SimulationService


router = APIRouter(prefix="/simulations", tags=["simulation"])


def get_service(db: AsyncSession = Depends(get_db)) -> SimulationService:
    """获取服务依赖"""
    return SimulationService(db)


# =============================================================================
# 仿真场景管理
# =============================================================================

@router.post("", response_model=SimulationScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_simulation(
    data: SimulationScenarioCreate,
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """
    创建仿真场景
    
    - **name**: 场景名称
    - **scenario_id**: 关联想定ID
    - **source_type**: 来源类型 (new/from_history)
    - **time_scale**: 时间倍率 (0.5-10.0)
    - **participants**: 参与人员列表
    - **inject_events**: 预设注入事件
    """
    try:
        return await service.create_scenario(data)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.detail)


@router.get("", response_model=SimulationListResponse)
async def list_simulations(
    scenario_id: Optional[UUID] = Query(None, description="按想定ID筛选"),
    status_filter: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: SimulationService = Depends(get_service),
) -> SimulationListResponse:
    """获取仿真场景列表"""
    return await service.list_scenarios(scenario_id, status_filter, page, page_size)


@router.get("/{simulation_id}", response_model=SimulationScenarioResponse)
async def get_simulation(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """获取仿真场景详情"""
    try:
        return await service.get_scenario(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


# =============================================================================
# 仿真生命周期
# =============================================================================

@router.post("/{simulation_id}/start", response_model=SimulationScenarioResponse)
async def start_simulation(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """
    启动仿真
    
    将仿真状态从 ready/paused 变为 running
    """
    try:
        return await service.start_simulation(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/{simulation_id}/pause", response_model=SimulationScenarioResponse)
async def pause_simulation(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """
    暂停仿真
    
    暂停时间流逝，保留当前状态
    """
    try:
        return await service.pause_simulation(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/{simulation_id}/resume", response_model=SimulationScenarioResponse)
async def resume_simulation(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """
    恢复仿真
    
    从暂停状态恢复
    """
    try:
        return await service.resume_simulation(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.post("/{simulation_id}/stop", response_model=SimulationScenarioResponse)
async def stop_simulation(
    simulation_id: UUID,
    rollback: bool = Query(True, description="是否回滚仿真期间的数据变更"),
    service: SimulationService = Depends(get_service),
) -> SimulationScenarioResponse:
    """
    停止仿真
    
    结束仿真，状态变为 stopped。
    默认回滚仿真期间的所有数据变更（事件、任务等）。
    
    - **rollback**: 是否回滚数据，默认True。设为False则保留仿真期间的数据
    """
    try:
        return await service.stop_simulation(simulation_id, rollback=rollback)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


# =============================================================================
# 时间控制
# =============================================================================

@router.patch("/{simulation_id}/time-scale", response_model=SimulationTimeResponse)
async def update_time_scale(
    simulation_id: UUID,
    request: TimeScaleUpdateRequest,
    service: SimulationService = Depends(get_service),
) -> SimulationTimeResponse:
    """
    调整时间倍率
    
    支持 0.5x - 10x 时间倍率：
    - 1.0x = 实时
    - 2.0x = 2倍速
    - 0.5x = 慢放
    """
    try:
        return await service.update_time_scale(simulation_id, request)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


# =============================================================================
# 事件注入
# =============================================================================

class InjectionResponse(BaseModel):
    """事件注入响应"""
    event_id: UUID
    message: str = "事件注入成功"


@router.post("/{simulation_id}/inject", response_model=InjectionResponse)
async def inject_event(
    simulation_id: UUID,
    request: ImmediateInjectionRequest,
    service: SimulationService = Depends(get_service),
) -> InjectionResponse:
    """
    注入事件
    
    向仿真中注入一个事件（如余震、道路中断等）。
    事件会直接写入真实的事件表，仿真结束时回滚。
    
    - **event**: 事件内容
    """
    try:
        event_id = await service.inject_event(simulation_id, request)
        return InjectionResponse(event_id=event_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.get("/{simulation_id}/inject-queue", response_model=InjectionQueueResponse)
async def get_inject_queue(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> InjectionQueueResponse:
    """获取注入队列"""
    try:
        return await service.get_injection_queue(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)


# =============================================================================
# 评估报告
# =============================================================================

@router.post("/{simulation_id}/assessment", response_model=AssessmentResponse)
async def create_assessment(
    simulation_id: UUID,
    request: AssessmentCreateRequest = AssessmentCreateRequest(),
    service: SimulationService = Depends(get_service),
) -> AssessmentResponse:
    """
    生成评估报告
    
    仿真结束后生成评估，包含各维度得分和改进建议
    """
    try:
        return await service.create_assessment(simulation_id, request)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)


@router.get("/{simulation_id}/assessment", response_model=AssessmentResponse)
async def get_assessment(
    simulation_id: UUID,
    service: SimulationService = Depends(get_service),
) -> AssessmentResponse:
    """获取评估报告"""
    try:
        return await service.get_assessment(simulation_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
