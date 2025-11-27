# Staging Area Spec Delta

## ADDED Requirements

### Requirement: Staging Area Agent

系统 SHALL 提供基于LangGraph的驻扎点选址智能体，支持多步分析推理和可解释输出。

#### Scenario: 自然语言灾情输入处理

- **GIVEN** 用户提供自然语言灾情描述"茂县叠溪镇发生7.0级地震，震源深度10公里，多处道路被滑坡阻断，目前有3个村庄失联"
- **AND** 队伍信息和救援目标列表
- **WHEN** 调用Agent进行驻扎点选址
- **THEN** Agent能够提取关键约束（震中位置、道路阻断风险）
- **AND** 返回带有解释的推荐结果

#### Scenario: 多维度分析流程

- **GIVEN** 灾情信息和候选驻扎点
- **WHEN** Agent执行分析流程
- **THEN** 依次完成地形分析、通信分析、安全分析
- **AND** 每个分析步骤产生可追溯的评估结果

#### Scenario: 风险警示输出

- **GIVEN** 某候选点位于潜在堰塞湖下游
- **WHEN** Agent完成安全分析
- **THEN** 必须生成风险警示"注意：该点位于潜在堰塞湖影响范围内"
- **AND** 提供备选方案

### Requirement: Agent降级机制

当LLM服务不可用或超时时，系统 SHALL 自动降级到纯算法服务。

#### Scenario: LLM超时降级

- **GIVEN** LLM服务响应超时（>30秒）
- **WHEN** Agent检测到超时
- **THEN** 自动调用StagingAreaCore纯算法服务
- **AND** 在响应中标注"降级模式：仅使用算法评分，无语义分析"

#### Scenario: LLM服务不可用

- **GIVEN** LLM服务返回错误
- **WHEN** Agent捕获错误
- **THEN** 降级到纯算法服务
- **AND** 记录降级事件到日志

### Requirement: 决策解释生成

Agent SHALL 为每个推荐生成可理解的决策解释。

#### Scenario: 推荐理由生成

- **GIVEN** 排序后的候选点列表
- **WHEN** Agent生成解释
- **THEN** 每个推荐点必须包含：
  - 推荐理由（为什么选择这个点）
  - 优势分析（地形/通信/安全的具体优势）
  - 潜在风险（需要注意的问题）
  - 置信度（0-1分数）

#### Scenario: 对比解释

- **GIVEN** 第一推荐点A和第二推荐点B
- **WHEN** 用户询问"为什么A比B更好"
- **THEN** Agent能够生成对比解释，说明A相对于B的具体优势

### Requirement: 地形分析节点

Agent SHALL 分析候选点的地形适宜性。

#### Scenario: 坡度评估

- **GIVEN** 候选点坡度数据
- **WHEN** 执行地形分析
- **THEN** 评估该坡度是否适合展开救援设备
- **AND** 生成地形评估报告

#### Scenario: 地质稳定性评估

- **GIVEN** 候选点地质数据和历史滑坡记录
- **WHEN** 执行地形分析
- **THEN** 评估地质稳定性风险
- **AND** 对高风险区域生成警告

### Requirement: 通信分析节点

Agent SHALL 分析候选点的通信可行性。

#### Scenario: 网络覆盖评估

- **GIVEN** 候选点位置和基站覆盖数据
- **WHEN** 执行通信分析
- **THEN** 评估移动网络覆盖质量
- **AND** 评估卫星通信可行性

#### Scenario: 通信冗余方案

- **GIVEN** 候选点网络覆盖不足
- **WHEN** 执行通信分析
- **THEN** 建议通信冗余方案（如应急通信车、卫星电话）

### Requirement: 安全分析节点

Agent SHALL 综合分析候选点的安全风险。

#### Scenario: 次生灾害风险评估

- **GIVEN** 候选点位置和次生灾害预测数据
- **WHEN** 执行安全分析
- **THEN** 评估滑坡、泥石流、堰塞湖等风险
- **AND** 生成安全等级（高/中/低）

#### Scenario: 余震影响评估

- **GIVEN** 震中位置和余震预测
- **WHEN** 执行安全分析
- **THEN** 评估余震对候选点的潜在影响
- **AND** 建议安全防护措施

## MODIFIED Requirements

### Requirement: 驻扎点推荐API

系统 SHALL 提供驻扎点推荐API，包括Agent入口和纯算法入口。

#### Scenario: Agent API调用

- **GIVEN** 用户需要智能分析的驻扎点推荐
- **WHEN** 调用 `POST /api/v2/ai/staging-area`
- **THEN** 使用LangGraph Agent进行多步分析
- **AND** 返回带解释的推荐结果

#### Scenario: 纯算法API调用（保留）

- **GIVEN** 用户需要快速的纯算法推荐
- **WHEN** 调用 `POST /api/v1/staging-area/recommend`
- **THEN** 使用StagingAreaCore纯算法服务
- **AND** 返回评分排序的候选点列表（无语义分析）

#### Scenario: 结构化输入快速通道

- **GIVEN** 用户提供完整结构化输入（震中、震级、目标列表）
- **AND** 不需要语义理解
- **WHEN** 调用Agent API但设置 `skip_llm_analysis=true`
- **THEN** 跳过LLM分析节点，直接调用算法
- **AND** 仍然生成基础解释
