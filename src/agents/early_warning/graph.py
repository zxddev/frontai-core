"""
预警监测智能体图定义

使用LangGraph构建预警处理流程。
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from .state import EarlyWarningState
from .nodes import (
    ingest_disaster,
    analyze_impact,
    decide_warning,
    generate_message,
    send_notifications,
)

logger = logging.getLogger(__name__)


def should_continue_after_ingest(state: EarlyWarningState) -> Literal["analyze", "end"]:
    """判断是否继续分析"""
    if state.get("disaster_situation") is None:
        return "end"
    if state.get("errors"):
        return "end"
    return "analyze"


def should_continue_after_analyze(state: EarlyWarningState) -> Literal["decide", "end"]:
    """判断是否继续决策"""
    affected_vehicles = state.get("affected_vehicles", [])
    affected_teams = state.get("affected_teams", [])
    
    if not affected_vehicles and not affected_teams:
        return "end"
    return "decide"


def should_continue_after_decide(state: EarlyWarningState) -> Literal["generate", "end"]:
    """判断是否继续生成消息"""
    warning_decisions = state.get("warning_decisions", [])
    
    if not warning_decisions:
        return "end"
    return "generate"


def build_early_warning_graph() -> StateGraph:
    """
    构建预警监测智能体图
    
    流程：
    ingest -> analyze -> decide -> generate -> notify -> END
    
    Returns:
        编译后的StateGraph
    """
    # 创建图
    workflow = StateGraph(EarlyWarningState)
    
    # 添加节点
    workflow.add_node("ingest", ingest_disaster)
    workflow.add_node("analyze", analyze_impact)
    workflow.add_node("decide", decide_warning)
    workflow.add_node("generate", generate_message)
    workflow.add_node("notify", send_notifications)
    
    # 设置入口
    workflow.set_entry_point("ingest")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "ingest",
        should_continue_after_ingest,
        {
            "analyze": "analyze",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "analyze",
        should_continue_after_analyze,
        {
            "decide": "decide",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "decide",
        should_continue_after_decide,
        {
            "generate": "generate",
            "end": END,
        }
    )
    
    # 线性边
    workflow.add_edge("generate", "notify")
    workflow.add_edge("notify", END)
    
    return workflow


# 编译图
early_warning_graph = build_early_warning_graph().compile()
