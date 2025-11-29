"""
资源计算节点 - 模块1-4, 6-8的Instructor封装

使用ResourcePlanner角色编排资源计算，结合Instructor结构化输出和SPHERE标准估算器。
"""

import logging
from typing import Any

import instructor

from src.agents.overall_plan.metagpt.estimators import EstimatorValidationError
from src.agents.overall_plan.metagpt.roles import ResourceCalculationError, ResourcePlanner
from src.agents.overall_plan.schemas import ResourceCalculationInput
from src.agents.overall_plan.state import OverallPlanState
from src.agents.overall_plan.instructor.client import (
    create_instructor_client,
    InstructorClientError,
)

logger = logging.getLogger(__name__)

# 领域相关的命名常量
DEFAULT_EMERGENCY_DURATION_DAYS = 3  # 默认应急期限（天）
SERIOUS_INJURY_RATIO = 0.25  # 重伤比例（约25%）


async def resource_calculation_node(
    state: OverallPlanState,
    client: instructor.AsyncInstructor | None = None,
) -> dict[str, Any]:
    """
    使用ResourcePlanner和Instructor执行资源计算

    生成模块1-4和6-8，使用：
    1. SPHERE标准计算（确定性）
    2. Instructor结构化LLM输出
    3. Jinja2模板保证格式一致

    Args:
        state: 当前工作流状态
        client: 可选的Instructor客户端（若未提供则创建默认客户端）

    Returns:
        状态更新字典，包含模块1-4, 6-8和计算详情

    Raises:
        ResourceCalculationError: 计算失败时抛出
        EstimatorValidationError: 输入验证失败时抛出
        InstructorClientError: 结构化输出生成失败时抛出
    """
    event_id = state.get("event_id", "unknown")
    logger.info("开始资源计算", extra={"event_id": event_id})

    try:
        # 若未提供客户端则创建
        if client is None:
            client = create_instructor_client()

        # 从状态构建输入
        input_data = _build_calculation_input(state)

        # 执行ResourcePlanner
        planner = ResourcePlanner(client)
        output = await planner.run(input_data)

        logger.info("资源计算完成", extra={"event_id": event_id})

        return {
            "module_1_rescue_force": output.module_1_rescue_force,
            "module_2_medical": output.module_2_medical,
            "module_3_infrastructure": output.module_3_infrastructure,
            "module_4_shelter": output.module_4_shelter,
            "module_6_communication": output.module_6_communication,
            "module_7_logistics": output.module_7_logistics,
            "module_8_self_support": output.module_8_self_support,
            "calculation_details": output.calculation_details,
            "current_phase": "resource_calculation_completed",
        }

    except (ResourceCalculationError, EstimatorValidationError, InstructorClientError):
        raise
    except Exception as e:
        logger.exception("资源计算失败", extra={"event_id": event_id})
        raise ResourceCalculationError(f"资源计算失败: {e}") from e


def _build_calculation_input(state: OverallPlanState) -> ResourceCalculationInput:
    """
    从状态构建ResourceCalculationInput

    从event_data和module_0_basic_disaster提取数值。
    """
    event_data = state.get("event_data", {})
    module_0 = state.get("module_0_basic_disaster", {})

    # 优先使用module_0数据（CrewAI分析结果），否则回退到event_data

    return ResourceCalculationInput(
        affected_population=_get_int(module_0, event_data, "affected_population", 0),
        trapped_count=_get_int(module_0, event_data, "trapped", 0),
        injured_count=_get_int(module_0, event_data, "injuries", 0),
        serious_injury_count=_estimate_serious_injuries(
            _get_int(module_0, event_data, "injuries", 0)
        ),
        emergency_duration_days=DEFAULT_EMERGENCY_DURATION_DAYS,
        buildings_collapsed=_get_int(module_0, event_data, "buildings_collapsed", 0),
        buildings_damaged=_get_int(module_0, event_data, "buildings_damaged", 0),
        roads_damaged_km=_get_float(event_data, "roads_damaged_km", 0.0),
        bridges_damaged=_get_int(event_data, {}, "bridges_damaged", 0),
        power_outage_households=_get_int(event_data, {}, "power_outage_households", 0),
        communication_towers_damaged=_get_int(event_data, {}, "communication_towers_damaged", 0),
        disaster_type=module_0.get("disaster_type") or event_data.get("type", "unknown"),
        affected_area=module_0.get("affected_area") or _format_location(event_data),
    )


def _get_int(
    primary: dict[str, object],
    fallback: dict[str, object],
    key: str,
    default: int,
) -> int:
    """
    从主字典获取整数值，失败则回退到备用字典

    正确处理None、空字符串和0值。
    """
    val = primary.get(key)
    if val is not None and val != "":
        try:
            return int(val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            pass
    val = fallback.get(key)
    if val is not None and val != "":
        try:
            return int(val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            pass
    return default


def _get_float(
    data: dict[str, object],
    key: str,
    default: float,
) -> float:
    """
    从字典获取浮点数值

    正确处理None、空字符串和0值。
    """
    val = data.get(key)
    if val is not None and val != "":
        try:
            return float(val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            pass
    return default


def _estimate_serious_injuries(total_injuries: int) -> int:
    """
    基于SERIOUS_INJURY_RATIO估算重伤人数

    Args:
        total_injuries: 总伤员人数

    Returns:
        估算的重伤人数（有伤员时至少为1）
    """
    if total_injuries <= 0:
        return 0
    return max(1, int(total_injuries * SERIOUS_INJURY_RATIO))


def _format_location(event_data: dict) -> str:
    """从事件数据格式化地点字符串"""
    location = event_data.get("location", {})
    if isinstance(location, dict):
        parts = []
        for key in ["province", "city", "district"]:
            if location.get(key):
                parts.append(location[key])
        if parts:
            return "".join(parts)
    return "未知区域"
