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
)

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
