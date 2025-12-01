"""LangGraph workflow for unmanned initial reconnaissance planning.

支持两种模式：
1. 规则模式（默认）：score_targets -> generate_recon_plan
2. CrewAI 设备分配模式：设置 RECON_USE_CREWAI=true，使用专家 Agent 分配设备

工作流：
- 规则模式: START -> score_targets -> generate_recon_plan -> END
- CrewAI 模式: START -> score_targets -> assign_devices_crewai -> generate_recon_plan -> END

设置 RECON_SKIP_PLAN=true 可跳过方案生成节点（用于快速测试）。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from .nodes import score_targets, assign_devices_with_crewai, is_crewai_enabled, generate_recon_plan
from .state import ReconState


logger = logging.getLogger(__name__)


async def _score_targets_node(state: ReconState) -> Dict[str, Any]:
    """Wrapper around ``score_targets`` with basic error handling.

    Errors are recorded into state.errors/current_phase rather than bubbling up,
    to keep the external API predictable.
    """

    try:
        update = await score_targets(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Recon] score_targets node failed")
        errors = state.get("errors", [])
        errors.append(str(exc))
        return {
            "errors": errors,
            "current_phase": "score_targets_failed",
        }

    trace = state.get("trace", {}) or {}
    # 合并 update 中的 trace 数据
    update_trace_data = update.pop("trace", {})
    
    phases = list(trace.get("phases_executed", []))
    phases.append("score_targets")

    merged_trace = {
        **trace,
        **update_trace_data,
        "phases_executed": phases,
    }

    return {
        **update,
        "trace": merged_trace,
        "current_phase": update.get("current_phase", "score_targets_completed"),
    }


async def _assign_devices_crewai_node(state: ReconState) -> Dict[str, Any]:
    """CrewAI 设备分配节点
    
    使用专家 Agent 进行智能设备筛选和任务分配。
    """
    try:
        update = await assign_devices_with_crewai(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Recon] assign_devices_crewai node failed")
        errors = state.get("errors", [])
        errors.append(f"CrewAI assign failed: {exc}")
        return {
            "errors": errors,
            "current_phase": "assign_devices_failed",
        }
    
    if not update:
        # CrewAI 返回空结果，保持原有分配
        return {"current_phase": "assign_devices_skipped"}
    
    trace = state.get("trace", {}) or {}
    phases = list(trace.get("phases_executed", []))
    phases.append("assign_devices_crewai")
    
    update_trace = {
        **trace,
        "phases_executed": phases,
    }
    
    return {
        **update,
        "trace": update_trace,
    }


async def _generate_recon_plan_node(state: ReconState) -> Dict[str, Any]:
    """侦察方案生成节点
    
    使用 CrewAI 为每个设备分配生成详细的侦察执行方案。
    """
    try:
        update = await generate_recon_plan(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Recon] generate_recon_plan node failed")
        errors = state.get("errors", [])
        errors.append(f"Plan generation failed: {exc}")
        return {
            "errors": errors,
            "current_phase": "generate_plan_failed",
        }
    
    trace = state.get("trace", {}) or {}
    phases = list(trace.get("phases_executed", []))
    phases.append("generate_recon_plan")
    
    update_trace = {
        **trace,
        "phases_executed": phases,
    }
    
    return {
        **update,
        "trace": update_trace,
    }


def _should_skip_plan_generation() -> bool:
    """检查是否跳过方案生成"""
    return os.getenv("RECON_SKIP_PLAN", "").lower() in ("true", "1", "yes")


def build_recon_graph(use_crewai: bool | None = None, skip_plan: bool | None = None) -> StateGraph:
    """Build the Recon LangGraph workflow (uncompiled).

    Args:
        use_crewai: 是否使用 CrewAI 设备分配。
                    None = 从环境变量 RECON_USE_CREWAI 读取
                    True/False = 强制启用/禁用
        skip_plan: 是否跳过方案生成节点。
                   None = 从环境变量 RECON_SKIP_PLAN 读取
                   True/False = 强制跳过/不跳过

    Flow (规则模式):
        ``START -> score_targets -> generate_recon_plan -> END``
    
    Flow (CrewAI 模式):
        ``START -> score_targets -> assign_devices_crewai -> generate_recon_plan -> END``
    
    Flow (跳过方案生成):
        ``START -> score_targets -> END``
    """
    if use_crewai is None:
        use_crewai = is_crewai_enabled()
    
    if skip_plan is None:
        skip_plan = _should_skip_plan_generation()
    
    mode = "CrewAI" if use_crewai else "规则"
    plan_mode = "跳过" if skip_plan else "生成"
    logger.info(f"[Recon] Building reconnaissance LangGraph workflow (设备分配: {mode}, 方案: {plan_mode})")

    workflow: StateGraph = StateGraph(ReconState)
    workflow.add_node("score_targets", _score_targets_node)
    
    if use_crewai:
        workflow.add_node("assign_devices_crewai", _assign_devices_crewai_node)
        if skip_plan:
            # CrewAI 分配，跳过方案生成
            workflow.add_edge(START, "score_targets")
            workflow.add_edge("score_targets", "assign_devices_crewai")
            workflow.add_edge("assign_devices_crewai", END)
        else:
            # CrewAI 分配 + 方案生成
            workflow.add_node("generate_recon_plan", _generate_recon_plan_node)
            workflow.add_edge(START, "score_targets")
            workflow.add_edge("score_targets", "assign_devices_crewai")
            workflow.add_edge("assign_devices_crewai", "generate_recon_plan")
            workflow.add_edge("generate_recon_plan", END)
    else:
        if skip_plan:
            # 规则分配，跳过方案生成
            workflow.add_edge(START, "score_targets")
            workflow.add_edge("score_targets", END)
        else:
            # 规则分配 + 方案生成
            workflow.add_node("generate_recon_plan", _generate_recon_plan_node)
            workflow.add_edge(START, "score_targets")
            workflow.add_edge("score_targets", "generate_recon_plan")
            workflow.add_edge("generate_recon_plan", END)

    return workflow


_compiled_graph = None


def get_recon_graph():
    """Return compiled Recon graph (singleton)."""

    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_recon_graph()
        _compiled_graph = workflow.compile()
        logger.info("[Recon] LangGraph compiled successfully")
    return _compiled_graph


__all__ = ["build_recon_graph", "get_recon_graph"]
