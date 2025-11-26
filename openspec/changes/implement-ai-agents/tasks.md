# Tasks: AI Agent核心模块

## 1. 算法层补充

- [x] 1.1 创建 `src/planning/algorithms/assessment/confirmation_scorer.py`
  - 实现ConfirmationScorer类（继承AlgorithmBase）
  - 实现评分公式：ai_confidence×0.6 + rule_match×0.3 + source_trust×0.1
  - 实现AC规则检查（AC-001~AC-004）
  - 实现状态决策逻辑

- [x] 1.2 更新 `src/planning/algorithms/assessment/__init__.py`
  - 导出ConfirmationScorer

- [x] 1.3 更新 `src/planning/algorithms/__init__.py`
  - 导出ConfirmationScorer

## 2. Agent基础设施

- [x] 2.1 创建 `src/agents/__init__.py`
- [x] 2.2 创建 `src/agents/base/__init__.py`
- [x] 2.3 创建 `src/agents/base/agent.py` - BaseAgent抽象类
  - 定义run(), arun()抽象方法
  - 定义日志记录方法
- [x] 2.4 创建 `src/agents/base/state.py` - 共享State类型
- [x] 2.5 创建 `src/agents/base/tools.py` - 工具函数

## 3. EventAnalysis Agent

- [x] 3.1 创建 `src/agents/event_analysis/__init__.py`
- [x] 3.2 创建 `src/agents/event_analysis/state.py` - EventAnalysisState
- [x] 3.3 创建 `src/agents/event_analysis/nodes/__init__.py`
- [x] 3.4 创建 `src/agents/event_analysis/nodes/assess.py` - assess_disaster节点
  - 调用DisasterAssessment算法
  - 返回assessment_result到状态
- [x] 3.5 创建 `src/agents/event_analysis/nodes/predict.py` - predict_hazards节点
  - 调用SecondaryHazardPredictor算法
  - 返回secondary_hazards到状态
- [x] 3.6 创建 `src/agents/event_analysis/nodes/loss.py` - estimate_loss节点
  - 调用LossEstimator算法
  - 返回loss_estimation到状态
- [x] 3.7 创建 `src/agents/event_analysis/nodes/confirm.py` - 确认评分节点
  - 调用ConfirmationScorer算法
  - 决定状态流转
  - 返回confirmation_score, recommended_status
- [x] 3.8 创建 `src/agents/event_analysis/graph.py` - LangGraph定义
  - 定义StateGraph
  - 添加节点和边
  - 编译图
- [x] 3.9 创建 `src/agents/event_analysis/agent.py` - Agent类
  - 实现analyze()方法
  - 集成图执行
  - 记录决策日志

## 4. API层

- [x] 4.1 创建 `src/agents/schemas.py` - Pydantic模型
  - AnalyzeEventRequest
  - AnalyzeEventResponse
  - AnalysisTaskStatus
  - AnalysisResult
  - ConfirmationDecision

- [x] 4.2 创建 `src/agents/router.py` - AI路由
  - POST /ai/analyze-event - 提交分析任务
  - GET /ai/analyze-event/{task_id} - 查询任务状态

- [x] 4.3 更新 `src/main.py`
  - 添加agents路由挂载

## 5. 集成测试

- [x] 5.1 语法检查 (py_compile所有新文件)
- [x] 5.2 启动服务验证路由注册
- [x] 5.3 测试POST /api/v2/ai/analyze-event接口
- [x] 5.4 验证算法调用链
- [x] 5.5 验证ai_decision_logs_v2记录

## 依赖关系

```
1.1 → 1.2 → 1.3 (算法层)
      ↓
2.1~2.5 (Agent基础) → 3.1~3.9 (EventAnalysis)
                              ↓
                        4.1~4.3 (API层)
                              ↓
                        5.1~5.5 (测试)
```
