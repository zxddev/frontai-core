# Emergency AI Spec Delta

## ADDED Requirements

### Requirement: Task Decomposition

系统 SHALL 在规则匹配后执行任务分解，根据知识图谱中的任务依赖关系（`DEPENDS_ON`）生成正确的执行顺序。

#### Scenario: 拓扑排序生成任务序列
- **GIVEN** 规则匹配产出任务列表 `[MEDICAL_EMERGENCY, SEARCH_RESCUE]`
- **AND** 知识图谱定义 `MEDICAL_EMERGENCY -[:DEPENDS_ON]-> SEARCH_RESCUE`
- **WHEN** 执行 `decompose_tasks` 节点
- **THEN** 输出 `task_sequence` 为 `[SEARCH_RESCUE, MEDICAL_EMERGENCY]`
- **AND** `SEARCH_RESCUE.sequence = 1`
- **AND** `MEDICAL_EMERGENCY.sequence = 2`

#### Scenario: 严格依赖验证失败
- **GIVEN** 任务列表包含 `SHELTER_SETUP` 但不包含 `EVACUATION`
- **AND** 知识图谱定义 `SHELTER_SETUP -[:DEPENDS_ON {is_strict: true}]-> EVACUATION`
- **WHEN** 执行 `decompose_tasks` 节点
- **THEN** `dependency_violations` 包含 `"严格依赖未满足: SHELTER_SETUP 依赖 EVACUATION"`
- **AND** 流程继续但方案标记为高风险

#### Scenario: 非严格依赖记录警告
- **GIVEN** 任务列表包含 `SEARCH_RESCUE` 但不包含 `ROAD_CLEARANCE`
- **AND** 知识图谱定义 `SEARCH_RESCUE -[:DEPENDS_ON {is_strict: false}]-> ROAD_CLEARANCE`
- **WHEN** 执行 `decompose_tasks` 节点
- **THEN** 流程正常继续
- **AND** `trace.warnings` 包含依赖未满足的警告信息

### Requirement: NSGA-II Multi-Objective Optimization

系统 SHALL 使用 NSGA-II 算法进行多目标优化，生成帕累托最优解集。

#### Scenario: NSGA-II生成帕累托前沿
- **GIVEN** 资源候选列表包含100支队伍
- **AND** 优化目标为响应时间、覆盖率、成本、风险
- **WHEN** 执行 `optimize_allocation` 节点
- **THEN** `pareto_solutions` 包含多个非支配解
- **AND** 每个解在不同目标之间有权衡

#### Scenario: NSGA-II失败不降级
- **GIVEN** NSGA-II优化过程发生异常
- **WHEN** 执行 `optimize_allocation` 节点
- **THEN** 直接抛出 `RuntimeError`
- **AND** 不使用降级方案
- **AND** 错误信息记录到日志

#### Scenario: 大规模场景超时配置
- **GIVEN** 大型灾害场景，队伍数量>200
- **WHEN** 执行 `optimize_allocation` 节点
- **THEN** 优化超时时间为60秒
- **AND** 超时后抛出 `TimeoutError`

### Requirement: Dynamic Team Limit

系统 SHALL 支持动态配置队伍查询数量上限，以支持大规模救援场景。

#### Scenario: 默认查询限制
- **GIVEN** 请求未指定 `constraints.max_teams`
- **WHEN** 执行 `match_resources` 节点
- **THEN** SQL查询使用 `LIMIT 200`

#### Scenario: 自定义查询限制
- **GIVEN** 请求指定 `constraints.max_teams = 500`
- **WHEN** 执行 `match_resources` 节点
- **THEN** SQL查询使用 `LIMIT 500`

#### Scenario: 大规模场景支持
- **GIVEN** 大型地震场景，预估需要300支队伍
- **AND** 请求指定 `constraints.max_teams = 400`
- **WHEN** 执行 `match_resources` 节点
- **THEN** 查询返回最多400支队伍
- **AND** NSGA-II在更大解空间中优化

### Requirement: Five-Dimensional Evaluation

系统 SHALL 使用5维评估体系对救援方案进行综合评分。

#### Scenario: 5维评分计算
- **GIVEN** 候选方案具备以下指标：
  - 响应时间: 30分钟
  - 能力覆盖: 90%
  - 成本估算: 20000元
  - 风险等级: 10%
  - 相似案例成功率: 85%
  - 备用资源覆盖: 2个/3个能力
- **WHEN** 执行 `score_soft_rules` 节点
- **THEN** `soft_rule_scores` 包含:
  - `success_rate`: 基于案例相似度和能力匹配的评分
  - `response_time`: 时间效用评分
  - `coverage_rate`: 覆盖率评分
  - `risk`: 风险评分
  - `redundancy`: 冗余性评分
- **AND** `weighted_score` 为5维加权总分

#### Scenario: 自定义权重生效
- **GIVEN** 请求包含 `optimization_weights = {"success_rate": 0.4, "response_time": 0.2, ...}`
- **WHEN** 执行 `score_soft_rules` 节点
- **THEN** 评分使用用户指定的权重
- **AND** 权重总和归一化为1.0

### Requirement: Task Sequence Output

系统 SHALL 在分析结果中输出任务执行序列。

#### Scenario: 输出包含任务序列
- **GIVEN** 任务分解完成，生成 `task_sequence`
- **WHEN** 执行 `generate_output` 节点
- **THEN** `reasoning.task_sequence` 包含排序后的任务列表
- **AND** 每个任务包含 `task_code`, `sequence`, `golden_hour`, `depends_on`

#### Scenario: 输出包含依赖分析
- **GIVEN** 任务分解发现依赖违规
- **WHEN** 执行 `generate_output` 节点
- **THEN** `reasoning.dependency_analysis` 包含:
  - `all_satisfied`: false
  - `violations`: 违规列表
  - `warnings`: 警告列表

## MODIFIED Requirements

### Requirement: Graph Flow

系统 SHALL 在规则推理后执行任务分解节点，并使用NSGA-II进行优化。

修改后的流程：
```
START
  → understand_disaster → enhance_with_cases
  → query_rules → apply_rules → decompose_tasks  [新增]
  → match_resources → optimize_allocation [NSGA-II]
  → filter_hard_rules → score_soft_rules [5维评估]
  → explain_scheme → generate_output
  → END
```

#### Scenario: 任务分解后继续资源匹配
- **GIVEN** `apply_rules` 完成，产出 `matched_rules` 和 `task_requirements`
- **WHEN** 进入 `decompose_tasks` 节点
- **THEN** 生成 `task_sequence`
- **AND** 流程继续到 `match_resources`

#### Scenario: 无任务时跳过分解
- **GIVEN** `apply_rules` 完成但 `task_requirements` 为空
- **WHEN** 评估条件边
- **THEN** 跳转到 `generate_output`
- **AND** 不执行 `decompose_tasks`

### Requirement: Resource Matching Query

系统 SHALL 使用动态LIMIT进行队伍查询，替代硬编码的LIMIT 50。

#### Scenario: 查询使用动态限制
- **GIVEN** 约束条件 `constraints = {"max_teams": 300}`
- **WHEN** 执行 `match_resources` 节点
- **THEN** SQL查询为 `... LIMIT 300`
- **AND** 候选资源可包含最多300支队伍
