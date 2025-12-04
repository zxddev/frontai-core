"""
Phase 6: 航线规划节点

选择扫描模式、生成航点序列、优化航线。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ..state import (
    ReconSchedulerState,
    FlightPlan,
    Waypoint,
    FlightSegment,
    FlightStatistics,
    TaskAllocation,
    ReconTask,
)
from ..algorithms.coverage import (
    generate_zigzag_waypoints,
    generate_spiral_waypoints,
    generate_circular_waypoints,
)

logger = logging.getLogger(__name__)


async def flight_planning_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    航线规划节点
    
    输入:
        - resource_allocation: 资源分配结果
        - all_tasks: 所有任务列表
        - target_area: 目标区域
        - environment_assessment: 环境评估结果
    
    输出:
        - flight_plans: 航线计划列表
    """
    logger.info("Phase 6: 航线规划")
    
    resource_allocation = state.get("resource_allocation", {})
    all_tasks = state.get("all_tasks", [])
    target_area = state.get("target_area")
    environment = state.get("environment_assessment", {})
    disaster_analysis = state.get("disaster_analysis", {})
    
    allocations = resource_allocation.get("allocations", [])
    weather = environment.get("weather", {})
    
    flight_plans = []
    warnings = state.get("warnings", [])
    
    for allocation in allocations:
        if allocation.get("is_backup"):
            continue  # 跳过备份分配
        
        task_id = allocation.get("task_id", "")
        device_id = allocation.get("device_id", "")
        device_name = allocation.get("device_name", "")
        
        # 查找对应的任务
        task = next((t for t in all_tasks if t.get("task_id") == task_id), None)
        if not task:
            logger.warning(f"找不到任务: {task_id}")
            continue
        
        # 生成航线
        try:
            flight_plan = _generate_flight_plan(
                task=task,
                allocation=allocation,
                target_area=target_area,
                weather=weather,
                disaster_analysis=disaster_analysis,
            )
            
            if flight_plan:
                flight_plans.append(flight_plan)
                logger.info(f"生成航线: {task_id} -> {device_name}, "
                           f"航点数={len(flight_plan.get('waypoints', []))}, "
                           f"距离={flight_plan.get('statistics', {}).get('total_distance_m', 0):.0f}m")
            else:
                warnings.append(f"任务 {task_id} 航线生成失败")
                
        except Exception as e:
            logger.error(f"生成航线失败: {task_id}, 错误: {e}")
            warnings.append(f"任务 {task_id} 航线生成异常: {str(e)}")
    
    logger.info(f"航线规划完成: 生成{len(flight_plans)}条航线")
    
    return {
        "flight_plans": flight_plans,
        "warnings": warnings,
        "current_phase": "flight_planning",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "flight_planning",
            "timestamp": datetime.now().isoformat(),
            "plans_count": len(flight_plans),
        }],
    }


def _generate_flight_plan(
    task: ReconTask,
    allocation: TaskAllocation,
    target_area: Optional[Dict[str, Any]],
    weather: Dict[str, Any],
    disaster_analysis: Dict[str, Any],
) -> Optional[FlightPlan]:
    """
    为单个任务生成航线计划
    """
    task_id = task.get("task_id", "")
    task_type = task.get("task_type", "area_survey")
    scan_config = task.get("scan_config", {})
    
    pattern = scan_config.get("pattern", "zigzag")
    altitude_m = scan_config.get("altitude_m", 100)
    speed_ms = scan_config.get("speed_ms", 10)
    overlap_percent = scan_config.get("overlap_percent", 20)
    
    # 解析目标区域
    polygon = _parse_target_area(target_area, task.get("target_area"))
    if not polygon:
        logger.warning(f"任务 {task_id} 没有有效的目标区域")
        # 使用默认区域（示例坐标）
        polygon = [
            (31.68, 103.85),
            (31.70, 103.85),
            (31.70, 103.87),
            (31.68, 103.87),
        ]
    
    # 根据扫描模式生成航点
    waypoints = []
    statistics = {}
    
    if pattern == "zigzag":
        waypoints, statistics = generate_zigzag_waypoints(
            polygon=polygon,
            altitude_m=altitude_m,
            speed_ms=speed_ms,
            sensor_fov_deg=scan_config.get("sensor_fov_deg", 84),
            overlap_percent=overlap_percent,
            heading_deg=scan_config.get("heading_deg"),
            home_point=polygon[0] if polygon else None,
        )
        
    elif pattern in ["spiral_inward", "spiral_outward"]:
        # 螺旋扫描
        center = scan_config.get("center")
        if not center and polygon:
            # 使用区域中心
            center = (
                sum(p[0] for p in polygon) / len(polygon),
                sum(p[1] for p in polygon) / len(polygon),
            )
        
        direction = "inward" if pattern == "spiral_inward" else "outward"
        
        waypoints, statistics = generate_spiral_waypoints(
            center=center,
            start_radius_m=scan_config.get("radius_m", 100),
            end_radius_m=10,
            altitude_m=altitude_m,
            speed_ms=speed_ms,
            ring_spacing_m=scan_config.get("ring_spacing_m", 30),
            direction=direction,
            home_point=polygon[0] if polygon else None,
        )
        
    elif pattern == "circular":
        # 环形扫描
        center = scan_config.get("center")
        
        # 处理字符串形式的center（如"fire_center"）
        if isinstance(center, str) or not center:
            # 使用灾情中心或区域中心
            epicenter = disaster_analysis.get("epicenter")
            if epicenter and isinstance(epicenter, dict):
                center = (epicenter.get("lat", 0), epicenter.get("lng", 0))
            elif polygon:
                center = (
                    sum(p[0] for p in polygon) / len(polygon),
                    sum(p[1] for p in polygon) / len(polygon),
                )
            else:
                center = (31.69, 103.86)  # 默认坐标
        
        radius_m = scan_config.get("radius_m") or 300  # 确保不为None
        
        waypoints, statistics = generate_circular_waypoints(
            center=center,
            radius_m=radius_m,
            altitude_m=altitude_m,
            speed_ms=speed_ms,
            approach_direction=scan_config.get("approach_direction", "upwind"),
            wind_direction_deg=weather.get("wind_direction_deg") or 0,
            orbit_direction="clockwise",
            laps=1,
            points_per_lap=16,
            home_point=polygon[0] if polygon else None,
        )
        
    else:
        # 默认使用Z字形
        logger.warning(f"未知的扫描模式 {pattern}，使用zigzag")
        waypoints, statistics = generate_zigzag_waypoints(
            polygon=polygon,
            altitude_m=altitude_m,
            speed_ms=speed_ms,
            overlap_percent=overlap_percent,
        )
    
    if not waypoints:
        return None
    
    # 生成航段信息
    segments = _generate_segments(waypoints)
    
    # 安全检查
    safety_checks = _perform_safety_checks(
        waypoints=waypoints,
        task=task,
        weather=weather,
    )
    
    # 构建航线计划
    plan_id = f"FP-{uuid.uuid4().hex[:8]}"
    
    flight_plan: FlightPlan = {
        "plan_id": plan_id,
        "task_id": task_id,
        "device_id": allocation.get("device_id", ""),
        "device_name": allocation.get("device_name", ""),
        
        "phase": task.get("phase", 1),
        "task_name": task.get("task_name", ""),
        "scan_pattern": pattern,
        
        "target_area": target_area or {},
        
        "flight_parameters": {
            "altitude_m": altitude_m,
            "speed_ms": speed_ms,
            "turn_radius_m": 10,
            "climb_rate_ms": 3,
            "descent_rate_ms": 2,
        },
        
        "scan_parameters": scan_config,
        
        "waypoints": waypoints,
        "segments": segments,
        "statistics": statistics,
        "safety_checks": safety_checks,
    }
    
    return flight_plan


def _parse_target_area(
    global_area: Optional[Dict[str, Any]],
    task_area: Optional[Dict[str, Any]]
) -> List[Tuple[float, float]]:
    """解析目标区域为多边形坐标列表"""
    area = task_area or global_area
    
    if not area:
        return []
    
    # 处理GeoJSON格式
    if area.get("type") == "Polygon":
        coords = area.get("coordinates", [[]])
        if coords and coords[0]:
            # GeoJSON是 [lng, lat]，需要转换为 (lat, lng)
            return [(c[1], c[0]) for c in coords[0]]
    
    # 处理简单的坐标列表
    if isinstance(area, list):
        if all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in area):
            return [(p[0], p[1]) for p in area]
    
    # 处理边界框
    if "min_lat" in area:
        return [
            (area["min_lat"], area["min_lng"]),
            (area["max_lat"], area["min_lng"]),
            (area["max_lat"], area["max_lng"]),
            (area["min_lat"], area["max_lng"]),
        ]
    
    return []


def _generate_segments(waypoints: List[Waypoint]) -> List[FlightSegment]:
    """生成航段信息"""
    segments = []
    
    for i in range(1, len(waypoints)):
        prev = waypoints[i - 1]
        curr = waypoints[i]
        
        # 判断航段类型
        action = curr.get("action", "fly_to")
        if action in ["scan", "start_scan"]:
            segment_type = "scan"
        elif action == "turn":
            segment_type = "turn"
        elif action == "hover":
            segment_type = "hover"
        else:
            segment_type = "transit"
        
        # 计算距离和时间
        import math
        lat_diff = (curr["lat"] - prev["lat"]) * 111000
        lng_diff = (curr["lng"] - prev["lng"]) * 111000 * math.cos(math.radians((curr["lat"] + prev["lat"]) / 2))
        alt_diff = curr["alt_m"] - prev["alt_m"]
        
        distance = math.sqrt(lat_diff**2 + lng_diff**2 + alt_diff**2)
        speed = curr.get("speed_ms", 10)
        duration = distance / speed if speed > 0 else 0
        
        segments.append({
            "segment_id": f"seg_{i}",
            "segment_type": segment_type,
            "start_waypoint": i - 1,
            "end_waypoint": i,
            "distance_m": distance,
            "duration_s": duration,
            "energy_consumption_percent": distance / 1000 * 0.5,
        })
    
    return segments


def _perform_safety_checks(
    waypoints: List[Waypoint],
    task: ReconTask,
    weather: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """执行安全检查"""
    checks = []
    
    # 检查高度
    safety_rules = task.get("safety_rules")
    if safety_rules:
        min_alt = safety_rules.get("min_altitude_m")
        max_alt = safety_rules.get("max_altitude_m")
        
        for wp in waypoints:
            alt = wp.get("alt_m", 0)
            if min_alt and alt < min_alt:
                checks.append({
                    "check_type": "altitude",
                    "passed": False,
                    "message": f"航点{wp['seq']}高度{alt}m低于最低要求{min_alt}m",
                    "severity": "warning",
                })
            if max_alt and alt > max_alt:
                checks.append({
                    "check_type": "altitude",
                    "passed": False,
                    "message": f"航点{wp['seq']}高度{alt}m超过最高限制{max_alt}m",
                    "severity": "warning",
                })
    
    # 检查航点数量
    if len(waypoints) > 200:
        checks.append({
            "check_type": "waypoint_count",
            "passed": False,
            "message": f"航点数量{len(waypoints)}过多，建议拆分任务",
            "severity": "warning",
        })
    
    # 如果没有问题
    if not checks:
        checks.append({
            "check_type": "overall",
            "passed": True,
            "message": "所有安全检查通过",
            "severity": "info",
        })
    
    return checks
