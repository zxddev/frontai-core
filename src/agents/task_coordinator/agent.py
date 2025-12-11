"""
Task Coordinator Agent - LangGraph 流程定义

6阶段流水线：
1. receive_allocation - 接收任务分配
2. match_sop - 匹配 SOP 模板
3. decompose_steps - 分解步骤
4. assign_roles - 分配角色
5. match_equipment - 匹配设备
6. generate_instructions - 生成指令
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END

from .state import TaskCoordinatorState
from .schemas import TaskAllocation, TaskCoordinatorInput, TaskCoordinatorOutput
from .nodes import (
    receive_allocation,
    match_sop,
    decompose_steps,
    assign_roles,
    match_equipment,
    generate_instructions,
)

logger = logging.getLogger(__name__)


def create_task_coordinator_graph() -> StateGraph:
    """
    创建 Task Coordinator 状态图

    流程：
    receive_allocation → match_sop → decompose_steps → assign_roles
                                                           ↓
                         END ← generate_instructions ← match_equipment

    Returns:
        编译后的 StateGraph
    """
    # 创建状态图
    graph = StateGraph(TaskCoordinatorState)

    # 添加节点
    graph.add_node("receive_allocation", receive_allocation)
    graph.add_node("match_sop", match_sop)
    graph.add_node("decompose_steps", decompose_steps)
    graph.add_node("assign_roles", assign_roles)
    graph.add_node("match_equipment", match_equipment)
    graph.add_node("generate_instructions", generate_instructions)

    # 设置入口
    graph.set_entry_point("receive_allocation")

    # 添加边（线性流程）
    graph.add_edge("receive_allocation", "match_sop")
    graph.add_edge("match_sop", "decompose_steps")
    graph.add_edge("decompose_steps", "assign_roles")
    graph.add_edge("assign_roles", "match_equipment")
    graph.add_edge("match_equipment", "generate_instructions")
    graph.add_edge("generate_instructions", END)

    return graph.compile()


async def run_task_coordinator(
    event_id: str,
    task_allocation: TaskAllocation,
    disaster_info: Optional[Dict[str, Any]] = None,
) -> TaskCoordinatorOutput:
    """
    运行 Task Coordinator Agent

    Args:
        event_id: 事件ID
        task_allocation: 来自 emergency_ai 的任务分配
        disaster_info: 灾情信息（可选）

    Returns:
        TaskCoordinatorOutput 包含步骤级指令
    """
    logger.info(
        f"[TaskCoordinator] 开始协调任务: event_id={event_id}, "
        f"task_id={task_allocation.task_id}"
    )

    # 构建初始状态
    initial_state: TaskCoordinatorState = {
        "event_id": event_id,
        "task_allocation": task_allocation,
        "disaster_info": disaster_info,
        "current_phase": "receive_allocation",
        "warnings": [],
        "errors": [],
        "trace": {},
        "execution_time_ms": 0,
    }

    # 创建并运行图
    graph = create_task_coordinator_graph()
    final_state = await graph.ainvoke(initial_state)

    # 提取输出
    output = final_state.get("final_output")
    if not output:
        raise RuntimeError("[TaskCoordinator] 未能生成有效输出")

    logger.info(
        f"[TaskCoordinator] 协调完成: "
        f"steps={output.total_steps}, "
        f"duration={output.estimated_duration_minutes}min"
    )

    return output


async def coordinate_from_emergency_ai(
    emergency_ai_output: Dict[str, Any],
) -> Dict[str, TaskCoordinatorOutput]:
    """
    从 emergency_ai 输出批量协调任务

    Args:
        emergency_ai_output: emergency_ai 的完整输出

    Returns:
        {task_id: TaskCoordinatorOutput} 映射
    """
    event_id = emergency_ai_output.get("event_id", "unknown")
    recommended_scheme = emergency_ai_output.get("recommended_scheme", {})
    allocations = recommended_scheme.get("allocations", [])
    parsed_disaster = emergency_ai_output.get("understanding", {}).get("parsed_disaster", {})

    results: Dict[str, TaskCoordinatorOutput] = {}

    for alloc in allocations:
        # 转换为 TaskAllocation
        task_allocation = TaskAllocation(
            task_id=alloc.get("task_id", alloc.get("resource_id", "unknown")),
            task_name=alloc.get("assigned_task_name", "救援任务"),
            disaster_type=parsed_disaster.get("disaster_type", "unknown"),
            scene_code=parsed_disaster.get("scene_code"),
            allocated_teams=[{
                "team_id": alloc.get("resource_id"),
                "team_name": alloc.get("resource_name"),
                "capabilities": alloc.get("assigned_capabilities", []),
                "equipment": alloc.get("equipments", []),
            }],
            location=alloc.get("location"),
            priority=alloc.get("priority", 1),
        )

        try:
            output = await run_task_coordinator(
                event_id=event_id,
                task_allocation=task_allocation,
                disaster_info=parsed_disaster,
            )
            results[task_allocation.task_id] = output
        except Exception as e:
            logger.error(f"[TaskCoordinator] 任务协调失败: {task_allocation.task_id}, {e}")

    return results
