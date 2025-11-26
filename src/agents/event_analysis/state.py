"""
事件分析Agent状态定义

使用TypedDict定义LangGraph状态类型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from typing_extensions import TypedDict


class Location(TypedDict):
    """位置坐标"""
    longitude: float
    latitude: float


class AssessmentResult(TypedDict, total=False):
    """灾情评估结果"""
    disaster_type: str
    disaster_level: str          # I/II/III/IV
    disaster_level_color: str    # 红/橙/黄/蓝
    response_level: str          # 国家级/省级/市级/县级
    affected_area_km2: float
    affected_population: int
    estimated_casualties: Dict[str, int]  # {"deaths": x, "injuries": y, "missing": z}
    intensity_map: Optional[Dict]
    risk_zones: Optional[List[Dict]]
    confidence: float


class SecondaryHazard(TypedDict, total=False):
    """次生灾害预测"""
    type: str                    # fire/landslide/aftershock等
    probability: float           # 发生概率
    risk_level: str              # high/medium/low
    predicted_locations: List[Dict]
    trigger_conditions: str


class LossEstimation(TypedDict, total=False):
    """损失估算"""
    direct_economic_loss_yuan: float
    indirect_economic_loss_yuan: float
    infrastructure_damage: Dict[str, Any]
    building_damage: Dict[str, Any]


class ConfirmationDecision(TypedDict, total=False):
    """确认评分决策"""
    confirmation_score: float
    score_breakdown: Dict[str, Dict]
    matched_auto_confirm_rules: List[str]
    recommended_status: str
    auto_confirmed: bool
    rationale: str


class EventAnalysisState(TypedDict, total=False):
    """
    事件分析Agent状态
    
    LangGraph状态定义，记录分析过程中的所有数据
    """
    # 任务标识
    task_id: str
    
    # 输入数据
    event_id: str                # UUID字符串
    scenario_id: str             # UUID字符串
    disaster_type: str           # earthquake/flood/hazmat/fire/landslide
    location: Location           # 事件位置
    initial_data: Dict[str, Any] # 灾害参数（震级/降雨量等）
    source_system: str           # 来源系统
    source_type: str             # 来源类型
    source_trust_level: float    # 来源可信度
    is_urgent: bool              # 是否紧急
    estimated_victims: int       # 预估被困人数
    priority: str                # 优先级
    context: Dict[str, Any]      # 上下文信息（人口密度/建筑类型等）
    nearby_events: List[Dict]    # 邻近事件（用于多源验证）
    
    # 中间结果
    assessment_result: Optional[AssessmentResult]
    secondary_hazards: Optional[List[SecondaryHazard]]
    loss_estimation: Optional[LossEstimation]
    
    # 确认评分
    ai_confidence: float
    confirmation_decision: Optional[ConfirmationDecision]
    
    # 输出
    recommended_actions: List[str]
    urgency_score: float
    
    # 追踪
    trace: Dict[str, Any]
    errors: List[str]
    
    # 时间戳
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
