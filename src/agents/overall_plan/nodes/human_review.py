"""Human Review Node - HITL checkpoint for commander approval.

此节点暂停执行，等待指挥员审核总体方案。
"""

import logging
from typing import Any, Literal

from langgraph.types import Command, interrupt

from src.agents.overall_plan.schemas import MODULE_TITLES
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


def human_review_node(
    state: OverallPlanState,
) -> Command[Literal["document_generation", "__end__"]]:
    """Human review checkpoint node.

    暂停执行等待指挥员审核。
    指挥员可以批准（进入文档生成）或退回（结束流程）。

    Args:
        state: 当前工作流状态，包含CrewAI生成的所有模块

    Returns:
        Command指向document_generation或__end__
    """
    import sys
    
    # 前置节点失败时直接结束，不触发interrupt
    if state.get("status") == "failed":
        logger.warning("Skipping human_review due to previous failure")
        return Command(goto="__end__", update={})

    event_id = state.get("event_id", "unknown")
    task_id = state.get("task_id", "unknown")
    logger.info(f"Entering human review for event {event_id}, task {task_id}")

    # 准备审核数据
    review_data = _prepare_review_data(state)

    # Python < 3.11 在异步上下文中 interrupt 不可用（contextvar 传播问题）
    # 直接标记为 awaiting_approval 状态，让 router 轮询获取 modules
    if sys.version_info < (3, 11):
        logger.info(f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.11, "
                    "skipping interrupt, returning modules directly")
        return Command(
            goto="__end__",
            update={
                "status": "awaiting_approval",
                "current_phase": "human_review_ready",
                "review_data": review_data,
            }
        )

    # Python >= 3.11 使用正常的 interrupt 流程
    review_result = interrupt(review_data)

    # 处理审核结果
    decision = review_result.get("decision", "reject")
    feedback = review_result.get("feedback", "")
    modifications = review_result.get("modifications", {})

    logger.info(f"Commander decision for task {task_id}: {decision}")

    # 构建状态更新
    update: dict[str, Any] = {
        "commander_feedback": feedback,
    }

    # 应用修改
    if modifications:
        for key, value in modifications.items():
            if key.startswith("module_") and isinstance(value, str):
                update[key] = value
                logger.debug(f"Applied modification to {key}")

    if decision == "approve":
        update["approved"] = True
        update["status"] = "running"
        update["current_phase"] = "human_review_approved"
        logger.info(f"Plan approved for task {task_id}")
        return Command(goto="document_generation", update=update)
    else:
        update["approved"] = False
        update["status"] = "failed"
        update["current_phase"] = "human_review_rejected"
        errors = state.get("errors", [])
        errors.append(f"rejected_by_commander: {feedback}" if feedback else "rejected_by_commander")
        update["errors"] = errors
        logger.warning(f"Plan rejected for task {task_id}")
        return Command(goto="__end__", update=update)


def _prepare_review_data(state: OverallPlanState) -> dict[str, Any]:
    """准备审核数据
    
    将CrewAI生成的模块整理为前端可用的格式。
    """
    modules = []

    # 模块0: 总体描述
    module_0 = state.get("module_0_basic_disaster", "")
    if isinstance(module_0, dict):
        overview = _generate_overview_from_dict(module_0)
    else:
        overview = str(module_0) if module_0 else "（待生成）"
    
    modules.append({
        "index": 0,
        "title": MODULE_TITLES[0],
        "value": overview,
        "type": "text",
    })

    # 模块1: 当前灾情初步评估
    modules.append({
        "index": 1,
        "title": MODULE_TITLES[1],
        "value": module_0 if isinstance(module_0, dict) else {"raw": str(module_0)},
        "type": "structured",
    })

    # 模块2: 组织指挥（目前由CrewAI生成，但可能为空）
    modules.append({
        "index": 2,
        "title": MODULE_TITLES[2],
        "value": "（待完善：组织指挥结构）",
        "type": "text",
    })

    # 模块3: 救援力量部署 - 合并module_1到module_4
    chapter_3 = _merge_rescue_modules(state)
    modules.append({
        "index": 3,
        "title": MODULE_TITLES[3],
        "value": chapter_3,
        "type": "text",
    })

    # 模块4: 次生灾害
    module_5 = state.get("module_5_secondary_disaster", "")
    if isinstance(module_5, dict):
        secondary_text = module_5.get("narrative", str(module_5))
    else:
        secondary_text = str(module_5) if module_5 else "（待生成）"
    
    modules.append({
        "index": 4,
        "title": MODULE_TITLES[4],
        "value": secondary_text,
        "type": "text",
    })

    # 模块5: 通信保障
    module_6 = state.get("module_6_communication", "")
    modules.append({
        "index": 5,
        "title": MODULE_TITLES[5],
        "value": str(module_6) if module_6 else "（待生成）",
        "type": "text",
    })

    # 模块6: 物资调配
    module_7 = state.get("module_7_logistics", "")
    modules.append({
        "index": 6,
        "title": MODULE_TITLES[6],
        "value": str(module_7) if module_7 else "（待生成）",
        "type": "text",
    })

    # 模块7: 自身保障
    module_8 = state.get("module_8_self_support", "")
    modules.append({
        "index": 7,
        "title": MODULE_TITLES[7],
        "value": str(module_8) if module_8 else "（待生成）",
        "type": "text",
    })

    return {
        "event_id": state.get("event_id"),
        "task_id": state.get("task_id"),
        "modules": modules,
        "calculation_details": state.get("calculation_details", {}),
        "message": "请审核以下总体救灾方案各模块内容，确认无误后点击批准。",
    }


def _generate_overview_from_dict(basic_disaster: dict[str, Any]) -> str:
    """从灾情数据生成总体描述"""
    if not basic_disaster:
        return "（待生成：总体描述）"
    
    name = basic_disaster.get("disaster_name", "未知灾害")
    dtype = basic_disaster.get("disaster_type", "未知")
    area = basic_disaster.get("affected_area", "未知地区")
    time = basic_disaster.get("occurrence_time", "未知时间")
    trapped = basic_disaster.get("trapped", 0)
    injuries = basic_disaster.get("injuries", 0)
    deaths = basic_disaster.get("deaths", 0)
    
    return f"""本方案针对{name}制定总体救灾部署。

灾害类型：{dtype}
发生地点：{area}
发生时间：{time}
当前伤亡情况：死亡{deaths}人，受伤{injuries}人，被困{trapped}人

本方案按照国家应急预案和SPHERE国际人道主义标准，对救援力量部署、医疗救护、工程抢险、物资保障等方面进行统一规划。"""


def _merge_rescue_modules(state: OverallPlanState) -> str:
    """合并救援相关模块为第三章"""
    sections = []
    
    # 救援力量
    module_1 = state.get("module_1_rescue_force", "")
    if module_1:
        sections.append(f"（一）应急救援力量\n{module_1}")
    
    # 医疗救护
    module_2 = state.get("module_2_medical", "")
    if module_2:
        sections.append(f"（二）医疗救护\n{module_2}")
    
    # 工程抢险
    module_3 = state.get("module_3_infrastructure", "")
    if module_3:
        sections.append(f"（三）工程抢险\n{module_3}")
    
    # 群众安置
    module_4 = state.get("module_4_shelter", "")
    if module_4:
        sections.append(f"（四）群众安置\n{module_4}")
    
    return "\n\n".join(sections) if sections else "（待生成：救援力量部署）"
