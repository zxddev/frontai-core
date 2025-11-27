"""
路径规划智能体LangGraph流程定义

实现评估-重规划循环的状态图，参考DynamicRouteGPT/LeAD论文架构。
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from langgraph.graph import StateGraph, START, END

from .state import RoutePlanningState
from .nodes import (
    analyze_scenario,
    select_strategy,
    compute_route,
    evaluate_result,
    explain_route,
)

logger = logging.getLogger(__name__)


def should_replan(state: RoutePlanningState) -> Literal["adjust_strategy", "explain_route"]:
    """
    评估后条件路由：决定是否重规划
    
    如果评估结果建议重规划且未达最大次数，进入策略调整；
    否则进入路径解释生成最终结果。
    """
    evaluation = state.get("route_evaluation")
    replan_count = state.get("replan_count", 0)
    max_replan = state.get("max_replan_attempts", 3)
    
    if evaluation and evaluation.get("should_replan") and replan_count < max_replan:
        logger.info(f"[流程控制] 触发重规划 attempt={replan_count+1}/{max_replan}")
        return "adjust_strategy"
    
    logger.info("[流程控制] 进入路径解释")
    return "explain_route"


async def adjust_strategy(state: RoutePlanningState) -> dict:
    """
    策略调整节点（重规划时使用）
    
    增加重规划计数，并重新进入策略选择流程。
    策略选择节点会根据replan_count调整参数。
    """
    replan_count = state.get("replan_count", 0)
    evaluation = state.get("route_evaluation", {})
    
    logger.info(
        f"[策略调整] 开始 attempt={replan_count+1} "
        f"reason={evaluation.get('replan_reason', 'unknown')}"
    )
    
    return {
        "replan_count": replan_count + 1,
        "current_phase": "adjusting_strategy",
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["adjust_strategy"],
            "replan_history": state.get("trace", {}).get("replan_history", []) + [
                {
                    "attempt": replan_count + 1,
                    "reason": evaluation.get("replan_reason"),
                    "weaknesses": evaluation.get("weaknesses", []),
                }
            ],
        },
    }


def build_route_planning_graph() -> StateGraph:
    """
    构建路径规划状态图
    
    流程：
    ```
    START
      │
      ▼
    analyze_scenario (LLM)     ← 理解场景、评估紧急程度
      │
      ▼
    select_strategy (LLM)      ← 选择规划策略、生成算法参数
      │
      ▼
    compute_route (Algorithm)  ← 调用A*/VRP算法计算路径
      │
      ▼
    evaluate_result (LLM)      ← 评估结果是否满足需求
      │
      ├──[should_replan=true]──▶ adjust_strategy
      │                              │
      │                              ▼
      │                         select_strategy (循环)
      │
      └──[should_replan=false]──▶ explain_route (LLM)
                                      │
                                      ▼
                                    END
    ```
    
    关键特性：
    1. LLM参与场景理解和策略决策（不只是包装算法）
    2. 有评估-重规划循环（LangGraph核心价值）
    3. 算法负责纯计算
    
    Returns:
        构建好的StateGraph（未编译）
    """
    logger.info("构建路径规划 LangGraph...")
    
    # 创建状态图
    workflow = StateGraph(RoutePlanningState)
    
    # ========== 添加节点 ==========
    
    # 阶段1: 场景分析
    workflow.add_node("analyze_scenario", analyze_scenario)
    
    # 阶段2: 策略选择
    workflow.add_node("select_strategy", select_strategy)
    
    # 阶段3: 路径计算
    workflow.add_node("compute_route", compute_route)
    
    # 阶段4: 结果评估
    workflow.add_node("evaluate_result", evaluate_result)
    
    # 策略调整（重规划入口）
    workflow.add_node("adjust_strategy", adjust_strategy)
    
    # 阶段5: 路径解释
    workflow.add_node("explain_route", explain_route)
    
    # ========== 定义边 ==========
    
    # START → 场景分析
    workflow.add_edge(START, "analyze_scenario")
    
    # 场景分析 → 策略选择
    workflow.add_edge("analyze_scenario", "select_strategy")
    
    # 策略选择 → 路径计算
    workflow.add_edge("select_strategy", "compute_route")
    
    # 路径计算 → 结果评估
    workflow.add_edge("compute_route", "evaluate_result")
    
    # 结果评估 → 条件路由（重规划循环的关键）
    workflow.add_conditional_edges(
        "evaluate_result",
        should_replan,
        {
            "adjust_strategy": "adjust_strategy",
            "explain_route": "explain_route",
        }
    )
    
    # 策略调整 → 策略选择（形成循环）
    workflow.add_edge("adjust_strategy", "select_strategy")
    
    # 路径解释 → END
    workflow.add_edge("explain_route", END)
    
    logger.info("路径规划 LangGraph 构建完成")
    
    return workflow


# 编译后的图（单例）
_compiled_graph = None


def get_route_planning_graph():
    """获取编译后的图（单例模式）"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_route_planning_graph()
        _compiled_graph = workflow.compile()
        logger.info("路径规划图编译完成")
    return _compiled_graph
