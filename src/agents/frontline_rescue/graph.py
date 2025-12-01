"""LangGraph StateGraph for Frontline multi-event rescue dispatch."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.agents.frontline_rescue.nodes import (
    allocate_resources_node,
    hard_rules_check_node,
    human_review_node,
    load_context_node,
    prioritize_events_node,
)
from src.agents.frontline_rescue.state import FrontlineRescueState


logger = logging.getLogger(__name__)


def _handle_error(state: FrontlineRescueState, error: Exception, phase: str) -> dict[str, Any]:
    """统一错误处理：在状态中记录错误并标记失败。"""

    errors = list(state.get("errors", []))
    errors.append(f"{phase}: {error}")
    return {
        "status": "failed",
        "current_phase": f"{phase}_failed",
        "errors": errors,
    }


async def _safe_load_context(state: FrontlineRescueState) -> dict[str, Any]:
    try:
        return await load_context_node(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] load_context failed")
        return _handle_error(state, exc, "load_context")


async def _safe_prioritize_events(state: FrontlineRescueState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    try:
        return await prioritize_events_node(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] prioritize_events failed")
        return _handle_error(state, exc, "prioritize_events")


async def _safe_allocate_resources(state: FrontlineRescueState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    try:
        return await allocate_resources_node(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] allocate_resources failed")
        return _handle_error(state, exc, "allocate_resources")


async def _safe_hard_rules_check(state: FrontlineRescueState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    try:
        return await hard_rules_check_node(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] hard_rules_check failed")
        return _handle_error(state, exc, "hard_rules_check")


async def _safe_human_review(state: FrontlineRescueState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    try:
        return human_review_node(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] human_review failed")
        return _handle_error(state, exc, "human_review")


def build_frontline_rescue_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Build the Frontline multi-event rescue StateGraph.

    当前版本的工作流较为简单：
      load_context -> prioritize_events -> END
    后续可以在此基础上扩展资源分配、硬规则检查和 HITL 审核节点。
    """

    logger.info("[Frontline] Building frontline rescue graph")

    graph = StateGraph(FrontlineRescueState)

    graph.add_node("load_context", _safe_load_context)
    graph.add_node("prioritize_events", _safe_prioritize_events)
    graph.add_node("allocate_resources", _safe_allocate_resources)
    graph.add_node("hard_rules_check", _safe_hard_rules_check)
    graph.add_node("human_review", _safe_human_review)

    graph.add_edge("load_context", "prioritize_events")
    graph.add_edge("prioritize_events", "allocate_resources")
    graph.add_edge("allocate_resources", "hard_rules_check")
    graph.add_edge("hard_rules_check", "human_review")
    graph.add_edge("human_review", END)

    graph.set_entry_point("load_context")

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[Frontline] Frontline rescue graph built successfully")
    return compiled


__all__ = ["build_frontline_rescue_graph"]
