"""
Phase 5: 资源分配节点

设备-任务匹配、约束检查、备份方案。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..state import (
    ReconSchedulerState,
    ResourceAllocation,
    TaskAllocation,
    CoordinatedGroup,
    DeviceStatus,
    ReconTask,
)

logger = logging.getLogger(__name__)


async def resource_allocation_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    资源分配节点
    
    输入:
        - all_tasks: 所有任务列表
        - available_devices: 可用设备列表
        - environment_assessment: 环境评估结果
    
    输出:
        - resource_allocation: 资源分配结果
        - unallocated_tasks: 未分配的任务
    """
    logger.info("Phase 5: 资源分配")
    
    all_tasks = state.get("all_tasks", [])
    available_devices = state.get("available_devices", [])
    environment = state.get("environment_assessment", {})
    
    weather = environment.get("weather", {})
    
    # 按优先级排序任务
    sorted_tasks = sorted(
        all_tasks,
        key=lambda t: _priority_score(t.get("priority", "medium")),
        reverse=True
    )
    
    # 分配结果
    allocations = []
    backup_allocations = []
    unallocated_tasks = []
    device_usage = {}  # 追踪设备使用情况
    
    for task in sorted_tasks:
        task_id = task.get("task_id", "")
        
        # 查找匹配的设备
        matches = _find_matching_devices(task, available_devices, weather, device_usage)
        
        if not matches:
            logger.warning(f"任务 {task_id} 无法找到匹配的设备")
            unallocated_tasks.append(task_id)
            continue
        
        # 选择最佳匹配
        best_match = matches[0]
        device_id = best_match["device_id"]
        
        # 创建分配
        allocation = _create_allocation(task, best_match, is_backup=False)
        allocations.append(allocation)
        
        # 更新设备使用情况
        if device_id not in device_usage:
            device_usage[device_id] = []
        device_usage[device_id].append({
            "task_id": task_id,
            "start_min": allocation.get("estimated_start_min", 0),
            "end_min": allocation.get("estimated_end_min", 0),
        })
        
        # 如果有备选，创建备份分配
        if len(matches) > 1:
            backup = _create_allocation(task, matches[1], is_backup=True)
            backup_allocations.append(backup)
    
    # 识别协同任务组（并行执行的任务）
    coordinated_groups = _identify_coordinated_groups(allocations, all_tasks)
    
    # 计算资源利用率
    resource_utilization = _calculate_utilization(device_usage, available_devices)
    
    # 构建分配结果
    resource_allocation: ResourceAllocation = {
        "allocations": allocations,
        "backup_allocations": backup_allocations,
        "unallocated_tasks": unallocated_tasks,
        "coordinated_groups": coordinated_groups,
        "resource_utilization": resource_utilization,
    }
    
    # 生成警告
    warnings = state.get("warnings", [])
    if unallocated_tasks:
        warnings.append(f"有{len(unallocated_tasks)}个任务无法分配设备: {unallocated_tasks}")
    
    # 检查关键任务是否都已分配
    critical_unallocated = [t for t in all_tasks 
                           if t.get("task_id") in unallocated_tasks 
                           and t.get("priority") == "critical"]
    if critical_unallocated:
        warnings.append(f"关键任务未分配: {[t.get('task_id') for t in critical_unallocated]}")
    
    logger.info(f"资源分配完成: 已分配={len(allocations)}, 未分配={len(unallocated_tasks)}")
    
    return {
        "resource_allocation": resource_allocation,
        "unallocated_tasks": unallocated_tasks,
        "warnings": warnings,
        "current_phase": "resource_allocation",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "resource_allocation",
            "timestamp": datetime.now().isoformat(),
            "allocated_count": len(allocations),
            "unallocated_count": len(unallocated_tasks),
        }],
    }


def _priority_score(priority: str) -> int:
    """优先级转换为分数"""
    scores = {
        "critical": 100,
        "high": 75,
        "medium": 50,
        "low": 25,
    }
    return scores.get(priority, 50)


def _find_matching_devices(
    task: ReconTask,
    devices: List[DeviceStatus],
    weather: Dict[str, Any],
    device_usage: Dict[str, List[Dict]]
) -> List[Dict[str, Any]]:
    """
    查找匹配任务的设备
    
    评分因素：
    - 能力匹配度 (40%)
    - 续航充足度 (25%)
    - 就绪时间 (15%)
    - 天气适应性 (20%)
    """
    requirements = task.get("device_requirements", {})
    type_preference = requirements.get("type_preference", [])
    capabilities_required = requirements.get("capabilities_required", [])
    min_endurance = requirements.get("min_endurance_min", 0)
    
    task_type = task.get("task_type", "")
    
    candidates = []
    
    for device in devices:
        device_id = device.get("device_id", "")
        device_type = device.get("device_type", "")
        category = device.get("category", "")
        capabilities = device.get("capabilities", [])
        endurance = device.get("effective_endurance_min", 0)
        ready_time = device.get("ready_time_min", 0)
        max_wind = device.get("max_wind_resistance_ms", 12)
        
        # 检查设备是否已被大量使用
        usage = device_usage.get(device_id, [])
        if len(usage) >= 3:  # 每个设备最多执行3个任务
            continue
        
        score = 0
        reasons = []
        
        # 1. 能力匹配 (40%)
        if capabilities_required:
            matched_caps = sum(1 for cap in capabilities_required if cap in capabilities)
            capability_score = (matched_caps / len(capabilities_required)) * 100
        else:
            capability_score = 100
        
        if capability_score < 50:
            continue  # 能力不足，跳过
        
        score += capability_score * 0.4
        reasons.append(f"能力匹配: {capability_score:.0f}%")
        
        # 2. 类型偏好 (bonus)
        type_match = False
        for pref in type_preference:
            if pref in category or pref in device_type:
                type_match = True
                score += 10  # 类型匹配加分
                reasons.append(f"类型匹配: {pref}")
                break
        
        # 3. 续航充足度 (25%)
        min_endurance_val = min_endurance or 0
        if min_endurance_val > 0 and endurance < min_endurance_val:
            continue  # 续航不足，跳过
        
        endurance_score = min(100, endurance / max(min_endurance_val, 30) * 100)
        score += endurance_score * 0.25
        reasons.append(f"续航: {endurance}min")
        
        # 4. 就绪时间 (15%)
        ready_score = max(0, 100 - ready_time * 5)
        score += ready_score * 0.15
        reasons.append(f"就绪: {ready_time}min")
        
        # 5. 天气适应性 (20%)
        wind_speed = weather.get("wind_speed_ms", 0)
        if wind_speed > 0:
            weather_score = min(100, max_wind / wind_speed * 50)
        else:
            weather_score = 100
        score += weather_score * 0.2
        
        candidates.append({
            "device_id": device_id,
            "device_name": device.get("device_name", ""),
            "device_category": category,
            "match_score": score,
            "match_reasons": reasons,
            "device": device,
        })
    
    # 按分数排序
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    
    return candidates


def _create_allocation(
    task: ReconTask,
    match: Dict[str, Any],
    is_backup: bool
) -> TaskAllocation:
    """创建任务分配"""
    device = match.get("device", {})
    
    # 估算任务时间
    scan_config = task.get("scan_config", {})
    altitude = scan_config.get("altitude_m", 100)
    speed = scan_config.get("speed_ms", 10)
    
    # 简化估算：假设覆盖1km²需要的时间
    estimated_duration = task.get("time_budget_min") or 30
    
    # 估算开始时间（基于任务阶段）
    phase = task.get("phase", 1)
    estimated_start = (phase - 1) * 30  # 每阶段30分钟
    
    return {
        "task_id": task.get("task_id", ""),
        "device_id": match.get("device_id", ""),
        "device_name": match.get("device_name", ""),
        "device_category": match.get("device_category", ""),
        
        "match_score": match.get("match_score", 0),
        "match_reasons": match.get("match_reasons", []),
        
        "capability_match": True,
        "endurance_sufficient": True,
        "weather_compatible": True,
        
        "estimated_start_min": estimated_start,
        "estimated_duration_min": estimated_duration,
        "estimated_end_min": estimated_start + estimated_duration,
        
        "is_backup": is_backup,
    }


def _identify_coordinated_groups(
    allocations: List[TaskAllocation],
    all_tasks: List[ReconTask]
) -> List[CoordinatedGroup]:
    """识别可并行执行的协同任务组"""
    groups = []
    
    # 按阶段分组
    phase_tasks = {}
    for alloc in allocations:
        task_id = alloc.get("task_id", "")
        task = next((t for t in all_tasks if t.get("task_id") == task_id), None)
        if task:
            phase = task.get("phase", 1)
            if phase not in phase_tasks:
                phase_tasks[phase] = []
            phase_tasks[phase].append(alloc)
    
    # 同阶段内的任务可以并行
    for phase, allocs in phase_tasks.items():
        if len(allocs) > 1:
            groups.append({
                "group_id": f"parallel_phase_{phase}",
                "group_type": "parallel_coverage",
                "task_ids": [a.get("task_id") for a in allocs],
                "device_ids": [a.get("device_id") for a in allocs],
                "coordination_mode": "独立并行执行",
                "sync_points": [],
            })
    
    return groups


def _calculate_utilization(
    device_usage: Dict[str, List[Dict]],
    devices: List[DeviceStatus]
) -> Dict[str, float]:
    """计算资源利用率"""
    utilization = {}
    
    for device in devices:
        device_id = device.get("device_id", "")
        usage = device_usage.get(device_id, [])
        
        if usage:
            total_time = sum(u.get("end_min", 0) - u.get("start_min", 0) for u in usage)
            endurance = device.get("effective_endurance_min", 60)
            utilization[device_id] = min(100, total_time / endurance * 100)
        else:
            utilization[device_id] = 0
    
    return utilization
