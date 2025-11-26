"""
AI Agent API请求响应模型

定义AI接口的Pydantic模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# 通用模型
# ============================================================================

class Location(BaseModel):
    """位置坐标"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class ScoreBreakdown(BaseModel):
    """评分细分"""
    value: float = Field(..., description="原始值")
    weight: float = Field(..., description="权重")
    contribution: float = Field(..., description="贡献值")


# ============================================================================
# 事件分析接口
# ============================================================================

class AnalyzeEventRequest(BaseModel):
    """事件分析请求"""
    event_id: UUID = Field(..., description="事件ID")
    disaster_type: str = Field(..., description="灾害类型: earthquake/flood/hazmat/fire/landslide")
    location: Location = Field(..., description="事件位置")
    source_system: str = Field(default="unknown", description="来源系统: 110/119/120/sensor/manual等")
    source_trust_level: float = Field(default=0.5, ge=0, le=1, description="来源可信度")
    initial_data: Dict[str, Any] = Field(default_factory=dict, description="灾害参数")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    analysis_options: Optional[Dict[str, Any]] = Field(default=None, description="分析选项")
    
    # 可选字段
    scenario_id: Optional[UUID] = Field(default=None, description="想定ID")
    source_type: str = Field(default="manual_report", description="来源类型")
    is_urgent: bool = Field(default=False, description="是否紧急")
    estimated_victims: int = Field(default=0, ge=0, description="预估被困人数")
    priority: str = Field(default="medium", description="优先级: critical/high/medium/low")
    nearby_events: List[Dict[str, Any]] = Field(default_factory=list, description="邻近事件列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "disaster_type": "earthquake",
                "location": {"longitude": 104.0657, "latitude": 30.5728},
                "source_system": "110",
                "source_trust_level": 0.95,
                "initial_data": {
                    "magnitude": 5.5,
                    "depth_km": 10,
                    "occurred_at": "2025-11-25T10:30:00Z",
                },
                "context": {
                    "population_density": 5000,
                    "building_types": ["residential", "commercial"],
                },
                "is_urgent": True,
                "estimated_victims": 20,
                "priority": "critical",
            }
        }


class AnalyzeEventTaskResponse(BaseModel):
    """事件分析任务提交响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    status: str = Field(..., description="任务状态: processing/completed/failed")
    message: str = Field(..., description="状态消息")
    created_at: datetime = Field(..., description="创建时间")


class AssessmentResult(BaseModel):
    """灾情评估结果"""
    disaster_type: Optional[str] = None
    disaster_level: Optional[str] = None
    disaster_level_color: Optional[str] = None
    response_level: Optional[str] = None
    affected_area_km2: Optional[float] = None
    affected_population: Optional[int] = None
    estimated_casualties: Optional[Dict[str, int]] = None
    intensity_map: Optional[Dict[str, Any]] = None
    risk_zones: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None


class SecondaryHazard(BaseModel):
    """次生灾害预测"""
    type: str = Field(..., description="灾害类型")
    probability: float = Field(..., ge=0, le=1, description="发生概率")
    risk_level: str = Field(..., description="风险等级: high/medium/low")
    predicted_locations: List[Dict[str, Any]] = Field(default_factory=list, description="预测位置")
    trigger_conditions: Optional[str] = None


class LossEstimation(BaseModel):
    """损失估算"""
    direct_economic_loss_yuan: Optional[float] = None
    indirect_economic_loss_yuan: Optional[float] = None
    infrastructure_damage: Optional[Dict[str, Any]] = None
    building_damage: Optional[Dict[str, Any]] = None


class ConfirmationDecision(BaseModel):
    """确认评分决策"""
    confirmation_score: float = Field(..., ge=0, le=1, description="确认评分")
    score_breakdown: Dict[str, ScoreBreakdown] = Field(..., description="评分细分")
    matched_auto_confirm_rules: List[str] = Field(default_factory=list, description="匹配的AC规则")
    recommended_status: str = Field(..., description="推荐状态: confirmed/pre_confirmed/pending")
    auto_confirmed: bool = Field(..., description="是否自动确认")
    rationale: str = Field(..., description="决策理由")


class PreConfirmation(BaseModel):
    """预确认信息"""
    countdown_expires_at: datetime = Field(..., description="倒计时截止时间")
    countdown_minutes: int = Field(default=30, description="倒计时分钟数")
    pre_allocated_resources: List[Dict[str, Any]] = Field(default_factory=list, description="预分配资源")
    pre_generated_scheme_id: Optional[str] = None
    auto_escalate_if_timeout: bool = Field(default=True, description="超时是否自动升级")


class EventStatusUpdate(BaseModel):
    """事件状态更新"""
    previous_status: str = Field(..., description="原状态")
    new_status: str = Field(..., description="新状态")
    auto_confirmed: bool = Field(default=False, description="是否自动确认")
    pre_confirmation: Optional[PreConfirmation] = None


class AnalysisResult(BaseModel):
    """分析结果"""
    disaster_level: Optional[str] = None
    disaster_level_color: Optional[str] = None
    response_level: Optional[str] = None
    ai_confidence: float = Field(default=0, description="AI置信度")
    assessment: Optional[AssessmentResult] = None
    secondary_hazards: List[SecondaryHazard] = Field(default_factory=list)
    loss_estimation: Optional[LossEstimation] = None
    urgency_score: float = Field(default=0, description="紧急度评分")
    recommended_actions: List[str] = Field(default_factory=list, description="推荐行动")


class TraceInfo(BaseModel):
    """追踪信息"""
    algorithms_used: List[str] = Field(default_factory=list, description="使用的算法")
    nodes_executed: List[str] = Field(default_factory=list, description="执行的节点")
    execution_time_ms: Optional[float] = None
    model_version: Optional[str] = None


class AnalyzeEventResult(BaseModel):
    """事件分析完整结果"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    status: str = Field(..., description="任务状态")
    analysis_result: AnalysisResult = Field(..., description="分析结果")
    confirmation_decision: ConfirmationDecision = Field(..., description="确认决策")
    event_status_update: EventStatusUpdate = Field(..., description="状态更新")
    trace: TraceInfo = Field(..., description="追踪信息")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    execution_time_ms: Optional[float] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# 方案生成接口
# ============================================================================

class GenerateSchemeRequest(BaseModel):
    """方案生成请求"""
    event_id: UUID = Field(..., description="事件ID")
    scenario_id: Optional[UUID] = Field(default=None, description="想定ID")
    event_analysis: Dict[str, Any] = Field(..., description="事件分析结果（来自EventAnalysisAgent）")
    constraints: Optional[Dict[str, Any]] = Field(default=None, description="约束条件")
    optimization_weights: Optional[Dict[str, float]] = Field(default=None, description="优化权重")
    options: Optional[Dict[str, Any]] = Field(default=None, description="生成选项")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "scenario_id": "660e8400-e29b-41d4-a716-446655440001",
                "event_analysis": {
                    "disaster_type": "earthquake",
                    "title": "某市6.2级地震",
                    "location": {"latitude": 30.5, "longitude": 104.0},
                    "assessment": {
                        "magnitude": 6.2,
                        "estimated_casualties": {"trapped": 50, "deaths": 5, "injuries": 30},
                        "has_trapped": True,
                        "collapse_area_sqm": 5000,
                    },
                },
                "constraints": {
                    "max_response_time_min": 30,
                    "max_teams": 10,
                },
                "optimization_weights": {
                    "response_time": 0.35,
                    "coverage_rate": 0.30,
                    "cost": 0.15,
                    "risk": 0.20,
                },
                "options": {
                    "generate_alternatives": 3,
                },
            }
        }


class GenerateSchemeTaskResponse(BaseModel):
    """方案生成任务提交响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    status: str = Field(..., description="任务状态: processing/completed/failed")
    message: str = Field(..., description="状态消息")
    created_at: datetime = Field(..., description="创建时间")


# ============================================================================
# 批量方案生成接口
# ============================================================================

class BatchGenerateSchemeRequest(BaseModel):
    """批量方案生成请求"""
    requests: List[GenerateSchemeRequest] = Field(
        ..., 
        min_length=1, 
        max_length=10,
        description="方案生成请求列表（最多10个）"
    )
    parallel: bool = Field(default=True, description="是否并行执行")
    
    class Config:
        json_schema_extra = {
            "example": {
                "requests": [
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "event_analysis": {
                            "disaster_type": "earthquake",
                            "location": {"latitude": 30.5, "longitude": 104.0},
                            "assessment": {"magnitude": 6.2, "has_trapped": True},
                        },
                    },
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440001",
                        "event_analysis": {
                            "disaster_type": "fire",
                            "location": {"latitude": 31.2, "longitude": 121.5},
                            "assessment": {"building_height_m": 50},
                        },
                    },
                ],
                "parallel": True,
            }
        }


class BatchGenerateSchemeResponse(BaseModel):
    """批量方案生成响应"""
    success: bool = Field(..., description="整体是否成功")
    total: int = Field(..., description="请求总数")
    succeeded: int = Field(..., description="成功数量")
    failed: int = Field(..., description="失败数量")
    results: List[Dict[str, Any]] = Field(..., description="各请求结果")
    execution_time_ms: float = Field(..., description="总执行时间(ms)")


# ============================================================================
# 应急AI混合分析接口
# ============================================================================

class EmergencyAnalyzeRequest(BaseModel):
    """应急AI分析请求"""
    event_id: UUID = Field(..., description="事件ID")
    scenario_id: UUID = Field(..., description="想定ID")
    disaster_description: str = Field(..., min_length=10, description="灾情描述（自然语言）")
    structured_input: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="结构化输入，必须包含location.longitude和location.latitude用于计算队伍响应时间"
    )
    constraints: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="约束条件，如max_response_time_hours（最大响应时间/小时）"
    )
    optimization_weights: Optional[Dict[str, float]] = Field(default=None, description="优化权重")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "scenario_id": "550e8400-e29b-41d4-a716-446655440002",
                "disaster_description": "XX市XX区发生5.5级地震，多栋建筑倒塌，预计有30人被困，部分区域发生火灾",
                "structured_input": {
                    "location": {"longitude": 104.0657, "latitude": 30.5728},
                    "occurred_at": "2025-11-25T10:30:00Z",
                },
                "constraints": {
                    "max_response_time_min": 30,
                    "max_teams": 10,
                },
                "optimization_weights": {
                    "response_time": 0.40,
                    "coverage_rate": 0.30,
                    "cost": 0.10,
                    "risk": 0.20,
                },
            }
        }


class EmergencyAnalyzeTaskResponse(BaseModel):
    """应急AI分析任务提交响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="状态消息")
    created_at: datetime = Field(..., description="创建时间")


class MatchedRuleInfo(BaseModel):
    """匹配规则信息"""
    rule_id: str = Field(..., description="规则ID")
    rule_name: str = Field(..., description="规则名称")
    priority: str = Field(..., description="优先级")
    match_reason: str = Field(..., description="匹配原因")


class SchemeScoreInfo(BaseModel):
    """方案评分信息"""
    scheme_id: str = Field(..., description="方案ID")
    passed: bool = Field(..., description="是否通过硬规则")
    violations: List[str] = Field(default_factory=list, description="违反的规则")
    weighted_score: float = Field(..., description="加权得分")
    rank: int = Field(..., description="排名")


class EmergencyAnalyzeResult(BaseModel):
    """应急AI分析结果"""
    success: bool = Field(..., description="是否成功")
    event_id: str = Field(..., description="事件ID")
    scenario_id: str = Field(..., description="想定ID")
    status: str = Field(..., description="状态")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    
    # 各阶段结果
    understanding: Optional[Dict[str, Any]] = Field(default=None, description="灾情理解结果")
    reasoning: Optional[Dict[str, Any]] = Field(default=None, description="规则推理结果")
    matching: Optional[Dict[str, Any]] = Field(default=None, description="资源匹配结果")
    optimization: Optional[Dict[str, Any]] = Field(default=None, description="方案优化结果")
    
    # 推荐方案
    recommended_scheme: Optional[Dict[str, Any]] = Field(default=None, description="推荐方案")
    scheme_explanation: Optional[str] = Field(default=None, description="方案解释")
    
    # 追踪和错误
    trace: Optional[Dict[str, Any]] = Field(default=None, description="执行追踪")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    execution_time_ms: Optional[int] = Field(default=None, description="执行时间(ms)")


# ============================================================================
# 任务调度接口
# ============================================================================

class DispatchConfig(BaseModel):
    """调度配置"""
    strategy: str = Field(default="critical_path", description="调度策略: critical_path/priority_list")
    vehicle_capacity: int = Field(default=10, description="车辆容量")
    max_distance_km: float = Field(default=100, description="最大行驶距离(km)")
    max_time_min: int = Field(default=480, description="最大工作时间(分钟)")
    speed_kmh: float = Field(default=40, description="平均行驶速度(km/h)")
    base_time: Optional[str] = Field(default=None, description="基准时间(ISO格式)")


class DispatchTasksRequest(BaseModel):
    """任务调度请求"""
    event_id: UUID = Field(..., description="事件ID")
    scenario_id: UUID = Field(..., description="想定ID")
    scheme_id: UUID = Field(..., description="方案ID")
    scheme_data: Dict[str, Any] = Field(..., description="方案数据(来自SchemeGenerationAgent)")
    dispatch_config: Optional[DispatchConfig] = Field(default=None, description="调度配置")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "scenario_id": "550e8400-e29b-41d4-a716-446655440001",
                "scheme_id": "550e8400-e29b-41d4-a716-446655440002",
                "scheme_data": {
                    "resource_allocations": [
                        {
                            "resource_id": "team-001",
                            "resource_name": "重型救援队",
                            "resource_type": "heavy_rescue",
                            "assigned_task_types": ["search_rescue"],
                        }
                    ]
                },
                "dispatch_config": {
                    "strategy": "critical_path",
                    "speed_kmh": 40,
                }
            }
        }


class DispatchTasksTaskResponse(BaseModel):
    """任务调度任务提交响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    event_id: str = Field(..., description="事件ID")
    scheme_id: str = Field(..., description="方案ID")
    status: str = Field(..., description="任务状态: processing/completed/failed")
    message: str = Field(..., description="状态消息")
    created_at: datetime = Field(..., description="创建时间")


class DispatchOrderInfo(BaseModel):
    """调度单信息"""
    order_id: str = Field(..., description="调度单ID")
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    executor_id: str = Field(..., description="执行者ID")
    executor_name: str = Field(..., description="执行者名称")
    priority: int = Field(..., description="优先级")
    scheduled_start_time: str = Field(..., description="计划开始时间")
    scheduled_end_time: str = Field(..., description="计划结束时间")
    location: Location = Field(..., description="任务位置")
    instructions: List[str] = Field(default_factory=list, description="执行指令")
    required_equipment: List[str] = Field(default_factory=list, description="所需装备")
    route_summary: Optional[str] = Field(default=None, description="路线摘要")
    status: str = Field(default="pending", description="状态")


class ScheduledTaskInfo(BaseModel):
    """已调度任务信息"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    start_time_min: int = Field(..., description="开始时间(分钟)")
    end_time_min: int = Field(..., description="结束时间(分钟)")
    assigned_resource_ids: List[str] = Field(default_factory=list, description="分配的资源ID")
    priority: int = Field(..., description="优先级")
    is_critical_path: bool = Field(default=False, description="是否在关键路径上")


class PlannedRouteInfo(BaseModel):
    """规划路线信息"""
    vehicle_id: str = Field(..., description="车辆ID")
    vehicle_name: str = Field(..., description="车辆名称")
    stop_count: int = Field(..., description="停靠点数量")
    total_distance_km: float = Field(..., description="总距离(km)")
    total_time_min: int = Field(..., description="总时间(分钟)")


class DispatchSummary(BaseModel):
    """调度结果摘要"""
    task_count: int = Field(..., description="任务数量")
    scheduled_count: int = Field(..., description="已调度数量")
    order_count: int = Field(..., description="调度单数量")
    route_count: int = Field(..., description="路线数量")
    makespan_min: int = Field(..., description="总工期(分钟)")
    total_distance_km: float = Field(..., description="总行驶距离(km)")
    total_travel_time_min: int = Field(..., description="总行驶时间(分钟)")
    critical_path_tasks: List[str] = Field(default_factory=list, description="关键路径任务")


class DispatchTasksResult(BaseModel):
    """任务调度结果"""
    success: bool = Field(..., description="是否成功")
    event_id: str = Field(..., description="事件ID")
    scenario_id: str = Field(..., description="想定ID")
    scheme_id: str = Field(..., description="方案ID")
    
    # 摘要
    summary: DispatchSummary = Field(..., description="调度摘要")
    
    # 详细结果
    dispatch_orders: List[Dict[str, Any]] = Field(default_factory=list, description="调度单列表")
    scheduled_tasks: List[Dict[str, Any]] = Field(default_factory=list, description="已调度任务")
    planned_routes: List[Dict[str, Any]] = Field(default_factory=list, description="规划路线")
    executor_assignments: List[Dict[str, Any]] = Field(default_factory=list, description="执行者分配")
    gantt_data: List[Dict[str, Any]] = Field(default_factory=list, description="甘特图数据")
    
    # 追踪和错误
    trace: Optional[Dict[str, Any]] = Field(default=None, description="执行追踪")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    execution_time_ms: Optional[float] = Field(default=None, description="执行时间(ms)")
    
    # 时间戳
    started_at: Optional[str] = Field(default=None, description="开始时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
