# Change: 加固AI Agent模块（错误码规范 + 并发资源锁）

## Why

当前AI Agent模块存在两个生产环境阻塞问题：

### 1. 错误码混乱
- AI模块只有AI4001和AI4002两个硬编码错误码
- 无法区分不同类型的错误（规则加载失败/熔断器打开/数据库超时等）
- 前端无法根据错误码做差异化处理
- 运维无法快速定位问题

### 2. 并发资源竞争
- 多个事件同时请求时，可能将同一支队伍分配给多个方案
- 当前流程：_fetch_available_teams查询 → run生成方案 → _save_schemes_to_db保存
- 问题点：查询和保存之间没有锁定，两个并发请求可能查到同一支队伍
- 后果：队伍被重复分配，执行时冲突

**参考代码**:
- `src/agents/router.py` L355-362: 错误码硬编码
- `src/agents/scheme_generation/agent.py` L187-195: 资源分配流程无锁
- `sql/v2_rescue_resource_model.sql` L103: rescue_teams_v2.status字段

## What Changes

### ADDED

- **src/agents/exceptions.py** - AI模块专用异常类
  - `AIAgentError` - 基类
  - `AITaskNotFoundError` (AI4001)
  - `AISchemeNotFoundError` (AI4002)
  - `AIResourceLockedError` (AI4003)
  - `AIRuleLoadError` (AI5001)
  - `AICircuitBreakerOpenError` (AI5002)
  - `AIDatabaseTimeoutError` (AI5003)
  - `AIInvalidInputError` (AI4004)

- **src/core/redis.py** - Redis客户端基础设施
  - `get_redis_client()` - 获取异步Redis客户端
  - 基于`src/core/config.py`的`redis_url`配置

- **src/agents/utils/resource_lock.py** - 资源分配锁
  - `ResourceLock` - 资源锁管理器
  - `acquire_team_locks()` - 批量锁定队伍
  - `release_team_locks()` - 释放队伍锁
  - 锁键格式：`ai:team_lock:{team_id}`
  - TTL：5分钟（可配置）

### MODIFIED

- **src/agents/router.py**
  - 导入并使用新的异常类
  - 添加全局异常处理器

- **src/agents/scheme_generation/agent.py**
  - `run_with_db()` 中添加资源锁定逻辑
  - 保存方案后更新队伍状态（status='deployed', current_task_id）

- **src/agents/db/schemes.py**
  - `save_scheme()` 增加`update_team_status`参数
  - 新增`_update_team_status()`方法

## Impact

- **Affected specs**: 修改 `ai-agents` capability
- **Affected code**:
  - 新增 `src/agents/exceptions.py` (~80行)
  - 新增 `src/core/redis.py` (~50行)
  - 新增 `src/agents/utils/resource_lock.py` (~150行)
  - 修改 `src/agents/router.py` (异常处理)
  - 修改 `src/agents/scheme_generation/agent.py` (资源锁)
  - 修改 `src/agents/db/schemes.py` (队伍状态更新)

## SQL Tables

**无需新增表**，使用现有字段：
- `rescue_teams_v2.status` - 队伍状态（standby→deployed）
- `rescue_teams_v2.current_task_id` - 当前任务ID

## Dependencies

需要新增依赖：
- `redis>=5.0.0` - 异步Redis客户端（用于分布式锁）

## References

- 配置：`src/core/config.py` L13: redis_url
- 队伍表：`sql/v2_rescue_resource_model.sql` L83-130
- 现有异常：`src/core/exceptions.py`
- 熔断器：`src/agents/utils/circuit_breaker.py`
