# Design: 加固AI Agent模块

## 1. 错误码设计

### 错误码规范

| 错误码 | 名称 | HTTP状态码 | 说明 |
|--------|------|------------|------|
| AI4001 | AI_TASK_NOT_FOUND | 404 | 任务不存在 |
| AI4002 | AI_SCHEME_NOT_FOUND | 404 | 方案不存在 |
| AI4003 | AI_RESOURCE_LOCKED | 409 | 资源已被锁定 |
| AI4004 | AI_INVALID_INPUT | 400 | 输入参数无效 |
| AI4005 | AI_EVENT_NOT_FOUND | 404 | 事件不存在 |
| AI5001 | AI_RULE_LOAD_FAILED | 500 | 规则加载失败 |
| AI5002 | AI_CIRCUIT_BREAKER_OPEN | 503 | 熔断器已打开 |
| AI5003 | AI_DATABASE_TIMEOUT | 504 | 数据库查询超时 |
| AI5004 | AI_REDIS_UNAVAILABLE | 503 | Redis不可用 |
| AI5005 | AI_ALGORITHM_FAILED | 500 | 算法执行失败 |

### 错误响应格式

```json
{
  "error_code": "AI4003",
  "message": "资源已被锁定: team-001, team-002",
  "details": {
    "locked_resources": ["team-001", "team-002"],
    "locked_by": "event-123",
    "retry_after_seconds": 30
  }
}
```

## 2. 资源锁设计

### 锁键设计

```
ai:team_lock:{team_id}
```

- 值：`{event_id}:{timestamp}:{ttl}`
- TTL：300秒（5分钟）

### 锁定流程

```
┌─────────────────────────────────────────────────────────────┐
│                     run_with_db()                           │
├─────────────────────────────────────────────────────────────┤
│  1. _fetch_available_teams() ──► 查询可用队伍（不锁定）     │
│                                                             │
│  2. run() ──► LangGraph执行，选择最优队伍组合               │
│                                                             │
│  3. acquire_team_locks(selected_teams) ──► 尝试锁定         │
│     │                                                       │
│     ├── 成功 ──► 继续                                       │
│     │                                                       │
│     └── 失败 ──► 抛出AIResourceLockedError                  │
│                                                             │
│  4. _save_schemes_to_db() ──► 保存方案 + 更新队伍状态       │
│                                                             │
│  5. release_team_locks() ──► 释放Redis锁                    │
│     （队伍状态已通过DB标记为deployed，不再需要Redis锁）     │
└─────────────────────────────────────────────────────────────┘
```

### 锁定策略

**原子性批量锁定**：
```python
async def acquire_team_locks(team_ids: List[str], event_id: str) -> bool:
    """
    原子性批量锁定队伍
    
    使用Redis MULTI/EXEC保证原子性：
    - 要么全部锁定成功
    - 要么全部失败（已被其他事件锁定的队伍不会被部分锁定）
    """
    pipe = redis.pipeline()
    for team_id in team_ids:
        key = f"ai:team_lock:{team_id}"
        # SET NX = 仅当key不存在时设置
        pipe.set(key, f"{event_id}:{time.time()}", nx=True, ex=300)
    
    results = await pipe.execute()
    
    if all(results):
        return True
    else:
        # 回滚已锁定的
        for i, result in enumerate(results):
            if result:
                await redis.delete(f"ai:team_lock:{team_ids[i]}")
        return False
```

### 降级策略

当Redis不可用时：
1. 记录警告日志
2. 使用数据库乐观锁（SELECT FOR UPDATE）
3. 设置degraded状态

```python
async def acquire_team_locks_with_fallback(...):
    try:
        return await acquire_team_locks_redis(...)
    except RedisError:
        logger.warning("Redis不可用，降级到数据库锁")
        return await acquire_team_locks_db(...)
```

## 3. 队伍状态管理

### 状态流转

```
standby ──┬──► deployed ──► standby (任务完成)
          │
          └──► unavailable (设备故障/休整)
```

### 更新逻辑

保存方案时同步更新队伍状态：

```python
async def _update_team_status(
    db: AsyncSession,
    team_ids: List[str],
    status: str,
    task_id: Optional[str] = None,
):
    """
    批量更新队伍状态
    
    使用单条UPDATE语句提高效率
    """
    await db.execute(
        update(RescueTeam)
        .where(RescueTeam.id.in_(team_ids))
        .values(status=status, current_task_id=task_id, updated_at=func.now())
    )
```

## 4. 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          API Layer                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  router.py                                               │   │
│  │  - Exception Handler (AIAgentError → JSON响应)           │   │
│  │  - /ai/generate-scheme                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                        Agent Layer                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  agent.py                                                │   │
│  │  run_with_db():                                          │   │
│  │    1. fetch_teams()                                      │   │
│  │    2. run() → LangGraph                                  │   │
│  │    3. acquire_locks() ←── resource_lock.py               │   │
│  │    4. save_scheme() + update_team_status()               │   │
│  │    5. release_locks()                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                     Infrastructure Layer                        │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  Redis           │  │  PostgreSQL      │                    │
│  │  - team_lock:*   │  │  - rescue_teams_v2│                   │
│  │  - TTL 5min      │  │  - status字段     │                   │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## 5. 性能考量

| 操作 | 预期延迟 | 备注 |
|------|----------|------|
| Redis锁获取 | <5ms | 单次SETNX |
| 批量锁定(10队伍) | <20ms | Pipeline |
| 队伍状态更新 | <10ms | 批量UPDATE |
| 总增加延迟 | <50ms | 可接受 |

## 6. 监控指标

新增Prometheus指标：
- `ai_resource_lock_acquired_total` - 锁获取成功次数
- `ai_resource_lock_failed_total` - 锁获取失败次数
- `ai_resource_lock_timeout_total` - 锁超时次数
- `ai_redis_fallback_total` - Redis降级次数
