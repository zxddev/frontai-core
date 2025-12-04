"""
Z字形扫描航线生成算法

适用于大面积均匀覆盖的侦察任务。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ...state import Waypoint, FlightStatistics


def generate_zigzag_waypoints(
    polygon: List[Tuple[float, float]],
    altitude_m: float,
    speed_ms: float,
    sensor_fov_deg: float = 84,
    overlap_percent: float = 20,
    heading_deg: Optional[float] = None,
    home_point: Optional[Tuple[float, float]] = None,
) -> Tuple[List[Waypoint], FlightStatistics]:
    """
    生成Z字形扫描航线
    
    Args:
        polygon: 目标区域多边形坐标列表 [(lat, lng), ...]
        altitude_m: 飞行高度（米）
        speed_ms: 飞行速度（米/秒）
        sensor_fov_deg: 传感器视场角（度）
        overlap_percent: 重叠率（%）
        heading_deg: 航线方向（度，0=北，None=自动优化）
        home_point: 起降点坐标 (lat, lng)
    
    Returns:
        (waypoints, statistics)
    """
    if not polygon or len(polygon) < 3:
        return [], _empty_statistics()
    
    # 计算传感器覆盖宽度
    swath_width_m = 2 * altitude_m * math.tan(math.radians(sensor_fov_deg / 2))
    
    # 计算航线间距
    line_spacing_m = swath_width_m * (1 - overlap_percent / 100)
    
    # 确定起降点
    if home_point is None:
        home_point = polygon[0]
    
    # 计算边界框
    min_lat = min(p[0] for p in polygon)
    max_lat = max(p[0] for p in polygon)
    min_lng = min(p[1] for p in polygon)
    max_lng = max(p[1] for p in polygon)
    
    # 如果未指定航向，自动选择最优方向（沿短边）
    if heading_deg is None:
        lat_span = _lat_to_meters(max_lat - min_lat)
        lng_span = _lng_to_meters(max_lng - min_lng, (min_lat + max_lat) / 2)
        heading_deg = 0 if lat_span > lng_span else 90
    
    # 生成航点
    waypoints = []
    seq = 1
    
    # 起飞点
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=0,
        speed_ms=0,
        action="takeoff",
    ))
    seq += 1
    
    # 爬升到巡航高度
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms / 2,
        action="climb",
    ))
    seq += 1
    
    # 根据航向生成扫描航线
    if heading_deg == 0 or heading_deg == 180:
        # 南北向飞行，东西向移动
        scan_waypoints, scan_distance = _generate_ns_lines(
            min_lat, max_lat, min_lng, max_lng,
            line_spacing_m, altitude_m, speed_ms, seq
        )
    else:
        # 东西向飞行，南北向移动
        scan_waypoints, scan_distance = _generate_ew_lines(
            min_lat, max_lat, min_lng, max_lng,
            line_spacing_m, altitude_m, speed_ms, seq
        )
    
    waypoints.extend(scan_waypoints)
    seq = len(waypoints) + 1
    
    # 返回起降点
    last_wp = waypoints[-1] if waypoints else None
    if last_wp:
        # 返航
        waypoints.append(_create_waypoint(
            seq=seq,
            lat=home_point[0],
            lng=home_point[1],
            alt_m=altitude_m,
            speed_ms=speed_ms,
            action="return",
        ))
        seq += 1
    
    # 降落
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=0,
        speed_ms=speed_ms / 3,
        action="land",
    ))
    
    # 计算统计信息
    total_distance = _calculate_total_distance(waypoints)
    coverage_area = _lat_to_meters(max_lat - min_lat) * _lng_to_meters(max_lng - min_lng, (min_lat + max_lat) / 2)
    
    statistics: FlightStatistics = {
        "total_distance_m": total_distance,
        "total_duration_min": total_distance / speed_ms / 60 if speed_ms > 0 else 0,
        "coverage_area_m2": coverage_area,
        "waypoint_count": len(waypoints),
        "battery_consumption_percent": _estimate_battery(total_distance, altitude_m),
    }
    
    return waypoints, statistics


def _generate_ns_lines(
    min_lat: float, max_lat: float,
    min_lng: float, max_lng: float,
    line_spacing_m: float,
    altitude_m: float,
    speed_ms: float,
    start_seq: int
) -> Tuple[List[Waypoint], float]:
    """生成南北向扫描航线"""
    waypoints = []
    seq = start_seq
    total_distance = 0
    
    # 计算航线数量
    lng_span_m = _lng_to_meters(max_lng - min_lng, (min_lat + max_lat) / 2)
    num_lines = max(1, int(lng_span_m / line_spacing_m) + 1)
    
    # 经度增量
    lng_step = (max_lng - min_lng) / max(1, num_lines - 1) if num_lines > 1 else 0
    
    for i in range(num_lines):
        lng = min_lng + i * lng_step
        
        if i % 2 == 0:
            # 从南向北
            start_lat, end_lat = min_lat, max_lat
        else:
            # 从北向南
            start_lat, end_lat = max_lat, min_lat
        
        # 起点
        action = "start_scan" if i == 0 else "scan"
        waypoints.append(_create_waypoint(
            seq=seq,
            lat=start_lat,
            lng=lng,
            alt_m=altitude_m,
            speed_ms=speed_ms,
            action=action,
            heading_deg=0 if i % 2 == 0 else 180,
        ))
        seq += 1
        
        # 终点
        waypoints.append(_create_waypoint(
            seq=seq,
            lat=end_lat,
            lng=lng,
            alt_m=altitude_m,
            speed_ms=speed_ms,
            action="scan",
            heading_deg=0 if i % 2 == 0 else 180,
        ))
        seq += 1
        
        # 计算距离
        line_distance = _lat_to_meters(abs(end_lat - start_lat))
        total_distance += line_distance
        
        # 转弯距离
        if i < num_lines - 1:
            total_distance += line_spacing_m
    
    return waypoints, total_distance


def _generate_ew_lines(
    min_lat: float, max_lat: float,
    min_lng: float, max_lng: float,
    line_spacing_m: float,
    altitude_m: float,
    speed_ms: float,
    start_seq: int
) -> Tuple[List[Waypoint], float]:
    """生成东西向扫描航线"""
    waypoints = []
    seq = start_seq
    total_distance = 0
    
    # 计算航线数量
    lat_span_m = _lat_to_meters(max_lat - min_lat)
    num_lines = max(1, int(lat_span_m / line_spacing_m) + 1)
    
    # 纬度增量
    lat_step = (max_lat - min_lat) / max(1, num_lines - 1) if num_lines > 1 else 0
    
    avg_lat = (min_lat + max_lat) / 2
    
    for i in range(num_lines):
        lat = min_lat + i * lat_step
        
        if i % 2 == 0:
            # 从西向东
            start_lng, end_lng = min_lng, max_lng
        else:
            # 从东向西
            start_lng, end_lng = max_lng, min_lng
        
        # 起点
        action = "start_scan" if i == 0 else "scan"
        waypoints.append(_create_waypoint(
            seq=seq,
            lat=lat,
            lng=start_lng,
            alt_m=altitude_m,
            speed_ms=speed_ms,
            action=action,
            heading_deg=90 if i % 2 == 0 else 270,
        ))
        seq += 1
        
        # 终点
        waypoints.append(_create_waypoint(
            seq=seq,
            lat=lat,
            lng=end_lng,
            alt_m=altitude_m,
            speed_ms=speed_ms,
            action="scan",
            heading_deg=90 if i % 2 == 0 else 270,
        ))
        seq += 1
        
        # 计算距离
        line_distance = _lng_to_meters(abs(end_lng - start_lng), lat)
        total_distance += line_distance
        
        # 转弯距离
        if i < num_lines - 1:
            total_distance += line_spacing_m
    
    return waypoints, total_distance


def _create_waypoint(
    seq: int,
    lat: float,
    lng: float,
    alt_m: float,
    speed_ms: float,
    action: str,
    heading_deg: Optional[float] = None,
    gimbal_pitch_deg: float = -90,
) -> Waypoint:
    """创建航点"""
    return {
        "seq": seq,
        "lat": lat,
        "lng": lng,
        "alt_m": alt_m,
        "alt_agl_m": alt_m,  # 假设地面高度为0
        "speed_ms": speed_ms,
        "heading_deg": heading_deg,
        "action": action,
        "action_params": None,
        "gimbal_pitch_deg": gimbal_pitch_deg if action in ["scan", "start_scan"] else None,
        "gimbal_yaw_deg": None,
        "dwell_time_s": None,
        "trigger": "photo" if action in ["scan", "start_scan"] else None,
    }


def _lat_to_meters(lat_diff: float) -> float:
    """纬度差转换为米"""
    return lat_diff * 111000


def _lng_to_meters(lng_diff: float, lat: float) -> float:
    """经度差转换为米"""
    return lng_diff * 111000 * math.cos(math.radians(lat))


def _calculate_total_distance(waypoints: List[Waypoint]) -> float:
    """计算总航程"""
    total = 0
    for i in range(1, len(waypoints)):
        prev = waypoints[i - 1]
        curr = waypoints[i]
        
        lat_diff = _lat_to_meters(curr["lat"] - prev["lat"])
        lng_diff = _lng_to_meters(curr["lng"] - prev["lng"], (curr["lat"] + prev["lat"]) / 2)
        alt_diff = curr["alt_m"] - prev["alt_m"]
        
        total += math.sqrt(lat_diff**2 + lng_diff**2 + alt_diff**2)
    
    return total


def _estimate_battery(distance_m: float, altitude_m: float) -> float:
    """估算电池消耗百分比"""
    # 简化估算：每公里消耗约3%，爬升额外消耗
    base_consumption = distance_m / 1000 * 3
    climb_consumption = altitude_m / 100 * 2
    return min(100, base_consumption + climb_consumption)


def _empty_statistics() -> FlightStatistics:
    """返回空统计信息"""
    return {
        "total_distance_m": 0,
        "total_duration_min": 0,
        "coverage_area_m2": 0,
        "waypoint_count": 0,
        "battery_consumption_percent": 0,
    }
