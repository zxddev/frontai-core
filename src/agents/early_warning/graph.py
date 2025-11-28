"""
预警监测智能体图定义（扩展为RealTimeRiskAgent）

使用LangGraph构建预警处理流程 + 风险预测流程。
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from .state import EarlyWarningState
from .nodes import (
    # 原有预警节点
    ingest_disaster,
    analyze_impact,
    decide_warning,
    generate_message,
    send_notifications,
    # 风险预测节点
    predict_path_risk,
    predict_operation_risk,
    predict_disaster_spread,
    human_review_gate,
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


def should_run_prediction(state: EarlyWarningState) -> Literal["predict", "skip_prediction"]:
    """判断是否需要运行风险预测"""
    prediction_request = state.get("prediction_request")
    if prediction_request:
        return "predict"
    return "skip_prediction"


def should_human_review(state: EarlyWarningState) -> Literal["human_review", "skip_review"]:
    """判断是否需要人工审核"""
    pending = state.get("pending_human_review", [])
    if pending:
        return "human_review"
    return "skip_review"


def build_early_warning_graph() -> StateGraph:
    """
    构建预警监测智能体图（扩展为RealTimeRiskAgent）
    
    流程：
    1. 预警流程：ingest -> analyze -> decide -> generate -> notify -> END
    2. 预测流程：predict_* -> human_review -> END
    
    Returns:
        编译后的StateGraph
    """
    workflow = StateGraph(EarlyWarningState)
    
    # ========== 原有预警节点 ==========
    workflow.add_node("ingest", ingest_disaster)
    workflow.add_node("analyze", analyze_impact)
    workflow.add_node("decide", decide_warning)
    workflow.add_node("generate", generate_message)
    workflow.add_node("notify", send_notifications)
    
    # ========== 风险预测节点 ==========
    workflow.add_node("predict_path_risk", predict_path_risk)
    workflow.add_node("predict_operation_risk", predict_operation_risk)
    workflow.add_node("predict_disaster_spread", predict_disaster_spread)
    workflow.add_node("human_review", human_review_gate)
    
    # 设置入口
    workflow.set_entry_point("ingest")
    
    # ========== 预警流程边 ==========
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
    
    workflow.add_edge("generate", "notify")
    
    # notify之后检查是否需要预测
    workflow.add_conditional_edges(
        "notify",
        should_run_prediction,
        {
            "predict": "predict_path_risk",
            "skip_prediction": END,
        }
    )
    
    # ========== 预测流程边 ==========
    workflow.add_edge("predict_path_risk", "predict_operation_risk")
    workflow.add_edge("predict_operation_risk", "predict_disaster_spread")
    
    # 扩散预测后检查是否需要人工审核
    workflow.add_conditional_edges(
        "predict_disaster_spread",
        should_human_review,
        {
            "human_review": "human_review",
            "skip_review": END,
        }
    )
    
    workflow.add_edge("human_review", END)
    
    return workflow


def build_prediction_only_graph() -> StateGraph:
    """
    构建仅风险预测的图（不含预警流程）
    
    流程：
    predict_path_risk -> predict_operation_risk -> predict_disaster_spread -> human_review -> END
    """
    workflow = StateGraph(EarlyWarningState)
    
    workflow.add_node("predict_path_risk", predict_path_risk)
    workflow.add_node("predict_operation_risk", predict_operation_risk)
    workflow.add_node("predict_disaster_spread", predict_disaster_spread)
    workflow.add_node("human_review", human_review_gate)
    
    workflow.set_entry_point("predict_path_risk")
    
    workflow.add_edge("predict_path_risk", "predict_operation_risk")
    workflow.add_edge("predict_operation_risk", "predict_disaster_spread")
    
    workflow.add_conditional_edges(
        "predict_disaster_spread",
        should_human_review,
        {
            "human_review": "human_review",
            "skip_review": END,
        }
    )
    
    workflow.add_edge("human_review", END)
    
    return workflow


# 编译图
early_warning_graph = build_early_warning_graph().compile()

# 仅预测图（用于独立调用风险预测）
prediction_graph = build_prediction_only_graph().compile(
    interrupt_before=["human_review"]
)
