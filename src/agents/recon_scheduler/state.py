"""
侦察调度智能体状态定义

包含完整的State和所有TypedDict定义
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Literal
from enum import Enum


# ==================== 枚举定义 ====================

class DisasterType(str, Enum):
    """灾情类型"""
    EARTHQUAKE_COLLAPSE = "earthquake_collapse"
    FLOOD = "flood"
    FIRE = "fire"
    HAZMAT = "hazmat"
    LANDSLIDE = "landslide"


class SeverityLevel(str, Enum):
    """严重程度"""
    CRITICAL = "critical"
    SEVERE = "severe"
    MODERATE = "moderate"
    MINOR = "minor"


class FlightCondition(str, Enum):
    """飞行条件"""
    GREEN = "green"      # 良好
    YELLOW = "yellow"    # 谨慎
    RED = "red"          # 危险
    BLACK = "black"      # 禁飞


class DeviceCategory(str, Enum):
    """设备类别"""
    MULTIROTOR = "multirotor"
    VTOL_FIXED_WING = "vtol_fixed_wing"
    LARGE_FIXED_WING = "large_fixed_wing"
    UGV_QUADRUPED = "ugv_quadruped"
    USV = "usv"


class ScanPattern(str, Enum):
    """扫描模式"""
    ZIGZAG = "zigzag"
    SPIRAL_INWARD = "spiral_inward"
    SPIRAL_OUTWARD = "spiral_outward"
    CIRCULAR = "circular"
    STRIP = "strip"
    GRID = "grid"
    EXPANDING_SQUARE = "expanding_square"


class TaskType(str, Enum):
    """任务类型"""
    AREA_SURVEY = "area_survey"
    THERMAL_SEARCH = "thermal_search"
    POINT_INSPECTION = "point_inspection"
    INDOOR_SEARCH = "indoor_search"
    FIRE_MONITORING = "fire_monitoring"
    FLOOD_MAPPING = "flood_mapping"
    HAZMAT_SURVEY = "hazmat_survey"
    LANDSLIDE_MAPPING = "landslide_mapping"


class WaypointAction(str, Enum):
    """航点动作"""
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    FLY_TO = "fly_to"
    START_SCAN = "start_scan"
    SCAN = "scan"
    TURN = "turn"
    HOVER = "hover"
    TAKE_PHOTO = "take_photo"
    START_VIDEO = "start_video"
    STOP_VIDEO = "stop_video"
    DESCEND = "descend"
    LAND = "land"
    RETURN = "return"


class Priority(str, Enum):
    """优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ==================== Phase 1: 灾情分析 ====================

class SecondaryRisk(TypedDict):
    """次生灾害风险"""
    risk_type: str                      # fire/gas_leak/secondary_collapse/dam_breach
    location: Optional[Dict[str, float]]
    probability: str                    # high/medium/low
    description: str


class PriorityTarget(TypedDict):
    """优先目标"""
    target_id: str
    target_type: str                    # residential/school/hospital/industrial
    location: Dict[str, Any]            # GeoJSON
    estimated_population: int
    priority_score: int
    description: str


class DisasterAnalysis(TypedDict):
    """灾情深度分析"""
    disaster_type: str
    severity_level: str
    
    # 空间特征
    affected_area: Dict[str, Any]       # GeoJSON Polygon
    epicenter: Optional[Dict[str, float]]
    spread_direction: Optional[str]
    
    # 时间特征
    onset_time: Optional[str]
    time_since_onset_hours: float
    golden_hour_remaining: float
    
    # 人员估计
    estimated_affected_population: int
    estimated_trapped: int
    high_risk_zones: List[Dict[str, Any]]
    
    # 次生灾害风险
    secondary_risks: List[SecondaryRisk]
    
    # 侦察优先级
    priority_targets: List[PriorityTarget]
    
    # 关键特征
    characteristics: Dict[str, Any]


# ==================== Phase 2: 环境评估 ====================

class WeatherCondition(TypedDict):
    """天气条件"""
    wind_speed_ms: float
    wind_direction_deg: float
    rain_level: str                     # none/light/moderate/heavy/storm
    visibility_m: float
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float


class WeatherForecast(TypedDict):
    """天气预报"""
    time: str
    conditions: WeatherCondition


class NoFlyZone(TypedDict):
    """禁飞区"""
    zone_id: str
    zone_type: str                      # airport/military/temporary
    geometry: Dict[str, Any]            # GeoJSON
    max_altitude_m: Optional[float]
    description: str


class Obstacle(TypedDict):
    """障碍物"""
    obstacle_id: str
    obstacle_type: str                  # power_line/building/tower
    location: Dict[str, Any]
    height_m: float
    buffer_m: float


class EnvironmentAssessment(TypedDict):
    """环境评估"""
    # 天气
    weather: WeatherCondition
    weather_forecast: List[WeatherForecast]
    weather_risk_level: str
    
    # 空域
    no_fly_zones: List[NoFlyZone]
    restricted_zones: List[Dict[str, Any]]
    
    # 地形
    terrain_elevation_range: Dict[str, float]
    obstacles: List[Obstacle]
    
    # 通信
    signal_coverage: Dict[str, Any]
    
    # 综合评估
    flight_condition: str               # green/yellow/red/black
    recommended_altitude_range: Dict[str, float]
    time_window_hours: float
    restrictions: List[str]


# ==================== Phase 3: 资源盘点 ====================

class DeviceStatus(TypedDict):
    """设备状态"""
    device_id: str
    device_code: str
    device_name: str
    device_type: str                    # drone/dog/ship
    category: str                       # multirotor/vtol_fixed_wing/large_fixed_wing/ugv/usv
    
    # 状态
    status: str                         # available/in_use/maintenance/charging
    battery_percent: Optional[int]
    location: Optional[Dict[str, float]]
    
    # 能力
    capabilities: List[str]
    max_endurance_min: int
    max_speed_ms: float
    max_wind_resistance_ms: float
    ip_rating: Optional[str]
    sensor_fov_deg: Optional[float]
    
    # 约束
    requires_runway: bool
    is_autonomous: bool
    
    # 计算属性
    effective_endurance_min: int
    ready_time_min: int
    vehicle_id: Optional[str]
    vehicle_name: Optional[str]


class ResourceInventory(TypedDict):
    """资源盘点"""
    # 可用设备
    available_devices: List[DeviceStatus]
    
    # 按类型分组
    devices_by_type: Dict[str, List[DeviceStatus]]
    devices_by_category: Dict[str, List[DeviceStatus]]
    
    # 能力汇总
    total_flight_time_available_min: int
    thermal_imaging_devices: List[str]
    mapping_devices: List[str]
    
    # 就绪时间
    immediate_ready: List[str]
    ready_in_15min: List[str]
    ready_in_30min: List[str]


# ==================== Phase 4: 任务规划 ====================

class PhaseTrigger(TypedDict):
    """阶段触发条件"""
    trigger_type: str                   # immediate/phase_complete/condition
    phase: Optional[int]
    condition: Optional[str]


class TaskRequirement(TypedDict):
    """任务需求"""
    type_preference: List[str]
    capabilities_required: List[str]
    min_endurance_min: Optional[int]


class ScanConfig(TypedDict):
    """扫描配置"""
    pattern: str
    altitude_m: float
    speed_ms: float
    overlap_percent: Optional[float]
    line_spacing_m: Optional[float]
    radius_m: Optional[float]
    center: Optional[Dict[str, float]]
    heading_deg: Optional[float]
    approach_direction: Optional[str]


class SafetyRule(TypedDict):
    """安全规则"""
    min_altitude_m: Optional[float]
    max_altitude_m: Optional[float]
    approach_direction: Optional[str]
    min_distance_m: Optional[float]


class ReconTask(TypedDict):
    """侦察任务"""
    task_id: str
    task_name: str
    task_type: str
    phase: int
    priority: str
    
    # 目标
    objective: str
    target_area: Optional[Dict[str, Any]]
    focus_areas: Optional[List[str]]
    
    # 设备需求
    device_requirements: TaskRequirement
    
    # 扫描配置
    scan_config: ScanConfig
    
    # 安全规则
    safety_rules: Optional[SafetyRule]
    
    # 时间约束
    time_budget_min: Optional[int]
    must_start_before_min: Optional[int]
    
    # 依赖
    depends_on: List[str]
    
    # 触发条件
    trigger: PhaseTrigger
    
    # 预期输出
    expected_outputs: List[str]


class MissionPhase(TypedDict):
    """任务阶段"""
    phase_id: str
    phase_number: int
    phase_name: str
    objective: str
    priority: str
    
    # 触发
    trigger: PhaseTrigger
    
    # 任务
    tasks: List[ReconTask]
    
    # 时间
    time_budget_min: Optional[int]
    
    # 输出
    expected_outputs: List[str]


# ==================== Phase 5: 资源分配 ====================

class TaskAllocation(TypedDict):
    """任务分配"""
    task_id: str
    device_id: str
    device_name: str
    device_category: str
    
    # 匹配评分
    match_score: float
    match_reasons: List[str]
    
    # 约束检查
    capability_match: bool
    endurance_sufficient: bool
    weather_compatible: bool
    
    # 预计时间
    estimated_start_min: int
    estimated_duration_min: int
    estimated_end_min: int
    
    # 备份
    is_backup: bool


class CoordinatedGroup(TypedDict):
    """协同任务组"""
    group_id: str
    group_type: str                     # parallel_coverage/relay/sequential
    task_ids: List[str]
    device_ids: List[str]
    coordination_mode: str
    sync_points: List[Dict[str, Any]]


class ResourceAllocation(TypedDict):
    """资源分配结果"""
    allocations: List[TaskAllocation]
    backup_allocations: List[TaskAllocation]
    unallocated_tasks: List[str]
    coordinated_groups: List[CoordinatedGroup]
    resource_utilization: Dict[str, float]


# ==================== Phase 6: 航线规划 ====================

class Waypoint(TypedDict):
    """航点"""
    seq: int
    lat: float
    lng: float
    alt_m: float
    alt_agl_m: Optional[float]
    
    # 速度
    speed_ms: float
    
    # 航向
    heading_deg: Optional[float]
    
    # 动作
    action: str
    action_params: Optional[Dict[str, Any]]
    
    # 云台
    gimbal_pitch_deg: Optional[float]
    gimbal_yaw_deg: Optional[float]
    
    # 停留
    dwell_time_s: Optional[float]
    
    # 触发
    trigger: Optional[str]


class FlightSegment(TypedDict):
    """航段"""
    segment_id: str
    segment_type: str                   # transit/scan/turn/hover
    start_waypoint: int
    end_waypoint: int
    distance_m: float
    duration_s: float
    energy_consumption_percent: float


class FlightStatistics(TypedDict):
    """航线统计"""
    total_distance_m: float
    total_duration_min: float
    coverage_area_m2: float
    waypoint_count: int
    battery_consumption_percent: float


class FlightPlan(TypedDict):
    """航线计划"""
    plan_id: str
    task_id: str
    device_id: str
    device_name: str
    
    # 任务信息
    phase: int
    task_name: str
    scan_pattern: str
    
    # 区域定义
    target_area: Dict[str, Any]
    
    # 航线参数
    flight_parameters: Dict[str, Any]
    scan_parameters: Dict[str, Any]
    
    # 航点序列
    waypoints: List[Waypoint]
    
    # 分段信息
    segments: List[FlightSegment]
    
    # 统计
    statistics: FlightStatistics
    
    # 安全检查
    safety_checks: List[Dict[str, Any]]


# ==================== Phase 7: 时间线编排 ====================

class TimelineEvent(TypedDict):
    """时间线事件"""
    event_id: str
    event_type: str                     # task_start/task_end/milestone/phase_change
    time_min: int
    task_id: Optional[str]
    device_id: Optional[str]
    description: str


class Milestone(TypedDict):
    """里程碑"""
    milestone_id: str
    name: str
    time_min: int
    criteria: str
    dependencies: List[str]


class GanttBar(TypedDict):
    """甘特图条目"""
    task_id: str
    task_name: str
    device_name: str
    start_min: int
    end_min: int
    phase: int
    is_critical: bool


class TimelineScheduling(TypedDict):
    """时间线编排"""
    timeline: List[TimelineEvent]
    gantt_data: List[GanttBar]
    milestones: List[Milestone]
    critical_path: List[str]
    total_duration_min: int
    max_parallel_tasks: int


# ==================== Phase 8: 风险评估 ====================

class Risk(TypedDict):
    """风险"""
    risk_id: str
    risk_type: str                      # weather/equipment/communication/terrain/secondary
    description: str
    probability: str                    # low/medium/high
    impact: str                         # low/medium/high/critical
    risk_score: int
    mitigation: str
    monitoring_indicators: List[str]


class ContingencyPlan(TypedDict):
    """应急预案"""
    plan_id: str
    trigger_condition: str
    immediate_actions: List[str]
    follow_up_actions: List[str]
    resource_reallocation: Optional[Dict[str, Any]]
    notification_chain: List[str]


class RiskAssessment(TypedDict):
    """风险评估"""
    identified_risks: List[Risk]
    overall_risk_level: str
    contingency_plans: List[ContingencyPlan]
    pre_flight_checklist: List[Dict[str, Any]]


# ==================== Phase 9: 计划校验 ====================

class ValidationError(TypedDict):
    """校验错误"""
    error_type: str
    severity: str                       # critical/error/warning
    message: str
    affected_items: List[str]


class CoverageCheckResult(TypedDict):
    """覆盖检查结果"""
    target_area_m2: float
    planned_coverage_m2: float
    coverage_percent: float
    uncovered_areas: List[Dict[str, Any]]
    is_acceptable: bool


class ResourceCheckResult(TypedDict):
    """资源检查结果"""
    all_tasks_allocated: bool
    unallocated_tasks: List[str]
    device_utilization: Dict[str, float]
    battery_margins: Dict[str, float]
    is_acceptable: bool


class TimeCheckResult(TypedDict):
    """时间检查结果"""
    total_duration_min: int
    within_time_window: bool
    golden_hour_coverage: float
    time_critical_tasks_on_schedule: bool
    is_acceptable: bool


class SafetyCheckResult(TypedDict):
    """安全检查结果"""
    no_fly_zone_violations: List[Dict[str, Any]]
    altitude_violations: List[Dict[str, Any]]
    weather_risk_level: str
    communication_gaps: List[Dict[str, Any]]
    is_acceptable: bool


class ConflictCheckResult(TypedDict):
    """冲突检查结果"""
    flight_path_conflicts: List[Dict[str, Any]]
    time_slot_conflicts: List[Dict[str, Any]]
    resource_conflicts: List[Dict[str, Any]]
    is_acceptable: bool


class PlanValidation(TypedDict):
    """计划校验"""
    is_valid: bool
    validation_errors: List[ValidationError]
    validation_warnings: List[ValidationError]
    
    coverage_check: CoverageCheckResult
    resource_check: ResourceCheckResult
    time_check: TimeCheckResult
    safety_check: SafetyCheckResult
    conflict_check: ConflictCheckResult


# ==================== Phase 10: 输出 ====================

class ExecutiveSummary(TypedDict):
    """执行摘要"""
    mission_name: str
    disaster_type: str
    disaster_location: str
    
    # 关键数字
    total_devices: int
    total_phases: int
    total_tasks: int
    estimated_duration_min: int
    target_coverage_km2: float
    
    # 关键时间
    planned_start: str
    estimated_completion: str
    
    # 优先目标
    priority_targets: List[str]
    
    # 风险
    overall_risk_level: str
    weather_window_hours: float


class FlightFile(TypedDict):
    """航线文件"""
    device_id: str
    device_name: str
    file_format: str                    # kml/gpx/waypoint/dji_mission
    file_content: str
    waypoints_json: List[Waypoint]


class CheckItem(TypedDict):
    """检查项"""
    item_id: str
    category: str
    description: str
    is_critical: bool
    checked: bool


class ExecutionPackage(TypedDict):
    """执行包"""
    task_assignment_table: List[Dict[str, Any]]
    schedule_table: List[Dict[str, Any]]
    checklists: Dict[str, List[CheckItem]]
    communication_plan: Dict[str, Any]
    emergency_cards: List[Dict[str, Any]]


class ReconPlan(TypedDict):
    """完整侦察计划"""
    plan_id: str
    event_id: str
    scenario_id: str
    created_at: str
    version: str
    
    # 概述
    executive_summary: ExecutiveSummary
    
    # 分析
    disaster_analysis: DisasterAnalysis
    environment_assessment: EnvironmentAssessment
    
    # 资源
    resource_inventory: ResourceInventory
    resource_allocation: ResourceAllocation
    
    # 任务
    mission_phases: List[MissionPhase]
    
    # 航线
    flight_plans: List[FlightPlan]
    
    # 时间线
    timeline: TimelineScheduling
    
    # 风险
    risk_assessment: RiskAssessment
    
    # 校验
    validation: PlanValidation
    
    # 输出
    flight_files: List[FlightFile]
    execution_package: ExecutionPackage
    
    # 预期产出
    expected_outputs: List[str]


# ==================== 主State定义 ====================

class ReconSchedulerState(TypedDict):
    """侦察调度智能体状态"""
    
    # ========== 输入 ==========
    event_id: str
    scenario_id: str
    recon_request: str
    target_area: Optional[Dict[str, Any]]
    disaster_context: Optional[Dict[str, Any]]
    
    # ========== Phase 1: 灾情分析 ==========
    disaster_analysis: Optional[DisasterAnalysis]
    
    # ========== Phase 2: 环境评估 ==========
    environment_assessment: Optional[EnvironmentAssessment]
    flight_condition: str
    
    # ========== Phase 3: 资源盘点 ==========
    resource_inventory: Optional[ResourceInventory]
    available_devices: List[DeviceStatus]
    
    # ========== Phase 4: 任务规划 ==========
    mission_phases: List[MissionPhase]
    all_tasks: List[ReconTask]
    task_dependencies: Dict[str, List[str]]
    
    # ========== Phase 5: 资源分配 ==========
    resource_allocation: Optional[ResourceAllocation]
    unallocated_tasks: List[str]
    
    # ========== Phase 6: 航线规划 ==========
    flight_plans: List[FlightPlan]
    
    # ========== Phase 7: 时间线 ==========
    timeline_scheduling: Optional[TimelineScheduling]
    milestones: List[Milestone]
    critical_path: List[str]
    total_duration_min: int
    
    # ========== Phase 8: 风险评估 ==========
    risk_assessment: Optional[RiskAssessment]
    contingency_plans: List[ContingencyPlan]
    overall_risk_level: str
    
    # ========== Phase 9: 校验 ==========
    validation_result: Optional[PlanValidation]
    
    # ========== Phase 10: 输出 ==========
    recon_plan: Optional[ReconPlan]
    execution_package: Optional[ExecutionPackage]
    flight_files: List[FlightFile]
    
    # ========== 追踪 ==========
    current_phase: str
    phase_history: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
    adjustment_count: int
    
    # ========== 追溯 ==========
    trace: Dict[str, Any]
