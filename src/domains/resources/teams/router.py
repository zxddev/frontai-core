"""
救援队伍API路由

接口前缀: /teams
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .service import TeamService
from .schemas import (
    TeamCreate, TeamUpdate, TeamResponse, 
    TeamListResponse, TeamStatus, TeamAvailabilityCheck,
    TeamLocationUpdate, TeamLocationResponse,
)


router = APIRouter(prefix="/teams", tags=["teams"])


def get_service(db: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(db)


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    data: TeamCreate,
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """
    创建救援队伍
    
    队伍是静态资源，不属于特定场景。通过方案资源分配关联到具体任务。
    """
    return await service.create(data)


@router.get("", response_model=TeamListResponse)
async def list_teams(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: standby/deployed/resting/unavailable"),
    team_type: Optional[str] = Query(None, description="类型筛选"),
    min_capability_level: Optional[int] = Query(None, ge=1, le=5, description="最小能力等级"),
    service: TeamService = Depends(get_service),
) -> TeamListResponse:
    """分页查询队伍列表"""
    return await service.list(page, page_size, status, team_type, min_capability_level)


@router.get("/available", response_model=list[TeamResponse])
async def list_available_teams(
    team_type: Optional[str] = Query(None, description="队伍类型筛选"),
    min_personnel: Optional[int] = Query(None, ge=1, description="最小可用人数"),
    min_capability_level: Optional[int] = Query(None, ge=1, le=5, description="最小能力等级"),
    service: TeamService = Depends(get_service),
) -> list[TeamResponse]:
    """
    查询可用队伍（用于资源分配）
    
    仅返回状态为standby的队伍
    """
    return await service.list_available(team_type, min_personnel, min_capability_level)


@router.get("/code/{code}", response_model=TeamResponse)
async def get_team_by_code(
    code: str,
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """根据编号获取队伍"""
    return await service.get_by_code(code)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: UUID,
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """根据ID获取队伍详情"""
    return await service.get_by_id(team_id)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    data: TeamUpdate,
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """更新队伍信息"""
    return await service.update(team_id, data)


@router.post("/{team_id}/status", response_model=TeamResponse)
async def update_team_status(
    team_id: UUID,
    status: TeamStatus = Query(..., description="目标状态"),
    task_id: Optional[UUID] = Query(None, description="任务ID（部署时必填）"),
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """
    更新队伍状态
    
    状态转换规则:
    - standby -> deployed (需要task_id)
    - deployed -> standby, resting
    - resting -> standby
    - unavailable <-> standby
    """
    return await service.update_status(team_id, status, task_id)


@router.post("/{team_id}/personnel", response_model=TeamResponse)
async def update_team_personnel(
    team_id: UUID,
    total: Optional[int] = Query(None, ge=0, description="总人数"),
    available: Optional[int] = Query(None, ge=0, description="可用人数"),
    service: TeamService = Depends(get_service),
) -> TeamResponse:
    """更新队伍人员数量"""
    return await service.update_personnel(team_id, total, available)


@router.get("/{team_id}/availability", response_model=TeamAvailabilityCheck)
async def check_team_availability(
    team_id: UUID,
    service: TeamService = Depends(get_service),
) -> TeamAvailabilityCheck:
    """检查队伍可用性"""
    return await service.check_availability(team_id)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: UUID,
    service: TeamService = Depends(get_service),
) -> None:
    """
    删除队伍
    
    限制: 已部署(deployed)状态的队伍不能删除
    """
    await service.delete(team_id)


@router.patch("/{team_id}/location", response_model=TeamLocationResponse)
async def update_team_location(
    team_id: UUID,
    data: TeamLocationUpdate,
    service: TeamService = Depends(get_service),
) -> TeamLocationResponse:
    """
    更新队伍当前位置
    
    由GPS遥测数据、手动输入或仿真模块调用。
    区别于base_location(驻地)，这是实时位置。
    """
    return await service.update_location(team_id, data)
