"""
救援业务流程数据模型

覆盖五阶段救援流程的所有接口
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================================================
# 通用模型
# ============================================================================

class Location(BaseModel):
    longitude: float = Field(..., ge=-180, le=180)
    latitude: float = Field(..., ge=-90, le=90)
    altitude: Optional[float] = None


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ============================================================================
# 阶段1: 接警通报
# ============================================================================

class IncidentNotification(BaseModel):
    """事件通报（从外部系统接收）"""
    incident_type: str
    title: str
    description: Optional[str] = None
    location: Location
    address: Optional[str] = None
    severity: str = "medium"
    source: str = "external_system"
    reporter_info: Optional[dict[str, Any]] = None
    attachments: Optional[list[dict[str, Any]]] = None


class EquipmentSuggestionRequest(BaseModel):
    """装备建议请求"""
    event_id: UUID
    incident_type: str
    estimated_victims: int = 0
    terrain_type: Optional[str] = None
    weather_conditions: Optional[dict[str, Any]] = None


class EquipmentItem(BaseModel):
    """装备项"""
    equipment_id: UUID
    equipment_name: str
    equipment_type: str
    quantity: int
    priority: str
    reason: str


class EquipmentSuggestionResponse(BaseModel):
    """装备建议响应"""
    event_id: UUID
    suggested_equipment: list[EquipmentItem]
    suggested_vehicles: list[dict[str, Any]]
    suggested_teams: list[dict[str, Any]]
    ai_confidence: float
    reasoning: str


class PreparationTask(BaseModel):
    """准备任务"""
    task_type: str  # equipment_check/vehicle_prep/team_assembly/briefing
    title: str
    description: Optional[str] = None
    assigned_to: Optional[UUID] = None
    deadline_minutes: int = 30


class CompletedItem(BaseModel):
    """已完成项"""
    item_type: str
    item_name: str
    quantity: Optional[int] = None


class PreparationTaskComplete(BaseModel):
    """准备任务完成"""
    completed_items: Optional[list[CompletedItem]] = None
    personnel_onboard: int = 0
    fuel_level: int = 100  # 百分比
    notes: Optional[str] = None


class DepartCommand(BaseModel):
    """出发指令"""
    event_id: UUID
    team_ids: list[UUID]
    vehicle_ids: list[UUID]
    destination: Location
    departure_time: Optional[datetime] = None
    notes: Optional[str] = None


# ============================================================================
# 阶段2: 途中导航
# ============================================================================

class RouteRequest(BaseModel):
    """路径规划请求"""
    event_id: UUID
    vehicle_id: UUID
    origin: Location
    destination: Location
    waypoints: Optional[list[Location]] = None
    avoid_areas: Optional[list[dict[str, Any]]] = None  # 避开区域
    optimization: str = "fastest"  # fastest/shortest/safest


class RouteSegment(BaseModel):
    """路段"""
    start_point: Location
    end_point: Location
    distance_meters: float
    duration_seconds: int
    road_name: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.low
    instructions: Optional[str] = None


class RouteResponse(BaseModel):
    """路径规划响应"""
    route_id: UUID
    event_id: UUID
    vehicle_id: UUID
    total_distance_meters: float
    total_duration_seconds: int
    segments: list[RouteSegment]
    risk_areas: list[dict[str, Any]]
    alternative_routes: Optional[list[dict[str, Any]]] = None


class RiskPrediction(BaseModel):
    """风险预警"""
    risk_id: UUID
    risk_type: str  # road_damage/flood/landslide/traffic/weather
    location: Location
    radius_meters: float
    risk_level: RiskLevel
    description: str
    prediction_confidence: float
    recommended_action: str


class SafePoint(BaseModel):
    """安全点"""
    point_id: UUID
    name: str
    location: Location
    point_type: str  # rest_area/medical_station/supply_point/evacuation_point
    capacity: Optional[int] = None
    facilities: Optional[list[str]] = None
    contact_info: Optional[str] = None


class SafePointConfirm(BaseModel):
    """确认安全点"""
    point_id: UUID
    confirmed_by: Optional[UUID] = None
    notes: Optional[str] = None


# ============================================================================
# 阶段3: 现场指挥
# ============================================================================

class CommandPostRecommendation(BaseModel):
    """指挥所选址推荐"""
    event_id: UUID
    recommended_locations: list[dict[str, Any]]  # [{location, score, reasons}]
    factors_considered: list[str]  # safety/accessibility/communication/visibility
    ai_reasoning: str


class CommandPostConfirm(BaseModel):
    """确认指挥所位置"""
    event_id: UUID
    location: Location
    name: str = "现场指挥所"
    established_at: Optional[datetime] = None


class UAVClusterControl(BaseModel):
    """无人机集群控制"""
    event_id: UUID
    command_type: str  # deploy/recall/reposition/search_pattern
    uav_ids: list[UUID]
    target_area: Optional[dict[str, Any]] = None  # polygon/circle
    parameters: Optional[dict[str, Any]] = None


class RescuePointDetection(BaseModel):
    """救援点识别结果（AI检测）"""
    detection_id: UUID
    event_id: UUID
    location: Location
    detection_type: str  # trapped_person/collapsed_building/fire/flood_area
    confidence: float
    source: str  # uav_image/sensor/manual
    image_url: Optional[str] = None
    estimated_victims: int = 0
    priority: str = "medium"


class RescuePointConfirm(BaseModel):
    """确认救援点检测结果"""
    detection_id: UUID
    is_confirmed: bool
    # 以下字段在确认时用于创建救援点
    event_id: Optional[UUID] = None
    name: Optional[str] = None
    location: Optional[Location] = None
    point_type: Optional[str] = None
    estimated_victims: Optional[int] = None
    notes: Optional[str] = None


# ============================================================================
# 阶段4: 救援作业
# ============================================================================

class RescuePointCreate(BaseModel):
    """手动添加救援点"""
    event_id: UUID
    name: str
    location: Location
    point_type: str
    priority: str = "medium"
    estimated_victims: int = 0
    description: Optional[str] = None
    reported_by: Optional[UUID] = None


class RescuePointUpdate(BaseModel):
    """更新救援点"""
    status: Optional[str] = None  # pending/in_progress/completed/cancelled
    rescued_count: Optional[int] = None
    remaining_victims: Optional[int] = None
    notes: Optional[str] = None


class RescuePointResponse(BaseModel):
    """救援点详情"""
    id: UUID
    event_id: UUID
    name: str
    location: Location
    point_type: str
    priority: str
    status: str
    estimated_victims: int
    rescued_count: int
    remaining_victims: int
    assigned_teams: list[UUID]
    created_at: datetime
    updated_at: datetime


class CoordinationTracking(BaseModel):
    """协同追踪状态"""
    event_id: UUID
    rescue_points: list[RescuePointResponse]
    team_locations: list[dict[str, Any]]
    vehicle_locations: list[dict[str, Any]]
    total_rescued: int
    total_remaining: int
    overall_progress: float


class CoordinationUpdate(BaseModel):
    """协同更新"""
    event_id: UUID
    update_type: str  # team_arrival/rescue_complete/resource_request/status_change
    entity_id: UUID
    entity_type: str  # team/vehicle/rescue_point
    data: dict[str, Any]


# ============================================================================
# 阶段5: 评估总结
# ============================================================================

class EvaluationReportRequest(BaseModel):
    """生成评估报告请求"""
    event_id: UUID
    include_sections: list[str] = [
        "summary", "timeline", "resources", "rescued", "lessons_learned"
    ]


class EvaluationReport(BaseModel):
    """评估报告"""
    report_id: UUID
    event_id: UUID
    generated_at: datetime
    
    # 总体概况
    summary: dict[str, Any]
    
    # 时间线
    timeline: list[dict[str, Any]]
    
    # 资源使用统计
    resource_usage: dict[str, Any]
    
    # 救援成果
    rescue_results: dict[str, Any]
    
    # 经验教训
    lessons_learned: Optional[list[str]] = None
    
    # AI分析
    ai_analysis: Optional[str] = None


# ============================================================================
# 操作手册相关
# ============================================================================

class ManualRecommendation(BaseModel):
    """操作手册推荐"""
    manual_id: UUID
    title: str
    relevance_score: float
    matched_keywords: list[str]
    summary: str


class ManualSearchRequest(BaseModel):
    """操作手册搜索"""
    query: str
    disaster_type: Optional[str] = None
    limit: int = 10
