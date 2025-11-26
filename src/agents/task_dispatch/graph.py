"""
任务调度LangGraph定义

定义5节点的任务调度流程图
"""
from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from .state import TaskDispatchState
from .nodes import (
    decompose_scheme,
    schedule_tasks,
    plan_routes,
    assign_executors,
    generate_dispatch_orders,
)

logger = logging.getLogger(__name__)


def build_task_dispatch_graph() -> CompiledStateGraph:
    """
    构建任务调度LangGraph
    
    流程：
    1. decompose_scheme - 方案拆解为任务
    2. schedule_tasks - 任务调度（依赖排序、时间安排）
    3. plan_routes - 多车辆路径规划
    4. assign_executors - 执行者分配
    5. generate_dispatch_orders - 生成调度单
    
    Returns:
        编译后的StateGraph
    """
    logger.info("构建任务调度LangGraph...")
    
    # 创建StateGraph
    builder = StateGraph(TaskDispatchState)
    
    # 添加节点
    builder.add_node("decompose_scheme", decompose_scheme)
    builder.add_node("schedule_tasks", schedule_tasks)
    builder.add_node("plan_routes", plan_routes)
    builder.add_node("assign_executors", assign_executors)
    builder.add_node("generate_dispatch_orders", generate_dispatch_orders)
    
    # 定义边（线性流程）
    builder.add_edge(START, "decompose_scheme")
    builder.add_edge("decompose_scheme", "schedule_tasks")
    builder.add_edge("schedule_tasks", "plan_routes")
    builder.add_edge("plan_routes", "assign_executors")
    builder.add_edge("assign_executors", "generate_dispatch_orders")
    builder.add_edge("generate_dispatch_orders", END)
    
    # 编译图
    graph = builder.compile()
    
    logger.info("任务调度LangGraph构建完成")
    return graph
