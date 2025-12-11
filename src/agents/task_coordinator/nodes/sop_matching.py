"""
SOP 匹配节点

从 Neo4j 知识图谱查询匹配的 SOP 模板。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, Optional

from ..state import TaskCoordinatorState
from ..schemas import SOPTemplate, CoordinatorWarning

logger = logging.getLogger(__name__)


# SOP 模板缓存（避免重复查询）
_SOP_CACHE: Dict[str, SOPTemplate] = {}


async def _query_sop_from_neo4j(
    disaster_type: str,
    scene_code: Optional[str] = None,
) -> Optional[SOPTemplate]:
    """
    从 Neo4j 查询 SOP 模板

    Args:
        disaster_type: 灾害类型
        scene_code: 场景代码（可选，更精确匹配）

    Returns:
        匹配的 SOPTemplate 或 None
    """
    # 检查缓存
    cache_key = f"{disaster_type}:{scene_code or 'default'}"
    if cache_key in _SOP_CACHE:
        logger.debug(f"[SOP匹配] 命中缓存: {cache_key}")
        return _SOP_CACHE[cache_key]

    try:
        from src.infra.settings import load_settings
        from neo4j import AsyncGraphDatabase

        settings = load_settings()
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

        async with driver.session() as session:
            # 优先按 scene_code 匹配，其次按 disaster_type
            if scene_code:
                query = """
                MATCH (sop:SOPTemplate)
                WHERE sop.scene_code = $scene_code
                   OR sop.disaster_type = $disaster_type
                RETURN sop
                ORDER BY CASE WHEN sop.scene_code = $scene_code THEN 0 ELSE 1 END
                LIMIT 1
                """
                result = await session.run(
                    query,
                    scene_code=scene_code,
                    disaster_type=disaster_type,
                )
            else:
                query = """
                MATCH (sop:SOPTemplate)
                WHERE sop.disaster_type = $disaster_type
                RETURN sop
                LIMIT 1
                """
                result = await session.run(query, disaster_type=disaster_type)

            record = await result.single()
            if record:
                sop_data = dict(record["sop"])
                sop = SOPTemplate(
                    id=sop_data.get("id", ""),
                    name=sop_data.get("name", ""),
                    disaster_type=sop_data.get("disaster_type", ""),
                    scene_code=sop_data.get("scene_code", ""),
                    description=sop_data.get("description"),
                    version=sop_data.get("version", "1.0"),
                    total_steps=sop_data.get("total_steps", 0),
                    estimated_duration_minutes=sop_data.get("estimated_duration_minutes", 0),
                )
                # 缓存结果
                _SOP_CACHE[cache_key] = sop
                return sop

        await driver.close()

    except Exception as e:
        logger.warning(f"[SOP匹配] Neo4j 查询失败: {e}，使用默认 SOP")

    return None


def _get_fallback_sop(disaster_type: str) -> SOPTemplate:
    """
    获取默认 SOP 模板（当 Neo4j 查询失败时）

    Args:
        disaster_type: 灾害类型

    Returns:
        默认 SOPTemplate
    """
    # 默认 SOP 映射
    default_sops = {
        "earthquake": SOPTemplate(
            id="SOP-EARTHQUAKE-BUILDING-COLLAPSE",
            name="地震建筑倒塌救援SOP",
            disaster_type="earthquake",
            scene_code="building_collapse",
            total_steps=4,
            estimated_duration_minutes=165,
        ),
        "hazmat": SOPTemplate(
            id="SOP-HAZMAT-LEAK",
            name="危化品泄漏处置SOP",
            disaster_type="hazmat",
            scene_code="chemical_leak",
            total_steps=5,
            estimated_duration_minutes=210,
        ),
        "fire": SOPTemplate(
            id="SOP-FIRE-SUPPRESSION",
            name="火灾扑救SOP",
            disaster_type="fire",
            scene_code="building_fire",
            total_steps=4,
            estimated_duration_minutes=150,
        ),
        "flood": SOPTemplate(
            id="SOP-FLOOD-RESCUE",
            name="洪水救援SOP",
            disaster_type="flood",
            scene_code="flood_rescue",
            total_steps=4,
            estimated_duration_minutes=180,
        ),
    }

    # 尝试匹配
    for key, sop in default_sops.items():
        if key in disaster_type.lower():
            return sop

    # 通用默认
    return SOPTemplate(
        id="SOP-GENERIC-RESCUE",
        name="通用救援SOP",
        disaster_type="generic",
        scene_code="generic_rescue",
        total_steps=3,
        estimated_duration_minutes=120,
    )


async def match_sop(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    SOP 匹配节点

    根据灾害类型和场景代码匹配最合适的 SOP 模板。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info("[TaskCoordinator] 匹配 SOP 模板")
    start_time = time.time()

    task_allocation = state.get("task_allocation")
    disaster_info = state.get("disaster_info", {})
    warnings = list(state.get("warnings", []))

    # 提取匹配参数
    disaster_type = task_allocation.disaster_type
    if disaster_type == "unknown":
        disaster_type = disaster_info.get("disaster_type", "unknown")

    scene_code = task_allocation.scene_code
    if not scene_code:
        scene_code = disaster_info.get("scene_code")

    # 查询 Neo4j
    matched_sop = await _query_sop_from_neo4j(disaster_type, scene_code)

    # 如果查询失败，使用默认 SOP
    if not matched_sop:
        matched_sop = _get_fallback_sop(disaster_type)
        warnings.append(CoordinatorWarning(
            code="SOP_FALLBACK",
            message=f"使用默认 SOP 模板: {matched_sop.name}",
            severity="info",
        ))
        match_score = 0.7
        match_reason = "使用默认模板（Neo4j 查询失败或无匹配）"
    else:
        # 计算匹配分数
        if scene_code and matched_sop.scene_code == scene_code:
            match_score = 1.0
            match_reason = f"场景代码精确匹配: {scene_code}"
        elif matched_sop.disaster_type == disaster_type:
            match_score = 0.9
            match_reason = f"灾害类型匹配: {disaster_type}"
        else:
            match_score = 0.8
            match_reason = "部分匹配"

    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"[TaskCoordinator] SOP 匹配完成: "
        f"sop_id={matched_sop.id}, "
        f"score={match_score}, "
        f"reason={match_reason}"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_sop"]
    trace["sop_match_score"] = match_score

    return {
        "matched_sop": matched_sop,
        "sop_match_score": match_score,
        "sop_match_reason": match_reason,
        "warnings": warnings,
        "trace": trace,
        "current_phase": "decompose_steps",
        "execution_time_ms": state.get("execution_time_ms", 0) + elapsed_ms,
    }
