"""LangGraph State Graph definition for Overall Plan Generation.

This module defines the workflow graph that orchestrates:
1. Data loading (load_context) - 加载基础数据
2. Disaster summary (disaster_summary) - 灾情数据汇总（数据库，无LLM）
3. Command structure (command_structure) - 组织指挥结构（数据库模板）
4. Resource demand (resource_demand) - 资源需求计算（SPHERE标准）
5. Gap analysis (gap_analysis) - 缺口分析（复用emergency_ai）
6. Secondary disaster (secondary_disaster) - 次生灾害分析（保留CrewAI）
7. Situational awareness (situational_awareness) - 其他模块文本（CrewAI润色）
8. Human review (HITL interrupt) - 人工审核
9. Document generation (document_generation) - 最终文档生成
"""

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.agents.overall_plan.nodes.load_context import load_context_node
from src.agents.overall_plan.nodes.disaster_summary import disaster_summary_node
from src.agents.overall_plan.nodes.command_structure import command_structure_node
from src.agents.overall_plan.nodes.resource_demand import resource_demand_node
from src.agents.overall_plan.nodes.gap_analysis import gap_analysis_node
from src.agents.overall_plan.nodes.secondary_disaster import secondary_disaster_node
from src.agents.overall_plan.nodes.situational_awareness import situational_awareness_node
from src.agents.overall_plan.nodes.resource_calculation import resource_calculation_node
from src.agents.overall_plan.nodes.human_review import human_review_node
from src.agents.overall_plan.nodes.document_generation import document_generation_node
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


async def _safe_disaster_summary(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for disaster_summary_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await disaster_summary_node(state)
    except Exception as e:
        logger.exception("disaster_summary failed")
        return _handle_error(state, e, "disaster_summary")


async def _safe_command_structure(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for command_structure_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await command_structure_node(state)
    except Exception as e:
        logger.exception("command_structure failed")
        return _handle_error(state, e, "command_structure")


async def _safe_resource_demand(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for resource_demand_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await resource_demand_node(state)
    except Exception as e:
        logger.exception("resource_demand failed")
        return _handle_error(state, e, "resource_demand")


async def _safe_gap_analysis(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for gap_analysis_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await gap_analysis_node(state)
    except Exception as e:
        logger.exception("gap_analysis failed")
        return _handle_error(state, e, "gap_analysis")


async def _safe_secondary_disaster(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for secondary_disaster_node with error handling."""
    if state.get("status") == "failed":
        return {}
    try:
        return await secondary_disaster_node(state)
    except Exception as e:
        logger.exception("secondary_disaster failed")
        return _handle_error(state, e, "secondary_disaster")


async def _safe_situational_awareness(state: OverallPlanState) -> dict[str, Any]:
    """Wrapper for situational_awareness_node with error handling."""
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


def should_continue_after_situational(state: OverallPlanState) -> str:
    """Determine next step after situational awareness."""
    if state.get("status") == "failed":
        return END
    return "human_review"


def build_overall_plan_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Build the Overall Plan Generation state graph.

    新架构：数据驱动 + LLM润色
    - 前6个节点：数据库查询 + SPHERE算法（无LLM幻觉风险）
    - 后3个节点：CrewAI生成文档文本（保留LLM能力）

    Args:
        checkpointer: Optional checkpoint saver for state persistence

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building overall plan graph (data-driven + LLM polishing)")

    graph = StateGraph(OverallPlanState)

    # 数据层节点（无LLM）
    graph.add_node("load_context", _safe_load_context)
    graph.add_node("disaster_summary", _safe_disaster_summary)
    graph.add_node("command_structure", _safe_command_structure)
    graph.add_node("resource_demand", _safe_resource_demand)
    graph.add_node("gap_analysis", _safe_gap_analysis)

    # LLM层节点（保留CrewAI）
    graph.add_node("secondary_disaster", _safe_secondary_disaster)
    graph.add_node("situational_awareness", _safe_situational_awareness)

    # 审批和文档生成
    graph.add_node("human_review", human_review_node)
    graph.add_node("document_generation", _safe_document_generation)

    # 定义工作流边
    # 数据层：顺序执行
    graph.add_edge("load_context", "disaster_summary")
    graph.add_edge("disaster_summary", "command_structure")
    graph.add_edge("command_structure", "resource_demand")
    graph.add_edge("resource_demand", "gap_analysis")

    # 数据层 → LLM层
    graph.add_edge("gap_analysis", "secondary_disaster")
    graph.add_edge("secondary_disaster", "situational_awareness")

    # LLM层 → 审批
    graph.add_conditional_edges(
        "situational_awareness",
        should_continue_after_situational,
        {
            "human_review": "human_review",
            END: END,
        },
    )

    # 审批后 → 文档生成
    graph.add_edge("document_generation", END)

    graph.set_entry_point("load_context")

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("Overall plan graph built successfully")
    return compiled
