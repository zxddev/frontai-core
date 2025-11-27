"""
路径规划智能体状态定义

使用TypedDict定义强类型状态，支持LangGraph状态管理。
参考DynamicRouteGPT/LeAD论文的双频架构思想。
"""
from __future__ import annotations

from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from uuid import UUID
from enum import Enum

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class PlanningStrategy(str, Enum):
    """规划策略枚举"""
    FASTEST = "fastest"           # 最快到达
    SAFEST = "safest"             # 最安全路线
    BALANCED = "balanced"         # 平衡时间与安全
    CAPACITY = "capacity"         # 优先道路承载力（重型设备）
    FUEL_EFFICIENT = "fuel"       # 燃油效率优先


class Point(TypedDict):
    """地理坐标点"""
    lon: float                    # 经度
    lat: float                    # 纬度


class TaskPoint(TypedDict):
    """任务点（VRP场景）"""
    id: str                       # 任务点ID
    location: Point               # 位置坐标
    demand: int                   # 需求量
    priority: int                 # 优先级 1-5
    time_window_start: Optional[int]   # 时间窗开始（分钟）
    time_window_end: Optional[int]     # 时间窗结束（分钟）
    service_time_min: int         # 服务时间（分钟）


class VehicleInfo(TypedDict):
    """车辆信息"""
    vehicle_id: str               # 车辆ID
    vehicle_code: str             # 车辆编码
    vehicle_type: str             # 车辆类型
    max_speed_kmh: int            # 最大速度
    is_all_terrain: bool          # 是否全地形
    capacity: int                 # 载重能力
    current_location: Point       # 当前位置


class RouteConstraint(TypedDict, total=False):
    """路径约束条件"""
    max_distance_km: float        # 最大距离限制
    max_time_min: int             # 最大时间限制
    avoid_areas: List[str]        # 避开区域ID列表
    avoid_road_types: List[str]   # 避开道路类型
    prefer_highways: bool         # 优先高速公路
    require_all_terrain: bool     # 需要全地形能力


class DisasterContext(TypedDict, total=False):
    """灾情上下文（用于LLM决策）"""
    disaster_type: str            # 灾害类型
    severity: str                 # 严重程度
    urgency_level: str            # 紧急程度: critical/high/medium/low
    affected_roads: List[str]     # 受影响道路
    blocked_areas: List[str]      # 封锁区域
    weather_conditions: str       # 天气状况
    time_of_day: str              # 时间段: day/night


class ScenarioAnalysis(TypedDict):
    """LLM场景分析结果"""
    urgency_assessment: str       # 紧急程度评估
    key_risks: List[str]          # 关键风险点
    recommended_strategy: str     # 推荐策略
    strategy_reason: str          # 策略选择理由
    special_considerations: List[str]  # 特殊注意事项


class StrategySelection(TypedDict):
    """LLM策略选择结果"""
    primary_strategy: str         # 主要策略
    optimization_weights: Dict[str, float]  # 优化权重
    algorithm_params: Dict[str, Any]        # 算法参数调整
    fallback_strategy: Optional[str]        # 备选策略


class RouteSegment(TypedDict):
    """路径分段信息"""
    segment_id: str               # 分段ID
    from_point: Point             # 起点
    to_point: Point               # 终点
    distance_m: float             # 距离（米）
    duration_seconds: float       # 耗时（秒）
    road_type: str                # 道路类型
    terrain_type: str             # 地形类型
    risk_level: str               # 风险等级


class SingleRouteResult(TypedDict):
    """单条路径结果"""
    route_id: str                 # 路径ID
    vehicle_id: str               # 车辆ID
    path_points: List[Point]      # 路径点序列
    segments: List[RouteSegment]  # 分段详情
    total_distance_m: float       # 总距离
    total_duration_seconds: float # 总耗时
    risk_score: float             # 风险评分 0-1
    warnings: List[str]           # 警告信息


class MultiVehicleRouteResult(TypedDict):
    """多车辆路径结果"""
    solution_id: str              # 方案ID
    routes: List[SingleRouteResult]  # 各车辆路径
    total_distance_m: float       # 总行驶距离
    total_duration_seconds: float # 最大完成时间
    served_tasks: int             # 服务任务数
    total_tasks: int              # 总任务数
    coverage_rate: float          # 覆盖率


class RouteEvaluation(TypedDict):
    """LLM路径评估结果"""
    meets_requirements: bool      # 是否满足需求
    evaluation_summary: str       # 评估摘要
    strengths: List[str]          # 优点
    weaknesses: List[str]         # 不足
    improvement_suggestions: List[str]  # 改进建议
    should_replan: bool           # 是否需要重新规划
    replan_reason: Optional[str]  # 重规划原因


class RouteExplanation(TypedDict):
    """LLM路径解释"""
    summary: str                  # 路径摘要（给指挥员）
    route_description: str        # 路线描述
    key_waypoints: List[str]      # 关键途经点说明
    risk_warnings: List[str]      # 风险提醒
    time_estimate: str            # 时间估计说明
    alternative_options: List[str]  # 备选方案说明
    commander_notes: str          # 指挥员注意事项


class RoutePlanningState(TypedDict):
    """
    路径规划智能体状态
    
    双频架构：
    - 高频层：纯算法计算（A*/VRP）
    - 低频层：LLM决策（场景分析、策略选择、结果评估）
    """
    # ========== 输入参数 ==========
    request_id: str                                         # 请求ID
    request_type: Literal["single", "multi", "replan"]      # 规划类型
    
    # 单车规划参数
    start: Optional[Point]                                  # 起点
    end: Optional[Point]                                    # 终点
    vehicle_id: Optional[str]                               # 车辆ID
    
    # 多车规划参数
    vehicles: List[VehicleInfo]                             # 车辆列表
    task_points: List[TaskPoint]                            # 任务点列表
    depot_location: Optional[Point]                         # 车辆基地位置
    
    # 通用参数
    scenario_id: Optional[str]                              # 想定ID（用于灾害区域）
    constraints: RouteConstraint                            # 约束条件
    disaster_context: Optional[DisasterContext]             # 灾情上下文
    natural_language_request: Optional[str]                 # 自然语言请求
    
    # ========== LLM对话历史 ==========
    messages: Annotated[List[BaseMessage], add_messages]    # 消息历史
    
    # ========== 阶段1: 场景分析 (LLM) ==========
    scenario_analysis: Optional[ScenarioAnalysis]           # 场景分析结果
    
    # ========== 阶段2: 策略选择 (LLM) ==========
    strategy_selection: Optional[StrategySelection]         # 策略选择结果
    current_strategy: str                                   # 当前使用的策略
    
    # ========== 阶段3: 路径计算 (算法) ==========
    algorithm_used: str                                     # 使用的算法
    route_result: Optional[SingleRouteResult]               # 单车路径结果
    multi_route_result: Optional[MultiVehicleRouteResult]   # 多车路径结果
    computation_time_ms: int                                # 计算耗时
    
    # ========== 阶段4: 结果评估 (LLM) ==========
    route_evaluation: Optional[RouteEvaluation]             # 路径评估结果
    replan_count: int                                       # 重规划次数
    max_replan_attempts: int                                # 最大重规划次数
    
    # ========== 阶段5: 路径解释 (LLM) ==========
    route_explanation: Optional[RouteExplanation]           # 路径解释
    
    # ========== 最终输出 ==========
    final_output: Dict[str, Any]                            # 最终输出
    success: bool                                           # 是否成功
    
    # ========== 追踪信息 ==========
    trace: Dict[str, Any]                                   # 执行追踪
    errors: List[str]                                       # 错误列表
    current_phase: str                                      # 当前阶段
    execution_time_ms: int                                  # 总执行耗时


def create_initial_state(
    request_id: str,
    request_type: Literal["single", "multi", "replan"],
    start: Optional[Point] = None,
    end: Optional[Point] = None,
    vehicle_id: Optional[str] = None,
    vehicles: Optional[List[VehicleInfo]] = None,
    task_points: Optional[List[TaskPoint]] = None,
    depot_location: Optional[Point] = None,
    scenario_id: Optional[str] = None,
    constraints: Optional[RouteConstraint] = None,
    disaster_context: Optional[DisasterContext] = None,
    natural_language_request: Optional[str] = None,
) -> RoutePlanningState:
    """
    创建初始状态
    
    Args:
        request_id: 请求唯一标识
        request_type: 规划类型 single/multi/replan
        start: 起点坐标（单车规划必填）
        end: 终点坐标（单车规划必填）
        vehicle_id: 车辆ID（单车规划必填）
        vehicles: 车辆列表（多车规划必填）
        task_points: 任务点列表（多车规划必填）
        depot_location: 车辆基地位置
        scenario_id: 想定ID
        constraints: 约束条件
        disaster_context: 灾情上下文
        natural_language_request: 自然语言请求
        
    Returns:
        初始化的RoutePlanningState
    """
    return RoutePlanningState(
        request_id=request_id,
        request_type=request_type,
        start=start,
        end=end,
        vehicle_id=vehicle_id,
        vehicles=vehicles or [],
        task_points=task_points or [],
        depot_location=depot_location,
        scenario_id=scenario_id,
        constraints=constraints or {},
        disaster_context=disaster_context,
        natural_language_request=natural_language_request,
        messages=[],
        scenario_analysis=None,
        strategy_selection=None,
        current_strategy=PlanningStrategy.BALANCED.value,
        algorithm_used="",
        route_result=None,
        multi_route_result=None,
        computation_time_ms=0,
        route_evaluation=None,
        replan_count=0,
        max_replan_attempts=3,
        route_explanation=None,
        final_output={},
        success=False,
        trace={
            "phases_executed": [],
            "llm_calls": 0,
            "algorithm_calls": 0,
            "replan_history": [],
        },
        errors=[],
        current_phase="init",
        execution_time_ms=0,
    )
