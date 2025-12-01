## ADDED Requirements

### Requirement: Multi-Event Frontline Rescue Prioritization
系统 SHALL 支持在同一想定下对多个 `confirmed` 且尚未关联任务的事件进行统一优先级排序，并为指挥员展示每个事件的关键评分维度。

#### Scenario: Prioritize multiple concurrent events
- **WHEN** 想定下存在 2 个及以上状态为 `confirmed` 且未关联执行任务的事件
- **AND** 系统成功从数据库 `config.algorithm_parameters` 中加载 `category='scoring', code='SCORING_FRONTLINE_EVENT_V1'` 的打分规则
- **THEN** 系统 SHALL 为每个事件计算 0~1 之间的综合得分，依据得分高低给出 `critical/high/medium/low` 等优先级
- **AND** 系统 SHALL 在前端展示各事件的生命威胁、时间紧迫、受影响人数、成功概率等维度贡献

### Requirement: Global Resource Allocation With Safety Constraints
系统 SHALL 在多事件场景下对救援队伍进行全局互斥分配，并严格遵守来自数据库配置的覆盖率与响应时间等安全阈值。

#### Scenario: Allocate teams under DB-backed constraints
- **WHEN** 系统已加载所有可用且状态为 `standby` 的救援队伍及其能力、位置
- **AND** 系统已从 `config.algorithm_parameters` 中加载 `code='FRONTLINE_ALLOCATION_CONSTRAINTS_V1'` 的约束配置
- **THEN** 系统 SHALL 在一次优化过程中，为每支队伍分配至最多一个事件（或保持未分配）
- **AND** 系统 SHALL 确保每个事件的能力覆盖率不低于配置中的 `min_coverage_rate`（否则标记为资源缺口）
- **AND** 系统 SHALL 确保分配方案中所有队伍的预计响应时间不超过 `max_response_time_minutes`（否则该方案被视为不满足硬约束）

### Requirement: DB-Backed Scoring and Hard Rules Only (No Hardcoded Thresholds)
所有 Frontline 决策相关的权重、阈值、优先级区间及硬规则 MUST 完全来自数据库配置，不允许在业务代码中写死关键数值或规则逻辑。

#### Scenario: Missing DB configuration must fail fast
- **WHEN** FrontlineRescueAgent 在任意阶段需要加载 `SCORING_FRONTLINE_EVENT_V1`、`FRONTLINE_ALLOCATION_CONSTRAINTS_V1` 或 `HARD_RULES_FRONTLINE_V1` 等配置
- **AND** AlgorithmConfigService 报告配置不存在或解析失败
- **THEN** 系统 MUST 立即终止本次调度流程，并返回明确的错误给调用方（包括缺失的 category/code）
- **AND** 系统 MUST 不得回退到任何硬编码默认阈值或简化规则

### Requirement: Human-in-the-Loop Approval for Dispatch Plans
系统 MUST 在生成 Frontline 救援行动方案后暂停执行，等待指挥员审核和确认，禁止在无人审核的情况下自动下发执行任务。

#### Scenario: Commander reviews and adjusts suggested allocation
- **WHEN** FrontlineRescueAgent 已根据规则生成一份或多份候选多事件调度方案
- **THEN** 系统 SHALL 通过前端展示：按优先级排序的事件列表、推荐队伍及 ETA/能力匹配度、硬规则警告与资源缺口提示
- **AND** 指挥员 SHALL 能够选择/取消队伍、调整事件优先级、拒绝整个方案
- **AND** 只有当指挥员显式确认方案后，系统才可以创建对应执行任务并更新事件/队伍状态

### Requirement: Audit Logging of Critical Decisions
系统 SHALL 为多事件优先级、队伍分配、硬规则判定和人审修改等关键步骤记录可追踪的审计日志，用于事后复盘和责任认定。

#### Scenario: Log key decisions and rule triggers
- **WHEN** FrontlineRescueAgent 完成一次多事件调度流程（无论成功或失败）
- **THEN** 系统 SHALL 在审计日志中记录本次流程的唯一标识、输入事件与队伍集合、所用规则版本（scoring/constraints/hard_rules 的 code/version）
- **AND** 系统 SHALL 记录最终采用的调度方案、被触发的硬规则 ID、指挥员的主要修改操作与最终决策结果
