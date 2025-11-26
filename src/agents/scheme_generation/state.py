"""
方案生成Agent状态定义

使用TypedDict定义LangGraph状态
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class CapabilityRequirementState(TypedDict):
    """能力需求状态"""
    code: str                      # 能力代码
    priority: str                  # critical/high/medium/low
    min_quantity: int              # 最小数量
    source_rule_id: Optional[str]  # 来源规则ID


class ResourceCandidateState(TypedDict):
    """候选资源状态"""
    resource_id: str
    resource_name: str
    resource_type: str
    capabilities: List[str]
    match_score: float
    distance_km: float
    eta_minutes: int
    availability: float
    score_breakdown: Dict[str, float]


class ResourceAllocationState(TypedDict):
    """资源分配状态"""
    resource_id: str
    resource_name: str
    resource_type: str
    assigned_task_types: List[str]
    match_score: float
    recommendation_reason: str
    alternatives: List[Dict[str, Any]]


class MatchedRuleState(TypedDict):
    """匹配规则状态"""
    rule_id: str
    rule_name: str
    priority: str
    weight: float
    task_types: List[str]
    required_capabilities: List[Dict[str, Any]]
    resource_types: List[str]
    grouping_pattern: Optional[str]
    tactical_notes: Optional[str]


class ScenePriorityState(TypedDict):
    """场景优先级状态"""
    scene_id: str
    scene_name: str
    priority_score: float
    rank: int
    dimension_scores: Dict[str, float]


class ParetoSolutionState(TypedDict):
    """Pareto解状态"""
    solution_id: str
    variables: List[float]
    objectives: Dict[str, float]
    rank: int


class SchemeScoreState(TypedDict):
    """方案评分状态"""
    scheme_id: str
    total_score: float
    dimension_scores: Dict[str, float]
    rank: int


class HardRuleResultState(TypedDict):
    """硬规则检查结果状态"""
    rule_id: str
    rule_name: str
    passed: bool
    action: str  # reject/warn
    message: str
    severity: str


class SchemeOutputState(TypedDict):
    """方案输出状态"""
    scheme_id: str
    rank: int
    score: float
    confidence_score: float  # AI置信度评分 (0-1)
    tasks: List[Dict[str, Any]]
    resource_allocations: List[ResourceAllocationState]
    triggered_rules: List[MatchedRuleState]
    estimated_metrics: Dict[str, Any]
    rationale: str


class SchemeGenerationState(TypedDict):
    """
    方案生成Agent完整状态
    
    包含输入、中间结果、输出和追踪信息
    """
    # ========== 输入 ==========
    event_id: str
    scenario_id: str
    
    # 事件分析结果（来自EventAnalysisAgent）
    event_analysis: Dict[str, Any]
    
    # 约束条件
    constraints: Dict[str, Any]
    
    # 优化权重（可由用户传入覆盖默认值）
    optimization_weights: Dict[str, float]
    
    # 生成选项
    options: Dict[str, Any]
    
    # ========== 预查询数据（由外部提供，避免节点内异步查询） ==========
    available_teams: List[Dict[str, Any]]
    
    # ========== 规则触发结果 ==========
    matched_rules: List[MatchedRuleState]
    
    # ========== 能力需求 ==========
    capability_requirements: List[CapabilityRequirementState]
    
    # ========== 资源匹配结果 ==========
    resource_candidates: List[ResourceCandidateState]
    resource_allocations: List[ResourceAllocationState]
    
    # ========== 场景仲裁结果（多事件场景） ==========
    scene_priorities: List[ScenePriorityState]
    conflict_resolutions: List[Dict[str, Any]]
    
    # ========== 优化结果 ==========
    pareto_solutions: List[ParetoSolutionState]
    
    # ========== 过滤评分结果 ==========
    hard_rule_results: List[HardRuleResultState]
    feasible_schemes: List[Dict[str, Any]]
    scheme_scores: List[SchemeScoreState]
    recommended_scheme: Optional[SchemeOutputState]
    
    # ========== 输出 ==========
    schemes: List[SchemeOutputState]
    
    # ========== 追踪 ==========
    trace: Dict[str, Any]
    errors: List[str]
    
    # ========== 时间戳 ==========
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
