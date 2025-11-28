"""
救援队驻扎点选址数据模型

强类型定义，确保类型安全和IDE支持。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StagingSiteType(str, Enum):
    """驻扎点类型"""
    OPEN_GROUND = "open_ground"
    PARKING_LOT = "parking_lot"
    SPORTS_FIELD = "sports_field"
    SCHOOL_YARD = "school_yard"
    FACTORY_YARD = "factory_yard"
    PLAZA = "plaza"
    HELIPAD = "helipad"
    LOGISTICS_CENTER = "logistics_center"
    OTHER = "other"


class GroundStability(str, Enum):
    """地面稳定性"""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    UNKNOWN = "unknown"


class NetworkType(str, Enum):
    """通信网络类型"""
    FIVE_G = "5g"
    FOUR_G_LTE = "4g_lte"
    THREE_G = "3g"
    SATELLITE = "satellite"
    SHORTWAVE = "shortwave"
    MESH = "mesh"
    NONE = "none"


class PassageStatus(str, Enum):
    """通行状态枚举"""
    CONFIRMED_BLOCKED = "confirmed_blocked"        # 已确认完全不可通行（塌方、断桥）
    NEEDS_RECONNAISSANCE = "needs_reconnaissance"  # 高危险但未确认，需侦察判断
    PASSABLE_WITH_CAUTION = "passable_with_caution"  # 可通行但有风险（降速、救援优先）
    CLEAR = "clear"                                # 已确认安全通行
    UNKNOWN = "unknown"                            # 未知状态（初始值）


class RiskZoneType(str, Enum):
    """风险区域类型"""
    SEISMIC_RED = "seismic_red"      # 烈度>=8
    SEISMIC_ORANGE = "seismic_orange"  # 烈度6-8
    SEISMIC_YELLOW = "seismic_yellow"  # 烈度4-6
    DANGER_ZONE = "danger_zone"
    BLOCKED = "blocked"
    FLOODED = "flooded"
    FIRE = "fire"
    LANDSLIDE = "landslide"


class TargetPriority(str, Enum):
    """救援目标优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EarthquakeParams(BaseModel):
    """地震参数"""
    model_config = ConfigDict(populate_by_name=True)

    epicenter_lon: float = Field(..., description="震中经度")
    epicenter_lat: float = Field(..., description="震中纬度")
    magnitude: float = Field(..., ge=0, le=10, description="震级")
    depth_km: float = Field(10.0, ge=0, description="震源深度(km)")


class RescueTarget(BaseModel):
    """救援目标"""
    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(..., description="目标ID")
    name: str = Field("", description="目标名称")
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    priority: TargetPriority = Field(TargetPriority.MEDIUM, description="优先级")
    estimated_trapped: int = Field(0, ge=0, description="预估被困人数")


class TeamInfo(BaseModel):
    """队伍信息"""
    model_config = ConfigDict(populate_by_name=True)

    team_id: UUID = Field(..., description="队伍ID")
    team_name: str = Field("", description="队伍名称")
    base_lon: float = Field(..., description="驻地经度")
    base_lat: float = Field(..., description="驻地纬度")
    vehicle_id: Optional[UUID] = Field(None, description="主要车辆ID")
    max_speed_kmh: float = Field(50.0, ge=0, description="最大速度km/h")


class StagingConstraints(BaseModel):
    """驻扎点选址约束"""
    model_config = ConfigDict(populate_by_name=True)

    min_buffer_m: float = Field(500.0, ge=0, description="距危险区最小缓冲距离(m)")
    max_slope_deg: float = Field(15.0, ge=0, le=90, description="最大坡度(度)")
    max_search_radius_m: float = Field(50000.0, ge=0, description="最大搜索半径(m)")
    require_water_supply: bool = Field(False, description="是否要求水源")
    require_power_supply: bool = Field(False, description="是否要求电源")
    require_helicopter_landing: bool = Field(False, description="是否要求直升机起降")
    max_candidates: int = Field(50, ge=1, description="最大候选点数量")
    top_n: int = Field(5, ge=1, description="返回前N个推荐")


class EvaluationWeights(BaseModel):
    """评估权重配置"""
    model_config = ConfigDict(populate_by_name=True)

    response_time: float = Field(0.35, ge=0, le=1.0, description="响应时间权重")
    safety: float = Field(0.25, ge=0, le=1.0, description="安全性权重")
    logistics: float = Field(0.20, ge=0, le=1.0, description="后勤保障权重")
    facility: float = Field(0.10, ge=0, le=1.0, description="设施条件权重")
    communication: float = Field(0.10, ge=0, le=1.0, description="通信质量权重")


@dataclass
class RiskZone:
    """风险区域"""
    zone_type: RiskZoneType
    geometry_wkt: str
    risk_level: int  # 1-10
    passable: bool = False
    source: str = ""
    passage_status: PassageStatus = PassageStatus.UNKNOWN  # 通行状态
    reconnaissance_required: bool = False  # 是否需侦察


@dataclass
class CandidateSite:
    """候选驻扎点"""
    id: UUID
    site_code: str
    name: str
    site_type: StagingSiteType
    longitude: float
    latitude: float
    area_m2: Optional[float] = None
    slope_degree: Optional[float] = None
    ground_stability: GroundStability = GroundStability.UNKNOWN
    has_water_supply: bool = False
    has_power_supply: bool = False
    can_helicopter_land: bool = False
    primary_network_type: NetworkType = NetworkType.NONE
    signal_quality: Optional[str] = None
    nearest_supply_depot_m: Optional[float] = None
    nearest_medical_point_m: Optional[float] = None
    nearest_command_post_m: Optional[float] = None
    distance_to_danger_m: Optional[float] = None
    scenario_id: Optional[UUID] = None


@dataclass
class RouteToTarget:
    """到救援目标的路径"""
    target_id: UUID
    target_name: str
    distance_m: float
    duration_seconds: float
    priority: TargetPriority = TargetPriority.MEDIUM


@dataclass
class CandidateWithRoutes:
    """带路径信息的候选点"""
    site: CandidateSite
    route_from_base_distance_m: float
    route_from_base_duration_s: float
    routes_to_targets: List[RouteToTarget] = field(default_factory=list)
    is_reachable: bool = True


@dataclass
class DimensionScores:
    """五维评分"""
    response_time: float = 0.0
    safety: float = 0.0
    logistics: float = 0.0
    facility: float = 0.0
    communication: float = 0.0


class RankedStagingSite(BaseModel):
    """排序后的驻扎点推荐"""
    model_config = ConfigDict(populate_by_name=True)

    site_id: UUID
    site_code: str
    name: str
    site_type: str
    longitude: float
    latitude: float
    area_m2: Optional[float] = None
    slope_degree: Optional[float] = None
    
    has_water_supply: bool = False
    has_power_supply: bool = False
    can_helicopter_land: bool = False
    network_type: str = "none"
    
    distance_to_danger_m: Optional[float] = None
    route_from_base_distance_m: float
    route_from_base_duration_s: float
    
    avg_response_time_to_targets_s: float
    reachable_target_count: int
    
    scores: Dict[str, float] = Field(default_factory=dict)
    total_score: float = 0.0


class StagingRecommendation(BaseModel):
    """驻扎点推荐结果"""
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    error: Optional[str] = None
    
    risk_zones_count: int = 0
    candidates_total: int = 0
    candidates_reachable: int = 0
    
    recommended_sites: List[RankedStagingSite] = Field(default_factory=list)
    
    elapsed_ms: int = 0


class StagingRecommendationRequest(BaseModel):
    """驻扎点推荐请求"""
    model_config = ConfigDict(populate_by_name=True)

    scenario_id: UUID = Field(..., description="想定ID")
    earthquake: EarthquakeParams = Field(..., description="地震参数")
    rescue_targets: List[RescueTarget] = Field(..., min_length=1, description="救援目标列表")
    team: TeamInfo = Field(..., description="救援队伍信息")
    constraints: StagingConstraints = Field(
        default_factory=StagingConstraints,
        description="约束条件"
    )
    weights: EvaluationWeights = Field(
        default_factory=EvaluationWeights,
        description="评估权重"
    )
