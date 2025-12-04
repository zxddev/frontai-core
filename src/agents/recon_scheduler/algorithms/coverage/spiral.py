"""
螺旋扫描航线生成算法

适用于定点详查、从已知点展开搜索。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ...state import Waypoint, FlightStatistics


def generate_spiral_waypoints(
    center: Tuple[float, float],
    start_radius_m: float,
    end_radius_m: float,
    altitude_m: float,
    speed_ms: float,
    ring_spacing_m: float = 30,
    direction: str = "inward",
    home_point: Optional[Tuple[float, float]] = None,
) -> Tuple[List[Waypoint], FlightStatistics]:
    """
    生成螺旋扫描航线
    
    Args:
        center: 螺旋中心点 (lat, lng)
        start_radius_m: 起始半径（米）
        end_radius_m: 结束半径（米）
        altitude_m: 飞行高度（米）
        speed_ms: 飞行速度（米/秒）
        ring_spacing_m: 环间距（米）
        direction: 螺旋方向 "inward"(向内) 或 "outward"(向外)
        home_point: 起降点坐标 (lat, lng)
    
    Returns:
        (waypoints, statistics)
    """
    if home_point is None:
        home_point = center
    
    waypoints = []
    seq = 1
    total_distance = 0
    
    # 起飞
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=0,
        speed_ms=0,
        action="takeoff",
    ))
    seq += 1
    
    # 爬升
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms / 2,
        action="climb",
    ))
    seq += 1
    
    # 计算螺旋参数
    if direction == "inward":
        radii = _generate_radii(start_radius_m, end_radius_m, ring_spacing_m, descending=True)
    else:
        radii = _generate_radii(end_radius_m, start_radius_m, ring_spacing_m, descending=False)
    
    # 飞往起始点
    first_radius = radii[0] if radii else start_radius_m
    first_point = _offset_point(center, first_radius, 0)
    
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=first_point[0],
        lng=first_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms,
        action="fly_to",
    ))
    seq += 1
    total_distance += _distance_between(home_point, first_point)
    
    # 生成螺旋航点
    prev_point = first_point
    angle = 0
    
    for i, radius in enumerate(radii):
        # 每圈的航点数量（保证足够的覆盖）
        circumference = 2 * math.pi * radius
        points_per_ring = max(8, int(circumference / ring_spacing_m))
        angle_step = 2 * math.pi / points_per_ring
        
        for j in range(points_per_ring):
            angle = j * angle_step
            point = _offset_point(center, radius, angle)
            
            action = "start_scan" if i == 0 and j == 0 else "scan"
            
            waypoints.append(_create_waypoint(
                seq=seq,
                lat=point[0],
                lng=point[1],
                alt_m=altitude_m,
                speed_ms=speed_ms,
                action=action,
                heading_deg=math.degrees(angle) + 90,  # 朝向中心
            ))
            seq += 1
            
            total_distance += _distance_between(prev_point, point)
            prev_point = point
    
    # 返回起降点
    last_point = waypoints[-1] if waypoints else home_point
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms,
        action="return",
    ))
    seq += 1
    total_distance += _distance_between((last_point["lat"], last_point["lng"]), home_point)
    
    # 降落
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=0,
        speed_ms=speed_ms / 3,
        action="land",
    ))
    
    # 计算覆盖面积
    max_radius = max(start_radius_m, end_radius_m)
    coverage_area = math.pi * max_radius ** 2
    
    statistics: FlightStatistics = {
        "total_distance_m": total_distance,
        "total_duration_min": total_distance / speed_ms / 60 if speed_ms > 0 else 0,
        "coverage_area_m2": coverage_area,
        "waypoint_count": len(waypoints),
        "battery_consumption_percent": _estimate_battery(total_distance, altitude_m),
    }
    
    return waypoints, statistics


def _generate_radii(
    start: float,
    end: float,
    spacing: float,
    descending: bool
) -> List[float]:
    """生成半径序列"""
    if descending:
        radii = []
        r = start
        while r >= end:
            radii.append(r)
            r -= spacing
        if not radii or radii[-1] > end:
            radii.append(end)
    else:
        radii = []
        r = start
        while r <= end:
            radii.append(r)
            r += spacing
        if not radii or radii[-1] < end:
            radii.append(end)
    
    return radii


def _offset_point(
    center: Tuple[float, float],
    radius_m: float,
    angle_rad: float
) -> Tuple[float, float]:
    """从中心点偏移指定距离和角度"""
    # 纬度偏移
    lat_offset = radius_m * math.cos(angle_rad) / 111000
    # 经度偏移（考虑纬度的影响）
    lng_offset = radius_m * math.sin(angle_rad) / (111000 * math.cos(math.radians(center[0])))
    
    return (center[0] + lat_offset, center[1] + lng_offset)


def _distance_between(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """计算两点间距离（米）"""
    lat_diff = (p2[0] - p1[0]) * 111000
    lng_diff = (p2[1] - p1[1]) * 111000 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(lat_diff**2 + lng_diff**2)


def _create_waypoint(
    seq: int,
    lat: float,
    lng: float,
    alt_m: float,
    speed_ms: float,
    action: str,
    heading_deg: Optional[float] = None,
) -> Waypoint:
    """创建航点"""
    return {
        "seq": seq,
        "lat": lat,
        "lng": lng,
        "alt_m": alt_m,
        "alt_agl_m": alt_m,
        "speed_ms": speed_ms,
        "heading_deg": heading_deg,
        "action": action,
        "action_params": None,
        "gimbal_pitch_deg": -90 if action in ["scan", "start_scan"] else None,
        "gimbal_yaw_deg": None,
        "dwell_time_s": 2 if action in ["scan", "start_scan"] else None,
        "trigger": "photo" if action in ["scan", "start_scan"] else None,
    }


def _estimate_battery(distance_m: float, altitude_m: float) -> float:
    """估算电池消耗"""
    base_consumption = distance_m / 1000 * 3
    climb_consumption = altitude_m / 100 * 2
    return min(100, base_consumption + climb_consumption)
