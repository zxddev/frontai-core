# Spec: AI模块错误码规范

## ADDED Requirements

### Requirement: AI模块统一错误码体系

AI模块所有接口必须使用统一的错误码格式，便于前端处理和运维排查。

#### Scenario: 任务不存在

- **Given**: 用户查询一个不存在的分析任务
- **When**: 调用 `GET /ai/analyze-event/{task_id}` 且task_id不存在
- **Then**: 返回HTTP 404，body包含 `{"error_code": "AI4001", "message": "任务不存在: task-xxx"}`

#### Scenario: 资源被锁定

- **Given**: 用户请求生成方案，但所需队伍已被其他事件锁定
- **When**: 调用 `POST /ai/generate-scheme`，RescueTeamSelector选中的队伍已被锁定
- **Then**: 返回HTTP 409，body包含 `{"error_code": "AI4003", "message": "资源已被锁定", "details": {"locked_resources": [...], "retry_after_seconds": 30}}`

#### Scenario: 熔断器打开

- **Given**: 算法节点连续失败触发熔断
- **When**: 调用 `POST /ai/generate-scheme`，优化器熔断器处于OPEN状态
- **Then**: 返回HTTP 503，body包含 `{"error_code": "AI5002", "message": "熔断器已打开: pymoo_optimizer", "details": {"recovery_time_seconds": 60}}`

#### Scenario: 数据库查询超时

- **Given**: 数据库负载过高
- **When**: 调用 `POST /ai/generate-scheme`，队伍查询超时
- **Then**: 返回HTTP 504，body包含 `{"error_code": "AI5003", "message": "数据库查询超时"}`

---

### Requirement: 异常类层次结构

所有AI模块异常必须继承自`AIAgentError`基类。

#### Scenario: 异常继承检查

- **Given**: AI模块抛出任意异常
- **When**: 异常被全局处理器捕获
- **Then**: 异常必须是`AIAgentError`的实例，且包含`error_code`属性

---

## Cross-References

- 依赖: `src/core/exceptions.py` 中的 `AppException` 基类
- 被依赖: `src/agents/router.py` 异常处理器
