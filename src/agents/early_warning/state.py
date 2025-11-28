"""
预警监测智能体状态定义

使用TypedDict定义强类型状态，支持LangGraph状态管理。
"""
from __future__ import annotations

from typing import TypedDict, List, Dict, Any, Optional, Literal
from uuid import UUID
from datetime import datetime
from enum import Enum


class DisasterType(str, Enum):
    """灾害类型"""
    FIRE = "fire"
    FLOOD = "flood"
    CHEMICAL = "chemical"
    LANDSLIDE = "landslide"
    EARTHQUAKE = "earthquake"


class WarningLevel(str, Enum):
    """预警级别"""
    BLUE = "blue"      # >5km
    YELLOW = "yellow"  # 3-5km
    ORANGE = "orange"  # 1-3km
    RED = "red"        # <1km


class WarningStatus(str, Enum):
    """预警状态"""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESPONDED = "responded"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class ResponseAction(str, Enum):
    """响应行动"""
    CONTINUE = "continue"
    DETOUR = "detour"
    STANDBY = "standby"


class Point(TypedDict):
    """地理坐标点"""
    lon: float
    lat: float


class Polygon(TypedDict):
    """多边形"""
    type: str  # "Polygon"
    coordinates: List[List[List[float]]]


class DisasterSituation(TypedDict):
    """灾害态势数据"""
    id: str
    scenario_id: Optional[str]
    disaster_type: str
    disaster_name: Optional[str]
    boundary: Polygon
    center_point: Point
    buffer_distance_m: int
    spread_direction: Optional[str]
    spread_speed_mps: Optional[float]
    severity_level: int
    status: str
    source: Optional[str]


class AffectedObject(TypedDict):
    """受影响对象"""
    object_type: str           # vehicle/team
    object_id: str
    object_name: str
    current_location: Point
    distance_to_disaster_m: float
    estimated_contact_minutes: Optional[int]
    route_affected: bool
    route_intersection_point: Optional[Point]
    notify_target_type: str    # commander/team_leader
    notify_target_id: Optional[str]
    notify_target_name: Optional[str]


class WarningDecision(TypedDict):
    """预警决策"""
    should_warn: bool
    warning_level: str
    affected_object: AffectedObject
    warning_title: str
    warning_message: str


class WarningRecord(TypedDict):
    """预警记录"""
    id: str
    disaster_id: str
    scenario_id: Optional[str]
    affected_type: str
    affected_id: str
    affected_name: str
    warning_level: str
    distance_m: float
    estimated_contact_minutes: Optional[int]
    route_affected: bool
    warning_title: str
    warning_message: str
    status: str
    notify_target_type: str
    notify_target_id: Optional[str]
    created_at: str


class RiskLevel(str, Enum):
    """风险等级"""
    BLUE = "blue"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class PredictionType(str, Enum):
    """预测类型"""
    PATH_RISK = "path_risk"
    OPERATION_RISK = "operation_risk"
    DISASTER_SPREAD = "disaster_spread"


class RiskFactor(TypedDict):
    """风险因素"""
    factor_type: str
    risk_level: str
    value: float
    description: str


class RiskPrediction(TypedDict):
    """风险预测结果"""
    prediction_id: str
    prediction_type: str
    target_type: str
    target_id: Optional[str]
    target_name: Optional[str]
    risk_level: str
    risk_score: float
    confidence_score: float
    risk_factors: List[RiskFactor]
    recommendations: List[str]
    explanation: str
    prediction_horizon_hours: int
    requires_human_review: bool
    weather_data: Optional[Dict[str, Any]]
    created_at: str


class EarlyWarningState(TypedDict):
    """
    预警监测智能体状态（扩展为RealTimeRiskAgent）
    """
    # ========== 输入参数 ==========
    request_id: str
    scenario_id: Optional[str]
    
    # 灾害数据输入
    disaster_input: Optional[Dict[str, Any]]
    
    # ========== 阶段1: 数据接入 ==========
    disaster_situation: Optional[DisasterSituation]
    
    # ========== 阶段2: 影响分析 ==========
    affected_vehicles: List[AffectedObject]
    affected_teams: List[AffectedObject]
    
    # ========== 阶段3: 预警决策 ==========
    warning_decisions: List[WarningDecision]
    
    # ========== 阶段4: 消息生成 ==========
    warning_records: List[WarningRecord]
    
    # ========== 阶段5: 通知发送 ==========
    notifications_sent: int
    notification_errors: List[str]
    
    # ========== 风险预测扩展 ==========
    prediction_request: Optional[Dict[str, Any]]
    risk_predictions: List[RiskPrediction]
    weather_context: Optional[Dict[str, Any]]
    pending_human_review: List[str]
    
    # ========== 最终输出 ==========
    success: bool
    summary: str
    
    # ========== 追踪信息 ==========
    trace: Dict[str, Any]
    errors: List[str]
    current_phase: str


def create_initial_state(
    request_id: str,
    scenario_id: Optional[str] = None,
    disaster_input: Optional[Dict[str, Any]] = None,
    prediction_request: Optional[Dict[str, Any]] = None,
) -> EarlyWarningState:
    """创建初始状态"""
    return EarlyWarningState(
        request_id=request_id,
        scenario_id=scenario_id,
        disaster_input=disaster_input,
        disaster_situation=None,
        affected_vehicles=[],
        affected_teams=[],
        warning_decisions=[],
        warning_records=[],
        notifications_sent=0,
        notification_errors=[],
        prediction_request=prediction_request,
        risk_predictions=[],
        weather_context=None,
        pending_human_review=[],
        success=False,
        summary="",
        trace={
            "phases_executed": [],
            "start_time": datetime.utcnow().isoformat(),
        },
        errors=[],
        current_phase="init",
    )
