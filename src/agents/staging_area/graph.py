"""
驻扎点选址智能体图定义

使用LangGraph构建多步分析流程（6节点完整版）：
灾情理解 → [地形|通信|安全] 并行分析 → 评估排序 → 决策解释

遵循项目架构规范，Agent节点调用Service，Service调用Core。
"""
from __future__ import annotations

import logging
from typing import List, Literal, Union

from langgraph.graph import StateGraph, END

from src.agents.staging_area.state import StagingAreaAgentState
from src.agents.staging_area.nodes import (
    understand_disaster,
    analyze_terrain,
    analyze_communication,
    analyze_safety,
    evaluate_candidates,
    explain_decision,
)

logger = logging.getLogger(__name__)


def route_after_understand(
    state: StagingAreaAgentState,
) -> Union[List[str], Literal["end"]]:
    """
    判断灾情理解后的路由
    
    返回值：
    - 关键错误 → "end"
    - skip_llm_analysis=True → ["evaluate"]（跳过LLM分析）
    - 正常 → ["terrain", "communication", "safety"]（并行分析）
    """
    errors = state.get("errors", [])
    
    # 关键参数缺失则结束
    critical_errors = [e for e in errors if "缺少" in e and ("scenario" in e or "震中" in e)]
    if critical_errors:
        logger.warning(f"[Graph] 关键参数缺失，结束流程: {critical_errors}")
        return "end"
    
    # 跳过LLM分析，直接评估
    if state.get("skip_llm_analysis", False):
        logger.info("[Graph] skip_llm_analysis=True，跳过分析节点")
        return ["evaluate"]
    
    # 并行执行三个分析节点
    logger.info("[Graph] 启动并行分析：terrain, communication, safety")
    return ["terrain", "communication", "safety"]


def should_continue_after_evaluate(
    state: StagingAreaAgentState,
) -> Literal["explain", "end"]:
    """
    判断评估排序后是否继续
    
    如果没有候选点，直接结束；否则继续生成解释。
    """
    ranked_sites = state.get("ranked_sites", [])
    
    if not ranked_sites:
        logger.warning("[Graph] 无候选点，结束流程")
        return "end"
    
    return "explain"


def build_staging_area_graph() -> StateGraph:
    """
    构建驻扎点选址智能体图（6节点完整版）
    
    流程：
    understand → [terrain | communication | safety] → evaluate → explain → END
                 ↑__________ 并行执行 __________↑
    
    节点职责：
    1. understand: LLM解析灾情描述，提取约束
    2. terrain: LLM评估地形适宜性
    3. communication: LLM评估通信可行性
    4. safety: LLM评估安全风险
    5. evaluate: 算法执行候选搜索、路径验证、评分排序
    6. explain: LLM生成推荐理由和风险警示
    
    Returns:
        编译后的StateGraph
    """
    workflow = StateGraph(StagingAreaAgentState)
    
    # ========== 添加6个节点 ==========
    workflow.add_node("understand", understand_disaster)
    workflow.add_node("terrain", analyze_terrain)
    workflow.add_node("communication", analyze_communication)
    workflow.add_node("safety", analyze_safety)
    workflow.add_node("evaluate", evaluate_candidates)
    workflow.add_node("explain", explain_decision)
    
    # ========== 设置入口 ==========
    workflow.set_entry_point("understand")
    
    # ========== understand 后的路由 ==========
    # 并行执行 terrain/communication/safety，或跳过直接 evaluate，或结束
    workflow.add_conditional_edges(
        "understand",
        route_after_understand,
        ["terrain", "communication", "safety", "evaluate", END],
    )
    
    # ========== 三个分析节点汇聚到 evaluate ==========
    workflow.add_edge("terrain", "evaluate")
    workflow.add_edge("communication", "evaluate")
    workflow.add_edge("safety", "evaluate")
    
    # ========== evaluate 后的路由 ==========
    workflow.add_conditional_edges(
        "evaluate",
        should_continue_after_evaluate,
        {
            "explain": "explain",
            "end": END,
        }
    )
    
    # ========== explain 后结束 ==========
    workflow.add_edge("explain", END)
    
    return workflow


# 编译图
staging_area_graph = build_staging_area_graph().compile()
