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
    magnitude: Optional[float]            # 震级（地震专用，如6.5）
    has_building_collapse: bool           # 是否有建筑倒塌
    has_trapped_persons: bool             # 是否有被困人员
    estimated_trapped: int                # 预估被困人数
    has_secondary_fire: bool              # 是否有次生火灾
    has_hazmat_leak: bool                 # 是否有危化品泄漏
    has_road_damage: bool                 # 是否有道路损毁
    affected_population: int              # 受影响人口
    affected_area_km2: Optional[float]    # 受影响面积(km2)
    disaster_level: Optional[str]         # 灾情等级(I-IV)
    building_damage_level: str            # 建筑损坏等级
    estimated_casualties: Optional[Dict[str, int]] # 预估伤亡
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
    rescue_capacity: int                  # 救援容量（72小时内可救援人数）


class AllocationSolution(TypedDict):
    """
    资源分配方案
    
    对齐参考系统的杀伤链路径概念，包含：
    1. allocations: 资源列表（向后兼容）
    2. task_assignments: 任务-资源分配序列（新增，核心字段）
    3. execution_path: 完整执行路径字符串，如 "探测(队A)→支撑(队B)→救治(队C)"
    """
    solution_id: str                      # 方案ID
    allocations: List[Dict[str, Any]]     # 分配详情（向后兼容）
    task_assignments: List[Dict[str, Any]]  # 【新增】任务-资源分配序列
    execution_path: str                   # 【新增】执行路径字符串，如 "探测(队A)→支撑(队B)"
    total_score: float                    # 总分
    response_time_min: float              # 预计响应时间(分钟)
    coverage_rate: float                  # 能力覆盖率
    resource_scale: int                   # 资源调动规模（队伍数），仅供参考不参与评分
    risk_level: float                     # 风险等级
    total_rescue_capacity: int            # 总救援容量（所有队伍容量之和）
    capacity_coverage_rate: float         # 容量覆盖率（总容量/被困人数）
    capacity_warning: Optional[str]       # 容量不足警告（覆盖率<80%时生成）


class SchemeScore(TypedDict):
    """方案评分"""
    scheme_id: str                        # 方案ID
    hard_rule_passed: bool                # 是否通过硬规则
    hard_rule_violations: List[str]       # 违反的硬规则
    soft_rule_scores: Dict[str, float]    # 软规则各维度得分
    weighted_score: float                 # 加权总分
    rank: int                             # 排名


# ============================================================================
# 战略层相关类型定义
# ============================================================================

class TaskDomainInfo(TypedDict):
    """任务域信息"""
    domain_id: str                        # 任务域ID: life_rescue/evacuation/engineering/logistics/hazard_control
    name: str                             # 任务域名称
    priority: int                         # 当前阶段的优先级
    description: str                      # 描述


class RecommendedModule(TypedDict):
    """推荐的预编组模块"""
    module_id: str                        # 模块ID
    module_name: str                      # 模块名称
    personnel: int                        # 人员数量
    dogs: int                             # 搜救犬数量
    vehicles: int                         # 车辆数量
    provided_capabilities: List[str]      # 提供的能力列表
    match_score: float                    # 能力匹配分数
    equipment_list: List[Dict[str, Any]]  # 装备清单


class TransportPlan(TypedDict):
    """运力规划"""
    transport_type: str                   # 运输方式
    capacity: int                         # 运力
    required: int                         # 需求
    gap: int                              # 缺口
    eta_hours: float                      # 预计到达时间(小时)


class SafetyViolation(TypedDict):
    """安全规则违反"""
    rule_id: str                          # 规则ID
    rule_type: str                        # 规则类型: hard/soft
    action: str                           # 动作: block/warn
    message: str                          # 提示信息
    matched_condition: Dict[str, Any]     # 匹配的条件


# ============================================================================
# HTN任务分解相关类型定义
# ============================================================================

class MetaTask(TypedDict):
    """
    元任务定义
    
    对应mt_library.json中的EM01-EM32元任务。
    """
    id: str                               # 任务ID，如EM01
    name: str                             # 任务名称，如"无人机广域侦察"
    category: str                         # 任务类别，如sensing/assessment/search_rescue
    precondition: str                     # 前置条件描述
    effect: str                           # 执行效果描述
    outputs: List[str]                    # 输出产物列表
    typical_scenes: List[str]             # 适用场景列表，如["S1", "S2"]
    phase: str                            # 所属阶段，如detect/assess/plan/execute
    duration_range: Dict[str, int]        # 时长范围，{min: 10, max: 30}分钟
    required_capabilities: List[str]      # 所需能力列表
    risk_level: str                       # 风险等级，low/medium/high


class TaskSequenceItem(TypedDict):
    """
    任务序列项
    
    拓扑排序后的任务执行序列中的单个任务。
    """
    task_id: str                          # 任务ID，如EM06
    task_name: str                        # 任务名称
    sequence: int                         # 执行顺序，从1开始
    depends_on: List[str]                 # 依赖的任务ID列表
    golden_hour: Optional[int]            # 黄金救援时间窗口（分钟），来自Neo4j
    phase: str                            # 所属阶段
    is_parallel: bool                     # 是否可并行执行
    parallel_group_id: Optional[str]      # 并行组ID，同组任务可并行
    required_capabilities: List[str]      # 所需能力列表，来自Neo4j MetaTask节点


class ParallelTaskGroup(TypedDict):
    """
    并行任务组
    
    可同时执行的任务集合，来自mt_library.json的parallel_groups。
    """
    group_id: str                         # 并行组ID
    task_ids: List[str]                   # 组内任务ID列表
    reason: str                           # 可并行的原因


# ============================================================================
# 任务-资源分配相关类型定义（对齐杀伤链路径概念）
# ============================================================================

class TaskResourceAssignment(TypedDict):
    """
    任务-资源分配
    
    对应参考系统的杀伤链路径中的单个环节：
    例如 "诱敌开机(UCAV-F_6)" 表示任务"诱敌开机"由资源"UCAV-F_6"执行
    
    在救援系统中，例如：
    "生命探测(搜救队A)" 表示任务"生命探测"由"搜救队A"执行
    """
    task_id: str                          # HTN任务ID (如 EM006)
    task_name: str                        # 任务名称 (如 "生命探测")
    resource_id: str                      # 执行资源ID (如 team_uuid)
    resource_name: str                    # 执行资源名称 (如 "消防搜救一队")
    resource_type: str                    # 资源类型 (如 "FIRE_TEAM")
    execution_sequence: int               # 执行顺序 (从1开始)
    phase: str                            # 任务阶段 (detect/assess/execute等)
    eta_minutes: float                    # 预计到达/执行时间(分钟)
    match_score: float                    # 任务-资源匹配分数 (0-1)
    match_reason: str                     # 匹配原因说明


class ExecutionPath(TypedDict):
    """
    执行路径（对应参考系统的杀伤链路径）
    
    参考系统的路径示例：
    S1-P4: 诱敌开机(UCAV-F_6) → 无源定位(J-35_4) → 稳定跟踪(UCAV-F_6)
    
    救援系统的路径示例：
    P1: 生命探测(搜救队A) → 结构支撑(工程队B) → 伤员救治(医疗队C) → 安全转运(救护队D)
    """
    path_id: str                          # 路径ID (如 "P1", "P2")
    scene_code: str                       # 所属场景 (如 "S1")
    assignments: List[TaskResourceAssignment]  # 任务-资源分配序列
    total_duration_min: float             # 总执行时间(分钟)
    # 5维评估得分
    success_rate: float                   # 成功率效用 (0-1)
    time_utility: float                   # 时间效用 (0-1)
    cost_utility: float                   # 成本效用 (0-1)
    risk_utility: float                   # 风险效用 (0-1)
    redundancy_utility: float             # 冗余效用 (0-1)
    composite_score: float                # 综合得分 (加权计算)
    selection_reason: str                 # 选择理由


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
    _kg_rules: List[Dict[str, Any]]                         # KG查询的原始TRR规则（中间状态）
    matched_rules: List[MatchedTRRRule]                     # 匹配的TRR规则
    task_requirements: List[Dict[str, Any]]                 # 任务需求列表
    capability_requirements: List[CapabilityRequirement]    # 能力需求列表
    
    # ========== 阶段2.5: HTN任务分解 ==========
    scene_codes: List[str]                                  # 识别的场景代码，如["S1", "S2"]
    task_sequence: List[TaskSequenceItem]                   # 拓扑排序后的任务执行序列
    parallel_tasks: List[ParallelTaskGroup]                 # 可并行执行的任务组
    
    # ========== 阶段2.6: 战略层 - 任务域/阶段/模块 ==========
    active_domains: List[str]                               # 激活的任务域ID列表
    domain_priorities: List[TaskDomainInfo]                 # 任务域优先级（按当前阶段排序）
    disaster_phase: str                                     # 当前灾害阶段: initial/golden/intensive/recovery
    disaster_phase_name: str                                # 阶段名称
    recommended_modules: List[RecommendedModule]            # 推荐的预编组模块
    
    # ========== 阶段2.7: 战略层 - 运力/安全/报告 ==========
    transport_plans: List[TransportPlan]                    # 运力规划列表
    transport_warnings: List[str]                           # 运力警告
    safety_violations: List[SafetyViolation]                # 安全规则违反列表
    generated_reports: Dict[str, str]                       # 生成的报告 {"initial": "...", "daily": "..."}
    
    # ========== 阶段3: 资源匹配 ==========
    resource_candidates: List[ResourceCandidate]            # 候选资源
    allocation_solutions: List[AllocationSolution]          # 分配方案
    pareto_solutions: List[AllocationSolution]              # Pareto最优解
    equipment_allocations: List[Dict[str, Any]]             # 装备分配（人装物：装）
    supply_requirements: List[Dict[str, Any]]               # 物资需求（人装物：物）
    
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
    # 默认优化权重（5维评估，严格对齐军事版）
    default_weights: Dict[str, float] = {
        "success_rate": 0.35,     # 人命关天，最高权重
        "response_time": 0.30,    # 黄金救援期72小时
        "coverage_rate": 0.20,    # 全区域覆盖
        "risk": 0.05,             # 生命优先于风险规避
        "redundancy": 0.10,       # 备用资源保障
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
        _kg_rules=[],
        matched_rules=[],
        task_requirements=[],
        capability_requirements=[],
        scene_codes=[],
        task_sequence=[],
        parallel_tasks=[],
        # 战略层字段初始化
        active_domains=[],
        domain_priorities=[],
        disaster_phase="",
        disaster_phase_name="",
        recommended_modules=[],
        transport_plans=[],
        transport_warnings=[],
        safety_violations=[],
        generated_reports={},
        # 资源匹配
        resource_candidates=[],
        allocation_solutions=[],
        pareto_solutions=[],
        equipment_allocations=[],
        supply_requirements=[],
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
