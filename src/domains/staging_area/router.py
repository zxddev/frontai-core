"""
救援队驻扎点选址 API 路由

遵循调用规范：Router → Service → Core
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.staging_area.service import StagingAreaService
from src.domains.staging_area.schemas import (
    StagingRecommendation,
    StagingRecommendationRequest,
    FindSafePointRequest,
    FindSafePointResponse,
    SafePointResult,
    SafePointFacilities,
)
from src.domains.staging_area.repository import StagingAreaRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/staging-area",
    tags=["staging-area"],
)


@router.post(
    "/recommend",
    response_model=StagingRecommendation,
    summary="推荐救援队驻扎点（纯算法模式）",
    description="""
    根据地震参数、救援目标和队伍信息，推荐安全的前沿驻扎点。
    
    **算法流程**：
    1. 计算风险区域（烈度影响 + 已标记危险区）
    2. 搜索候选点（PostGIS空间查询，排除危险区）
    3. 验证路径可行性（A*路径规划）
    4. 多目标评估排序（响应时间、安全性、后勤、设施、通信）
    
    **返回**：按总分排序的驻扎点推荐列表
    
    **注意**：此为纯算法接口，如需LLM分析请使用 /api/v2/ai/staging-area
    """,
)
async def recommend_staging_site(
    request: StagingRecommendationRequest,
    db: AsyncSession = Depends(get_db),
) -> StagingRecommendation:
    """
    推荐救援队驻扎点（纯算法模式）
    
    遵循调用规范：Router调用Service，Service调用Core
    """
    try:
        # 遵循调用规范：实例化Service，由Service管理Core
        service = StagingAreaService(db)
        result = await service.recommend(request)
        
        if not result.success and result.error:
            logger.warning(f"[驻扎点API] 推荐失败: {result.error}")
        
        return result
        
    except Exception as e:
        logger.error(f"[驻扎点API] 异常: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"驻扎点推荐失败: {str(e)}",
        )


@router.get(
    "/health",
    summary="健康检查",
)
async def health_check() -> dict:
    """
    健康检查端点
    """
    return {"status": "ok", "service": "staging-area"}


@router.post(
    "/find-safe-point",
    response_model=FindSafePointResponse,
    summary="查找安全点位",
    description="""
    根据中心坐标和筛选条件，查找符合要求的安全点位。
    
    **筛选条件**：
    - 距危险区最小缓冲距离
    - 最大坡度、最小面积
    - 水源、电源、直升机起降要求
    - 地面稳定性、通信网络类型
    - 距补给点/医疗点最大距离
    - 场地类型限定
    
    **返回**：按距离排序的安全点位列表，附带综合评分
    """,
)
async def find_safe_point(
    request: FindSafePointRequest,
    db: AsyncSession = Depends(get_db),
) -> FindSafePointResponse:
    """
    查找安全点位
    """
    import time
    start_time = time.perf_counter()
    
    try:
        repo = StagingAreaRepository(db)
        constraints = request.constraints
        
        sites = await repo.find_safe_points(
            scenario_id=request.scenario_id,
            center_lon=request.center_lon,
            center_lat=request.center_lat,
            search_radius_m=request.search_radius_m,
            min_buffer_m=constraints.min_buffer_m,
            max_slope_deg=constraints.max_slope_deg,
            min_area_m2=constraints.min_area_m2,
            require_water=constraints.require_water_supply,
            require_power=constraints.require_power_supply,
            require_helicopter=constraints.require_helicopter_landing,
            require_ground_stability=constraints.require_ground_stability,
            require_network_type=constraints.require_network_type,
            max_distance_to_supply_m=constraints.max_distance_to_supply_m,
            max_distance_to_medical_m=constraints.max_distance_to_medical_m,
            site_types=constraints.site_types,
            top_n=request.top_n,
        )
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        results = [
            SafePointResult(
                site_id=s["site_id"],
                site_code=s["site_code"],
                name=s["name"],
                longitude=s["longitude"],
                latitude=s["latitude"],
                site_type=s["site_type"],
                area_m2=s["area_m2"],
                slope_degree=s["slope_degree"],
                distance_m=s["distance_m"],
                distance_to_danger_m=s["distance_to_danger_m"],
                score=s["score"],
                facilities=SafePointFacilities(
                    has_water=s["has_water_supply"],
                    has_power=s["has_power_supply"],
                    can_helicopter=s["can_helicopter_land"],
                    network_type=s["primary_network_type"],
                    ground_stability=s["ground_stability"],
                ),
                nearest_supply_depot_m=s["nearest_supply_depot_m"],
                nearest_medical_point_m=s["nearest_medical_point_m"],
            )
            for s in sites
        ]
        
        return FindSafePointResponse(
            success=True,
            sites=results,
            total_candidates=len(results),
            elapsed_ms=elapsed_ms,
        )
        
    except Exception as e:
        logger.error(f"[安全点位API] 异常: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"安全点位查找失败: {str(e)}",
        )
