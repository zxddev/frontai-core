"""
Phase 4: 任务规划节点

分阶段定义任务、排序优先级、建立依赖关系。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List
import uuid

from ..state import (
    ReconSchedulerState,
    MissionPhase,
    ReconTask,
    PhaseTrigger,
)
from ..config import get_disaster_scenarios

logger = logging.getLogger(__name__)


async def mission_planning_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    任务规划节点
    
    输入:
        - disaster_analysis: 灾情分析结果
        - environment_assessment: 环境评估结果
        - resource_inventory: 资源盘点结果
    
    输出:
        - mission_phases: 任务阶段列表
        - all_tasks: 所有任务列表
        - task_dependencies: 任务依赖关系
    """
    logger.info("Phase 4: 任务规划")
    
    disaster_analysis = state.get("disaster_analysis", {})
    environment = state.get("environment_assessment", {})
    resource_inventory = state.get("resource_inventory", {})
    target_area = state.get("target_area")
    
    disaster_type = disaster_analysis.get("disaster_type", "earthquake_collapse")
    
    # 加载灾情场景配置
    scenarios_config = get_disaster_scenarios()
    scenario = scenarios_config.get("scenarios", {}).get(disaster_type, {})
    
    if not scenario:
        logger.warning(f"未找到场景配置: {disaster_type}，使用默认")
        scenario = scenarios_config.get("scenarios", {}).get("earthquake_collapse", {})
    
    # 生成任务阶段
    mission_phases = []
    all_tasks = []
    task_dependencies = {}
    
    phase_configs = scenario.get("phases", [])
    
    for phase_config in phase_configs:
        phase_number = phase_config.get("phase", len(mission_phases) + 1)
        phase_id = f"phase_{phase_number}"
        
        # 生成阶段内的任务
        phase_tasks = []
        for task_config in phase_config.get("tasks", []):
            task_id = f"task_{phase_number}_{len(phase_tasks) + 1}_{uuid.uuid4().hex[:6]}"
            
            # 构建任务
            task = _build_task(
                task_id=task_id,
                task_config=task_config,
                phase_number=phase_number,
                target_area=target_area,
                disaster_analysis=disaster_analysis,
                environment=environment,
            )
            
            phase_tasks.append(task)
            all_tasks.append(task)
            
            # 建立依赖关系
            task_dependencies[task_id] = task.get("depends_on", [])
        
        # 构建阶段
        phase: MissionPhase = {
            "phase_id": phase_id,
            "phase_number": phase_number,
            "phase_name": phase_config.get("name", f"阶段{phase_number}"),
            "objective": phase_config.get("objective", ""),
            "priority": phase_config.get("priority", "high"),
            "trigger": phase_config.get("trigger", {"type": "immediate"}),
            "tasks": phase_tasks,
            "time_budget_min": phase_config.get("time_budget_min"),
            "expected_outputs": phase_config.get("expected_outputs", []),
        }
        
        mission_phases.append(phase)
    
    # 检查资源是否足够
    warnings = state.get("warnings", [])
    available_devices = resource_inventory.get("available_devices", [])
    
    # 简单的资源需求检查
    drone_tasks = [t for t in all_tasks if "drone" in str(t.get("device_requirements", {}).get("type_preference", []))]
    dog_tasks = [t for t in all_tasks if "ugv" in str(t.get("device_requirements", {}).get("type_preference", []))]
    
    available_drones = [d for d in available_devices if d.get("device_type") == "drone"]
    available_dogs = [d for d in available_devices if d.get("device_type") == "dog"]
    
    if len(drone_tasks) > len(available_drones) * 2:  # 假设每个设备可执行2个任务
        warnings.append(f"无人机任务数({len(drone_tasks)})可能超过可用设备能力")
    
    if dog_tasks and not available_dogs:
        warnings.append("有室内搜索任务但没有可用的机器狗")
    
    logger.info(f"任务规划完成: {len(mission_phases)}个阶段, {len(all_tasks)}个任务")
    
    return {
        "mission_phases": mission_phases,
        "all_tasks": all_tasks,
        "task_dependencies": task_dependencies,
        "warnings": warnings,
        "current_phase": "mission_planning",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "mission_planning",
            "timestamp": datetime.now().isoformat(),
            "phases_count": len(mission_phases),
            "tasks_count": len(all_tasks),
        }],
    }


def _build_task(
    task_id: str,
    task_config: Dict[str, Any],
    phase_number: int,
    target_area: Dict[str, Any],
    disaster_analysis: Dict[str, Any],
    environment: Dict[str, Any],
) -> ReconTask:
    """构建单个任务"""
    
    # 设备需求
    device_requirements = task_config.get("device_requirements", {})
    
    # 扫描配置
    scan_config = task_config.get("scan_config", {})
    
    # 根据环境调整扫描参数
    recommended_altitude = environment.get("recommended_altitude_range", {})
    if scan_config.get("altitude_m"):
        # 确保高度在推荐范围内
        min_alt = recommended_altitude.get("min_m", 50)
        max_alt = recommended_altitude.get("max_m", 500)
        scan_config["altitude_m"] = max(min_alt, min(max_alt, scan_config["altitude_m"]))
    
    # 安全规则
    safety_rules = task_config.get("safety_rules")
    
    # 依赖关系
    depends_on = []
    trigger = task_config.get("trigger", {"type": "immediate"})
    if trigger.get("type") == "phase_complete":
        # 依赖前一个阶段的所有任务
        prev_phase = trigger.get("phase", phase_number - 1)
        if prev_phase < phase_number:
            depends_on.append(f"phase_{prev_phase}_complete")
    
    # 时间约束
    time_budget = task_config.get("time_budget_min")
    
    task: ReconTask = {
        "task_id": task_id,
        "task_name": task_config.get("objective", f"任务{task_id}"),
        "task_type": task_config.get("task_type", "area_survey"),
        "phase": phase_number,
        "priority": task_config.get("priority", "high"),
        
        "objective": task_config.get("objective", ""),
        "target_area": target_area,
        "focus_areas": task_config.get("focus_areas"),
        
        "device_requirements": {
            "type_preference": device_requirements.get("type_preference", ["multirotor"]),
            "capabilities_required": device_requirements.get("capabilities_required", ["rgb_camera"]),
            "min_endurance_min": device_requirements.get("min_endurance_min"),
        },
        
        "scan_config": {
            "pattern": scan_config.get("pattern", "zigzag"),
            "altitude_m": scan_config.get("altitude_m", 100),
            "speed_ms": scan_config.get("speed_ms", 10),
            "overlap_percent": scan_config.get("overlap_percent", 20),
            "line_spacing_m": scan_config.get("line_spacing_m"),
            "radius_m": scan_config.get("radius_m"),
            "center": scan_config.get("center"),
            "heading_deg": scan_config.get("heading_deg"),
            "approach_direction": scan_config.get("approach_direction"),
        },
        
        "safety_rules": safety_rules,
        
        "time_budget_min": time_budget,
        "must_start_before_min": None,
        
        "depends_on": depends_on,
        
        "trigger": trigger,
        
        "expected_outputs": task_config.get("expected_outputs", []),
    }
    
    return task
