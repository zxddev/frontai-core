"""
路径规划数据模型
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Literal
from datetime import datetime


@dataclass
class Point:
    """地理坐标点"""
    lon: float
    lat: float


@dataclass
class RouteSegment:
    """路径段"""
    from_point: Point
    to_point: Point
    distance_m: float
    duration_s: float
    instruction: str = ""
    road_name: str = ""


@dataclass
class RouteResult:
    """路径规划结果"""
    source: Literal["amap", "internal", "fallback", "air_direct"]
    success: bool
    origin: Point
    destination: Point
    total_distance_m: float
    total_duration_s: float
    segments: List[RouteSegment] = field(default_factory=list)
    polyline: List[Point] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_distance_km(self) -> float:
        return self.total_distance_m / 1000
    
    @property
    def total_duration_min(self) -> float:
        return self.total_duration_s / 60


@dataclass
class AvoidArea:
    """避让区域"""
    polygon: List[Point]
    reason: str = ""
    severity: Literal["hard", "soft"] = "hard"
