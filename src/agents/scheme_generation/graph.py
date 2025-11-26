"""
方案生成LangGraph定义

定义8节点的方案生成流程图
"""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from .state import SchemeGenerationState
from .nodes import (
    apply_trr_rules,
    extract_capabilities,
    match_resources,
    arbitrate_scenes,
    optimize_scheme,
    filter_hard_rules,
    score_soft_rules,
    generate_output,
)

logger = logging.getLogger(__name__)


def build_scheme_generation_graph() -> CompiledStateGraph:
    """
    构建方案生成LangGraph
    
    流程：
    1. apply_trr_rules - 规则触发
    2. extract_capabilities - 能力提取
    3. match_resources - 资源匹配
    4. arbitrate_scenes - 场景仲裁
    5. optimize_scheme - 方案优化（NSGA-II）
    6. filter_hard_rules - 硬规则过滤
    7. score_soft_rules - 软规则评分（TOPSIS）
    8. generate_output - 输出生成
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建方案生成LangGraph...")
    
    # 创建StateGraph
    builder = StateGraph(SchemeGenerationState)
    
    # 添加节点
    builder.add_node("apply_trr_rules", apply_trr_rules)
    builder.add_node("extract_capabilities", extract_capabilities)
    builder.add_node("match_resources", match_resources)
    builder.add_node("arbitrate_scenes", arbitrate_scenes)
    builder.add_node("optimize_scheme", optimize_scheme)
    builder.add_node("filter_hard_rules", filter_hard_rules)
    builder.add_node("score_soft_rules", score_soft_rules)
    builder.add_node("generate_output", generate_output)
    
    # 定义边（线性流程）
    builder.add_edge(START, "apply_trr_rules")
    builder.add_edge("apply_trr_rules", "extract_capabilities")
    builder.add_edge("extract_capabilities", "match_resources")
    builder.add_edge("match_resources", "arbitrate_scenes")
    builder.add_edge("arbitrate_scenes", "optimize_scheme")
    builder.add_edge("optimize_scheme", "filter_hard_rules")
    builder.add_edge("filter_hard_rules", "score_soft_rules")
    builder.add_edge("score_soft_rules", "generate_output")
    builder.add_edge("generate_output", END)
    
    # 编译图
    graph = builder.compile()
    
    logger.info("方案生成LangGraph构建完成")
    return graph
