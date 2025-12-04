"""
Phase 9: 计划校验节点

覆盖完整性、资源冲突、安全检查、时间约束。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..state import (
    ReconSchedulerState,
    PlanValidation,
    ValidationError,
    CoverageCheckResult,
    ResourceCheckResult,
    TimeCheckResult,
    SafetyCheckResult,
    ConflictCheckResult,
)

logger = logging.getLogger(__name__)


async def plan_validation_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    计划校验节点
    
    输入:
        - flight_plans: 航线计划
        - resource_allocation: 资源分配
        - timeline_scheduling: 时间线编排
        - environment_assessment: 环境评估
        - disaster_analysis: 灾情分析
    
    输出:
        - validation_result: 校验结果
    """
    logger.info("Phase 9: 计划校验")
    
    flight_plans = state.get("flight_plans", [])
    resource_allocation = state.get("resource_allocation", {})
    timeline = state.get("timeline_scheduling", {})
    environment = state.get("environment_assessment", {})
    disaster_analysis = state.get("disaster_analysis", {})
    target_area = state.get("target_area")
    
    validation_errors = []
    validation_warnings = []
    
    # 1. 覆盖完整性检查
    coverage_check = _check_coverage(flight_plans, target_area)
    if not coverage_check.get("is_acceptable"):
        validation_errors.append({
            "error_type": "coverage",
            "severity": "warning",
            "message": f"覆盖率({coverage_check.get('coverage_percent', 0):.1f}%)低于目标(95%)",
            "affected_items": ["coverage"],
        })
    
    # 2. 资源检查
    resource_check = _check_resources(resource_allocation)
    if not resource_check.get("is_acceptable"):
        unallocated = resource_check.get("unallocated_tasks", [])
        if unallocated:
            validation_errors.append({
                "error_type": "resource",
                "severity": "error",
                "message": f"有{len(unallocated)}个任务未分配设备",
                "affected_items": unallocated,
            })
    
    # 3. 时间检查
    time_check = _check_time(timeline, environment, disaster_analysis)
    if not time_check.get("is_acceptable"):
        if not time_check.get("within_time_window"):
            validation_errors.append({
                "error_type": "time",
                "severity": "warning",
                "message": "任务时长可能超出可飞行时间窗口",
                "affected_items": ["timeline"],
            })
    
    # 4. 安全检查
    safety_check = _check_safety(flight_plans, environment)
    if not safety_check.get("is_acceptable"):
        for violation in safety_check.get("altitude_violations", []):
            validation_errors.append({
                "error_type": "safety",
                "severity": "warning",
                "message": violation.get("message", "高度违规"),
                "affected_items": [violation.get("plan_id", "unknown")],
            })
    
    # 5. 冲突检查
    conflict_check = _check_conflicts(flight_plans, timeline)
    if not conflict_check.get("is_acceptable"):
        for conflict in conflict_check.get("flight_path_conflicts", []):
            validation_errors.append({
                "error_type": "conflict",
                "severity": "warning",
                "message": conflict.get("message", "航线冲突"),
                "affected_items": conflict.get("plans", []),
            })
    
    # 判断是否通过校验
    critical_errors = [e for e in validation_errors if e.get("severity") == "critical"]
    regular_errors = [e for e in validation_errors if e.get("severity") == "error"]
    warnings = [e for e in validation_errors if e.get("severity") == "warning"]
    
    is_valid = len(critical_errors) == 0 and len(regular_errors) == 0
    
    # 构建结果
    validation_result: PlanValidation = {
        "is_valid": is_valid,
        "validation_errors": validation_errors,
        "validation_warnings": warnings,
        
        "coverage_check": coverage_check,
        "resource_check": resource_check,
        "time_check": time_check,
        "safety_check": safety_check,
        "conflict_check": conflict_check,
    }
    
    # 添加到状态警告
    state_warnings = state.get("warnings", [])
    for err in validation_errors:
        if err.get("severity") == "warning":
            state_warnings.append(f"校验警告: {err.get('message')}")
    
    logger.info(f"计划校验完成: 通过={is_valid}, "
                f"严重错误={len(critical_errors)}, 错误={len(regular_errors)}, 警告={len(warnings)}")
    
    return {
        "validation_result": validation_result,
        "warnings": state_warnings,
        "current_phase": "plan_validation",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "plan_validation",
            "timestamp": datetime.now().isoformat(),
            "is_valid": is_valid,
            "errors": len(validation_errors),
        }],
    }


def _check_coverage(
    flight_plans: List[Dict],
    target_area: Dict[str, Any]
) -> CoverageCheckResult:
    """检查覆盖完整性"""
    if not flight_plans:
        return {
            "target_area_m2": 0,
            "planned_coverage_m2": 0,
            "coverage_percent": 0,
            "uncovered_areas": [],
            "is_acceptable": False,
        }
    
    # 计算目标面积（简化）
    target_area_m2 = 0
    if target_area:
        # 假设方形区域
        if target_area.get("type") == "Polygon":
            # 简化计算
            target_area_m2 = 1000000  # 1 km²
    
    # 汇总航线覆盖面积
    total_coverage = sum(
        fp.get("statistics", {}).get("coverage_area_m2", 0)
        for fp in flight_plans
    )
    
    # 计算覆盖率（考虑重叠）
    coverage_percent = min(100, total_coverage / max(1, target_area_m2) * 100 * 0.9)  # 假设10%重叠
    
    return {
        "target_area_m2": target_area_m2,
        "planned_coverage_m2": total_coverage,
        "coverage_percent": coverage_percent,
        "uncovered_areas": [],
        "is_acceptable": coverage_percent >= 95 or not target_area,
    }


def _check_resources(resource_allocation: Dict) -> ResourceCheckResult:
    """检查资源分配"""
    allocations = resource_allocation.get("allocations", [])
    unallocated = resource_allocation.get("unallocated_tasks", [])
    utilization = resource_allocation.get("resource_utilization", {})
    
    # 计算电池余量
    battery_margins = {}
    for alloc in allocations:
        device_id = alloc.get("device_id", "")
        # 假设使用70%电量，剩余30%
        battery_margins[device_id] = 30
    
    return {
        "all_tasks_allocated": len(unallocated) == 0,
        "unallocated_tasks": unallocated,
        "device_utilization": utilization,
        "battery_margins": battery_margins,
        "is_acceptable": len(unallocated) == 0,
    }


def _check_time(
    timeline: Dict,
    environment: Dict,
    disaster_analysis: Dict
) -> TimeCheckResult:
    """检查时间约束"""
    total_duration = timeline.get("total_duration_min", 0)
    time_window = environment.get("time_window_hours", 4) * 60
    golden_hour = disaster_analysis.get("golden_hour_remaining", 72) * 60
    
    within_window = total_duration <= time_window
    golden_hour_coverage = min(1.0, total_duration / max(1, golden_hour))
    
    return {
        "total_duration_min": total_duration,
        "within_time_window": within_window,
        "golden_hour_coverage": golden_hour_coverage,
        "time_critical_tasks_on_schedule": True,  # 简化
        "is_acceptable": within_window,
    }


def _check_safety(
    flight_plans: List[Dict],
    environment: Dict
) -> SafetyCheckResult:
    """检查安全约束"""
    altitude_violations = []
    no_fly_violations = []
    
    recommended = environment.get("recommended_altitude_range", {})
    min_alt = recommended.get("min_m", 50)
    max_alt = recommended.get("max_m", 500)
    
    for fp in flight_plans:
        for wp in fp.get("waypoints", []):
            alt = wp.get("alt_m", 0)
            if alt > 0 and alt < min_alt:
                altitude_violations.append({
                    "plan_id": fp.get("plan_id", ""),
                    "waypoint": wp.get("seq", 0),
                    "message": f"航点高度{alt}m低于最低安全高度{min_alt}m",
                })
            if alt > max_alt:
                altitude_violations.append({
                    "plan_id": fp.get("plan_id", ""),
                    "waypoint": wp.get("seq", 0),
                    "message": f"航点高度{alt}m超过最高限制{max_alt}m",
                })
    
    weather_risk = environment.get("weather_risk_level", "low")
    
    return {
        "no_fly_zone_violations": no_fly_violations,
        "altitude_violations": altitude_violations,
        "weather_risk_level": weather_risk,
        "communication_gaps": [],
        "is_acceptable": len(altitude_violations) == 0 and len(no_fly_violations) == 0,
    }


def _check_conflicts(
    flight_plans: List[Dict],
    timeline: Dict
) -> ConflictCheckResult:
    """检查冲突"""
    path_conflicts = []
    time_conflicts = []
    resource_conflicts = []
    
    # 简化的航线冲突检测
    # 实际应该检查航点间的空间距离
    gantt_data = timeline.get("gantt_data", [])
    
    # 检查时间重叠的任务是否使用同一设备
    for i, bar1 in enumerate(gantt_data):
        for bar2 in gantt_data[i+1:]:
            # 检查时间重叠
            if (bar1["start_min"] < bar2["end_min"] and 
                bar1["end_min"] > bar2["start_min"]):
                # 检查是否同一设备
                device1 = next((fp.get("device_id") for fp in flight_plans 
                               if fp.get("task_id") == bar1["task_id"]), None)
                device2 = next((fp.get("device_id") for fp in flight_plans 
                               if fp.get("task_id") == bar2["task_id"]), None)
                
                if device1 and device1 == device2:
                    resource_conflicts.append({
                        "tasks": [bar1["task_id"], bar2["task_id"]],
                        "device": device1,
                        "message": f"设备{device1}在同一时间被分配给多个任务",
                    })
    
    return {
        "flight_path_conflicts": path_conflicts,
        "time_slot_conflicts": time_conflicts,
        "resource_conflicts": resource_conflicts,
        "is_acceptable": len(path_conflicts) == 0 and len(resource_conflicts) == 0,
    }
