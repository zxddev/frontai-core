# Emergency AI Hybrid System Specification

应急救灾AI+规则混合系统规格说明。

## ADDED Requirements

### Requirement: LLM灾情语义理解

系统 SHALL 使用大语言模型（LLM）解析自然语言灾情描述，提取结构化实体信息。

#### Scenario: 地震灾情描述解析
- **GIVEN** 用户输入自然语言灾情描述 "XX市XX区发生5.5级地震，多栋建筑倒塌，预计有30人被困"
- **WHEN** 系统调用LLM解析工具
- **THEN** 返回结构化信息包含：
  - disaster_type: "earthquake"
  - location: {longitude, latitude}
  - magnitude: 5.5
  - has_building_collapse: true
  - estimated_trapped: 30
  - severity: "critical"

#### Scenario: LLM解析失败处理
- **GIVEN** LLM服务不可用或超时
- **WHEN** 系统调用LLM解析工具
- **THEN** 系统 SHALL 抛出异常，禁止降级处理

---

### Requirement: RAG历史案例检索

系统 SHALL 使用向量检索（RAG）从历史案例库中检索相似灾情案例，增强决策依据。

#### Scenario: 相似案例检索成功
- **GIVEN** 灾情类型为 "earthquake" 且存在历史案例
- **WHEN** 系统调用RAG检索工具
- **THEN** 返回至少1个相似案例，包含：
  - case_id: 案例ID
  - similarity_score: ≥ 0.7
  - lessons_learned: 经验教训列表
  - best_practices: 最佳实践列表

#### Scenario: 无相似案例
- **GIVEN** 灾情类型罕见且案例库中无匹配
- **WHEN** 系统调用RAG检索工具
- **THEN** 系统 SHALL 返回空列表，继续后续流程，不报错

---

### Requirement: 知识图谱规则查询

系统 SHALL 从Neo4j知识图谱中查询TRR（任务-规则-资源）触发规则。

#### Scenario: TRR规则查询成功
- **GIVEN** 灾情类型为 "earthquake" 且知识图谱中存在规则
- **WHEN** 系统查询TRR规则
- **THEN** 返回匹配的规则列表，每条规则包含：
  - rule_id: 规则ID
  - trigger_conditions: 触发条件
  - required_tasks: 需要执行的任务类型
  - required_capabilities: 需要的能力

#### Scenario: 知识图谱查询失败
- **GIVEN** Neo4j服务不可用
- **WHEN** 系统查询TRR规则
- **THEN** 系统 SHALL 抛出异常，禁止降级处理

---

### Requirement: TRR规则引擎匹配

系统 SHALL 使用规则引擎对灾情上下文进行TRR规则匹配，生成任务和能力需求列表。

#### Scenario: 地震建筑倒塌规则匹配
- **GIVEN** 灾情包含 has_building_collapse=true 和 has_trapped_persons=true
- **WHEN** 规则引擎评估TRR规则
- **THEN** 匹配规则 TRR-EQ-001，生成任务需求：
  - task_type: "search_rescue"
  - priority: "critical"
  - required_capabilities: ["LIFE_DETECTION", "STRUCTURAL_RESCUE", "MEDICAL_TRIAGE"]

#### Scenario: 多规则优先级排序
- **GIVEN** 灾情同时满足多条TRR规则
- **WHEN** 规则引擎评估
- **THEN** 按规则权重（weight）降序排列匹配结果

---

### Requirement: CSP资源约束求解

系统 SHALL 使用约束满足问题（CSP）求解器进行资源匹配。

#### Scenario: 资源约束满足
- **GIVEN** 能力需求列表和可用资源列表
- **WHEN** CSP求解器执行
- **THEN** 返回满足所有约束的资源分配方案

#### Scenario: 资源约束无解
- **GIVEN** 可用资源不足以满足关键能力需求
- **WHEN** CSP求解器执行
- **THEN** 系统 SHALL 返回无解状态，不生成方案

---

### Requirement: NSGA-II多目标优化

系统 SHALL 使用NSGA-II算法对候选方案进行多目标优化，生成Pareto最优解集。

#### Scenario: 多目标优化执行
- **GIVEN** 多个候选资源分配方案
- **WHEN** NSGA-II算法执行
- **THEN** 返回Pareto最优解集，优化目标包括：
  - 响应时间（最小化）
  - 覆盖率（最大化）
  - 成本（最小化）
  - 风险（最小化）

---

### Requirement: 硬规则一票否决

系统 SHALL 对所有候选方案执行硬规则检查，不满足硬规则的方案必须被否决。

#### Scenario: 安全红线否决
- **GIVEN** 方案的救援人员伤亡风险 > 15%
- **WHEN** 硬规则HR-EM-001检查
- **THEN** 方案被否决，返回否决原因 "救援人员伤亡风险超过15%"

#### Scenario: 黄金时间否决
- **GIVEN** 方案预计响应时间超过黄金救援时间
- **WHEN** 硬规则HR-EM-002检查
- **THEN** 方案被否决，返回否决原因 "预计响应时间超过黄金救援时间"

---

### Requirement: 软规则加权评分

系统 SHALL 对通过硬规则的方案执行软规则加权评分，计算综合得分。

#### Scenario: 地震场景评分
- **GIVEN** 灾情类型为 "earthquake"
- **WHEN** 软规则评分执行
- **THEN** 使用地震场景权重配置：
  - response_time: 0.40
  - coverage_rate: 0.30
  - cost: 0.10
  - risk: 0.20

---

### Requirement: LLM方案解释生成

系统 SHALL 使用LLM为推荐方案生成自然语言解释。

#### Scenario: 方案解释生成
- **GIVEN** 推荐方案及其评分详情
- **WHEN** 系统调用LLM生成解释
- **THEN** 返回包含以下内容的解释文本：
  - 方案选择理由
  - 关键优势
  - 潜在风险及缓解措施
  - 执行建议

---

### Requirement: AI决策日志记录

系统 SHALL 将完整的AI决策过程记录到 ai_decision_logs_v2 表。

#### Scenario: 决策日志完整性
- **GIVEN** AI分析完成
- **WHEN** 保存决策日志
- **THEN** 日志包含：
  - input_snapshot: 输入数据快照
  - output_result: 输出结果
  - reasoning_chain: 完整推理链（LLM解析→规则匹配→优化→解释）
  - processing_time_ms: 处理耗时

---

### Requirement: 应急分析API

系统 SHALL 提供异步API端点进行应急AI分析。

#### Scenario: 提交分析任务
- **GIVEN** 有效的灾情分析请求
- **WHEN** POST /api/v2/ai/emergency-analyze
- **THEN** 返回202状态码和task_id

#### Scenario: 查询分析结果
- **GIVEN** 有效的task_id且任务已完成
- **WHEN** GET /api/v2/ai/emergency-analyze/{task_id}
- **THEN** 返回完整分析结果，包括：
  - understanding_report: 灾情理解报告
  - matched_rules: 匹配的TRR规则
  - recommended_scheme: 推荐方案
  - scheme_explanation: 方案解释
  - trace: 追踪信息
