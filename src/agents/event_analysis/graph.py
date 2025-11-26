"""
事件分析LangGraph定义

定义事件分析流程的状态图
"""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from .state import EventAnalysisState
from .nodes import (
    assess_disaster,
    predict_hazards,
    estimate_loss,
    calculate_confirmation,
    decide_status,
)

logger = logging.getLogger(__name__)


def build_event_analysis_graph() -> StateGraph:
    """
    构建事件分析状态图
    
    流程:
    START → assess_disaster → predict_hazards → estimate_loss 
          → calculate_confirmation → decide_status → END
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建事件分析LangGraph...")
    
    # 创建状态图
    workflow = StateGraph(EventAnalysisState)
    
    # 添加节点
    workflow.add_node("assess_disaster", assess_disaster)
    workflow.add_node("predict_hazards", predict_hazards)
    workflow.add_node("estimate_loss", estimate_loss)
    workflow.add_node("calculate_confirmation", calculate_confirmation)
    workflow.add_node("decide_status", decide_status)
    
    # 定义边（线性流程）
    workflow.add_edge(START, "assess_disaster")
    workflow.add_edge("assess_disaster", "predict_hazards")
    workflow.add_edge("predict_hazards", "estimate_loss")
    workflow.add_edge("estimate_loss", "calculate_confirmation")
    workflow.add_edge("calculate_confirmation", "decide_status")
    workflow.add_edge("decide_status", END)
    
    logger.info("事件分析LangGraph构建完成")
    
    return workflow
