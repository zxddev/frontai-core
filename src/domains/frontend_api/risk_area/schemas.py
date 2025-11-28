"""
风险区域数据模型

Pydantic v2 schemas for risk area management API
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskAreaType(str, Enum):
    """风险区域类型"""
    DANGER_ZONE = "danger_zone"          # 危险区
    BLOCKED = "blocked"                   # 封锁区
    DAMAGED = "damaged"                   # 损坏区
    FLOODED = "flooded"                   # 淹没区
    CONTAMINATED = "contaminated"         # 污染区
    LANDSLIDE = "landslide"               # 滑坡区
    FIRE = "fire"                         # 火灾区
    SEISMIC_RED = "seismic_red"           # 地震红区 (烈度>=8)
    SEISMIC_ORANGE = "seismic_orange"     # 地震橙区 (烈度6-8)
    SEISMIC_YELLOW = "seismic_yellow"     # 地震黄区 (烈度4-6)


class SeverityLevel(str, Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PassageStatus(str, Enum):
    """通行状态"""
    CONFIRMED_BLOCKED = "confirmed_blocked"        # 已确认完全不可通行
    NEEDS_RECONNAISSANCE = "needs_reconnaissance"  # 需侦察确认
    PASSABLE_WITH_CAUTION = "passable_with_caution"  # 可通行但需谨慎
    CLEAR = "clear"                                # 安全通行
    UNKNOWN = "unknown"                            # 未知状态


class GeoJsonPolygon(BaseModel):
    """GeoJSON 多边形几何对象"""
    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default="Polygon", description="几何类型")
    coordinates: list[list[list[float]]] = Field(
        ...,
        description="多边形坐标 [[[lng, lat], [lng, lat], ...]]"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v != "Polygon":
            raise ValueError("geometry type must be 'Polygon'")
        return v

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list) -> list:
        if not v or not v[0] or len(v[0]) < 4:
            raise ValueError("Polygon must have at least 4 coordinates (closed ring)")
        return v


class RiskAreaCreateRequest(BaseModel):
    """创建风险区域请求"""
    model_config = ConfigDict(populate_by_name=True)

    scenario_id: UUID = Field(..., alias="scenarioId", description="想定ID")
    name: str = Field(..., min_length=1, max_length=200, description="区域名称")
    area_type: RiskAreaType = Field(..., alias="areaType", description="区域类型")
    risk_level: int = Field(
        ...,
        ge=1,
        le=10,
        alias="riskLevel",
        description="风险等级 1-10，10为最高"
    )
    severity: SeverityLevel = Field(..., description="严重程度")
    passage_status: PassageStatus = Field(
        default=PassageStatus.UNKNOWN,
        alias="passageStatus",
        description="通行状态"
    )
    geometry: GeoJsonPolygon = Field(..., description="区域多边形")
    passable: bool = Field(default=False, description="是否允许通行")
    passable_vehicle_types: list[str] = Field(
        default_factory=list,
        alias="passableVehicleTypes",
        description="允许通行的车辆类型"
    )
    speed_reduction_percent: int = Field(
        default=100,
        ge=0,
        le=100,
        alias="speedReductionPercent",
        description="速度降低百分比"
    )
    reconnaissance_required: bool = Field(
        default=False,
        alias="reconnaissanceRequired",
        description="是否需要侦察确认"
    )
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    estimated_end_at: Optional[datetime] = Field(
        None,
        alias="estimatedEndAt",
        description="预计结束时间"
    )


class RiskAreaUpdateRequest(BaseModel):
    """更新风险区域请求"""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=200, description="区域名称")
    risk_level: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        alias="riskLevel",
        description="风险等级"
    )
    severity: Optional[SeverityLevel] = Field(None, description="严重程度")
    passage_status: Optional[PassageStatus] = Field(
        None,
        alias="passageStatus",
        description="通行状态"
    )
    passable: Optional[bool] = Field(None, description="是否允许通行")
    passable_vehicle_types: Optional[list[str]] = Field(
        None,
        alias="passableVehicleTypes",
        description="允许通行的车辆类型"
    )
    speed_reduction_percent: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        alias="speedReductionPercent",
        description="速度降低百分比"
    )
    reconnaissance_required: Optional[bool] = Field(
        None,
        alias="reconnaissanceRequired",
        description="是否需要侦察确认"
    )
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    estimated_end_at: Optional[datetime] = Field(
        None,
        alias="estimatedEndAt",
        description="预计结束时间"
    )


class PassageStatusUpdateRequest(BaseModel):
    """更新通行状态请求"""
    model_config = ConfigDict(populate_by_name=True)

    passage_status: PassageStatus = Field(..., alias="passageStatus", description="通行状态")
    verified_by: Optional[UUID] = Field(
        None,
        alias="verifiedBy",
        description="验证者ID（侦察队伍/无人机）"
    )


class RiskAreaResponse(BaseModel):
    """风险区域响应"""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: UUID = Field(..., description="区域ID")
    scenario_id: Optional[UUID] = Field(None, alias="scenarioId", description="想定ID")
    name: Optional[str] = Field(None, description="区域名称")
    area_type: str = Field(..., alias="areaType", description="区域类型")
    risk_level: int = Field(..., alias="riskLevel", description="风险等级")
    severity: str = Field(..., description="严重程度")
    passage_status: str = Field(..., alias="passageStatus", description="通行状态")
    passable: bool = Field(..., description="是否允许通行")
    passable_vehicle_types: Optional[list[str]] = Field(
        None,
        alias="passableVehicleTypes",
        description="允许通行的车辆类型"
    )
    speed_reduction_percent: int = Field(
        ...,
        alias="speedReductionPercent",
        description="速度降低百分比"
    )
    reconnaissance_required: bool = Field(
        ...,
        alias="reconnaissanceRequired",
        description="是否需要侦察确认"
    )
    description: Optional[str] = Field(None, description="描述")
    geometry_geojson: Optional[dict] = Field(
        None,
        alias="geometry",
        description="GeoJSON格式的几何数据"
    )
    started_at: Optional[datetime] = Field(None, alias="startedAt", description="开始时间")
    estimated_end_at: Optional[datetime] = Field(
        None,
        alias="estimatedEndAt",
        description="预计结束时间"
    )
    last_verified_at: Optional[datetime] = Field(
        None,
        alias="lastVerifiedAt",
        description="最后验证时间"
    )
    verified_by: Optional[UUID] = Field(
        None,
        alias="verifiedBy",
        description="验证者ID"
    )
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="创建时间")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="更新时间")


class RiskAreaListResponse(BaseModel):
    """风险区域列表响应"""
    model_config = ConfigDict(populate_by_name=True)

    items: list[RiskAreaResponse] = Field(default_factory=list, description="区域列表")
    total: int = Field(default=0, description="总数量")
