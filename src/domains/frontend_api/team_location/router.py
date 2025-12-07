"""
救援队伍位置查询API路由

接口路径: /team-location/*
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    TeamLocationListResponse,
    TeamLocationBatchRequest,
    TeamLocationBatchResponse,
)
from .service import TeamLocationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team-location", tags=["前端-队伍位置"])


def get_service(db: AsyncSession = Depends(get_db)) -> TeamLocationService:
    return TeamLocationService(db)


@router.get("/list", response_model=ApiResponse[TeamLocationListResponse])
async def list_team_locations(
    scenarioId: Optional[str] = Query(None, description="场景ID，默认查活动场景"),
    status: Optional[str] = Query(None, description="队伍状态筛选: standby/deployed/resting/unavailable"),
    teamType: Optional[str] = Query(None, description="队伍类型筛选"),
    convertToGcj02: bool = Query(True, description="是否转换为高德坐标系(GCJ02)"),
    service: TeamLocationService = Depends(get_service),
) -> ApiResponse[TeamLocationListResponse]:
    """
    查询救援队伍位置列表

    根据场景ID查询关联的救援队伍位置信息。
    未指定场景ID时，自动查询当前活动场景。

    位置数据优先使用实时位置(current_location)，回退到驻地位置(base_location)。
    超过30分钟未更新的位置会标记为 locationStale=true。
    """
    logger.info(
        f"查询队伍位置列表: scenarioId={scenarioId}, "
        f"status={status}, teamType={teamType}, convertToGcj02={convertToGcj02}"
    )

    try:
        result = await service.list_team_locations(
            scenario_id=scenarioId,
            status=status,
            team_type=teamType,
            convert_to_gcj02=convertToGcj02,
        )
        return ApiResponse.success(result)
    except Exception as e:
        logger.exception(f"查询队伍位置列表失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")


@router.post("/batch", response_model=ApiResponse[TeamLocationBatchResponse])
async def batch_team_locations(
    request: TeamLocationBatchRequest,
    service: TeamLocationService = Depends(get_service),
) -> ApiResponse[TeamLocationBatchResponse]:
    """
    批量查询指定队伍的位置

    根据队伍ID列表批量查询位置信息，最多支持100个队伍。

    位置数据优先使用实时位置(current_location)，回退到驻地位置(base_location)。
    无位置数据的队伍返回 hasLocation=false。
    """
    logger.info(f"批量查询队伍位置: {len(request.teamIds)} 个队伍")

    try:
        result = await service.batch_team_locations(
            team_ids=request.teamIds,
            convert_to_gcj02=request.convertToGcj02,
        )
        return ApiResponse.success(result)
    except Exception as e:
        logger.exception(f"批量查询队伍位置失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")
