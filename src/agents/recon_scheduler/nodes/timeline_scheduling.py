"""
Phase 7: 时间线编排节点

任务时序安排、关键路径分析、里程碑定义。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..state import (
    ReconSchedulerState,
    TimelineScheduling,
    TimelineEvent,
    Milestone,
    GanttBar,
)

logger = logging.getLogger(__name__)


async def timeline_scheduling_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    时间线编排节点
    
    输入:
        - flight_plans: 航线计划列表
        - mission_phases: 任务阶段列表
        - resource_allocation: 资源分配结果
    
    输出:
        - timeline_scheduling: 时间线编排结果
        - milestones: 里程碑列表
        - critical_path: 关键路径
        - total_duration_min: 总时长
    """
    logger.info("Phase 7: 时间线编排")
    
    flight_plans = state.get("flight_plans", [])
    mission_phases = state.get("mission_phases", [])
    resource_allocation = state.get("resource_allocation", {})
    
    allocations = resource_allocation.get("allocations", [])
    
    # 生成时间线事件
    timeline = []
    gantt_data = []
    current_time = 0
    
    # 按阶段组织任务
    phase_tasks = {}
    for alloc in allocations:
        task_id = alloc.get("task_id", "")
        # 从任务ID中提取阶段号
        parts = task_id.split("_")
        phase = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        
        if phase not in phase_tasks:
            phase_tasks[phase] = []
        phase_tasks[phase].append(alloc)
    
    # 按阶段生成时间线
    for phase_num in sorted(phase_tasks.keys()):
        phase_allocs = phase_tasks[phase_num]
        phase_config = next((p for p in mission_phases if p.get("phase_number") == phase_num), None)
        phase_name = phase_config.get("phase_name", f"阶段{phase_num}") if phase_config else f"阶段{phase_num}"
        
        # 阶段开始事件
        timeline.append({
            "event_id": f"event_phase_{phase_num}_start",
            "event_type": "phase_change",
            "time_min": current_time,
            "task_id": None,
            "device_id": None,
            "description": f"{phase_name}开始",
        })
        
        phase_start_time = current_time
        phase_max_end = current_time
        
        # 同一阶段内的任务可以并行
        for alloc in phase_allocs:
            task_id = alloc.get("task_id", "")
            device_id = alloc.get("device_id", "")
            device_name = alloc.get("device_name", "")
            
            # 查找对应的航线计划
            flight_plan = next((fp for fp in flight_plans if fp.get("task_id") == task_id), None)
            duration = alloc.get("estimated_duration_min", 30)
            
            if flight_plan:
                duration = flight_plan.get("statistics", {}).get("total_duration_min", duration)
            
            task_start = phase_start_time
            task_end = task_start + duration
            
            # 任务开始事件
            timeline.append({
                "event_id": f"event_{task_id}_start",
                "event_type": "task_start",
                "time_min": task_start,
                "task_id": task_id,
                "device_id": device_id,
                "description": f"任务开始: {task_id}",
            })
            
            # 任务结束事件
            timeline.append({
                "event_id": f"event_{task_id}_end",
                "event_type": "task_end",
                "time_min": task_end,
                "task_id": task_id,
                "device_id": device_id,
                "description": f"任务完成: {task_id}",
            })
            
            # 甘特图条目
            gantt_data.append({
                "task_id": task_id,
                "task_name": flight_plan.get("task_name", task_id) if flight_plan else task_id,
                "device_name": device_name,
                "start_min": task_start,
                "end_min": task_end,
                "phase": phase_num,
                "is_critical": True if phase_num == 1 else False,
            })
            
            phase_max_end = max(phase_max_end, task_end)
        
        # 更新当前时间到阶段结束
        current_time = phase_max_end + 5  # 阶段间隔5分钟
    
    # 生成里程碑
    milestones = _generate_milestones(timeline, mission_phases)
    
    # 识别关键路径（简化：第一阶段的所有任务）
    critical_path = [g["task_id"] for g in gantt_data if g.get("is_critical")]
    
    # 计算总时长
    total_duration = max(e["time_min"] for e in timeline) if timeline else 0
    
    # 计算最大并行任务数
    max_parallel = _calculate_max_parallel(gantt_data)
    
    # 构建结果
    timeline_scheduling: TimelineScheduling = {
        "timeline": timeline,
        "gantt_data": gantt_data,
        "milestones": milestones,
        "critical_path": critical_path,
        "total_duration_min": total_duration,
        "max_parallel_tasks": max_parallel,
    }
    
    logger.info(f"时间线编排完成: 总时长={total_duration}min, 事件数={len(timeline)}, "
                f"最大并行={max_parallel}")
    
    return {
        "timeline_scheduling": timeline_scheduling,
        "milestones": milestones,
        "critical_path": critical_path,
        "total_duration_min": total_duration,
        "current_phase": "timeline_scheduling",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "timeline_scheduling",
            "timestamp": datetime.now().isoformat(),
            "total_duration_min": total_duration,
        }],
    }


def _generate_milestones(
    timeline: List[TimelineEvent],
    mission_phases: List[Dict[str, Any]]
) -> List[Milestone]:
    """生成里程碑"""
    milestones = []
    
    # 任务开始里程碑
    milestones.append({
        "milestone_id": "ms_mission_start",
        "name": "任务开始",
        "time_min": 0,
        "criteria": "所有设备就绪，首批任务起飞",
        "dependencies": [],
    })
    
    # 每个阶段完成的里程碑
    phase_ends = {}
    for event in timeline:
        if event.get("event_type") == "task_end":
            task_id = event.get("task_id", "")
            parts = task_id.split("_")
            phase = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            
            if phase not in phase_ends:
                phase_ends[phase] = 0
            phase_ends[phase] = max(phase_ends[phase], event.get("time_min", 0))
    
    for phase_num, end_time in sorted(phase_ends.items()):
        phase_config = next((p for p in mission_phases if p.get("phase_number") == phase_num), None)
        phase_name = phase_config.get("phase_name", f"阶段{phase_num}") if phase_config else f"阶段{phase_num}"
        
        milestones.append({
            "milestone_id": f"ms_phase_{phase_num}_complete",
            "name": f"{phase_name}完成",
            "time_min": end_time,
            "criteria": f"阶段{phase_num}所有任务完成",
            "dependencies": [f"ms_phase_{phase_num-1}_complete"] if phase_num > 1 else ["ms_mission_start"],
        })
    
    # 任务完成里程碑
    max_time = max(e["time_min"] for e in timeline) if timeline else 0
    milestones.append({
        "milestone_id": "ms_mission_complete",
        "name": "任务完成",
        "time_min": max_time,
        "criteria": "所有侦察任务完成，设备返回",
        "dependencies": [m["milestone_id"] for m in milestones if m["milestone_id"].startswith("ms_phase_")],
    })
    
    return milestones


def _calculate_max_parallel(gantt_data: List[GanttBar]) -> int:
    """计算最大并行任务数"""
    if not gantt_data:
        return 0
    
    # 收集所有时间点
    events = []
    for bar in gantt_data:
        events.append((bar["start_min"], 1))   # 开始 +1
        events.append((bar["end_min"], -1))    # 结束 -1
    
    # 按时间排序
    events.sort(key=lambda x: (x[0], -x[1]))  # 同一时间点，结束在开始之前
    
    # 计算最大并行数
    current = 0
    max_parallel = 0
    for _, delta in events:
        current += delta
        max_parallel = max(max_parallel, current)
    
    return max_parallel
