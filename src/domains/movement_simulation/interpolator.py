"""
路径插值算法

提供沿路径的位置计算、距离计算、朝向计算等功能
"""
from __future__ import annotations

import math
from typing import Tuple, List, Optional
from dataclasses import dataclass

from .schemas import Point


# 地球半径（米）
EARTH_RADIUS_M = 6371000.0


@dataclass
class InterpolationResult:
    """插值结果"""
    position: Point           # 当前位置
    heading: float            # 朝向角度 (0-360, 正北为0)
    segment_index: int        # 当前路段索引
    segment_progress: float   # 当前路段进度 (0-1)
    traveled_distance_m: float  # 已行驶距离


class RouteInterpolator:
    """
    路径插值器
    
    核心功能：
    1. 计算路径总距离和各段距离
    2. 根据行驶距离计算当前位置
    3. 计算两点间的朝向角度
    """
    
    def __init__(self, route: List[Point]) -> None:
        """
        初始化插值器
        
        Args:
            route: 路径点序列，至少2个点
        """
        if len(route) < 2:
            raise ValueError("路径至少需要2个点")
        
        self._route = route
        self._segment_distances: List[float] = []
        self._cumulative_distances: List[float] = []
        self._total_distance_m: float = 0.0
        
        self._calculate_distances()
    
    def _calculate_distances(self) -> None:
        """计算各段距离和累计距离"""
        cumulative = 0.0
        self._cumulative_distances = [0.0]
        
        for i in range(len(self._route) - 1):
            p1 = self._route[i]
            p2 = self._route[i + 1]
            segment_dist = self.haversine_distance(p1.lon, p1.lat, p2.lon, p2.lat)
            self._segment_distances.append(segment_dist)
            cumulative += segment_dist
            self._cumulative_distances.append(cumulative)
        
        self._total_distance_m = cumulative
    
    @property
    def total_distance_m(self) -> float:
        """总距离（米）"""
        return self._total_distance_m
    
    @property
    def segment_distances(self) -> List[float]:
        """各段距离列表"""
        return self._segment_distances.copy()
    
    @property
    def segment_count(self) -> int:
        """路段数量"""
        return len(self._segment_distances)
    
    def interpolate_by_distance(self, traveled_m: float) -> InterpolationResult:
        """
        根据行驶距离计算当前位置
        
        Args:
            traveled_m: 已行驶距离（米）
            
        Returns:
            插值结果
        """
        # 边界处理
        if traveled_m <= 0:
            return InterpolationResult(
                position=self._route[0],
                heading=self._calculate_heading(0),
                segment_index=0,
                segment_progress=0.0,
                traveled_distance_m=0.0,
            )
        
        if traveled_m >= self._total_distance_m:
            return InterpolationResult(
                position=self._route[-1],
                heading=self._calculate_heading(len(self._route) - 2),
                segment_index=len(self._route) - 2,
                segment_progress=1.0,
                traveled_distance_m=self._total_distance_m,
            )
        
        # 二分查找当前所在路段
        segment_index = self._find_segment(traveled_m)
        
        # 计算路段内进度
        segment_start_dist = self._cumulative_distances[segment_index]
        segment_length = self._segment_distances[segment_index]
        distance_in_segment = traveled_m - segment_start_dist
        segment_progress = distance_in_segment / segment_length if segment_length > 0 else 0.0
        
        # 线性插值计算位置
        p1 = self._route[segment_index]
        p2 = self._route[segment_index + 1]
        
        position = Point(
            lon=p1.lon + (p2.lon - p1.lon) * segment_progress,
            lat=p1.lat + (p2.lat - p1.lat) * segment_progress,
            alt=self._interpolate_altitude(p1.alt, p2.alt, segment_progress),
        )
        
        # 计算朝向
        heading = self._calculate_heading(segment_index)
        
        return InterpolationResult(
            position=position,
            heading=heading,
            segment_index=segment_index,
            segment_progress=segment_progress,
            traveled_distance_m=traveled_m,
        )
    
    def interpolate_by_time(self, elapsed_s: float, speed_mps: float) -> InterpolationResult:
        """
        根据经过时间和速度计算位置
        
        Args:
            elapsed_s: 已经过时间（秒）
            speed_mps: 速度（米/秒）
            
        Returns:
            插值结果
        """
        traveled_m = elapsed_s * speed_mps
        return self.interpolate_by_distance(traveled_m)
    
    def _find_segment(self, distance_m: float) -> int:
        """二分查找当前所在路段索引"""
        left, right = 0, len(self._cumulative_distances) - 1
        
        while left < right:
            mid = (left + right + 1) // 2
            if self._cumulative_distances[mid] <= distance_m:
                left = mid
            else:
                right = mid - 1
        
        # 确保不超出最后一段
        return min(left, len(self._segment_distances) - 1)
    
    def _calculate_heading(self, segment_index: int) -> float:
        """计算指定路段的朝向角度"""
        if segment_index >= len(self._route) - 1:
            segment_index = len(self._route) - 2
        
        p1 = self._route[segment_index]
        p2 = self._route[segment_index + 1]
        
        return self.calculate_bearing(p1.lon, p1.lat, p2.lon, p2.lat)
    
    @staticmethod
    def _interpolate_altitude(
        alt1: Optional[float], 
        alt2: Optional[float], 
        progress: float
    ) -> Optional[float]:
        """插值计算高度"""
        if alt1 is None or alt2 is None:
            return alt1 or alt2
        return alt1 + (alt2 - alt1) * progress
    
    @staticmethod
    def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Haversine公式计算两点间球面距离（米）
        
        精度足够用于路径距离计算
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return EARTH_RADIUS_M * c
    
    @staticmethod
    def calculate_bearing(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        计算从点1到点2的方位角（度）
        
        返回值范围: 0-360，正北为0，顺时针增加
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = (
            math.cos(lat1_rad) * math.sin(lat2_rad) -
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
        )
        
        bearing_rad = math.atan2(x, y)
        bearing_deg = math.degrees(bearing_rad)
        
        # 转换为0-360范围
        return (bearing_deg + 360) % 360
    
    def get_remaining_distance(self, traveled_m: float) -> float:
        """计算剩余距离"""
        return max(0, self._total_distance_m - traveled_m)
    
    def get_estimated_remaining_time(self, traveled_m: float, speed_mps: float) -> float:
        """计算预计剩余时间（秒）"""
        remaining = self.get_remaining_distance(traveled_m)
        return remaining / speed_mps if speed_mps > 0 else float('inf')
    
    def check_waypoint_reached(
        self, 
        waypoint_index: int, 
        current_segment: int, 
        segment_progress: float
    ) -> bool:
        """
        检查是否到达指定的任务停靠点
        
        Args:
            waypoint_index: 停靠点对应的路径点索引
            current_segment: 当前路段索引
            segment_progress: 当前路段进度
            
        Returns:
            是否到达
        """
        # 停靠点在当前路段的终点
        if current_segment == waypoint_index - 1 and segment_progress >= 0.99:
            return True
        # 已经过了停靠点
        if current_segment >= waypoint_index:
            return True
        return False
