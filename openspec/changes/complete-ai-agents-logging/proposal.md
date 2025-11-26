# Change: 补全AI Agent决策日志和WebSocket推送

## Why

implement-ai-agents变更已实现AI Agent核心功能（EventAnalysisAgent、ConfirmationScorer等），但spec中两个关键需求未实现：

1. **AI决策日志未保存** - router.py执行分析后未将决策日志写入ai_decision_logs_v2表，导致AI决策无法追溯
2. **WebSocket推送未实现** - router.py有TODO注释，分析完成后未调用broadcast_event_update推送结果

这两个缺失导致：
- 前端无法实时获取分析结果，只能轮询
- AI决策过程不可追溯，无法审计和优化

## What Changes

### ADDED

- **src/domains/ai_decisions/** - AI决策日志域模块
  - `models.py` - AIDecisionLog SQLAlchemy模型
  - `repository.py` - 数据库操作（创建日志）
  - `schemas.py` - Pydantic模型
  - `__init__.py` - 模块导出

### MODIFIED

- **src/agents/router.py**
  - 在_run_event_analysis完成后调用AIDecisionLogRepository保存日志
  - 调用broadcast_event_update推送分析结果到WebSocket

## Impact

- **Affected specs**: 修改 `ai-agents` capability
- **Affected code**:
  - 新增 `src/domains/ai_decisions/` 模块（4个文件）
  - 修改 `src/agents/router.py` 添加日志保存和WebSocket推送

## SQL Tables

使用已存在的表 `ai_decision_logs_v2`，无需新增SQL。

## Dependencies

- `src/core/websocket.py` - broadcast_event_update函数
- `src/core/database.py` - AsyncSessionLocal
