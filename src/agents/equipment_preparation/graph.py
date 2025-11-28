"""
装备准备智能体图构建

流程：
```
START 
  │
  ├─→ understand_disaster (共享子图)
  │     │
  ▼     ▼
analyze_requirements
  │
  ▼
query_warehouse
  │
  ▼
match_and_recommend
  │
  ▼
analyze_shortage
  │
  ▼
generate_loading_plan
  │
  ▼
save_result
  │
  ▼
END
```
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, START, END

from .state import EquipmentPreparationState
from .nodes import (
    analyze_requirements,
    query_warehouse,
    match_and_recommend,
    analyze_shortage,
    generate_loading_plan,
    save_result,
)
from src.agents.shared.disaster_analysis import (
    understand_disaster,
    generate_summary,
)

logger = logging.getLogger(__name__)


async def _disaster_analysis_node(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    灾情分析封装节点
    
    将共享的灾情分析逻辑封装为本图的节点。
    """
    # 准备子图输入
    subgraph_state = {
        "disaster_description": state.get("disaster_description", ""),
        "structured_input": state.get("structured_input", {}),
        "errors": state.get("errors", []),
        "trace": state.get("trace", {}),
    }
    
    # 执行灾情理解
    result = await understand_disaster(subgraph_state)
    
    # 更新状态
    subgraph_state.update(result)
    
    # 执行摘要生成
    summary_result = await generate_summary(subgraph_state)
    subgraph_state.update(summary_result)
    
    return {
        "parsed_disaster": subgraph_state.get("parsed_disaster"),
        "similar_cases": subgraph_state.get("similar_cases", []),
        "understanding_summary": subgraph_state.get("understanding_summary", ""),
        "errors": subgraph_state.get("errors", []),
        "trace": subgraph_state.get("trace", {}),
        "current_phase": "disaster_analysis",
    }


def build_equipment_preparation_graph() -> StateGraph:
    """
    构建装备准备智能体图
    
    Returns:
        未编译的StateGraph
    """
    logger.info("构建装备准备智能体图...")
    
    workflow = StateGraph(EquipmentPreparationState)
    
    # 添加节点
    workflow.add_node("disaster_analysis", _disaster_analysis_node)
    workflow.add_node("analyze_requirements", analyze_requirements)
    workflow.add_node("query_warehouse", query_warehouse)
    workflow.add_node("match_recommend", match_and_recommend)
    workflow.add_node("analyze_shortage", analyze_shortage)
    workflow.add_node("generate_loading", generate_loading_plan)
    workflow.add_node("save_result", save_result)
    
    # 定义边（顺序执行）
    workflow.add_edge(START, "disaster_analysis")
    workflow.add_edge("disaster_analysis", "analyze_requirements")
    workflow.add_edge("analyze_requirements", "query_warehouse")
    workflow.add_edge("query_warehouse", "match_recommend")
    workflow.add_edge("match_recommend", "analyze_shortage")
    workflow.add_edge("analyze_shortage", "generate_loading")
    workflow.add_edge("generate_loading", "save_result")
    workflow.add_edge("save_result", END)
    
    return workflow


# 编译后的图（单例）
_compiled_graph = None


def get_equipment_preparation_graph():
    """获取编译后的装备准备智能体图（单例）"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_equipment_preparation_graph()
        _compiled_graph = workflow.compile()
        logger.info("装备准备智能体图编译完成")
    return _compiled_graph


async def run_equipment_preparation(
    event_id: str,
    disaster_description: str,
    structured_input: Optional[Dict[str, Any]] = None,
) -> EquipmentPreparationState:
    """
    运行装备准备智能体
    
    Args:
        event_id: 关联事件ID
        disaster_description: 灾情描述
        structured_input: 结构化输入（位置、类型提示等）
        
    Returns:
        最终状态，包含推荐结果
    """
    logger.info(f"启动装备准备智能体，事件ID: {event_id}")
    start_time = time.time()
    
    graph = get_equipment_preparation_graph()
    
    initial_state: EquipmentPreparationState = {
        "event_id": event_id,
        "disaster_description": disaster_description,
        "structured_input": structured_input or {},
        "errors": [],
        "trace": {
            "phases_executed": [],
            "llm_calls": 0,
            "start_time": start_time,
        },
    }
    
    # 执行图
    final_state = await graph.ainvoke(initial_state)
    
    # 记录总耗时
    total_time = int((time.time() - start_time) * 1000)
    if isinstance(final_state.get("trace"), dict):
        final_state["trace"]["total_time_ms"] = total_time
    
    logger.info(
        f"装备准备智能体执行完成",
        extra={
            "event_id": event_id,
            "total_time_ms": total_time,
            "devices_recommended": len(final_state.get("recommended_devices", [])),
            "supplies_recommended": len(final_state.get("recommended_supplies", [])),
            "shortage_alerts": len(final_state.get("shortage_alerts", [])),
        }
    )
    
    return final_state
