# Tasks: 补全AI Agent决策日志和WebSocket推送

## 1. AI决策日志模块

- [x] 1.1 创建 `src/domains/ai_decisions/__init__.py`
  - 导出AIDecisionLog模型和AIDecisionLogRepository

- [x] 1.2 创建 `src/domains/ai_decisions/models.py`
  - AIDecisionLog SQLAlchemy模型，映射ai_decision_logs_v2表
  - 字段: id, scenario_id, event_id, scheme_id, decision_type, algorithm_used
  - 字段: input_snapshot(JSONB), output_result(JSONB), confidence_score
  - 字段: reasoning_chain(JSONB), processing_time_ms
  - 字段: is_accepted, human_feedback, feedback_rating, created_at

- [x] 1.3 创建 `src/domains/ai_decisions/schemas.py`
  - CreateAIDecisionLogRequest Pydantic模型（用于创建日志的输入）

- [x] 1.4 创建 `src/domains/ai_decisions/repository.py`
  - AIDecisionLogRepository类
  - create(db, log_data) -> AIDecisionLog 异步方法

## 2. 集成到Agent路由

- [x] 2.1 修改 `src/agents/router.py`
  - 从src.domains.ai_decisions导入AIDecisionLogRepository
  - 从src.core.websocket导入broadcast_event_update
  - 在_run_event_analysis成功完成后:
    - 构造日志数据(scenario_id, event_id, decision_type="event_analysis", ...)
    - 调用AIDecisionLogRepository.create()保存到数据库
    - 调用broadcast_event_update()推送分析结果到WebSocket
  - 处理scenario_id为空的情况（跳过WebSocket推送或使用默认行为）

## 3. 验证

- [x] 3.1 语法检查所有新文件 (python3 -m py_compile)
- [x] 3.2 启动服务验证模块加载无报错
- [ ] 3.3 测试POST /api/v2/ai/analyze-event，验证日志写入ai_decision_logs_v2表（需要数据库环境）
- [ ] 3.4 验证WebSocket推送到events频道（需要数据库环境）

## 依赖关系

```
1.1 → 1.2 → 1.3 → 1.4 (AI决策日志模块)
                   ↓
               2.1 (集成到路由)
                   ↓
               3.1~3.4 (验证)
```

## 参考

- 数据库表定义: `sql/v2_event_scheme_model.sql` (ai_decision_logs_v2表)
- WebSocket广播: `src/core/websocket.py` (broadcast_event_update函数)
- 现有模型参考: `src/domains/events/models.py`
