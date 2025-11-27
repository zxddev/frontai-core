"""
资源调度数据模型

强类型定义，确保类型安全和IDE支持。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PriorityLevel(str, Enum):
    """优先级"""
    CRITICAL = "critical"  # 紧急（生命相关）
    HIGH = "high"          # 高优先级
    MEDIUM = "medium"      # 中优先级
    LOW = "low"            # 低优先级


class ResourceType(str, Enum):
    """资源类型"""
    FIRE_TEAM = "fire_team"             # 消防队伍
    MEDICAL_TEAM = "medical_team"       # 医疗队伍
    RESCUE_TEAM = "rescue_team"         # 搜救队伍
    HAZMAT_TEAM = "hazmat_team"         # 危化品处理队伍
    ENGINEERING_TEAM = "engineering_team"  # 工程队伍
    WATER_RESCUE_TEAM = "water_rescue_team"  # 水域救援队伍
    SUPPORT_TEAM = "support_team"       # 保障队伍
    VOLUNTEER_TEAM = "volunteer_team"   # 志愿者队伍
    VEHICLE = "vehicle"                 # 车辆
    EQUIPMENT = "equipment"             # 设备
    SUPPLY = "supply"                   # 物资


class CapabilityRequirement(BaseModel):
    """能力需求"""
    model_config = ConfigDict(populate_by_name=True)

    capability_code: str = Field(..., description="能力编码，如fire_fighting, medical_first_aid")
    min_count: int = Field(1, ge=1, description="最少需要的资源数量")
    priority: PriorityLevel = Field(PriorityLevel.MEDIUM, description="优先级")
    min_level: int = Field(1, ge=1, le=5, description="最低能力等级要求")
    preferred_resource_types: List[ResourceType] = Field(
        default_factory=list,
        description="优先选择的资源类型"
    )


class SchedulingConstraints(BaseModel):
    """调度约束条件"""
    model_config = ConfigDict(populate_by_name=True)

    max_response_time_minutes: float = Field(
        120.0, ge=0, description="最大响应时间（分钟）"
    )
    max_resources: int = Field(
        50, ge=1, description="最多分配的资源数量"
    )
    min_coverage_rate: float = Field(
        0.7, ge=0, le=1.0, description="最低能力覆盖率"
    )
    min_rescue_capacity: int = Field(
        0, ge=0, description="最低救援容量（人数）"
    )
    avoid_disaster_areas: bool = Field(
        True, description="是否避开灾害区域"
    )
    scenario_id: Optional[UUID] = Field(
        None, description="想定ID（用于查询灾害区域）"
    )
    excluded_resource_ids: Set[UUID] = Field(
        default_factory=set, description="排除的资源ID（已分配给其他任务）"
    )


class SchedulingObjectives(BaseModel):
    """优化目标权重"""
    model_config = ConfigDict(populate_by_name=True)

    response_time_weight: float = Field(0.35, ge=0, le=1.0, description="响应时间权重")
    coverage_weight: float = Field(0.30, ge=0, le=1.0, description="能力覆盖率权重")
    capacity_weight: float = Field(0.20, ge=0, le=1.0, description="救援容量权重")
    cost_weight: float = Field(0.10, ge=0, le=1.0, description="成本（队伍数量）权重")
    redundancy_weight: float = Field(0.05, ge=0, le=1.0, description="冗余性权重")


@dataclass
class RouteInfo:
    """路径信息"""
    origin_lon: float
    origin_lat: float
    destination_lon: float
    destination_lat: float
    distance_m: float           # 真实道路距离（米）
    duration_seconds: float     # 预计行驶时间（秒）
    path_edge_count: int = 0    # 路径边数
    blocked_by_disaster: bool = False  # 是否被灾害区域阻挡
    warnings: List[str] = field(default_factory=list)

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0

    @property
    def eta_minutes(self) -> float:
        return self.duration_seconds / 60.0


@dataclass
class ResourceCandidate:
    """候选资源"""
    resource_id: UUID
    resource_name: str
    resource_type: ResourceType
    capabilities: List[str]
    capability_level: int
    
    # 位置信息
    base_lon: float
    base_lat: float
    base_address: str
    
    # 容量信息
    personnel_count: int
    rescue_capacity: int
    
    # 车辆信息（可选）
    vehicle_id: Optional[UUID] = None
    vehicle_code: Optional[str] = None
    max_speed_kmh: int = 60
    is_all_terrain: bool = False
    
    # 路径规划结果（调度后填充）
    route: Optional[RouteInfo] = None
    
    # 评分（调度后计算）
    match_score: float = 0.0
    
    @property
    def direct_distance_km(self) -> float:
        """直线距离（需要外部计算后设置）"""
        return getattr(self, "_direct_distance_km", 0.0)
    
    @direct_distance_km.setter
    def direct_distance_km(self, value: float) -> None:
        self._direct_distance_km = value

    @property
    def eta_minutes(self) -> float:
        """响应时间（分钟）"""
        if self.route:
            return self.route.eta_minutes
        return 0.0

    @property
    def road_distance_km(self) -> float:
        """道路距离（公里）"""
        if self.route:
            return self.route.distance_km
        return 0.0


@dataclass
class ResourceAllocation:
    """资源分配结果"""
    resource_id: UUID
    resource_name: str
    resource_type: ResourceType
    assigned_capabilities: List[str]  # 分配的能力
    
    # 距离和时间
    direct_distance_km: float
    road_distance_km: float
    eta_minutes: float
    
    # 评分
    match_score: float
    rescue_capacity: int


@dataclass
class SchedulingSolution:
    """单个调度方案"""
    solution_id: str
    allocations: List[ResourceAllocation]
    
    # 方案评价指标
    max_eta_minutes: float      # 最大响应时间
    total_eta_minutes: float    # 总响应时间
    coverage_rate: float        # 能力覆盖率
    total_capacity: int         # 总救援容量
    resource_count: int         # 资源数量
    avg_match_score: float      # 平均匹配分数
    
    # 方案描述
    strategy: str               # 生成策略（nsga2/greedy_score/greedy_distance）
    is_feasible: bool           # 是否可行（满足约束）
    warnings: List[str] = field(default_factory=list)


@dataclass
class SchedulingResult:
    """调度结果"""
    success: bool
    solutions: List[SchedulingSolution]  # 多个Pareto最优方案
    best_solution: Optional[SchedulingSolution]  # 推荐方案
    
    # 候选资源信息
    candidates_total: int
    candidates_with_route: int
    candidates_reachable: int
    
    # 调度过程信息
    elapsed_ms: int
    algorithm_used: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
