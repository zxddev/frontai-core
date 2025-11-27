"""
任务智能分发LangGraph流程定义

支持双模式运行：
- Mode 1: 初始分配（批量处理方案）
- Mode 2: 动态调整（响应事件变化，支持human-in-the-loop）
"""
from __future__ import annotations

import logging
from typing import Literal, Optional
from functools import lru_cache

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from .state import TaskDispatchState
from .nodes import (
    # Mode 1: 初始分配
    extract_capability_needs,
    query_available_executors,
    match_executors,
    schedule_tasks,
    generate_dispatch_orders,
    # Mode 2: 动态调整
    analyze_dispatch_event,
    decide_dispatch_action,
    execute_dispatch_action,
    notify_stakeholders,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 条件路由函数
# ============================================================================

def route_by_mode(state: TaskDispatchState) -> Literal["extract_needs", "analyze_event"]:
    """
    根据运行模式路由
    
    Mode 1 (initial): 进入初始分配流程
    Mode 2 (dynamic): 进入动态调整流程
    """
    mode = state.get("mode", "initial")
    
    if mode == "dynamic":
        logger.info("[路由] 动态调整模式 -> analyze_event")
        return "analyze_event"
    else:
        logger.info("[路由] 初始分配模式 -> extract_needs")
        return "extract_needs"


def should_continue_initial_dispatch(
    state: TaskDispatchState
) -> Literal["query_executors", "end"]:
    """
    判断初始分配是否继续
    """
    scheme_tasks = state.get("scheme_tasks", [])
    errors = state.get("errors", [])
    
    if not scheme_tasks:
        logger.warning("[路由] 无方案任务，结束流程")
        return "end"
    
    if len(errors) > 3:
        logger.warning("[路由] 错误过多，结束流程")
        return "end"
    
    return "query_executors"


def should_continue_after_matching(
    state: TaskDispatchState
) -> Literal["schedule_tasks", "end"]:
    """
    判断匹配后是否继续
    """
    assignments = state.get("current_assignments", [])
    
    if not assignments:
        logger.warning("[路由] 无分配结果，结束流程")
        return "end"
    
    return "schedule_tasks"


def should_require_human_input(
    state: TaskDispatchState
) -> Literal["human_review", "execute_action"]:
    """
    判断是否需要人工审核
    """
    requires_human = state.get("requires_human_approval", False)
    
    if requires_human:
        logger.info("[路由] 需要人工审核 -> human_review")
        return "human_review"
    else:
        logger.info("[路由] 自动执行 -> execute_action")
        return "execute_action"


def should_continue_dynamic_loop(
    state: TaskDispatchState
) -> Literal["analyze_event", "end"]:
    """
    判断动态调整是否继续循环
    """
    pending_events = state.get("pending_events", [])
    errors = state.get("errors", [])
    
    # 如果还有待处理事件且错误不多，继续循环
    if pending_events and len(errors) < 5:
        logger.info(f"[路由] 还有{len(pending_events)}个待处理事件，继续循环")
        return "analyze_event"
    
    return "end"


# ============================================================================
# Human-in-the-loop节点
# ============================================================================

async def human_review_node(state: TaskDispatchState) -> dict:
    """
    人工审核节点
    
    此节点在需要人工审核时被执行。
    通过interrupt_before在图级别设置中断，而不是在节点内调用interrupt()。
    
    当用户通过Command(resume=decision)恢复时，此节点会被执行。
    resume值会通过__pregel_resuming标志和input传入。
    """
    proposed_action = state.get("proposed_action", {})
    human_decision = state.get("human_decision")
    
    logger.info(f"[人工审核] 处理人工决策: action={proposed_action.get('action_type')}, decision={human_decision}")
    
    # 如果已经有人工决策（从resume传入），直接使用
    if human_decision:
        decision = human_decision
        modified_action = state.get("modified_action")
    else:
        # 默认批准（当不需要人工审核时直接通过）
        decision = "approve"
        modified_action = None
    
    logger.info(f"[人工审核] 最终决策: {decision}")
    
    return {
        "human_decision": decision,
        "proposed_action": modified_action if modified_action else proposed_action,
    }


# ============================================================================
# 图构建
# ============================================================================

def build_task_dispatch_graph() -> StateGraph:
    """
    构建任务智能分发状态图
    
    流程架构：
    
    Mode 1: 初始分配
    ```
    START
      │
      ▼ (route_by_mode)
    ┌─────────────────────────────────────────┐
    │ extract_needs → query_executors →       │
    │ match_executors → schedule_tasks →      │
    │ generate_orders → notify                │
    └─────────────────────────────────────────┘
      │
      ▼
    END
    ```
    
    Mode 2: 动态调整
    ```
    START
      │
      ▼ (route_by_mode)
    ┌─────────────────────────────────────────┐
    │ analyze_event → decide_action →         │
    │                                         │
    │ ┌─── requires_human? ───┐               │
    │ │ Yes                   │ No            │
    │ ▼                       ▼               │
    │ human_review      execute_action        │
    │ │                       │               │
    │ └───────→ notify ←──────┘               │
    │              │                          │
    │              ▼                          │
    │ ┌─── more_events? ───┐                  │
    │ │ Yes                │ No               │
    │ ▼                    ▼                  │
    │ analyze_event       END                 │
    └─────────────────────────────────────────┘
    ```
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建TaskDispatch LangGraph...")
    
    # 创建状态图
    graph = StateGraph(TaskDispatchState)
    
    # ========== Mode 1: 初始分配节点 ==========
    graph.add_node("extract_needs", extract_capability_needs)
    graph.add_node("query_executors", query_available_executors)
    graph.add_node("match_executors", match_executors)
    graph.add_node("schedule_tasks", schedule_tasks)
    graph.add_node("generate_orders", generate_dispatch_orders)
    
    # ========== Mode 2: 动态调整节点 ==========
    graph.add_node("analyze_event", analyze_dispatch_event)
    graph.add_node("decide_action", decide_dispatch_action)
    graph.add_node("human_review", human_review_node)
    graph.add_node("execute_action", execute_dispatch_action)
    
    # ========== 共享节点 ==========
    graph.add_node("notify", notify_stakeholders)
    
    # ========== 入口路由 ==========
    graph.add_conditional_edges(
        START,
        route_by_mode,
        {
            "extract_needs": "extract_needs",
            "analyze_event": "analyze_event",
        }
    )
    
    # ========== Mode 1 边 ==========
    graph.add_conditional_edges(
        "extract_needs",
        should_continue_initial_dispatch,
        {
            "query_executors": "query_executors",
            "end": END,
        }
    )
    graph.add_edge("query_executors", "match_executors")
    graph.add_conditional_edges(
        "match_executors",
        should_continue_after_matching,
        {
            "schedule_tasks": "schedule_tasks",
            "end": END,
        }
    )
    graph.add_edge("schedule_tasks", "generate_orders")
    graph.add_edge("generate_orders", "notify")
    
    # ========== Mode 2 边 ==========
    graph.add_edge("analyze_event", "decide_action")
    graph.add_conditional_edges(
        "decide_action",
        should_require_human_input,
        {
            "human_review": "human_review",
            "execute_action": "execute_action",
        }
    )
    graph.add_edge("human_review", "execute_action")
    graph.add_edge("execute_action", "notify")
    
    # ========== 通知后的路由 ==========
    # Mode 1: 通知后结束
    # Mode 2: 通知后检查是否还有事件需要处理
    def route_after_notify(state: TaskDispatchState) -> Literal["analyze_event", "end"]:
        mode = state.get("mode", "initial")
        if mode == "dynamic":
            return should_continue_dynamic_loop(state)
        return "end"
    
    graph.add_conditional_edges(
        "notify",
        route_after_notify,
        {
            "analyze_event": "analyze_event",
            "end": END,
        }
    )
    
    logger.info("TaskDispatch LangGraph构建完成")
    return graph


def get_task_dispatch_graph(use_checkpointer: bool = True) -> StateGraph:
    """
    获取编译后的任务分发图（单例）
    
    Args:
        use_checkpointer: 是否启用状态持久化
        
    Returns:
        编译后的StateGraph
    """
    graph = build_task_dispatch_graph()
    
    if use_checkpointer:
        # 使用内存检查点器（生产环境应使用PostgresSaver）
        checkpointer = InMemorySaver()
        # 在human_review节点前设置中断点，支持human-in-the-loop
        compiled = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_review"],  # 在人工审核节点前暂停
        )
        logger.info("TaskDispatch图编译完成（带checkpointer和interrupt）")
    else:
        compiled = graph.compile()
        logger.info("TaskDispatch图编译完成（无checkpointer）")
    
    return compiled
