# Capability: AI Agents

## Overview

AI Agent模块提供智能分析能力，使用LangGraph编排多步骤分析流程，调用现有算法模块进行灾情评估、次生灾害预测、确认评分等。

## ADDED Requirements

### Requirement: EventAnalysisAgent

EventAnalysisAgent负责分析灾情事件，计算确认评分，决定事件状态流转。

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

### Requirement: ConfirmationScorer算法

ConfirmationScorer负责计算事件确认评分，检查自动确认规则。

#### Scenario: 评分计算

**Given** AI置信度=0.85
**And** 规则匹配度=0.90
**And** 来源可信度=0.95
**When** 计算确认评分
**Then** confirmation_score = 0.85×0.6 + 0.90×0.3 + 0.95×0.1 = 0.51 + 0.27 + 0.095 = 0.875

#### Scenario: AC-001多源交叉验证

**Given** 同位置(500m内)30分钟内收到2个不同来源上报
**When** 检查AC-001规则
**Then** 规则匹配，触发自动确认

#### Scenario: AC-004被困人员确认

**Given** estimated_victims >= 1
**And** AI置信度 >= 0.7
**When** 检查AC-004规则
**Then** 规则匹配，触发自动确认

### Requirement: AI决策日志

所有AI决策必须记录到ai_decision_logs_v2表，支持可追溯可解释。

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

### Requirement: 异步执行与结果查询

分析任务异步执行，支持任务状态查询。

#### Scenario: 提交分析任务

**When** POST /api/v2/ai/analyze-event
**Then** 立即返回 {"task_id": "task-{event_id}", "status": "processing"}
**And** 后台异步执行分析

#### Scenario: 查询任务状态

**Given** 分析任务已完成
**When** GET /api/v2/ai/analyze-event/{task_id}
**Then** 返回完整分析结果，包括：
  - analysis_result (灾情评估)
  - confirmation_decision (确认评分和状态决策)
  - trace (算法调用追踪)

## Dependencies

- `src/planning/algorithms/assessment/` - 灾情评估算法
- `src/core/websocket.py` - WebSocket广播
- `sql/v2_event_scheme_model.sql` - ai_decision_logs_v2表
