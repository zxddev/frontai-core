"""
EmergencyAI LangGraph流程定义

基于LangGraph 1.0构建4阶段AI+规则混合流程。
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from .state import EmergencyAIState
from .nodes import (
    # 阶段1
    understand_disaster,
    enhance_with_cases,
    # 阶段2
    query_rules,
    apply_rules,
    # 阶段2.5: HTN任务分解
    htn_decompose,
    # 阶段3
    match_resources,
    optimize_allocation,
    # 阶段4
    filter_hard_rules,
    score_soft_rules,
    explain_scheme,
    # 输出
    generate_output,
)

logger = logging.getLogger(__name__)


def should_continue_after_understanding(state: EmergencyAIState) -> Literal["query_rules", "generate_output"]:
    """
    判断灾情理解后是否继续
    
    如果灾情解析失败，直接生成输出；否则继续规则推理。
    """
    if state.get("parsed_disaster") is None:
        logger.warning("灾情解析失败，跳转到输出")
        return "generate_output"
    return "query_rules"


def should_continue_after_rules(state: EmergencyAIState) -> Literal["htn_decompose", "generate_output"]:
    """
    判断规则推理后是否继续
    
    如果没有匹配到任何规则，直接生成输出；否则进入HTN任务分解。
    """
    matched_rules = state.get("matched_rules", [])
    if not matched_rules:
        logger.warning("无匹配规则，跳转到输出")
        return "generate_output"
    return "htn_decompose"


def should_continue_after_htn_decompose(state: EmergencyAIState) -> Literal["match_resources", "generate_output"]:
    """
    判断HTN任务分解后是否继续
    
    如果任务序列为空，直接生成输出；否则继续资源匹配。
    """
    task_sequence = state.get("task_sequence", [])
    if not task_sequence:
        logger.warning("任务序列为空，跳转到输出")
        return "generate_output"
    return "match_resources"


def should_continue_after_matching(state: EmergencyAIState) -> Literal["filter_hard_rules", "generate_output"]:
    """
    判断资源匹配后是否继续
    
    如果没有候选方案，直接生成输出。
    """
    solutions = state.get("allocation_solutions", [])
    if not solutions:
        logger.warning("无候选方案，跳转到输出")
        return "generate_output"
    return "filter_hard_rules"


def should_explain_scheme(state: EmergencyAIState) -> Literal["explain_scheme", "generate_output"]:
    """
    判断是否需要生成方案解释
    
    如果有推荐方案，生成解释；否则直接输出。
    """
    recommended = state.get("recommended_scheme")
    if recommended:
        return "explain_scheme"
    return "generate_output"


def build_emergency_ai_graph() -> StateGraph:
    """
    构建EmergencyAI状态图
    
    流程：
    ```
    START
      │
      ▼
    ┌─────────────────────────────────────┐
    │ Phase 1: 灾情理解                   │
    │ understand_disaster → enhance_cases │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 解析成功?)
    ┌─────────────────────────────────────┐
    │ Phase 2: 规则推理                   │
    │ query_rules → apply_rules           │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有匹配规则?)
    ┌─────────────────────────────────────┐
    │ Phase 2.5: HTN任务分解              │
    │ 场景识别 → 任务链合并 → 拓扑排序    │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有任务序列?)
    ┌─────────────────────────────────────┐
    │ Phase 3: 资源匹配                   │
    │ match_resources → optimize_alloc    │
    └─────────────────────────────────────┘
      │
      ▼ (conditional: 有候选方案?)
    ┌─────────────────────────────────────┐
    │ Phase 4: 方案优化                   │
    │ filter_hard → score_soft → explain  │
    └─────────────────────────────────────┘
      │
      ▼
    generate_output
      │
      ▼
    END
    ```
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建EmergencyAI LangGraph...")
    
    # 创建状态图
    workflow = StateGraph(EmergencyAIState)
    
    # ========== 添加节点 ==========
    
    # 阶段1: 灾情理解
    workflow.add_node("understand_disaster", understand_disaster)
    workflow.add_node("enhance_with_cases", enhance_with_cases)
    
    # 阶段2: 规则推理
    workflow.add_node("query_rules", query_rules)
    workflow.add_node("apply_rules", apply_rules)
    
    # 阶段2.5: HTN任务分解
    workflow.add_node("htn_decompose", htn_decompose)
    
    # 阶段3: 资源匹配
    workflow.add_node("match_resources", match_resources)
    workflow.add_node("optimize_allocation", optimize_allocation)
    
    # 阶段4: 方案优化
    workflow.add_node("filter_hard_rules", filter_hard_rules)
    workflow.add_node("score_soft_rules", score_soft_rules)
    workflow.add_node("explain_scheme", explain_scheme)
    
    # 输出
    workflow.add_node("generate_output", generate_output)
    
    # ========== 定义边 ==========
    
    # START → Phase 1
    workflow.add_edge(START, "understand_disaster")
    workflow.add_edge("understand_disaster", "enhance_with_cases")
    
    # Phase 1 → Phase 2 (conditional)
    workflow.add_conditional_edges(
        "enhance_with_cases",
        should_continue_after_understanding,
        {
            "query_rules": "query_rules",
            "generate_output": "generate_output",
        }
    )
    
    # Phase 2 内部
    workflow.add_edge("query_rules", "apply_rules")
    
    # Phase 2 → HTN分解 (conditional)
    workflow.add_conditional_edges(
        "apply_rules",
        should_continue_after_rules,
        {
            "htn_decompose": "htn_decompose",
            "generate_output": "generate_output",
        }
    )
    
    # HTN分解 → Phase 3 (conditional)
    workflow.add_conditional_edges(
        "htn_decompose",
        should_continue_after_htn_decompose,
        {
            "match_resources": "match_resources",
            "generate_output": "generate_output",
        }
    )
    
    # Phase 3 内部
    workflow.add_edge("match_resources", "optimize_allocation")
    
    # Phase 3 → Phase 4 (conditional)
    workflow.add_conditional_edges(
        "optimize_allocation",
        should_continue_after_matching,
        {
            "filter_hard_rules": "filter_hard_rules",
            "generate_output": "generate_output",
        }
    )
    
    # Phase 4 内部
    workflow.add_edge("filter_hard_rules", "score_soft_rules")
    
    # Phase 4 → explain (conditional)
    workflow.add_conditional_edges(
        "score_soft_rules",
        should_explain_scheme,
        {
            "explain_scheme": "explain_scheme",
            "generate_output": "generate_output",
        }
    )
    
    workflow.add_edge("explain_scheme", "generate_output")
    
    # 输出 → END
    workflow.add_edge("generate_output", END)
    
    logger.info("EmergencyAI LangGraph构建完成")
    
    return workflow


# 编译图（懒加载）
_compiled_graph = None


def get_emergency_ai_graph():
    """获取编译后的图（单例）"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_emergency_ai_graph()
        _compiled_graph = workflow.compile()
        logger.info("EmergencyAI图编译完成")
    return _compiled_graph
