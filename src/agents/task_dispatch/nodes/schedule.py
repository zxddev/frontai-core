"""
任务调度节点

调用TaskScheduler算法执行任务调度，生成时间表和关键路径
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.planning.algorithms.scheduling import TaskScheduler
from src.planning.algorithms.base import AlgorithmStatus

from ..state import (
    TaskDispatchState,
    ScheduledTaskState,
    DecomposedTaskState,
)

logger = logging.getLogger(__name__)

# TaskScheduler单例
_scheduler: TaskScheduler | None = None


def _get_scheduler() -> TaskScheduler:
    """获取TaskScheduler单例"""
    global _scheduler
    if _scheduler is None:
        logger.info("初始化TaskScheduler")
        _scheduler = TaskScheduler()
    return _scheduler


def schedule_tasks(state: TaskDispatchState) -> Dict[str, Any]:
    """
    任务调度节点
    
    调用TaskScheduler执行任务调度，输出时间表和关键路径
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    decomposed_tasks = state.get("decomposed_tasks", [])
    available_resources = state.get("available_resources", [])
    dispatch_config = state.get("dispatch_config", {})
    
    logger.info(
        f"开始任务调度: {len(decomposed_tasks)} 个任务, {len(available_resources)} 个资源",
        extra={"event_id": state.get("event_id")}
    )
    
    if not decomposed_tasks:
        logger.warning("无任务需要调度")
        return {
            "scheduled_tasks": [],
            "critical_path_tasks": [],
            "makespan_min": 0,
            "trace": _update_trace(state, "schedule_tasks", {"status": "skipped", "reason": "no_tasks"}),
        }
    
    # 构建TaskScheduler输入
    scheduler_input = _build_scheduler_input(decomposed_tasks, available_resources, dispatch_config)
    
    # 执行调度
    scheduler = _get_scheduler()
    result = scheduler.run(scheduler_input)
    
    logger.info(
        f"TaskScheduler执行完成: status={result.status.value}",
        extra={"metrics": result.metrics}
    )
    
    # 处理结果
    if result.status == AlgorithmStatus.ERROR:
        error_msg = result.message or "任务调度算法执行失败"
        logger.error(f"任务调度失败: {error_msg}")
        return {
            "scheduled_tasks": [],
            "critical_path_tasks": [],
            "makespan_min": 0,
            "errors": state.get("errors", []) + [error_msg],
            "trace": _update_trace(state, "schedule_tasks", {"status": "error", "message": error_msg}),
        }
    
    if result.status == AlgorithmStatus.INFEASIBLE:
        logger.error("任务调度无可行解")
        return {
            "scheduled_tasks": [],
            "critical_path_tasks": [],
            "makespan_min": 0,
            "errors": state.get("errors", []) + ["任务调度无可行解，可能存在依赖循环或资源不足"],
            "trace": _update_trace(state, "schedule_tasks", {"status": "infeasible"}),
        }
    
    # 解析调度结果
    solution = result.solution or {}
    schedule_data = solution.get("schedule", [])
    
    scheduled_tasks = _parse_scheduled_tasks(schedule_data, decomposed_tasks)
    critical_path_tasks = _identify_critical_path(scheduled_tasks)
    makespan = result.metrics.get("makespan_min", 0)
    
    logger.info(
        f"任务调度成功: {len(scheduled_tasks)} 个任务已调度, 总工期 {makespan} 分钟",
        extra={"critical_path_count": len(critical_path_tasks)}
    )
    
    return {
        "scheduled_tasks": scheduled_tasks,
        "critical_path_tasks": critical_path_tasks,
        "makespan_min": int(makespan),
        "trace": _update_trace(state, "schedule_tasks", {
            "status": "success",
            "scheduled_count": len(scheduled_tasks),
            "makespan_min": makespan,
            "critical_path_count": len(critical_path_tasks),
            "resource_utilization": result.metrics.get("resource_utilization", {}),
        }),
    }


def _build_scheduler_input(
    tasks: List[DecomposedTaskState],
    resources: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """构建TaskScheduler输入格式"""
    # 转换任务格式
    scheduler_tasks = []
    for task in tasks:
        scheduler_tasks.append({
            "id": task["task_id"],
            "name": task["task_name"],
            "duration_min": task["duration_min"],
            "priority": task["priority"],
            "predecessors": task.get("predecessors", []),
            "required_resources": task.get("required_resources", {}),
            "required_skills": task.get("required_skills", []),
            "deadline": task.get("deadline_min"),
        })
    
    # 转换资源格式
    scheduler_resources = []
    for res in resources:
        scheduler_resources.append({
            "id": res.get("id", res.get("team_id", "")),
            "name": res.get("name", res.get("team_name", "")),
            "type": res.get("type", res.get("team_type", "rescue_team")),
            "skills": res.get("skills", res.get("capabilities", [])),
            "capacity": res.get("capacity", 1),
        })
    
    # 如果没有资源，使用默认资源
    if not scheduler_resources:
        logger.warning("无可用资源，使用默认资源配置")
        scheduler_resources = _generate_default_resources(tasks)
    
    return {
        "tasks": scheduler_tasks,
        "resources": scheduler_resources,
        "start_time": config.get("start_time", 0),
        "scheduling_strategy": config.get("strategy", "critical_path"),
    }


def _generate_default_resources(tasks: List[DecomposedTaskState]) -> List[Dict[str, Any]]:
    """根据任务需求生成默认资源"""
    # 收集所有需要的资源类型
    resource_types: Dict[str, int] = {}
    all_skills: set = set()
    
    for task in tasks:
        for rtype, count in task.get("required_resources", {}).items():
            resource_types[rtype] = max(resource_types.get(rtype, 0), count)
        all_skills.update(task.get("required_skills", []))
    
    # 生成资源
    resources = []
    for rtype, count in resource_types.items():
        for i in range(count):
            resources.append({
                "id": f"default-{rtype}-{i+1}",
                "name": f"默认{rtype}-{i+1}",
                "type": rtype,
                "skills": list(all_skills),
                "capacity": 1,
            })
    
    return resources


def _parse_scheduled_tasks(
    schedule_data: List[Dict[str, Any]],
    original_tasks: List[DecomposedTaskState],
) -> List[ScheduledTaskState]:
    """解析调度结果"""
    scheduled_tasks: List[ScheduledTaskState] = []
    
    # 建立任务ID到原始任务的映射
    task_map = {t["task_id"]: t for t in original_tasks}
    
    for item in schedule_data:
        task_id = item.get("task_id", "")
        original = task_map.get(task_id, {})
        
        scheduled_tasks.append(ScheduledTaskState(
            task_id=task_id,
            task_name=item.get("task_name", original.get("task_name", "")),
            start_time_min=item.get("start_time", 0),
            end_time_min=item.get("end_time", 0),
            assigned_resource_ids=item.get("resource_ids", []),
            priority=item.get("priority", original.get("priority", 3)),
            is_critical_path=False,  # 后续标记
        ))
    
    return scheduled_tasks


def _identify_critical_path(tasks: List[ScheduledTaskState]) -> List[str]:
    """识别关键路径上的任务"""
    if not tasks:
        return []
    
    # 找到最晚结束的任务
    max_end = max(t["end_time_min"] for t in tasks)
    
    # 关键路径：结束时间等于最大结束时间的任务链
    critical_tasks = []
    for task in tasks:
        # 简化处理：将高优先级且结束时间接近最大值的任务标记为关键路径
        if task["priority"] <= 2 or task["end_time_min"] >= max_end - 30:
            critical_tasks.append(task["task_id"])
            task["is_critical_path"] = True
    
    return critical_tasks


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
