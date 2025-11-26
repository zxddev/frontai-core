# Capability: AI Agents Extended (军事版架构)

## Overview

扩展AI Agent模块，实现军事版架构的应急救灾版本，包括规则引擎、方案生成、任务调度。

## ADDED Requirements

### Requirement: TRR规则引擎

系统应提供TRR触发规则引擎，基于业务规则自动推断任务类型和能力需求。

#### Scenario: 地震场景触发搜救规则
- Given 事件类型为 "earthquake" 且 has_trapped = true
- When 调用 TRRRuleEngine.evaluate(context)
- Then 返回匹配的规则列表，包含 TRR-EM-001
- And 规则actions包含 task_types: [search_rescue, medical_emergency]
- And 规则actions包含 required_capabilities: [SEARCH_LIFE_DETECT, RESCUE_STRUCTURAL]

#### Scenario: 危化品场景触发专业处置规则
- Given 事件类型为 "hazmat" 且 has_leak = true
- When 调用 TRRRuleEngine.evaluate(context)
- Then 返回匹配的规则列表，包含 TRR-EM-010
- And 规则actions包含 required_capabilities: [HAZMAT_DETECT, HAZMAT_CONTAIN]

### Requirement: 方案生成Agent

系统应提供方案生成Agent，自动生成救援方案并进行多目标优化。

#### Scenario: 生成地震救援方案
- Given 事件分析结果（disaster_level=III, affected_population=1000）
- And 约束条件（max_response_time_min=30, max_teams=10）
- When 调用 POST /ai/generate-scheme
- Then 返回 status=processing 和 task_id
- And 完成后返回 schemes 列表，包含≥1个方案
- And 每个方案包含 tasks, resource_allocations, triggered_rules
- And 每个资源分配包含 match_score 和 full_recommendation_reason

#### Scenario: 多目标优化返回Pareto解集
- Given 方案生成请求 options.include_pareto = true
- When 方案生成完成
- Then 返回 pareto_solutions 列表
- And 每个解包含 objectives: {response_time, coverage, cost, risk}
- And 所有解满足Pareto非支配条件

#### Scenario: 硬规则过滤危险方案
- Given 候选方案中存在 rescue_risk > 0.10 的方案
- When 执行硬规则过滤
- Then 该方案被过滤
- And trace.hard_rules_checked 包含 HR-EM-001
- And 日志记录过滤原因

### Requirement: 任务调度Agent

系统应提供任务调度Agent，将方案分解为具体任务并规划执行路径。

#### Scenario: 任务拆解和依赖生成
- Given 方案包含 search_rescue 和 medical_treatment 任务类型
- When 调用 TaskDispatchAgent
- Then 生成任务列表
- And 任务依赖关系正确（medical_treatment depends_on search_rescue）

#### Scenario: VRP路径规划
- Given 任务列表和执行者位置
- When 调用 POST /ai/dispatch-tasks
- Then 返回 vrp_solution
- And 每个执行者有优化后的路线
- And 路线waypoints包含经纬度和预计时间

### Requirement: AI决策日志记录

系统应记录所有AI决策过程到ai_decision_logs_v2表。

#### Scenario: 方案生成决策日志
- Given 方案生成请求
- When 方案生成完成
- Then ai_decision_logs_v2表新增一条记录
- And decision_type = 'scheme_generation'
- And input_snapshot 包含完整输入
- And output_result 包含方案列表
- And reasoning_chain 包含规则匹配、优化过程

## MODIFIED Requirements

### Requirement: AI API路由扩展

扩展现有AI路由，添加方案生成和任务调度端点。

#### Scenario: 方案生成API
- Given 用户调用 POST /api/v2/ai/generate-scheme
- When 请求包含有效的 event_id 和 scenario_id
- Then 返回 task_id 和 status=processing
- And 可通过 GET /api/v2/ai/generate-scheme/{task_id} 查询结果

#### Scenario: 任务调度API
- Given 用户调用 POST /api/v2/ai/dispatch-tasks
- When 请求包含有效的 scheme_id
- Then 返回 task_id 和 status=processing
- And 可通过 GET /api/v2/ai/dispatch-tasks/{task_id} 查询结果

## Cross-References

- 依赖 `ai-agents` capability（EventAnalysisAgent）
- 使用 `planning/algorithms/matching/` 资源匹配算法
- 使用 `planning/algorithms/optimization/` 多目标优化算法
- 使用 `planning/algorithms/routing/` 路径规划算法
- 写入 `schemes_v2`, `scheme_resource_allocations_v2`, `ai_decision_logs_v2` 表
