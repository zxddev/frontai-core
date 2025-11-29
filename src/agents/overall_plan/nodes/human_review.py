"""Human Review Node - HITL checkpoint for commander approval.

This node implements the interrupt mechanism for human-in-the-loop
review, allowing commanders to approve or reject the generated plan.
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

    This node pauses execution and waits for commander review.
    The commander can approve (proceed to document generation) or
    reject (end workflow with failed status).

    Args:
        state: Current workflow state with all 9 modules

    Returns:
        Command to either proceed to document_generation or end
    """
    event_id = state.get("event_id", "unknown")
    task_id = state.get("task_id", "unknown")
    logger.info(f"Entering human review for event {event_id}, task {task_id}")

    # Prepare review data for the commander
    review_data = _prepare_review_data(state)

    # Interrupt and wait for human input
    # The resume will provide: {"decision": "approve"|"reject", "feedback": "...", "modifications": {...}}
    review_result = interrupt(review_data)

    # Process the review result
    decision = review_result.get("decision", "reject")
    feedback = review_result.get("feedback", "")
    modifications = review_result.get("modifications", {})

    logger.info(f"Commander decision for task {task_id}: {decision}")

    # Build state update
    update: dict[str, Any] = {
        "commander_feedback": feedback,
    }

    # Apply any modifications
    if modifications:
        for key, value in modifications.items():
            if key.startswith("module_") and isinstance(value, str):
                update[key] = value
                logger.debug(f"Applied modification to {key}")

    if decision == "approve":
        update["approved"] = True
        update["status"] = "running"
        update["current_phase"] = "human_review_approved"
        logger.info(f"Plan approved for task {task_id}, proceeding to document generation")
        return Command(goto="document_generation", update=update)
    else:
        # Explicit rejection - mark as failed, do not auto-retry
        update["approved"] = False
        update["status"] = "failed"
        update["current_phase"] = "human_review_rejected"
        errors = state.get("errors", [])
        errors.append(f"rejected_by_commander: {feedback}" if feedback else "rejected_by_commander")
        update["errors"] = errors
        logger.warning(f"Plan rejected for task {task_id}")
        return Command(goto="__end__", update=update)


def _prepare_review_data(state: OverallPlanState) -> dict[str, Any]:
    """Prepare data for commander review.

    Structures the 9 modules and calculation details in a format
    suitable for the frontend review interface.
    """
    modules = []

    # Module 0
    module_0 = state.get("module_0_basic_disaster", {})
    modules.append({
        "index": 0,
        "title": MODULE_TITLES[0],
        "value": module_0,
        "type": "structured",
    })

    # Modules 1-4
    for i in range(1, 5):
        key = f"module_{i}_{'rescue_force' if i == 1 else 'medical' if i == 2 else 'infrastructure' if i == 3 else 'shelter'}"
        modules.append({
            "index": i,
            "title": MODULE_TITLES[i],
            "value": state.get(key, ""),
            "type": "text",
        })

    # Module 5
    module_5 = state.get("module_5_secondary_disaster", {})
    modules.append({
        "index": 5,
        "title": MODULE_TITLES[5],
        "value": module_5,
        "type": "structured",
    })

    # Modules 6-8
    for i in range(6, 9):
        key = f"module_{i}_{'communication' if i == 6 else 'logistics' if i == 7 else 'self_support'}"
        modules.append({
            "index": i,
            "title": MODULE_TITLES[i],
            "value": state.get(key, ""),
            "type": "text",
        })

    return {
        "event_id": state.get("event_id"),
        "task_id": state.get("task_id"),
        "modules": modules,
        "calculation_details": state.get("calculation_details", {}),
        "message": "请审核以下总体救灾方案各模块内容，确认无误后点击批准，如有问题可退回修改。",
    }
