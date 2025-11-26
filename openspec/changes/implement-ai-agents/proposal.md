# Change: 实现AI Agent核心模块

## Why

当前系统已实现业务CRUD接口（events/schemes/tasks等），但缺少AI智能层：
1. 事件无法自动分析和评估，confirmation_score字段需要外部传入
2. 无法调用现有算法模块（DisasterAssessment等）进行智能决策
3. 缺少AI接口供前端调用触发智能分析
4. 无法实现设计文档中的"自动确认/预确认"状态流转

这是应急救灾系统的核心能力缺失，阻塞了AI辅助决策流程。

## What Changes

### ADDED

- **agents/base/** - Agent基础设施
  - `agent.py` - BaseAgent抽象类，定义Agent生命周期
  - `state.py` - 共享State类型（TypedDict）
  - `tools.py` - 共享工具函数（算法调用封装）

- **agents/event_analysis/** - 事件分析Agent（P0核心）
  - `agent.py` - EventAnalysisAgent实现
  - `graph.py` - LangGraph StateGraph定义
  - `state.py` - EventAnalysisState类型
  - `nodes/assess.py` - 灾情评估节点
  - `nodes/predict.py` - 次生灾害预测节点
  - `nodes/confirm.py` - 确认评分节点

- **agents/router.py** - AI API路由 `/api/v2/ai/*`
- **agents/schemas.py** - Pydantic请求/响应模型

- **planning/algorithms/assessment/confirmation_scorer.py** - 确认评分算法
  - 计算 confirmation_score = ai_confidence × 0.6 + rule_match × 0.3 + source_trust × 0.1
  - 检查自动确认规则 AC-001 ~ AC-004

### MODIFIED

- **main.py** - 添加AI路由挂载
- **planning/algorithms/assessment/__init__.py** - 导出ConfirmationScorer

## Impact

- **Affected specs**: 新增 `ai-agents` capability
- **Affected code**:
  - 新增 `src/agents/` 模块（约15个文件）
  - 新增 `src/planning/algorithms/assessment/confirmation_scorer.py`
  - 更新 `src/main.py` 添加AI路由
- **Affected tables**: 使用现有表
  - `ai_decision_logs_v2` - 记录AI决策日志
  - `events_v2` - 更新confirmation_score字段

## SQL Tables (Already Exist)

已有表满足需求：
- `events_v2` - 包含confirmation_score, pre_confirm_expires_at, matched_auto_confirm_rules字段
- `ai_decision_logs_v2` - AI决策日志表

**无需新增SQL**

## Dependencies

现有依赖已满足：
- `langchain>=0.3.0` - LLM工具链
- `langgraph>=0.3.27` - 状态图编排（需确认版本）
- `langchain-openai>=0.3.0` - OpenAI兼容客户端

## References

- 设计文档：`docs/emergency-brain/接口设计/02_AI_Agent接口设计.md`
- 算法实现：`src/planning/algorithms/assessment/disaster_assessment.py`
- LLM客户端：`src/infra/clients/llm_client.py`
