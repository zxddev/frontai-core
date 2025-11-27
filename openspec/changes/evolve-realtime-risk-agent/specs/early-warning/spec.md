## MODIFIED Requirements

### Requirement: 预警监测智能体

系统SHALL提供RealTimeRiskAgent（实时风险智能体），整合灾害预警和风险预测能力。

#### Scenario: 灾害态势监测（原有功能）
- **WHEN** 系统接收到灾害数据更新
- **THEN** 分析影响范围内的队伍和车辆
- **AND** 生成预警记录并通过WebSocket推送

#### Scenario: 路径风险预测（新增）
- **WHEN** 队伍正在行进中
- **AND** 请求路径风险评估
- **THEN** 系统分析气象、地形、历史数据
- **AND** 返回风险等级（红/橙/黄/蓝）和置信度
- **AND** 生成规避建议

#### Scenario: 作业风险评估（新增）
- **WHEN** 队伍在现场执行救援作业
- **AND** 请求作业风险评估
- **THEN** 系统分析建筑结构、危化品、环境风险
- **AND** 返回风险等级和安全建议

#### Scenario: 灾害扩散预测（新增）
- **WHEN** 灾害正在发展
- **AND** 请求扩散预测
- **THEN** 系统预测1h/6h/24h影响范围
- **AND** 返回扩散概率和影响区域

## ADDED Requirements

### Requirement: 风险预测数据持久化

系统SHALL将所有风险预测记录持久化到数据库。

#### Scenario: 预测记录存储
- **WHEN** 完成一次风险预测
- **THEN** 记录存储到risk_predictions表
- **AND** 包含输入数据、预测结果、置信度、解释

#### Scenario: 预测记录查询
- **WHEN** 用户查询历史预测
- **THEN** 支持按scenario_id、target_id、risk_level过滤

### Requirement: Human-in-the-Loop风险确认

系统SHALL对红色风险实施人工确认机制。

#### Scenario: 红色风险人工审核
- **WHEN** 预测结果为红色风险
- **THEN** 系统设置requires_human_review=True
- **AND** 通过interrupt机制暂停流程
- **AND** 等待人工确认后继续

#### Scenario: 人工审核决策
- **WHEN** 人工审核红色风险
- **THEN** 支持approve/reject/modified决策
- **AND** 记录审核人、审核时间、审核备注

### Requirement: 预测可解释性

系统SHALL为所有预测提供可解释的推理过程。

#### Scenario: 风险因素解释
- **WHEN** 返回风险预测结果
- **THEN** 包含risk_factors列表（具体风险因素）
- **AND** 包含explanation文本（LLM生成的解释）
- **AND** 包含confidence_score（0-1置信度）

### Requirement: 与RoutePlanningAgent协同

系统SHALL与RoutePlanningAgent协同生成规避建议。

#### Scenario: 规避路线生成
- **WHEN** 路径风险预测结果为橙色或红色
- **THEN** 调用RoutePlanningAgent生成规避路线
- **AND** 规避路线避开高风险区域
- **AND** 返回多条备选路线

### Requirement: 多时间尺度预测

系统SHALL支持多时间尺度的风险预测。

#### Scenario: 短期预测（1小时）
- **WHEN** 请求战术级预测
- **THEN** 返回1小时内的风险预测
- **AND** 用于行进/作业即时决策

#### Scenario: 中期预测（6小时）
- **WHEN** 请求战役级预测
- **THEN** 返回6小时内的风险预测
- **AND** 用于阶段性规划

#### Scenario: 长期预测（24小时）
- **WHEN** 请求战略级预测
- **THEN** 返回24小时内的风险预测
- **AND** 用于整体部署决策
