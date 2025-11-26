# Capability: AI Agents

## MODIFIED Requirements

### Requirement: AI决策日志

系统SHALL将所有AI决策记录到ai_decision_logs_v2表，支持可追溯可解释。

#### Scenario: 记录分析决策

**Given** 完成事件分析
**When** 保存决策日志
**Then** 记录包含：
  - scenario_id, event_id
  - decision_type = "event_analysis"
  - algorithm_used = "DisasterAssessment,SecondaryHazardPredictor,ConfirmationScorer"
  - input_snapshot = 输入数据JSON
  - output_result = 分析结果JSON
  - confidence_score = confirmation_score
  - reasoning_chain = 推理链条
  - processing_time_ms = 执行耗时

#### Scenario: 日志保存到数据库

**Given** EventAnalysisAgent执行完成
**And** 生成分析结果和confirmation_decision
**When** _run_event_analysis函数执行完毕
**Then** 调用AIDecisionLogRepository.create()保存日志到ai_decision_logs_v2表
**And** 日志包含完整的input_snapshot和output_result
**And** 日志包含trace中的algorithms_used列表

### Requirement: EventAnalysisAgent

EventAnalysisAgent SHALL分析灾情事件，计算确认评分，决定事件状态流转，并通过WebSocket推送结果。

#### Scenario: 地震事件自动确认

**Given** 收到来自110系统的地震事件上报
**And** 事件标记为紧急(is_urgent=true)
**And** 预估有20人被困(estimated_victims=20)
**When** 调用 `POST /api/v2/ai/analyze-event` 提交分析
**Then** 系统异步执行分析流程
**And** 调用DisasterAssessment评估灾情等级
**And** 调用SecondaryHazardPredictor预测次生灾害
**And** 调用ConfirmationScorer计算确认评分
**And** 因满足AC-003和AC-004规则，事件自动确认(status=confirmed)
**And** 通过WebSocket推送分析结果

#### Scenario: 群众上报事件预确认

**Given** 收到群众电话上报的事件
**And** 来源可信度为0.6
**And** AI置信度为0.75
**When** 调用分析接口
**Then** 计算confirmation_score = 0.75×0.6 + 0×0.3 + 0.6×0.1 = 0.51 + 0.06 = 0.57
**And** 因0.57 < 0.6，事件状态设为pending
**And** 推送"新事件待人工确认"通知

#### Scenario: 传感器+AI双触发自动确认

**Given** 收到传感器告警事件
**And** 来源类型为sensor_alert
**And** AI置信度为0.82
**When** 调用分析接口
**Then** 因满足AC-002规则(传感器+AI>=0.8)
**And** 事件自动确认

#### Scenario: WebSocket推送分析结果

**Given** EventAnalysisAgent执行完成
**And** 请求中包含scenario_id
**When** 分析结果生成
**Then** 调用broadcast_event_update推送到events频道
**And** 推送payload包含event_id、status、analysis_result
**And** 订阅events频道的客户端实时收到更新
