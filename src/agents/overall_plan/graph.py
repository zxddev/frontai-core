"""LangGraph State Graph definition for Overall Plan Generation.

This module defines the workflow graph that orchestrates:
1. Data loading (load_context)
2. Situational awareness (CrewAI)
3. Resource calculation (MetaGPT)
4. Human review (HITL interrupt)
5. Document generation (MetaGPT)
"""

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.agents.overall_plan.nodes.document_generation import document_generation_node
from src.agents.overall_plan.nodes.human_review import human_review_node
from src.agents.overall_plan.nodes.load_context import load_context_node
from src.agents.overall_plan.nodes.resource_calculation import resource_calculation_node
from src.agents.overall_plan.nodes.situational_awareness import situational_awareness_node
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


def _handle_error(state: OverallPlanState, error: Exception, phase: str) -> dict[str, Any]:
    """Handle errors by updating state with failure info."""
    errors = state.get("errors", [])
    errors.append(f"{phase}: {str(error)}")
    return {
        "status": "failed",
        "current_phase": f"{phase}_failed",
        "errors": errors,
    }


async def _safe_load_context(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for load_context_node with error handling."""
    try:
        return await load_context_node(state)
    except Exception as e:
        logger.exception("load_context failed")
        return _handle_error(state, e, "load_context")


async def _safe_situational_awareness(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for situational_awareness_node with error handling."""
    # Check if previous step failed
    if state.get("status") == "failed":
        return {}
    try:
        return await situational_awareness_node(state)
    except Exception as e:
        logger.exception("situational_awareness failed")
        return _handle_error(state, e, "situational_awareness")


async def _safe_resource_calculation(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for resource_calculation_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await resource_calculation_node(state)
    except Exception as e:
        logger.exception("resource_calculation failed")
        return _handle_error(state, e, "resource_calculation")


async def _safe_document_generation(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for document_generation_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await document_generation_node(state)
    except Exception as e:
        logger.exception("document_generation failed")
        return _handle_error(state, e, "document_generation")


def should_continue_after_resource(state: OverallPlanState) -> str:
    """Determine next step after resource calculation."""
    if state.get("status") == "failed":
        return END
    return "human_review"


def build_overall_plan_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Build the Overall Plan Generation state graph.

    Args:
        checkpointer: Optional checkpoint saver for state persistence

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building overall plan graph")

    # Create the graph
    graph = StateGraph(OverallPlanState)

    # Add nodes
    graph.add_node("load_context", _safe_load_context)
    graph.add_node("situational_awareness", _safe_situational_awareness)
    graph.add_node("resource_calculation", _safe_resource_calculation)
    # human_review 直接注册，不使用包装器，避免破坏 LangGraph interrupt 上下文
    graph.add_node("human_review", human_review_node)
    graph.add_node("document_generation", _safe_document_generation)

    # Define edges
    graph.add_edge("load_context", "situational_awareness")
    graph.add_edge("situational_awareness", "resource_calculation")
    graph.add_conditional_edges(
        "resource_calculation",
        should_continue_after_resource,
        {
            "human_review": "human_review",
            END: END,
        },
    )
    # human_review uses Command to route to either document_generation or END
    graph.add_edge("document_generation", END)

    # Set entry point
    graph.set_entry_point("load_context")

    # Compile with checkpointer
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("Overall plan graph built successfully")
    return compiled
