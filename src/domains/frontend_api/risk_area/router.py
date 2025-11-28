"""
风险区域API路由

接口路径: /risk-area/*
提供风险区域的创建、查询、更新、删除等接口
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from .service import RiskAreaService
from .schemas import (
    RiskAreaCreateRequest,
    RiskAreaUpdateRequest,
    PassageStatusUpdateRequest,
    RiskAreaResponse,
    RiskAreaListResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk-area", tags=["前端-风险区域"])


def get_service(db: AsyncSession = Depends(get_db)) -> RiskAreaService:
    """获取风险区域服务实例"""
    return RiskAreaService(db)


@router.post("", response_model=ApiResponse[dict])
async def create_risk_area(
    request: RiskAreaCreateRequest,
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    创建风险区域
    
    在指定想定下创建一个新的风险区域，用于标记危险区、封锁区等。
    
    **风险分级规则**：
    - risk_level 9-10: 红色高危区，建议 passage_status=confirmed_blocked
    - risk_level 7-8: 橙色危险区，建议 passage_status=needs_reconnaissance  
    - risk_level 5-6: 黄色警告区，建议 passage_status=passable_with_caution
    - risk_level 1-4: 绿色安全区，建议 passage_status=clear
    
    **区域类型**：
    - danger_zone: 危险区
    - blocked: 封锁区
    - damaged: 损坏区
    - flooded: 淹没区
    - contaminated: 污染区
    - landslide: 滑坡区
    - fire: 火灾区
    - seismic_red/orange/yellow: 地震影响区
    
    **请求示例**：
    ```json
    {
        "scenarioId": "550e8400-e29b-41d4-a716-446655440000",
        "name": "北川滑坡危险区",
        "areaType": "landslide",
        "riskLevel": 9,
        "severity": "critical",
        "passageStatus": "confirmed_blocked",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[104.5, 31.2], [104.6, 31.2], [104.6, 31.3], [104.5, 31.3], [104.5, 31.2]]]
        },
        "passable": false,
        "speedReductionPercent": 100,
        "reconnaissanceRequired": false,
        "description": "因暴雨引发滑坡，道路完全中断"
    }
    ```
    """
    logger.info(
        f"创建风险区域请求: scenario={request.scenario_id}, "
        f"name={request.name}, type={request.area_type.value}"
    )
    
    try:
        result = await service.create(request)
        return ApiResponse.success(
            result.model_dump(by_alias=True),
            f"风险区域创建成功: {request.name}"
        )
    except Exception as e:
        logger.exception(f"创建风险区域失败: {e}")
        return ApiResponse.error(500, f"创建风险区域失败: {str(e)}")


@router.get("", response_model=ApiResponse[dict])
async def list_risk_areas(
    scenarioId: UUID = Query(..., description="想定ID"),
    areaType: Optional[str] = Query(None, description="区域类型筛选"),
    minRiskLevel: Optional[int] = Query(None, ge=1, le=10, description="最低风险等级"),
    passageStatus: Optional[str] = Query(None, description="通行状态筛选"),
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    获取风险区域列表
    
    查询指定想定下的所有风险区域，支持按类型、风险等级、通行状态筛选。
    结果按风险等级降序、创建时间降序排列。
    """
    logger.info(f"查询风险区域列表: scenario={scenarioId}")
    
    try:
        result = await service.list_by_scenario(
            scenario_id=scenarioId,
            area_type=areaType,
            min_risk_level=minRiskLevel,
            passage_status=passageStatus,
        )
        return ApiResponse.success(result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(f"查询风险区域列表失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")


@router.get("/{area_id}", response_model=ApiResponse[dict])
async def get_risk_area(
    area_id: UUID,
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    获取风险区域详情
    
    根据区域ID获取单个风险区域的详细信息。
    """
    logger.info(f"查询风险区域详情: id={area_id}")
    
    try:
        result = await service.get_by_id(area_id)
        if not result:
            return ApiResponse.error(404, "风险区域不存在")
        return ApiResponse.success(result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(f"查询风险区域详情失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")


@router.put("/{area_id}", response_model=ApiResponse[dict])
async def update_risk_area(
    area_id: UUID,
    request: RiskAreaUpdateRequest,
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    更新风险区域
    
    更新风险区域的属性，支持部分更新。
    仅传入需要更新的字段即可。
    """
    logger.info(f"更新风险区域: id={area_id}")
    
    try:
        result = await service.update(area_id, request)
        if not result:
            return ApiResponse.error(404, "风险区域不存在")
        return ApiResponse.success(
            result.model_dump(by_alias=True),
            "风险区域更新成功"
        )
    except Exception as e:
        logger.exception(f"更新风险区域失败: {e}")
        return ApiResponse.error(500, f"更新失败: {str(e)}")


@router.patch("/{area_id}/passage-status", response_model=ApiResponse[dict])
async def update_passage_status(
    area_id: UUID,
    request: PassageStatusUpdateRequest,
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    更新通行状态
    
    专门用于更新风险区域的通行状态，通常在侦察任务完成后调用。
    会自动记录验证时间和验证者ID。
    
    **通行状态**：
    - confirmed_blocked: 已确认完全不可通行（塌方、断桥、深水）
    - needs_reconnaissance: 需侦察确认
    - passable_with_caution: 可通行但需谨慎（降速、救援车辆优先）
    - clear: 已确认安全通行
    - unknown: 未知状态
    
    **请求示例**：
    ```json
    {
        "passageStatus": "confirmed_blocked",
        "verifiedBy": "550e8400-e29b-41d4-a716-446655440001"
    }
    ```
    """
    logger.info(f"更新风险区域通行状态: id={area_id}, status={request.passage_status.value}")
    
    try:
        result = await service.update_passage_status(area_id, request)
        if not result:
            return ApiResponse.error(404, "风险区域不存在")
        return ApiResponse.success(
            result.model_dump(by_alias=True),
            f"通行状态已更新为: {request.passage_status.value}"
        )
    except Exception as e:
        logger.exception(f"更新通行状态失败: {e}")
        return ApiResponse.error(500, f"更新失败: {str(e)}")


@router.delete("/{area_id}", response_model=ApiResponse)
async def delete_risk_area(
    area_id: UUID,
    service: RiskAreaService = Depends(get_service),
) -> ApiResponse:
    """
    删除风险区域
    
    根据区域ID删除风险区域。删除后无法恢复。
    """
    logger.info(f"删除风险区域: id={area_id}")
    
    try:
        success = await service.delete(area_id)
        if not success:
            return ApiResponse.error(404, "风险区域不存在")
        return ApiResponse.success(None, "风险区域删除成功")
    except Exception as e:
        logger.exception(f"删除风险区域失败: {e}")
        return ApiResponse.error(500, f"删除失败: {str(e)}")
