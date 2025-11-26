"""
EmergencyAI状态定义

使用TypedDict定义强类型状态，支持LangGraph消息管理。
"""
from __future__ import annotations

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from uuid import UUID

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class ParsedDisasterInfo(TypedDict):
    """LLM解析的灾情结构化信息"""
    disaster_type: str                    # 灾害类型: earthquake/fire/hazmat等
    location: Dict[str, float]            # 位置: {longitude, latitude}
    severity: str                         # 严重程度: critical/high/medium/low
    has_building_collapse: bool           # 是否有建筑倒塌
    has_trapped_persons: bool             # 是否有被困人员
    estimated_trapped: int                # 预估被困人数
    has_secondary_fire: bool              # 是否有次生火灾
    has_hazmat_leak: bool                 # 是否有危化品泄漏
    has_road_damage: bool                 # 是否有道路损毁
    affected_population: int              # 受影响人口
    building_damage_level: str            # 建筑损坏等级
    additional_info: Dict[str, Any]       # 其他信息


class SimilarCase(TypedDict):
    """相似历史案例"""
    case_id: str                          # 案例ID
    title: str                            # 案例标题
    disaster_type: str                    # 灾害类型
    description: str                      # 案例描述
    lessons_learned: List[str]            # 经验教训
    best_practices: List[str]             # 最佳实践
    similarity_score: float               # 相似度分数


class MatchedTRRRule(TypedDict):
    """匹配的TRR规则"""
    rule_id: str                          # 规则ID
    rule_name: str                        # 规则名称
    disaster_type: str                    # 适用灾害类型
    priority: str                         # 优先级
    weight: float                         # 权重
    triggered_tasks: List[str]            # 触发的任务类型
    required_capabilities: List[str]      # 需要的能力
    match_reason: str                     # 匹配原因


class CapabilityRequirement(TypedDict):
    """能力需求"""
    capability_code: str                  # 能力编码
    capability_name: str                  # 能力名称
    priority: str                         # 优先级
    source_rule: str                      # 来源规则
    provided_by: List[str]                # 可提供该能力的资源类型


class ResourceCandidate(TypedDict):
    """候选资源"""
    resource_id: str                      # 资源ID
    resource_name: str                    # 资源名称
    resource_type: str                    # 资源类型
    capabilities: List[str]               # 具备的能力
    distance_km: float                    # 距离(km)
    availability_score: float             # 可用性评分
    match_score: float                    # 综合匹配分数


class AllocationSolution(TypedDict):
    """资源分配方案"""
    solution_id: str                      # 方案ID
    allocations: List[Dict[str, Any]]     # 分配详情
    total_score: float                    # 总分
    response_time_min: float              # 预计响应时间(分钟)
    coverage_rate: float                  # 能力覆盖率
    cost_estimate: float                  # 成本估算
    risk_level: float                     # 风险等级


class SchemeScore(TypedDict):
    """方案评分"""
    scheme_id: str                        # 方案ID
    hard_rule_passed: bool                # 是否通过硬规则
    hard_rule_violations: List[str]       # 违反的硬规则
    soft_rule_scores: Dict[str, float]    # 软规则各维度得分
    weighted_score: float                 # 加权总分
    rank: int                             # 排名


class EmergencyAIState(TypedDict):
    """
    应急AI混合系统状态
    
    包含4个阶段的中间结果和最终输出。
    """
    # ========== 输入 ==========
    event_id: str                                           # 事件ID
    scenario_id: str                                        # 想定ID
    disaster_description: str                               # 自然语言灾情描述
    structured_input: Dict[str, Any]                        # 结构化输入数据
    constraints: Dict[str, Any]                             # 约束条件
    optimization_weights: Dict[str, float]                  # 优化权重配置
    
    # ========== LLM对话历史 ==========
    messages: Annotated[List[BaseMessage], add_messages]    # 消息历史
    
    # ========== 阶段1: 灾情理解 ==========
    parsed_disaster: Optional[ParsedDisasterInfo]           # LLM解析结果
    similar_cases: List[SimilarCase]                        # RAG检索的相似案例
    understanding_summary: str                              # 理解总结
    
    # ========== 阶段2: 规则推理 ==========
    matched_rules: List[MatchedTRRRule]                     # 匹配的TRR规则
    task_requirements: List[Dict[str, Any]]                 # 任务需求列表
    capability_requirements: List[CapabilityRequirement]    # 能力需求列表
    
    # ========== 阶段3: 资源匹配 ==========
    resource_candidates: List[ResourceCandidate]            # 候选资源
    allocation_solutions: List[AllocationSolution]          # 分配方案
    pareto_solutions: List[AllocationSolution]              # Pareto最优解
    
    # ========== 阶段4: 方案优化 ==========
    scheme_scores: List[SchemeScore]                        # 方案评分
    recommended_scheme: Optional[AllocationSolution]        # 推荐方案
    scheme_explanation: str                                 # LLM生成的方案解释
    
    # ========== 最终输出 ==========
    final_output: Dict[str, Any]                            # 最终输出结果
    
    # ========== 追踪信息 ==========
    trace: Dict[str, Any]                                   # 执行追踪
    errors: List[str]                                       # 错误列表
    current_phase: str                                      # 当前阶段
    execution_time_ms: int                                  # 执行耗时


def create_initial_state(
    event_id: str,
    scenario_id: str,
    disaster_description: str,
    structured_input: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    optimization_weights: Optional[Dict[str, float]] = None,
) -> EmergencyAIState:
    """
    创建初始状态
    
    Args:
        event_id: 事件ID
        scenario_id: 想定ID
        disaster_description: 灾情描述
        structured_input: 结构化输入
        constraints: 约束条件
        optimization_weights: 优化权重
        
    Returns:
        初始化的EmergencyAIState
    """
    # 默认优化权重（地震场景）
    default_weights: Dict[str, float] = {
        "response_time": 0.40,
        "coverage_rate": 0.30,
        "cost": 0.10,
        "risk": 0.20,
    }
    
    return EmergencyAIState(
        event_id=event_id,
        scenario_id=scenario_id,
        disaster_description=disaster_description,
        structured_input=structured_input or {},
        constraints=constraints or {},
        optimization_weights=optimization_weights or default_weights,
        messages=[],
        parsed_disaster=None,
        similar_cases=[],
        understanding_summary="",
        matched_rules=[],
        task_requirements=[],
        capability_requirements=[],
        resource_candidates=[],
        allocation_solutions=[],
        pareto_solutions=[],
        scheme_scores=[],
        recommended_scheme=None,
        scheme_explanation="",
        final_output={},
        trace={
            "phases_executed": [],
            "llm_calls": 0,
            "rag_calls": 0,
            "kg_calls": 0,
            "algorithms_used": [],
        },
        errors=[],
        current_phase="init",
        execution_time_ms=0,
    )
