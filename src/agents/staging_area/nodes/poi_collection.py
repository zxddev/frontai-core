"""
POI数据采集节点

在StagingAreaAgent流程中动态采集候选点。
当数据库中候选点数量不足时，自动从高德API采集POI数据。

功能：
1. 检查数据库中已有候选点数量
2. 如果不足，调用高德API动态采集
3. 合并去重后返回
4. 自动将新采集的POI保存到数据库
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.staging_area.state import StagingAreaAgentState

logger = logging.getLogger(__name__)


def calculate_search_radius(magnitude: float) -> float:
    """
    根据震级计算搜索半径

    Args:
        magnitude: 震级

    Returns:
        搜索半径（米）
    """
    # 5级30km，每增加1级增加10km
    base_radius_km = 30 + (magnitude - 5) * 10
    return max(base_radius_km, 20) * 1000  # 最小20km


async def collect_poi_candidates(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    POI数据采集节点

    根据震中位置动态采集附近的POI作为候选驻扎点。
    与数据库中已有数据合并后返回。

    Args:
        state: Agent状态
        db: 数据库会话

    Returns:
        更新后的状态字典，包含：
        - poi_candidates: 新采集的POI候选点列表
        - poi_collection_count: 新采集的POI数量
        - poi_collection_enabled: 是否启用了POI采集
        - timing.poi_collection_ms: 采集耗时
    """
    start_time = time.perf_counter()

    logger.debug("[POI采集节点] 节点入口")

    # 获取参数
    epicenter_lon = state.get("epicenter_lon")
    epicenter_lat = state.get("epicenter_lat")
    magnitude = state.get("magnitude", 6.0)
    scenario_id = state.get("scenario_id")

    logger.debug(
        f"[POI采集节点] 输入参数: epicenter=({epicenter_lon}, {epicenter_lat}), "
        f"magnitude={magnitude}, scenario_id={scenario_id}"
    )

    # 参数验证
    if not all([epicenter_lon, epicenter_lat]):
        logger.warning("[POI采集节点] 缺少震中坐标，跳过POI采集")
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "poi_candidates": [],
            "poi_collection_count": 0,
            "poi_collection_enabled": False,
            "timing": {**state.get("timing", {}), "poi_collection_ms": elapsed_ms},
        }

    try:
        from src.domains.staging_area.poi_service import POICollectionService

        service = POICollectionService(db)

        # 计算搜索半径
        search_radius_m = calculate_search_radius(magnitude)
        logger.debug(f"[POI采集节点] 计算搜索半径: magnitude={magnitude} → radius={search_radius_m/1000:.1f}km")

        logger.info(
            f"[POI采集节点] 开始采集: 震中({epicenter_lon}, {epicenter_lat}), "
            f"震级={magnitude}, 半径={search_radius_m/1000:.1f}km"
        )

        # 采集并合并
        # min_candidates=10 表示数据库中少于10个候选点时才触发采集
        logger.debug("[POI采集节点] 调用 POICollectionService.collect_and_merge()")
        poi_candidates, new_count = await service.collect_and_merge(
            center_lon=epicenter_lon,
            center_lat=epicenter_lat,
            search_radius_m=search_radius_m,
            scenario_id=scenario_id,
            min_candidates=10,
            save_to_db=True,  # 自动保存新采集的POI
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        if new_count > 0:
            logger.info(
                f"[POI采集节点] 完成: 新采集 {new_count} 个POI, 耗时 {elapsed_ms}ms"
            )
        else:
            logger.info(
                f"[POI采集节点] 数据库数据充足，跳过采集, 耗时 {elapsed_ms}ms"
            )

        logger.debug(
            f"[POI采集节点] 节点出口: poi_candidates={len(poi_candidates)}, "
            f"new_count={new_count}, elapsed_ms={elapsed_ms}"
        )

        return {
            "poi_candidates": poi_candidates,
            "poi_collection_count": new_count,
            "poi_collection_enabled": True,
            "timing": {**state.get("timing", {}), "poi_collection_ms": elapsed_ms},
        }

    except Exception as e:
        logger.error(f"[POI采集节点] 采集失败: {e}", exc_info=True)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 采集失败不影响后续流程，只记录错误
        errors = state.get("errors", [])
        errors.append(f"POI采集失败: {str(e)}")

        return {
            "poi_candidates": [],
            "poi_collection_count": 0,
            "poi_collection_enabled": True,
            "errors": errors,
            "timing": {**state.get("timing", {}), "poi_collection_ms": elapsed_ms},
        }
