"""路径规划通用类型。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def slope_deg_to_percent(deg: float) -> float:
    """将坡度从角度转换为百分比。
    
    公式: percent = tan(deg) * 100
    示例: 10° ≈ 17.6%, 30° ≈ 57.7%, 45° = 100%
    """
    return math.tan(math.radians(deg)) * 100


def slope_percent_to_deg(percent: float) -> float:
    """将坡度从百分比转换为角度。
    
    公式: deg = atan(percent / 100)
    示例: 10% ≈ 5.7°, 30% ≈ 16.7°, 100% = 45°
    """
    return math.degrees(math.atan(percent / 100))


class Point(BaseModel):
    lon: float
    lat: float


class CapabilityMetrics(BaseModel):
    """轻量级能力参数模型，用于算法接口。
    
    注意：slope_percent 使用百分比单位，与数据库字段 max_gradient_percent 一致。
    """
    width_m: Optional[float] = Field(None, ge=0)
    height_m: Optional[float] = Field(None, ge=0)
    weight_kg: Optional[float] = Field(None, ge=0)
    turn_radius_m: Optional[float] = Field(None, ge=0)
    slope_percent: Optional[float] = Field(None, ge=0, description="最大爬坡能力，百分比单位")
    tilt_deg: Optional[float] = Field(None, ge=0)
    wading_depth_m: Optional[float] = Field(None, ge=0)
    range_km: Optional[float] = Field(None, ge=0)
    endurance_min: Optional[float] = Field(None, ge=0)
    max_wind_mps: Optional[float] = Field(None, ge=0)
    payload_kg: Optional[float] = Field(None, ge=0)
    skills: List[str] = Field(default_factory=list)
    sensors: List[str] = Field(default_factory=list)

    @field_validator("skills", "sensors")
    @classmethod
    def _strip(cls, value: List[str]) -> List[str]:
        return [item.strip() for item in value if item.strip()]


class Audit(BaseModel):
    hard_hits: List[str] = Field(default_factory=list)
    soft_hits: List[str] = Field(default_factory=list)
    violated_soft: List[str] = Field(default_factory=list)
    waivers: List[str] = Field(default_factory=list)


@dataclass(slots=True)
class PathSearchMetrics:
    iterations: int
    nodes_expanded: int
    elapsed_ms: float
    path_points: int


@dataclass(slots=True)
class PathCandidate:
    id: str
    points: List[Point]
    distance_m: float
    duration_s: float
    cost: float
    audit: Audit
    metadata: dict
    metrics: PathSearchMetrics


class CapabilityProfileLocal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    platform_type: Literal["vehicle", "uav", "usv", "robot_dog", "team"]
    metrics: CapabilityMetrics
    version: Optional[str] = None
    updated_at: Optional[datetime] = None


class Obstacle(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    hard: bool
    geometry: dict
    time_window: dict | None = None
    severity: str | None = None
    source: str | None = None
    confidence: float | None = None
    metadata: dict = Field(default_factory=dict)


class PathPlanningError(RuntimeError):
    ...


class MissingDataError(PathPlanningError):
    ...


class InfeasiblePathError(PathPlanningError):
    ...


def dedupe(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
