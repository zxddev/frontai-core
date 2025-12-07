"""
Phase 6: 航线规划节点

选择扫描模式、生成航点序列、优化航线。
"""
from __future__ import annotations

import logging
import math
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
from ..mock_data import get_device_provider

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
    errors = state.get("errors", [])
    
    device_provider = get_device_provider()
    
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
        
        # 获取设备配置以进行能力预检查
        device_profile = await device_provider.get_device_profile(device_id)
        if not device_profile:
            logger.warning(f"找不到设备配置: {device_id}")
            warnings.append(f"设备 {device_id} 配置未找到")
            continue
        
        # 预检查：计算区域面积和预估飞行距离
        polygon = _parse_target_area(target_area, task.get("target_area"))
        if polygon:
            area_check = _check_area_feasibility(
                polygon=polygon,
                device_profile=device_profile,
                scan_config=task.get("scan_config", {}),
            )
            if not area_check["feasible"]:
                error_msg = (f"任务 {task_id} 区域过大无法单次覆盖: "
                           f"预估飞行{area_check['estimated_distance_km']:.1f}km, "
                           f"设备{device_name}最大可飞{area_check['max_distance_km']:.1f}km")
                logger.error(error_msg)
                errors.append(error_msg)
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
                # 二次检查：验证生成的航线是否在能力范围内
                actual_distance = flight_plan.get("statistics", {}).get("total_distance_m", 0)
                max_distance = device_profile.max_endurance_min * device_profile.energy_params.cruise_speed_ms * 60 * 0.9
                
                if actual_distance > max_distance:
                    error_msg = (f"航线 {task_id} 超出设备能力: "
                               f"距离{actual_distance/1000:.1f}km > 最大{max_distance/1000:.1f}km")
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                
                flight_plans.append(flight_plan)
                logger.info(f"生成航线: {task_id} -> {device_name}, "
                           f"航点数={len(flight_plan.get('waypoints', []))}, "
                           f"距离={actual_distance:.0f}m")
            else:
                warnings.append(f"任务 {task_id} 航线生成失败")
                
        except Exception as e:
            logger.error(f"生成航线失败: {task_id}, 错误: {e}")
            warnings.append(f"任务 {task_id} 航线生成异常: {str(e)}")
    
    logger.info(f"航线规划完成: 生成{len(flight_plans)}条航线, 错误{len(errors)}个")
    
    return {
        "flight_plans": flight_plans,
        "warnings": warnings,
        "errors": errors,
        "current_phase": "flight_planning",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "flight_planning",
            "timestamp": datetime.now().isoformat(),
            "plans_count": len(flight_plans),
            "errors_count": len(errors),
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


def _check_area_feasibility(
    polygon: List[Tuple[float, float]],
    device_profile: Any,
    scan_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    检查区域是否在设备能力范围内
    
    根据区域面积、扫描参数和设备续航能力，预估飞行距离并判断可行性。
    
    Args:
        polygon: 区域多边形坐标 [(lat, lng), ...]
        device_profile: 设备配置
        scan_config: 扫描配置
    
    Returns:
        包含feasible、estimated_distance_km、max_distance_km的字典
    """
    if not polygon or len(polygon) < 3:
        return {"feasible": True, "estimated_distance_km": 0, "max_distance_km": 0}
    
    # 计算区域边界
    min_lat = min(p[0] for p in polygon)
    max_lat = max(p[0] for p in polygon)
    min_lng = min(p[1] for p in polygon)
    max_lng = max(p[1] for p in polygon)
    
    # 计算区域尺寸（米）
    lat_span_m = (max_lat - min_lat) * 111000
    avg_lat = (min_lat + max_lat) / 2
    lng_span_m = (max_lng - min_lng) * 111000 * math.cos(math.radians(avg_lat))
    
    # 获取扫描参数
    altitude_m = scan_config.get("altitude_m", 100)
    sensor_fov_deg = scan_config.get("sensor_fov_deg", 84)
    overlap_percent = scan_config.get("overlap_percent", 20)
    
    # 计算航线间距
    swath_width_m = 2 * altitude_m * math.tan(math.radians(sensor_fov_deg / 2))
    line_spacing_m = swath_width_m * (1 - overlap_percent / 100)
    
    if line_spacing_m <= 0:
        line_spacing_m = 50  # 安全默认值
    
    # 预估航线数量（取较短边作为扫描方向）
    if lat_span_m > lng_span_m:
        num_lines = max(1, int(lng_span_m / line_spacing_m) + 1)
        line_length_m = lat_span_m
    else:
        num_lines = max(1, int(lat_span_m / line_spacing_m) + 1)
        line_length_m = lng_span_m
    
    # 预估总飞行距离（扫描距离 + 转弯 + 往返）
    scan_distance_m = num_lines * line_length_m
    turn_distance_m = (num_lines - 1) * line_spacing_m
    # 假设起降点在区域边缘，往返距离约为对角线
    return_distance_m = math.sqrt(lat_span_m**2 + lng_span_m**2) * 2
    
    estimated_distance_m = scan_distance_m + turn_distance_m + return_distance_m
    estimated_distance_km = estimated_distance_m / 1000
    
    # 计算设备最大可飞距离（90%安全系数）
    max_endurance_min = device_profile.max_endurance_min
    cruise_speed_ms = device_profile.energy_params.cruise_speed_ms
    max_distance_m = max_endurance_min * cruise_speed_ms * 60 * 0.9
    max_distance_km = max_distance_m / 1000
    
    feasible = estimated_distance_m <= max_distance_m
    
    # 关键日志：区域可行性检查结果
    logger.info(f"[FlightPlanning] 区域检查: {lat_span_m:.0f}m × {lng_span_m:.0f}m = {lat_span_m * lng_span_m / 1e6:.2f}km²")
    logger.info(f"[FlightPlanning] 预检查: feasible={feasible}, est={estimated_distance_km:.1f}km, max={max_distance_km:.1f}km, lines={num_lines}")
    
    return {
        "feasible": feasible,
        "estimated_distance_km": estimated_distance_km,
        "max_distance_km": max_distance_km,
        "area_size_m2": lat_span_m * lng_span_m,
        "num_lines": num_lines,
    }
