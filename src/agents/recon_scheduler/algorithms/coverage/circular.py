"""
环形扫描航线生成算法

适用于目标监视、火情监测等需要绕目标飞行的场景。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ...state import Waypoint, FlightStatistics


def generate_circular_waypoints(
    center: Tuple[float, float],
    radius_m: float,
    altitude_m: float,
    speed_ms: float,
    approach_direction: str = "upwind",
    wind_direction_deg: float = 0,
    orbit_direction: str = "clockwise",
    laps: int = 1,
    points_per_lap: int = 16,
    home_point: Optional[Tuple[float, float]] = None,
) -> Tuple[List[Waypoint], FlightStatistics]:
    """
    生成环形扫描航线
    
    Args:
        center: 环形中心点 (lat, lng)，通常是危险源位置
        radius_m: 飞行半径（米）
        altitude_m: 飞行高度（米）
        speed_ms: 飞行速度（米/秒）
        approach_direction: 接近方向 "upwind"(上风向)/"downwind"/"crosswind"
        wind_direction_deg: 风向（度，风来的方向，0=北风）
        orbit_direction: 绕行方向 "clockwise"/"counterclockwise"
        laps: 绕行圈数
        points_per_lap: 每圈航点数量
        home_point: 起降点坐标 (lat, lng)
    
    Returns:
        (waypoints, statistics)
    """
    if home_point is None:
        home_point = center
    
    waypoints = []
    seq = 1
    total_distance = 0
    
    # 计算接近角度（从上风向接近）
    if approach_direction == "upwind":
        # 上风向：从风来的反方向接近
        approach_angle = math.radians((wind_direction_deg + 180) % 360)
    elif approach_direction == "downwind":
        approach_angle = math.radians(wind_direction_deg)
    else:  # crosswind
        approach_angle = math.radians((wind_direction_deg + 90) % 360)
    
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
    
    # 计算进入点（从上风向进入轨道）
    entry_point = _offset_point(center, radius_m, approach_angle)
    
    # 飞往进入点
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=entry_point[0],
        lng=entry_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms,
        action="fly_to",
    ))
    seq += 1
    total_distance += _distance_between(home_point, entry_point)
    
    # 生成环形航点
    prev_point = entry_point
    angle_step = 2 * math.pi / points_per_lap
    
    # 确定旋转方向
    if orbit_direction == "clockwise":
        angle_multiplier = -1
    else:
        angle_multiplier = 1
    
    for lap in range(laps):
        for i in range(points_per_lap):
            angle = approach_angle + angle_multiplier * (i + 1) * angle_step
            point = _offset_point(center, radius_m, angle)
            
            # 计算朝向中心的航向
            heading = _calculate_heading_to_center(point, center)
            
            action = "start_scan" if lap == 0 and i == 0 else "scan"
            
            waypoints.append(_create_waypoint(
                seq=seq,
                lat=point[0],
                lng=point[1],
                alt_m=altitude_m,
                speed_ms=speed_ms,
                action=action,
                heading_deg=heading,
                gimbal_pitch_deg=-45,  # 斜向下看向中心
            ))
            seq += 1
            
            total_distance += _distance_between(prev_point, point)
            prev_point = point
    
    # 返回起降点
    last_wp = waypoints[-1]
    last_point = (last_wp["lat"], last_wp["lng"])
    
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=altitude_m,
        speed_ms=speed_ms,
        action="return",
    ))
    seq += 1
    total_distance += _distance_between(last_point, home_point)
    
    # 降落
    waypoints.append(_create_waypoint(
        seq=seq,
        lat=home_point[0],
        lng=home_point[1],
        alt_m=0,
        speed_ms=speed_ms / 3,
        action="land",
    ))
    
    # 计算统计
    circumference = 2 * math.pi * radius_m * laps
    
    statistics: FlightStatistics = {
        "total_distance_m": total_distance,
        "total_duration_min": total_distance / speed_ms / 60 if speed_ms > 0 else 0,
        "coverage_area_m2": 0,  # 环形监视不计覆盖面积
        "waypoint_count": len(waypoints),
        "battery_consumption_percent": _estimate_battery(total_distance, altitude_m),
    }
    
    return waypoints, statistics


def _offset_point(
    center: Tuple[float, float],
    radius_m: float,
    angle_rad: float
) -> Tuple[float, float]:
    """从中心点偏移指定距离和角度"""
    lat_offset = radius_m * math.cos(angle_rad) / 111000
    lng_offset = radius_m * math.sin(angle_rad) / (111000 * math.cos(math.radians(center[0])))
    return (center[0] + lat_offset, center[1] + lng_offset)


def _distance_between(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """计算两点间距离（米）"""
    lat_diff = (p2[0] - p1[0]) * 111000
    lng_diff = (p2[1] - p1[1]) * 111000 * math.cos(math.radians((p1[0] + p2[0]) / 2))
    return math.sqrt(lat_diff**2 + lng_diff**2)


def _calculate_heading_to_center(
    point: Tuple[float, float],
    center: Tuple[float, float]
) -> float:
    """计算从点指向中心的航向"""
    lat_diff = center[0] - point[0]
    lng_diff = center[1] - point[1]
    
    # 计算角度（相对于北）
    angle = math.atan2(lng_diff, lat_diff)
    heading = math.degrees(angle)
    
    # 归一化到 0-360
    if heading < 0:
        heading += 360
    
    return heading


def _create_waypoint(
    seq: int,
    lat: float,
    lng: float,
    alt_m: float,
    speed_ms: float,
    action: str,
    heading_deg: Optional[float] = None,
    gimbal_pitch_deg: Optional[float] = None,
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
        "gimbal_pitch_deg": gimbal_pitch_deg if action in ["scan", "start_scan"] else None,
        "gimbal_yaw_deg": None,
        "dwell_time_s": None,
        "trigger": "video" if action in ["scan", "start_scan"] else None,
    }


def _estimate_battery(distance_m: float, altitude_m: float) -> float:
    """估算电池消耗"""
    base_consumption = distance_m / 1000 * 3
    climb_consumption = altitude_m / 100 * 2
    return min(100, base_consumption + climb_consumption)
