# emergency-ai Spec Delta

## MODIFIED Requirements

### Requirement: 资源分配必须考虑救援容量

系统在分配救援资源时，MUST根据被困人数计算最低救援容量需求，不能仅依赖能力覆盖率作为终止条件。

#### Scenario: 大规模地震救援（3000人被困）
- Given 四川茂县6.8级地震，3000人被困，9支可用队伍
- When 系统执行资源分配
- Then 系统应使用所有可用队伍（不是仅4支）
- And 输出应包含 `total_rescue_capacity` 字段
- And 输出应包含 `capacity_coverage_rate` 字段
- And 当容量覆盖率<80%时应包含明确警告

#### Scenario: 中等规模救援（200人被困）
- Given 地震场景，200人被困，9支可用队伍
- When 系统执行资源分配
- Then 系统应选择足够队伍使救援容量>=160人（80%覆盖率）
- And 不应在能力覆盖100%时就停止

### Requirement: 贪心算法终止条件必须包含容量检查

贪心算法不能仅在能力覆盖100%时就停止，MUST同时满足救援容量需求。

#### Scenario: 能力覆盖但容量不足
- Given 被困100人，4支队伍能力覆盖100%但总容量仅50人
- When 贪心算法执行
- Then 算法应继续添加队伍直到容量>=80人
- And 日志应记录"能力已覆盖但容量不足，继续添加队伍"

### Requirement: SQL查询必须获取救援容量

数据库查询队伍时MUST获取 `team_capabilities_v2.max_capacity` 字段。

#### Scenario: 队伍查询包含救援容量
- Given 数据库中队伍配置了 max_capacity
- When 系统查询候选队伍
- Then 每支队伍应包含 `rescue_capacity` 字段
- And 当 max_capacity 为空时应使用估算值

### Requirement: 容量不足必须生成警告

当救援容量覆盖率低于80%时，系统MUST在输出中生成明确警告。

#### Scenario: 资源严重不足警告
- Given 被困3000人，可用队伍总容量仅240人
- When 系统生成方案
- Then 方案应包含 `capacity_warning` 字段
- And 警告应包含"救援容量严重不足"
- And 警告应建议"紧急请求省级/国家级增援"

## ADDED Requirements

### Requirement: 救援容量硬规则检查

系统MUST新增硬规则：救援容量覆盖率必须>=50%，否则方案标记为违规。

#### Scenario: 容量硬规则检查
- Given 被困1000人，方案总容量400人（覆盖率40%）
- When 硬规则检查执行
- Then 方案应被标记为 violation
- And violation 描述应为"救援容量覆盖率不足50%"

### Requirement: NSGA-II优化目标包含容量最大化

NSGA-II多目标优化MUST将"最大化救援容量覆盖率"作为优化目标之一。

#### Scenario: NSGA-II目标函数
- Given 启用NSGA-II优化（候选资源>10）
- When 优化执行
- Then 目标函数应包含"最大化救援容量覆盖率"
- And 约束条件应包含"容量覆盖率>=50%"
- And 不应包含"最小化队伍数量"作为优化目标
