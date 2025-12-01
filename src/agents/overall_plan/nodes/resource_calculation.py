"""
资源计算节点 - 已由CrewAI在situational_awareness节点完成

此节点现在只做简单的数据聚合和验证，主要内容由CrewAI生成。
"""

import logging
from typing import Any

from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


class ResourceCalculationError(Exception):
    """资源计算失败"""
    pass


async def resource_calculation_node(
    state: OverallPlanState,
) -> dict[str, Any]:
    """资源计算节点
    
    CrewAI已在situational_awareness节点生成所有模块内容。
    此节点只做数据验证和聚合。

    Args:
        state: 当前工作流状态

    Returns:
        状态更新
    """
    event_id = state.get("event_id", "unknown")
    logger.info(f"Resource calculation node for event {event_id}")

    try:
        # 检查CrewAI是否已生成所有模块
        module_keys = [
            "module_0_basic_disaster",
            "module_1_rescue_force",
            "module_2_medical",
            "module_3_infrastructure",
            "module_4_shelter",
            "module_5_secondary_disaster",
            "module_6_communication",
            "module_7_logistics",
            "module_8_self_support",
        ]
        
        missing_modules = []
        for key in module_keys:
            if not state.get(key):
                missing_modules.append(key)
        
        if missing_modules:
            logger.warning(f"Missing modules from CrewAI: {missing_modules}")
        
        # 聚合计算详情
        event_data = state.get("event_data", {})
        scenario_data = state.get("scenario_data", {})
        
        calculation_details = {
            "trapped_count": event_data.get("trapped", 0),
            "injured_count": event_data.get("injuries", 0),
            "affected_population": scenario_data.get("affected_population", 0),
            "emergency_duration_days": 3,
            "calculation_basis": "CrewAI + SPHERE国际人道主义标准",
        }

        logger.info(f"Resource calculation completed for event {event_id}")

        return {
            "calculation_details": calculation_details,
            "current_phase": "resource_calculation_completed",
        }

    except Exception as e:
        logger.exception(f"Resource calculation failed for event {event_id}")
        raise ResourceCalculationError(f"Resource calculation failed: {e}") from e
