"""
执行者分配和调度单生成节点

为每个任务分配具体执行者，生成调度单
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4

from ..state import (
    TaskDispatchState,
    ExecutorAssignmentState,
    DispatchOrderState,
    GanttItemState,
    ScheduledTaskState,
    PlannedRouteState,
)

logger = logging.getLogger(__name__)

# 任务类型颜色映射（用于甘特图）
TASK_TYPE_COLORS: Dict[str, str] = {
    "search_rescue": "#e74c3c",
    "fire_fighting": "#f39c12",
    "medical": "#27ae60",
    "logistics": "#3498db",
    "evacuation": "#9b59b6",
    "hazmat": "#e67e22",
    "assessment": "#1abc9c",
    "communication": "#95a5a6",
}


def assign_executors(state: TaskDispatchState) -> Dict[str, Any]:
    """
    执行者分配节点
    
    为每个调度任务分配具体执行者（队伍/车辆/人员）
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    scheduled_tasks = state.get("scheduled_tasks", [])
    available_resources = state.get("available_resources", [])
    planned_routes = state.get("planned_routes", [])
    decomposed_tasks = state.get("decomposed_tasks", [])
    
    logger.info(
        f"开始执行者分配: {len(scheduled_tasks)} 个任务",
        extra={"event_id": state.get("event_id")}
    )
    
    if not scheduled_tasks:
        logger.warning("无调度任务，跳过执行者分配")
        return {
            "executor_assignments": [],
            "trace": _update_trace(state, "assign_executors", {"status": "skipped", "reason": "no_tasks"}),
        }
    
    # 建立任务到原始数据的映射
    task_map = {t["task_id"]: t for t in decomposed_tasks}
    
    # 建立路线到车辆的映射
    route_vehicle_map = {r["vehicle_id"]: r for r in planned_routes}
    
    # 建立资源ID到资源详情的映射
    resource_map = {r.get("id", r.get("team_id", "")): r for r in available_resources}
    
    # 分配执行者
    assignments: List[ExecutorAssignmentState] = []
    
    for task in scheduled_tasks:
        task_id = task["task_id"]
        task_name = task["task_name"]
        original_task = task_map.get(task_id, {})
        
        assigned_ids = task.get("assigned_resource_ids", [])
        
        for idx, rid in enumerate(assigned_ids):
            resource = resource_map.get(rid, {})
            
            # 获取ETA
            route = route_vehicle_map.get(rid)
            eta = _calculate_eta(task, route)
            
            assignment = ExecutorAssignmentState(
                task_id=task_id,
                task_name=task_name,
                executor_id=rid,
                executor_name=resource.get("name", resource.get("team_name", rid)),
                executor_type=_determine_executor_type(resource),
                role="leader" if idx == 0 else "member",
                route_id=rid if route else None,
                eta_min=eta,
                contact_info=resource.get("contact_info"),
            )
            assignments.append(assignment)
        
        # 如果没有分配资源，使用默认
        if not assigned_ids:
            source_alloc_id = original_task.get("source_allocation_id")
            executor_name = "待分配"
            if source_alloc_id and source_alloc_id in resource_map:
                res = resource_map[source_alloc_id]
                executor_name = res.get("name", res.get("team_name", "待分配"))
            
            assignment = ExecutorAssignmentState(
                task_id=task_id,
                task_name=task_name,
                executor_id=source_alloc_id or f"default-{task_id}",
                executor_name=executor_name,
                executor_type="team",
                role="leader",
                route_id=None,
                eta_min=task["start_time_min"],
                contact_info=None,
            )
            assignments.append(assignment)
    
    logger.info(f"执行者分配完成: {len(assignments)} 个分配")
    
    return {
        "executor_assignments": assignments,
        "trace": _update_trace(state, "assign_executors", {
            "status": "success",
            "assignment_count": len(assignments),
        }),
    }


def generate_dispatch_orders(state: TaskDispatchState) -> Dict[str, Any]:
    """
    生成调度单节点
    
    基于执行者分配生成完整的调度单和甘特图数据
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    executor_assignments = state.get("executor_assignments", [])
    scheduled_tasks = state.get("scheduled_tasks", [])
    decomposed_tasks = state.get("decomposed_tasks", [])
    planned_routes = state.get("planned_routes", [])
    dispatch_config = state.get("dispatch_config", {})
    
    logger.info(
        f"开始生成调度单: {len(executor_assignments)} 个分配",
        extra={"event_id": state.get("event_id")}
    )
    
    # 建立任务映射
    task_map = {t["task_id"]: t for t in decomposed_tasks}
    scheduled_map = {t["task_id"]: t for t in scheduled_tasks}
    
    # 计算基准时间
    base_time = datetime.utcnow()
    if dispatch_config.get("base_time"):
        try:
            base_time = datetime.fromisoformat(dispatch_config["base_time"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    # 生成调度单
    dispatch_orders: List[DispatchOrderState] = []
    
    # 按任务分组分配
    task_assignments: Dict[str, List[ExecutorAssignmentState]] = {}
    for assign in executor_assignments:
        tid = assign["task_id"]
        if tid not in task_assignments:
            task_assignments[tid] = []
        task_assignments[tid].append(assign)
    
    for task_id, assigns in task_assignments.items():
        original = task_map.get(task_id, {})
        scheduled = scheduled_map.get(task_id, {})
        
        for assign in assigns:
            # 只为leader生成调度单
            if assign["role"] != "leader":
                continue
            
            order_id = f"order-{uuid4().hex[:8]}"
            
            # 计算时间
            start_min = scheduled.get("start_time_min", 0)
            end_min = scheduled.get("end_time_min", start_min + 60)
            start_time = base_time + timedelta(minutes=start_min)
            end_time = base_time + timedelta(minutes=end_min)
            
            # 生成指令
            instructions = _generate_instructions(original, scheduled, assign)
            
            # 获取所需装备
            required_equipment = _get_required_equipment(original)
            
            # 获取路线摘要
            route_summary = _get_route_summary(assign["executor_id"], planned_routes)
            
            order = DispatchOrderState(
                order_id=order_id,
                task_id=task_id,
                task_name=assign["task_name"],
                executor_id=assign["executor_id"],
                executor_name=assign["executor_name"],
                priority=scheduled.get("priority", 3),
                scheduled_start_time=start_time.isoformat() + "Z",
                scheduled_end_time=end_time.isoformat() + "Z",
                location=original.get("location", {"latitude": 31.2, "longitude": 121.5}),
                instructions=instructions,
                required_equipment=required_equipment,
                route_summary=route_summary,
                status="pending",
            )
            dispatch_orders.append(order)
    
    # 生成甘特图数据
    gantt_data = _generate_gantt_data(scheduled_tasks, executor_assignments, task_map)
    
    logger.info(f"调度单生成完成: {len(dispatch_orders)} 个调度单, {len(gantt_data)} 个甘特图项")
    
    return {
        "dispatch_orders": dispatch_orders,
        "gantt_data": gantt_data,
        "trace": _update_trace(state, "generate_dispatch_orders", {
            "status": "success",
            "order_count": len(dispatch_orders),
            "gantt_items": len(gantt_data),
        }),
    }


def _determine_executor_type(resource: Dict[str, Any]) -> str:
    """确定执行者类型"""
    res_type = resource.get("type", resource.get("team_type", ""))
    if "vehicle" in res_type.lower():
        return "vehicle"
    if "individual" in res_type.lower() or "person" in res_type.lower():
        return "individual"
    return "team"


def _calculate_eta(task: ScheduledTaskState, route: PlannedRouteState | None) -> int:
    """计算预计到达时间"""
    if route:
        for stop in route.get("stops", []):
            if stop.get("task_id") == task["task_id"]:
                return stop.get("arrival_time_min", task["start_time_min"])
    return task["start_time_min"]


def _generate_instructions(
    original: Dict[str, Any],
    scheduled: Dict[str, Any],
    assign: ExecutorAssignmentState,
) -> List[str]:
    """生成任务指令"""
    task_type = original.get("task_type", "")
    instructions = []
    
    # 通用指令
    instructions.append(f"执行{original.get('task_name', '任务')}")
    
    # 根据任务类型添加特定指令
    if task_type == "search_rescue":
        instructions.extend([
            "携带生命探测仪进行搜索",
            "发现被困人员立即标记位置并上报",
            "确保自身安全，注意余震和二次坍塌",
        ])
    elif task_type == "fire_fighting":
        instructions.extend([
            "评估火势规模和蔓延方向",
            "建立安全警戒线",
            "优先保护人员安全和重要设施",
        ])
    elif task_type == "medical":
        instructions.extend([
            "对伤员进行分级检伤",
            "优先处理危重伤员",
            "建立临时医疗点",
        ])
    elif task_type == "evacuation":
        instructions.extend([
            "确认疏散路线安全",
            "引导群众有序撤离",
            "统计疏散人数",
        ])
    
    # 优先级提示
    if scheduled.get("priority", 3) <= 1:
        instructions.insert(0, "【紧急】此任务为最高优先级")
    
    return instructions


def _get_required_equipment(task: Dict[str, Any]) -> List[str]:
    """获取任务所需装备"""
    task_type = task.get("task_type", "")
    equipment_map = {
        "search_rescue": ["生命探测仪", "破拆工具", "急救包", "通信设备"],
        "fire_fighting": ["消防水带", "灭火器", "防护服", "呼吸器"],
        "medical": ["急救药品", "担架", "医疗器械", "急救包"],
        "logistics": ["运输车辆", "物资清单", "装卸工具"],
        "evacuation": ["扩音器", "警示标志", "疏散指示牌"],
        "hazmat": ["防化服", "检测仪", "洗消设备", "隔离带"],
    }
    return equipment_map.get(task_type, ["通信设备", "基础装备"])


def _get_route_summary(executor_id: str, routes: List[PlannedRouteState]) -> str | None:
    """获取路线摘要"""
    for route in routes:
        if route["vehicle_id"] == executor_id:
            stops = route.get("stops", [])
            distance = route.get("total_distance_km", 0)
            time = route.get("total_time_min", 0)
            return f"途经 {len(stops)} 个任务点，总距离 {distance:.1f}km，预计耗时 {time} 分钟"
    return None


def _generate_gantt_data(
    tasks: List[ScheduledTaskState],
    assignments: List[ExecutorAssignmentState],
    task_map: Dict[str, Dict[str, Any]],
) -> List[GanttItemState]:
    """生成甘特图数据"""
    gantt_items: List[GanttItemState] = []
    
    # 建立任务到执行者的映射
    task_executor_map: Dict[str, str] = {}
    task_executor_name_map: Dict[str, str] = {}
    for assign in assignments:
        if assign["role"] == "leader":
            task_executor_map[assign["task_id"]] = assign["executor_id"]
            task_executor_name_map[assign["task_id"]] = assign["executor_name"]
    
    for task in tasks:
        task_id = task["task_id"]
        original = task_map.get(task_id, {})
        task_type = original.get("task_type", "")
        
        gantt_items.append(GanttItemState(
            task_id=task_id,
            task_name=task["task_name"],
            resource_id=task_executor_map.get(task_id, "unassigned"),
            resource_name=task_executor_name_map.get(task_id, "待分配"),
            start_min=task["start_time_min"],
            end_min=task["end_time_min"],
            color=TASK_TYPE_COLORS.get(task_type, "#95a5a6"),
        ))
    
    return gantt_items


def _update_trace(
    state: TaskDispatchState,
    node_name: str,
    node_result: Dict[str, Any],
) -> Dict[str, Any]:
    """更新追踪信息"""
    trace = state.get("trace", {}).copy()
    nodes_executed = trace.get("nodes_executed", [])
    nodes_executed.append(node_name)
    trace["nodes_executed"] = nodes_executed
    trace[node_name] = node_result
    return trace
